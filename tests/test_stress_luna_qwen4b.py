"""Offline stress-harness regression suite. Never runs or downloads Qwen."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import stress_luna_qwen4b as stress


class InferenceFake:
    def __init__(self, *, content="Resposta do Qwen de teste."):
        self.content = content
        self.calls = []
        self.state = {"status":"ready", "inference_verified":True}
        self.closed = False

    def ask(self, question, history, **options):
        self.calls.append((question,list(history),dict(options)))
        return {"answer":self.content,"mode":"model","generated_tokens":13,
                "answer_complete":True}

    def status(self):
        return self.state

    def close(self):
        self.closed = True


class HeavyStressContracts(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.directory = Path(tmp.name)
        self.output = self.directory / "result.json"
        self.events = self.directory / "result.events.jsonl"

    def test_1000_simulated_turns_are_clearly_labeled_not_qwen(self):
        report = stress.simulate(1000, 48, self.output)
        self.assertEqual(report["status"], "simulated")
        self.assertFalse(report["real_inference"])
        self.assertEqual(report["turns_completed"], 1000)
        self.assertEqual(len(report["results"]), 1000)
        self.assertEqual(report["results"][-1]["turn"], 1000)
        self.assertTrue(all(entry["simulated"] for entry in report["results"]))
        self.assertEqual(len([e for e in stress.load_events(self.events)
                              if e.get("event") == "turn_result"]), 1000)
        self.assertEqual(json.loads(self.output.read_text(encoding="utf-8"))
                         ["turns_completed"], 1000)

    def test_reject_response_without_verified_real_inference(self):
        fake = InferenceFake()
        fake.state["inference_verified"] = False
        with self.assertRaisesRegex(RuntimeError, "inferencia nao confirmada"):
            stress.run_turns(fake, turns=2, tokens=48, event_path=self.events)
        recorded = stress.load_events(self.events)
        self.assertEqual(recorded[0]["event"], "turn_start")
        self.assertFalse(any(e.get("event") == "turn_result" for e in recorded))

    def test_reject_local_action_even_if_an_engine_says_verified(self):
        with self.assertRaisesRegex(RuntimeError, "rota local"):
            stress.summarize_turn(0, "Teste", {"answer":"OK","mode":"local_command"},
                                  .1, inference_verified=True)

    def test_web_remains_disabled_and_history_bounded_to_six_messages(self):
        fake = InferenceFake()
        results = stress.run_turns(fake, turns=26, tokens=64, event_path=self.events)
        self.assertEqual(len(results), 26)
        self.assertLessEqual(max(len(history) for _,history,_ in fake.calls), 6)
        self.assertTrue(all(opts == {"response_tokens":64,"web_search":False}
                            for _,_,opts in fake.calls))
        self.assertEqual(fake.calls[0][1], [])
        self.assertIn("Qwen", str(results[0]))

    def test_repeated_results_record_sha_and_bounded_preview(self):
        fake = InferenceFake(content="A"*900)
        record = stress.run_turns(fake, turns=1, tokens=48,
                                  event_path=self.events)[0]
        self.assertEqual(record["answer_chars"], 900)
        self.assertEqual(len(record["answer_preview"]), 350)
        self.assertEqual(len(record["answer_sha256"]), 64)

    def test_event_file_cannot_silently_overwrite_previous_run(self):
        self.events.write_text("old evidence",encoding="utf-8")
        with self.assertRaises(FileExistsError):
            stress.simulate(10, 48, self.output)
        self.assertEqual(self.events.read_text(encoding="utf-8"),"old evidence")

    def test_main_simulation_never_checks_model_or_network(self):
        with patch.object(stress,"require_model",side_effect=AssertionError("No model!")):
            rc = stress.main(["--simulate","--turns","45","--tokens","48",
                              "--output",str(self.output)])
        self.assertEqual(rc,0)
        self.assertEqual(json.loads(self.output.read_text())["status"],"simulated")

    def test_limits_rejected_before_writing_reports(self):
        for opts in (["--turns","0"],["--tokens","4"],
                     ["--max-minutes","1"],["--per-turn-seconds","15"]):
            with self.subTest(opts=opts), self.assertRaises(SystemExit):
                stress.main(["--simulate","--output",str(self.output),*opts])
            self.assertFalse(self.output.exists())

    def test_prompts_are_bounded_and_stable(self):
        self.assertGreaterEqual(len(stress.PROMPTS),10)
        self.assertEqual(stress.turn_prompt(0),stress.turn_prompt(len(stress.PROMPTS)))
        self.assertLess(max(map(len, stress.PROMPTS)),350)


if __name__ == "__main__":
    unittest.main()
