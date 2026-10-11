"""Testes locais sem rede, Playwright ou contas."""
import unittest
from pathlib import Path
from lab import read_sessions, summarize, format_report
from decision import rank_hunts


class TestLab(unittest.TestCase):
    def setUp(self):
        self.data = read_sessions(Path(__file__).parent / "exemplo_sintetico.csv")

    def test_demo_is_not_real_income(self):
        result = {x["game"]: x for x in summarize(self.data)}
        self.assertEqual(result["world"]["usd_actually_withdrawn"], 0)
        self.assertEqual(result["io"]["usd_actually_withdrawn"], 0)
        self.assertIn("DEMONSTRACAO", format_report(list(result.values())))

    def test_world_conversion_is_unknown(self):
        result = {x["game"]: x for x in summarize(self.data)}
        self.assertIsNone(result["world"]["io_gems_usd_indicative_NOT_WITHDRAWN"])

    def test_reject_negative_xp(self):
        row = dict(self.data[0])
        row["xp"] = -5.0
        # Validation occurs while reading CSV, not during aggregation.
        from tempfile import TemporaryDirectory
        import csv
        with TemporaryDirectory() as temp:
            path = Path(temp) / "data.csv"
            with path.open("w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=row.keys())
                writer.writeheader()
                writer.writerow(row)
            with self.assertRaises(ValueError):
                read_sessions(path)

    def test_demo_withdrawal_not_counted(self):
        row = dict(self.data[2])
        row["withdrawn_usd"] = 100.0
        self.assertEqual(summarize([row])[0]["usd_actually_withdrawn"], 0)

    def test_ranking_prefers_lower_risk(self):
        choices = [
            dict(game="io", hunt="risk", xp_per_hour=10000, estimated_gems_per_hour=0, failure_probability=0.9, confidence=0.5),
            dict(game="io", hunt="safe", xp_per_hour=9000, estimated_gems_per_hour=0, failure_probability=0, confidence=0.9),
        ]
        self.assertEqual(rank_hunts(choices)[0][2], "safe")

    def test_invalid_risk(self):
        row = dict(game="io", hunt="bad", xp_per_hour=1, estimated_gems_per_hour=0, failure_probability=1.5, confidence=0.5)
        with self.assertRaises(ValueError):
            rank_hunts([row])


if __name__ == "__main__":
    unittest.main()
