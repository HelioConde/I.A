"""Offline, mocked tests for pinned and auditable Windows chat downloads.

These tests do not fetch or execute any third-party binaries and do not
touch user files. CI can run them on Linux as well as Windows.
"""
from __future__ import annotations

import hashlib
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))

import install_windows_chat as install


class TestWindowsChatBootstrap(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
        self.model=self.root / install.MODEL_RELATIVE
        self.runtime=self.root / install.RUNTIME_RELATIVE

    def tearDown(self):
        self.tmp.cleanup()

    def test_default_does_not_download(self):
        self.assertFalse(self.model.exists())
        self.assertFalse(self.runtime.exists())

    def test_verified_download_is_atomic_and_idempotently_safe(self):
        data=b"GGUF"+b"4"*64
        digest=hashlib.sha256(data).hexdigest()
        with patch("urllib.request.urlopen",return_value=io.BytesIO(data)) as fetch:
            installed=install.download_verified("https://example.invalid/model",self.model,
                sha256=digest,exact_size=len(data),max_size=len(data))
        self.assertEqual(installed.read_bytes(),data)
        self.assertEqual(fetch.call_count,1)
        self.assertTrue(install.verified_file(self.model,sha256=digest,exact_size=len(data)))
        with self.assertRaises(FileExistsError):
            install.download_verified("https://example.invalid/model",self.model,
                sha256=digest,max_size=len(data))
        self.assertFalse(any(self.model.parent.glob(".brainssd-staging-*")))

    def test_bad_sha_and_short_download_leave_no_file(self):
        data=b"bad bytes"
        with patch("urllib.request.urlopen",return_value=io.BytesIO(data)):
            with self.assertRaises(ValueError):
                install.download_verified("https://example.invalid/model",self.model,
                    sha256="0"*64,max_size=len(data))
        self.assertFalse(self.model.exists())
        self.assertFalse(any(self.model.parent.glob(".brainssd-staging-*")))
        with patch("urllib.request.urlopen",return_value=io.BytesIO(data)):
            with self.assertRaises(ValueError):
                install.download_verified("https://example.invalid/model",self.model,
                    sha256=hashlib.sha256(data).hexdigest(),max_size=30,exact_size=10)
        self.assertFalse(self.model.exists())

    def test_model_install_refuses_existing_invalid_and_never_deletes_notes(self):
        notes=self.root / "AppData/Local/BrainSSD/episodic-notes.sqlite3"
        notes.parent.mkdir(parents=True)
        notes.write_bytes(b"PRIVATE MEMORY")
        sample=b"GGUF"+b"q"*24
        with patch.object(install,"MODEL_BYTES",len(sample)),patch.object(
            install,"MODEL_SHA256",hashlib.sha256(sample).hexdigest()),patch(
            "urllib.request.urlopen",return_value=io.BytesIO(sample)):
            result=install.install_model(self.root)
            self.assertIn("GGUF oficial instalado",result)
            self.assertIn("íntegro",install.install_model(self.root))
            self.model.write_bytes(b"BROKEN partial file")
            with self.assertRaises(FileExistsError):
                install.install_model(self.root)
        self.assertEqual(notes.read_bytes(),b"PRIVATE MEMORY")
        self.assertEqual(self.model.read_bytes(),b"BROKEN partial file")

    def make_zip(self, files: dict[str,bytes]) -> Path:
        target=self.root / "cpu.zip"
        with zipfile.ZipFile(target,"w",compression=zipfile.ZIP_DEFLATED) as package:
            for name,data in files.items():
                package.writestr(name,data)
        return target

    def test_release_installs_in_separate_versioned_folder(self):
        archive=self.make_zip({
            "llama-b11552/llama-completion.exe":b"MZ-completion",
            "llama-b11552/llama-server.exe":b"MZ-server",
            "llama-b11552/ggml-base.dll":b"MZ dependency",
            "llama-b11552/LICENSE":b"license",
        })
        result=install.install_runtime_archive(archive,self.root)
        self.assertIn("instalado separadamente",result)
        self.assertEqual((self.runtime/"llama-completion.exe").read_bytes(),b"MZ-completion")
        self.assertEqual((self.runtime/"ggml-base.dll").read_bytes(),b"MZ dependency")
        self.assertFalse((self.runtime/"LICENSE").exists())
        self.assertFalse((self.root/"third_party/llama.cpp/build-win/bin").exists())
        with self.assertRaises(FileExistsError):
            install.install_runtime_archive(archive,self.root)

    def test_reject_zip_traversal_and_duplicate_dll(self):
        for entries in (
            {"../llama-completion.exe":b"bad"},
            {"C:/evil/llama-completion.exe":b"bad"},
            {"root/a/ggml.dll":b"1","root/b/ggml.dll":b"2","llama-completion.exe":b"MZ"},
            {"root/llama-server.exe":b"MZ"},
        ):
            archive=self.make_zip(entries)
            with self.assertRaises(ValueError):
                install.install_runtime_archive(archive,self.root)
            self.assertFalse(self.runtime.exists())

    def test_runtime_release_verification_rejects_modified_archive(self):
        archive=self.make_zip({"llama-completion.exe":b"MZ"})
        digest=hashlib.sha256(archive.read_bytes()).hexdigest()
        self.assertTrue(install.verified_file(archive,sha256=digest))
        self.assertFalse(install.verified_file(archive,sha256="0"*64))


if __name__=="__main__":
    unittest.main()
