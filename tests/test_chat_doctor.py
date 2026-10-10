"""Installation doctor tests; no real GGUF or llama.cpp required."""
from __future__ import annotations
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from doctor_chat import inspect_installation


class TestInstallationDoctor(unittest.TestCase):
    def test_missing_files_and_optional_ssd(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = inspect_installation(root)
            self.assertFalse(first["ready_for_test"])
            self.assertFalse(first["optional_ssd"]["available"])
            self.assertTrue(first["recommendations"])
            model = root / "models" / "Qwen3-0.6B-Q8_0.gguf"
            model.parent.mkdir(parents=True)
            model.write_bytes(b"GGUF" + b"\0" * 2048)
            exe = root / "third_party/llama.cpp/build-win/bin/llama-completion.exe"
            exe.parent.mkdir(parents=True)
            exe.write_bytes(b"MZ")
            # The resolver uses a suffix only on native Windows.
            exe.with_suffix("").write_bytes(b"ELF")
            too_small = inspect_installation(root)
            self.assertFalse(too_small["ready_for_test"])
            self.assertFalse(too_small["required"]["model_plausible_size"])
            with patch("doctor_chat.MIN_PLAUSIBLE_GGUF_BYTES", 1024):
                second = inspect_installation(root)
            self.assertTrue(second["ready_for_test"])
            self.assertFalse(second["optional_ssd"]["available"])
            self.assertEqual(second["status"], "READY_FOR_REAL_INFERENCE_TEST")

    def test_absent_runtime_does_not_claim_it_failed_to_start(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            report=inspect_installation(root,probe=True)
            text=" ".join(report["recommendations"])
            self.assertFalse(report["runtime"]["found"])
            self.assertNotIn("executável está presente mas falhou",text)
            self.assertNotIn("executável foi encontrado mas falhou",text)
            self.assertIn("PREPARAR-CHAT-WINDOWS.bat",text)

    def test_community_runtime_is_discovered_without_frozen_build(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            community=root/"third_party/llama.cpp/runtime-win-cpu-x64/bin/llama-completion.exe"
            community.parent.mkdir(parents=True)
            community.write_bytes(b"MZ")
            result=inspect_installation(root,probe=False)
            self.assertTrue(result["runtime"]["found"])
            self.assertEqual(result["runtime"]["distribution"],"official_cpu")

    def test_unreadable_gguf_is_reported_without_crashing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            model=root/"models"/"Qwen3-0.6B-Q8_0.gguf"
            model.parent.mkdir(parents=True)
            model.write_bytes(b"GGUF"+b"\0"*2048)
            # Patch Path.open for a single specific model file.
            real_open=Path.open
            def denied(path,*args,**kwargs):
                # Windows may canonicalize the temporary directory through
                # a junction when inspect_installation() calls resolve().
                if path.name == model.name and path.parent.name == "models":
                    raise PermissionError("private data must not escape")
                return real_open(path,*args,**kwargs)
            with patch("doctor_chat.MIN_PLAUSIBLE_GGUF_BYTES",1024),patch.object(Path,"open",denied):
                report=inspect_installation(root)
            self.assertFalse(report["ready_for_test"])
            self.assertTrue(any("não pôde ser lido" in x for x in report["recommendations"]))

    def test_existing_executable_can_fail_to_start(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            model=root/"models"/"Qwen3-0.6B-Q8_0.gguf"
            model.parent.mkdir(parents=True)
            model.write_bytes(b"GGUF"+b"\0"*2048)
            exe=root/"third_party/llama.cpp/build-win/bin/llama-completion.exe"
            exe.parent.mkdir(parents=True)
            exe.write_bytes(b"MZ")
            exe.with_suffix("").write_bytes(b"ELF")
            with patch("doctor_chat.MIN_PLAUSIBLE_GGUF_BYTES",1024),patch(
                "doctor_chat.probe_llama", return_value={
                    "version_return_code":1,"devices_return_code":1,
                    "cpu_only_build":False,"error":"native DLL absent"
                }):
                report=inspect_installation(root,probe=True)
            self.assertFalse(report["probe_passed"])
            self.assertFalse(report["ready_for_test"])
            self.assertTrue(any("executável está presente" in x for x in report["recommendations"]))
            with patch("doctor_chat.MIN_PLAUSIBLE_GGUF_BYTES",1024),patch(
                "doctor_chat.probe_llama", return_value={
                    "version_return_code":0,"devices_return_code":0,
                    "cpu_only_build":True
                }):
                ok=inspect_installation(root,probe=True)
            self.assertTrue(ok["ready_for_test"])


if __name__ == "__main__":
    unittest.main()
