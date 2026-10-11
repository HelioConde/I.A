"""Codex report quality audit must not treat SSE completion as a full answer."""
import sys
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.review_luna_evaluation import assess_report, render_summary


class ReportAuditTests(unittest.TestCase):
    def test_old_report_completed_true_does_not_mean_text_complete(self):
        fixture={"metadata":{"status_before":{"model":"Qwen3-4B-Q4_K_M.gguf","max_output_tokens":112}},
                 "results":[
                    {"id":4,"question":"Diferença memória e histórico?",
                     "status":"COMPLETED","complete":True,"mode":"experimental_chat",
                     "answer_type":"Qwen","share_answer":"Memória permanente, por outro lado,"},
                    {"id":12,"question":"3 x 12 - 8?","status":"COMPLETED","complete":True,
                     "mode":"experimental_chat","answer_type":"Qwen",
                     "share_answer":"28.","native_finish_reason":"stop"},
                    {"id":24,"question":"Pesquisar?","status":"AGUARDANDO_AUTORIZACAO",
                     "answer_type":"pesquisa"},
                    {"id":1,"question":"Nome?","status":"COMPLETED","mode":"local_command",
                     "answer_type":"local","share_answer":"Luna."},
                 ]}
        result=assess_report(fixture)
        self.assertEqual(result["total"],4)
        self.assertEqual(result["needs_review"],1)
        self.assertEqual(result["verified_complete"],1)
        self.assertEqual(result["results"][0]["quality_status"],"suspected_truncated")
        self.assertEqual(result["results"][1]["quality_status"],"complete")
        self.assertEqual(result["results"][2]["quality_status"],"not_executed")
        self.assertEqual(result["results"][3]["quality_status"],"local_action_not_inference")
        self.assertIn("Memória", render_summary(result))

if __name__=="__main__":
    unittest.main()
