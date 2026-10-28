"""Test local Ollama coder without running a model or calling a network."""
from __future__ import annotations
import importlib.util
from pathlib import Path
import shutil
import unittest
from unittest import mock

HERE=Path(__file__).resolve().parents[1]/"experiments"/"luna-forge-zero"
spec=importlib.util.spec_from_file_location("luna_coder_ollama",HERE/"luna_coder_ollama.py")
backend=importlib.util.module_from_spec(spec)
spec.loader.exec_module(backend)

class LocalCoderTests(unittest.TestCase):
    def test_code_fences_and_plain_code(self):
        fence=chr(96)*3
        self.assertEqual(backend.extract_code(f"{fence}javascript\nfunction play(){{return 1;}}\n{fence}"),
                         "function play(){return 1;}")
        self.assertEqual(backend.extract_code("~~~js\nconst x=2;\n~~~"),"const x=2;")
        self.assertEqual(backend.extract_code("function move(){return true;}"),
                         "function move(){return true;}")

    def test_no_remote_server_endpoints(self):
        with self.assertRaises(ValueError):
            backend.local_json("GET","https://evil.example/upload")
        with self.assertRaises(ValueError):
            backend.local_json("POST","/other")
        self.assertEqual(backend.HOST,"127.0.0.1")

    def test_missing_model_does_not_call_chat(self):
        with mock.patch.object(backend,"installed_models",return_value=[]), \
             mock.patch.object(backend,"chat") as chat:
            with self.assertRaises(backend.LocalModelError):
                backend.generate("Make a jump",model="qwen2.5-coder:3b")
            chat.assert_not_called()

    def test_repair_on_syntax_failure(self):
        fence=chr(96)*3
        calls=[
            f"{fence}js\nfunction move( {{ x }} \n{fence}",
            f"{fence}javascript\nfunction move(player, dt) {{ player.x += dt; return player; }}\n{fence}",
        ]
        with mock.patch.object(backend,"installed_models",return_value=["qwen2.5-coder:3b"]), \
             mock.patch.object(backend,"chat",side_effect=calls) as chat:
            if not shutil.which("node"):
                with mock.patch.object(backend,"syntax_check",
                                       side_effect=[{"status":"fail","reason":"syntax"},
                                                    {"status":"pass","reason":"syntax only"}]):
                    result=backend.generate("Move horizontally")
            else:
                result=backend.generate("Move horizontally")
            self.assertEqual(result["syntax"]["status"],"pass")
            self.assertEqual(result["attempts"],2)
            self.assertFalse(result["generated_code_executed"])
            self.assertFalse(result["active_luna_weights_modified"])
            self.assertEqual(result["cloud_calls"],0)
            self.assertEqual(chat.call_count,2)

    def test_no_automatic_repair_when_syntax_valid(self):
        with mock.patch.object(backend,"installed_models",return_value=["qwen2.5-coder:3b"]), \
             mock.patch.object(backend,"chat",return_value="function jump(p){return p;}") as chat, \
             mock.patch.object(backend,"syntax_check",return_value={"status":"pass","reason":"parse only"}):
            result=backend.generate("Implement jump")
            self.assertEqual(result["attempts"],1)
            chat.assert_called_once()

    def test_reject_large_or_unsupported_input(self):
        with self.assertRaises(ValueError):
            backend.generate("a"*2001)
        with self.assertRaises(ValueError):
            backend.generate("any",model="qwen3-coder:30b")

    @unittest.skipUnless(shutil.which("node"),"Node.js not installed in this test runner")
    def test_node_parser_is_syntax_only(self):
        ok=backend.syntax_check("function move(p,dt){p.x+=dt; return p;}")
        bad=backend.syntax_check("function move(p){ return (}")
        self.assertEqual(ok["status"],"pass")
        self.assertEqual(bad["status"],"fail")
        self.assertIn("behavior NOT tested",ok["reason"])

if __name__=="__main__":
    unittest.main()
