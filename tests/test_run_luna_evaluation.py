import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from run_luna_evaluation import objective_check, parse_sse, redact_for_sharing


def test_parse_sse_done_event():
    events = list(parse_sse([b"event: delta\n", b'data: {"text":"ola"}\n', b"\n", b"event: done\n", b'data: {"answer":"ola"}\n', b"\n"]))
    assert events == [("delta", {"text": "ola"}), ("done", {"answer": "ola"})]


def test_objective_criteria_are_explicit():
    assert objective_check(11, "17 vezes 8 é 136.") == "PASS"
    assert objective_check(12, "Sobram 28 maçãs.") == "PASS"
    assert objective_check(14, "Não, a conclusão não decorre das premissas.") == "PASS"


def test_sensitive_answer_is_not_shared():
    shared, redacted = redact_for_sharing("A senha: segredo123")
    assert redacted is True
    assert "segredo123" not in shared
