"""Regression checks for content truncation versus transport success."""
import sys
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))

from brain_ssd.chat.completion_quality import classify_completion
from brain_ssd.chat.server import ChatEngine

class Core:
    def __init__(self):
        self.prompts=[]
    def generate(self,request):
        self.prompts.append(request)
        return {
            "stdout": "A memória permanente, por outro lado,",
            "return_code":0,
            "metrics":{"generated_tokens":request.max_tokens,"finish_reason":None}
        }

class Runtime:
    def __init__(self):
        self.core_backend=Core()
        self.max_output_tokens=112
        self.prompt_budget_bytes=5600
    def retrieve(self,query):
        return {"status":"UNAVAILABLE","context":{"text":""},"sources":[],"activated_pages":[]}
    def close(self):
        pass

class CompletionTests(unittest.TestCase):
    def test_native_finish_reason_overrides_heuristic(self):
        finished=classify_completion("Texto.",max_tokens=112,generated_tokens=112,finish_reason="stop")
        self.assertTrue(finished["answer_complete"])
        self.assertFalse(finished["needs_continuation"])
        cut=classify_completion("Texto.",max_tokens=112,generated_tokens=45,finish_reason="length")
        self.assertFalse(cut["answer_complete"])
        self.assertTrue(cut["needs_continuation"])

    def test_cli_near_limit_and_dangling_text_flagged(self):
        for end in (
            "Memória permanente, por outro lado,",
            "A RAM é us",
            "O resultado do cálculo será: (100 × 80 + 10",
            "Aqui está o código:\n" + chr(96)*3 + "python\nprint(2)",
        ):
            with self.subTest(end=end):
                res=classify_completion(end,max_tokens=112,generated_tokens=112)
                self.assertEqual(res["status"],"truncated")
                self.assertTrue(res["needs_continuation"])

    def test_missing_native_reason_never_claims_verified_complete(self):
        res=classify_completion("A astronomia estuda os astros.",max_tokens=112)
        self.assertEqual(res["status"],"unverified")
        self.assertIsNone(res["answer_complete"])
        self.assertFalse(res["needs_continuation"])

    def test_engine_does_not_mark_partial_as_complete(self):
        runtime=Runtime()
        engine=ChatEngine(lambda:runtime)
        engine.start()
        try:
            result=engine.ask("Explique a diferença entre memórias e histórico.",[])
            self.assertEqual(result["generation_status"],"truncated")
            self.assertFalse(result["answer_complete"])
            self.assertTrue(result["needs_continuation"])
            self.assertEqual(result["generation_limit"],112)
            self.assertEqual(result["generated_tokens"],112)
            self.assertEqual(result["answer"],"A memória permanente, por outro lado,")
        finally:
            engine.close()

if __name__=="__main__":
    unittest.main()
