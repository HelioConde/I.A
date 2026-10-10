"""Telemetry privacy, rotation, sanitization, threading and engine smoke tests."""
from __future__ import annotations

import json
import sys
import tempfile
import threading
import unittest
import uuid
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))

from brain_ssd.chat.diagnostics import DiagnosticLogger, export_diagnostics, inspect_events
from brain_ssd.chat.server import ChatEngine


class DummyCore:
    def generate(self,request):
        return {"return_code":0,"stdout":"Esta resposta privada contém SENHA_DE_TESTE.",
                "metrics":{"latency_ms":12,"ttft_ms":5,"working_set_bytes_max":123456}}


class DummyRuntime:
    def __init__(self):
        self.core_backend=DummyCore()
        self.profile="economia"
        self.core_mode="subprocess"
    def retrieve(self,question):
        return {"status":"UNAVAILABLE","sources":[],"activated_pages":[],
                "context":{"text":""}}
    def status(self):
        return {"profile":"economia","core_mode":"subprocess","threads":2}
    def close(self):
        pass


class TestDiagnosticLogger(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.folder=Path(self.temp.name)/"private"
        self.log=DiagnosticLogger(self.folder,max_bytes=4096,backups=3)

    def tearDown(self):
        self.temp.cleanup()

    def test_no_prompts_responses_paths_or_unexpected_fields(self):
        secret="SENHA_DE_TESTE"
        self.assertTrue(self.log.emit("chat.start",request_id=str(uuid.uuid4()),
            question_chars=21,prompt=secret,response=secret,
            stack_trace="private\\n"+secret,raw_path="/home/private/"+secret,
            profile="arbitrario "+secret,error_type=secret))
        with self.log.file.open(encoding="utf-8") as stream:
            raw=stream.read()
        self.assertNotIn(secret,raw)
        self.assertNotIn("stack_trace",raw)
        self.assertNotIn("raw_path",raw)
        self.assertIn('"question_chars":21',raw)
        with self.assertRaises(ValueError):
            self.log.emit("unknown.secret",content=secret)

    def test_file_rotation_and_thread_safety(self):
        def worker():
            for i in range(60):
                self.log.emit("chat.prompt",prompt_utf8_bytes=i,question="never log this")
        workers=[threading.Thread(target=worker) for _ in range(4)]
        for thread in workers: thread.start()
        for thread in workers: thread.join(timeout=5)
        self.assertTrue(all(not thread.is_alive() for thread in workers))
        files=self.log.files()
        self.assertGreaterEqual(len(files),2)
        self.assertLessEqual(len(files),4)
        for path in files:
            self.assertLessEqual(path.stat().st_size,4200)
            for line in path.read_text(encoding="utf-8").splitlines():
                self.assertEqual(json.loads(line)["event"],"chat.prompt")

    def test_export_removes_injected_raw_sensitive_fields(self):
        self.log.emit("session.start",profile="economia")
        injected={"schema_version":1,"timestamp_utc":"2026-10-10T07:00:00+00:00",
            "session_id":self.log.session_id,"event":"test.result",
            "suite":"cognitive_lab","status":"PASS","password":"SENHA_DE_TESTE",
            "answer":"Minha resposta confidencial","prompt":"private","duration_ms":3.5}
        with self.log.file.open("a",encoding="utf-8") as stream:
            stream.write(json.dumps(injected)+"\n")
            stream.write('{"unparseable json\n')
        target=Path(self.temp.name)/"review.zip"
        summary=export_diagnostics(self.folder,target)
        self.assertGreater(summary["malformed_or_discarded_lines"],0)
        with zipfile.ZipFile(target) as zipfile_read:
            self.assertEqual(set(zipfile_read.namelist()),
                             {"events.jsonl","summary.json","LEIA-ME.txt"})
            blob=zipfile_read.read("events.jsonl").decode("utf-8")
            self.assertNotIn("SENHA_DE_TESTE",blob)
            self.assertNotIn("confidencial",blob)
            self.assertNotIn('"prompt"',blob)
            self.assertIn("cognitive_lab",blob)
        self.assertNotIn("SENHA_DE_TESTE",target.read_bytes().decode("latin1",errors="ignore"))

    def test_engine_correlation_and_no_model_text(self):
        engine=ChatEngine(DummyRuntime,diagnostics=self.log)
        engine.start()
        try:
            result=engine.ask("Pergunta muito privada",[])
            self.assertIn("SENHA_DE_TESTE",result["answer"])
        finally:
            engine.close()
        records,summary=inspect_events(self.log.files())
        kinds=[event["event"] for event in records]
        for event in ("runtime.ready","chat.start","retrieval.done","memory.recall",
                      "chat.prompt","inference.done","chat.complete"):
            self.assertIn(event,kinds)
        ids=[item["request_id"] for item in records if "request_id" in item]
        self.assertEqual(len(set(ids)),1)
        text="\n".join(path.read_text(encoding="utf-8") for path in self.log.files())
        self.assertNotIn("SENHA_DE_TESTE",text)
        self.assertNotIn("Pergunta muito privada",text)
        self.assertGreater(summary["latency"]["sample_count"],0)

    def test_chat_latency_and_inference_are_not_double_counted(self):
        request_id = str(uuid.uuid4())
        self.log.emit("inference.done", request_id=request_id,
                      duration_ms=120, ttft_ms=40, working_set_bytes_max=102400)
        self.log.emit("chat.complete", request_id=request_id,
                      duration_ms=160, process_working_set_bytes=204800)
        events, report = inspect_events(self.log.files())
        self.assertEqual(report["latency"]["sample_count"], 1)
        self.assertEqual(report["latency"]["latency_p50_ms"], 160)
        self.assertEqual(report["inference_latency_ms"]["p50"], 120)
        self.assertEqual(report["time_to_first_token_ms"]["p50"], 40)
        self.assertEqual(report["native_peak_working_set_bytes"]["maximum"], 102400)
        self.assertEqual(report["python_working_set_bytes"]["maximum"], 204800)

    def test_errors_are_types_not_raw_messages(self):
        class BrokenRuntime:
            def __init__(self):
                raise FileNotFoundError("SENHA_DE_TESTE/local/private/gguf")
        engine=ChatEngine(BrokenRuntime,diagnostics=self.log)
        engine.start()
        self.assertEqual(engine.status()["status"],"error")
        content=self.log.file.read_text(encoding="utf-8")
        self.assertNotIn("SENHA_DE_TESTE",content)
        self.assertIn("FileNotFoundError",content)


if __name__=="__main__":
    unittest.main()
