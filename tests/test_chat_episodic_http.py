"""Opt-in episodic notes in the real HTTP and prompt adapter (fake Core only)."""
from __future__ import annotations
import json
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from brain_ssd.chat.episodic import EpisodicMemory
from brain_ssd.chat.server import ChatEngine, create_chat_server


class FakeCore:
    def __init__(self):
        self.prompts=[]
    def generate(self,req):
        self.prompts.append(req.prompt)
        return {"return_code":0,"stdout":"Entendi o contexto.","metrics":{}}


class FakeRuntime:
    def __init__(self):
        self.core_backend=FakeCore()
        self.prompt_budget_bytes=3500
    def retrieve(self,question):
        return {"status":"UNAVAILABLE","context":{"text":""},"sources":[],"activated_pages":[]}
    def close(self):
        pass


class TestEngine(unittest.TestCase):
    def test_opt_in_recall_no_implicit_learning(self):
        with tempfile.TemporaryDirectory() as temp:
            mem=EpisodicMemory(Path(temp)/"brain.sqlite3")
            runtime=FakeRuntime()
            engine=ChatEngine(lambda:runtime,episodic_store=mem)
            engine.start()
            try:
                engine.ask("Qual é minha cor favorita?",[])
                self.assertEqual(mem.list(),[])
                self.assertNotIn("Notas episódicas",runtime.core_backend.prompts[-1])
                mem.add("Minha cor favorita é azul")
                result=engine.ask("Qual é minha cor favorita?",[])
                self.assertEqual(result["episodic_memories_used"],1)
                self.assertIn("cor favorita",runtime.core_backend.prompts[-1])
                self.assertIn("azul",runtime.core_backend.prompts[-1])
                self.assertLess(len(runtime.core_backend.prompts[-1].encode("utf-8")),3500)
                unrelated=engine.ask("Como funciona astronomia moderna?",[])
                self.assertEqual(unrelated["episodic_memories_used"],0)
                self.assertNotIn("azul",runtime.core_backend.prompts[-1])
            finally:
                engine.close()

    def test_shadow_reports_state_but_does_not_change_core_prompt(self):
        with tempfile.TemporaryDirectory() as temp:
            memory=EpisodicMemory(Path(temp)/"notes.sqlite3")
            memory.add("Meu projeto favorito é o rover azul")
            one=FakeRuntime()
            two=FakeRuntime()
            baseline=ChatEngine(lambda:one,episodic_store=memory)
            shadow=ChatEngine(lambda:two,episodic_store=memory,cognitive_shadow=True)
            baseline.start()
            shadow.start()
            try:
                b=baseline.ask("Qual meu projeto favorito?",[])
                s=shadow.ask("Qual meu projeto favorito?",[])
                self.assertEqual(one.core_backend.prompts[-1],two.core_backend.prompts[-1])
                self.assertIsNone(b["cognitive_shadow"])
                self.assertEqual(s["cognitive_shadow"]["mode"],"READ_ONLY_SHADOW")
                self.assertFalse(s["cognitive_shadow"]["changed_model_prompt"])
                self.assertEqual(shadow.status()["cognitive_shadow_enabled"],True)
            finally:
                baseline.close()
                shadow.close()

    def test_disabled_by_default(self):
        engine=ChatEngine(FakeRuntime)
        engine.start()
        self.assertFalse(engine.status()["episodic_memory_enabled"])
        engine.close()


class TestHttp(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.memory=EpisodicMemory(Path(self.temp.name)/"episodes.sqlite3")
        self.engine=ChatEngine(FakeRuntime,episodic_store=self.memory)
        self.engine.start()
        self.server=create_chat_server(self.engine,ROOT/"chat",port=0,episodic_store=self.memory)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()
        self.url=f"http://127.0.0.1:{self.server.server_address[1]}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)
        self.engine.close()
        self.temp.cleanup()

    def call(self,verb,path,body=None,origin=None):
        data=json.dumps(body or {}).encode("utf-8") if verb=="POST" else None
        req=urllib.request.Request(self.url+path,method=verb,data=data,
            headers={"Origin":origin or self.url,"Content-Type":"application/json"})
        with urllib.request.urlopen(req,timeout=5) as reply:
            return json.loads(reply.read())

    def test_add_list_delete_and_privacy(self):
        self.assertTrue(self.call("GET","/api/memories")["enabled"])
        item=self.call("POST","/api/memories",{"content":"Minha pasta de pesquisa é Estudos"})["memory"]
        self.assertEqual(len(self.call("GET","/api/memories")["memories"]),1)
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self.call("DELETE","/api/memories/"+item["id"],origin="https://outside.invalid")
        self.assertEqual(ctx.exception.code,403)
        self.assertTrue(self.call("DELETE","/api/memories/"+item["id"])["deleted"])
        self.assertEqual(self.call("GET","/api/memories")["memories"],[])

    def test_reject_oversized_or_cross_origin_memory(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self.call("POST","/api/memories",{"content":"x"*501})
        self.assertEqual(ctx.exception.code,400)
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self.call("POST","/api/memories",{"content":"Minha cidade é Recife"},
                      origin="https://outside.invalid")
        self.assertEqual(ctx.exception.code,403)
        self.assertEqual(self.memory.list(),[])


if __name__=="__main__":
    unittest.main()
