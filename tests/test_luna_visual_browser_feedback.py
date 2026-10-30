"""Failure feedback must not forge or edit real model-authored artifacts."""
import hashlib
import importlib.util
import json
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("luna_visual_browser_feedback",ROOT/"tools/luna_visual_browser_feedback.py")
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

def sample(tmp_path):
    source=tmp_path/"visual.js"
    source.write_text("window.LunaSkin = { draw(ctx,state,time) { ctx.fillRect(0,0,10,10); } };\n")
    digest=hashlib.sha256(source.read_bytes()).hexdigest()
    provenance=tmp_path/"visual-provenance.json"
    provenance.write_text(json.dumps({"status":"STATIC_VISUAL_CANDIDATE","visual_js_sha256":digest}))
    evidence=tmp_path/"browser-evidence.json"
    evidence.write_text(json.dumps({"passed":False,"checks":[{"name":"empty_enemies_menu","ok":False}],
      "errors":["Cannot read properties of undefined (reading 'x')"]}))
    return source,provenance,evidence

def test_feedback_preserves_model_source(tmp_path):
    source,prov,evidence=sample(tmp_path)
    original=source.read_bytes()
    message=module.feedback(evidence,prov,source)
    assert "empty_enemies_menu" in message
    assert "Cannot read properties" in message
    assert original==source.read_bytes()
    assert hashlib.sha256(original).hexdigest() in message

def test_mismatched_model_provenance_fails(tmp_path):
    source,prov,evidence=sample(tmp_path)
    source.write_text("tampered")
    with pytest.raises(ValueError,match="mismatched"):
        module.feedback(evidence,prov,source)

def test_passing_browser_result_needs_no_repair(tmp_path):
    source,prov,evidence=sample(tmp_path)
    evidence.write_text(json.dumps({"passed":True,"checks":[],"errors":[]}))
    with pytest.raises(ValueError,match="No browser failure"):
        module.feedback(evidence,prov,source)
