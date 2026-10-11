"""Regression for the user copying a placeholder instead of a report path."""
from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from tools.review_luna_evaluation import locate_results, assess_report


class TestLunaReview(unittest.TestCase):
    def test_finds_newest_json_under_reports(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            old = root / "reports" / "luna-evaluation-20261010-100000" / "resultados.json"
            new = root / "reports" / "luna-evaluation-20261011-120000" / "resultados.json"
            old.parent.mkdir(parents=True)
            new.parent.mkdir(parents=True)
            old.write_text("{}", encoding="utf-8")
            new.write_text("{}", encoding="utf-8")
            import os
            os.utime(old, (1_000_000_000, 1_000_000_000))
            os.utime(new, (1_000_000_500, 1_000_000_500))
            self.assertEqual(locate_results(None, root=root), new)
            self.assertEqual(locate_results(Path("CAMINHO_DO_RELATORIO/resultados.json"), root=root), new)
            self.assertEqual(locate_results(old, root=root), old.resolve())

    def test_missing_real_file_explains_how_to_find(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(FileNotFoundError, r"dir /s /b resultados.json"):
                locate_results(Path("nao-existe/resultados.json"), root=Path(folder))
            with self.assertRaisesRegex(FileNotFoundError, r"dir /s /b resultados.json"):
                locate_results(None, root=Path(folder))

    def test_concluded_transport_is_not_complete_content(self):
        data = {
            "metadata": {"status_before": {"model": "Qwen3-4B-Q4_K_M.gguf", "max_output_tokens": 112}},
            "results": [
                {"id": 1, "status": "COMPLETED", "mode": "experimental_chat",
                 "answer": "A memória permanente, por outro lado,"},
                {"id": 2, "status": "COMPLETED", "mode": "experimental_chat",
                 "answer": "A resposta completa.", "native_finish_reason": "stop"},
                {"id": 3, "status": "PENDING_CONSENT", "answer": ""},
            ],
        }
        result = assess_report(data)
        self.assertEqual(result["total"], 3)
        self.assertEqual(result["verified_complete"], 1)
        self.assertGreaterEqual(result["needs_review"], 1)
        self.assertEqual(result["results"][2]["quality_status"], "not_executed")


if __name__ == "__main__":
    unittest.main()
