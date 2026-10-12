"""Cheap zero-dependency HTML/JS wiring checks before deploying the UI.

Node validates JavaScript syntax in CI; this checks DOM contracts and
same-origin-only static assets without requiring a headless browser.
"""
from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "chat" / "index.html"
JS = ROOT / "chat" / "app.js"
CSS = ROOT / "chat" / "styles.css"


class HtmlInventory(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = []
        self.references = []
        self.scripts = []
        self.styles = []
        self.inline_handlers = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if "id" in attributes:
            self.ids.append(attributes["id"])
        if "aria-controls" in attributes:
            self.references.extend(attributes["aria-controls"].split())
        if "href" in attributes and (attributes["href"] or "").startswith("#"):
            self.references.append(attributes["href"][1:])
        for key in attributes:
            if key.startswith("on"):
                self.inline_handlers.append((tag,key))
        if tag == "script":
            self.scripts.append(attributes.get("src"))
        if tag == "link" and attributes.get("rel") == "stylesheet":
            self.styles.append(attributes.get("href"))


class TestStaticUI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = HTML.read_text(encoding="utf-8")
        cls.js = JS.read_text(encoding="utf-8")
        cls.inventory = HtmlInventory()
        cls.inventory.feed(cls.html)

    def test_no_duplicate_dom_ids(self):
        ids = self.inventory.ids
        self.assertEqual(len(ids),len(set(ids)),"HTML contains duplicated IDs")

    def test_all_static_js_id_references_exist(self):
        references = set(re.findall(r'\$\("([a-zA-Z][a-zA-Z0-9_-]*)"\)',self.js))
        self.assertTrue(references)
        self.assertFalse(references - set(self.inventory.ids),
                         f"JS references absent HTML IDs: {references - set(self.inventory.ids)}")

    def test_accessibility_references_exist(self):
        missing = set(self.inventory.references) - set(self.inventory.ids)
        self.assertFalse(missing, f"Broken anchor/aria-controls targets: {missing}")
        self.assertIn('lang="pt-BR"',self.html)
        self.assertIn('id="messageInput"',self.html)
        self.assertIn('aria-label="Mensagem para a Luna"',self.html)

    def test_no_dynamic_eval_and_protective_csp(self):
        # A console error mentioning "visualize.js" is not a Brain-SSD
        # asset: our UI serves only app.js. Do not weaken CSP to quiet
        # JavaScript injected by browser extensions.
        server = (ROOT / "src" / "brain_ssd" / "chat" / "server.py").read_text(
            encoding="utf-8"
        )
        hud = (ROOT / "hud" / "app.js").read_text(encoding="utf-8")
        for name, source in (("chat/app.js", self.js), ("hud/app.js", hud)):
            with self.subTest(script=name):
                self.assertIsNone(re.search(r"\beval\s*\(", source))
                self.assertIsNone(re.search(r"\bnew\s+Function\s*\(", source))
                self.assertIsNone(re.search(r"\bsetTimeout\s*\(\s*[\x27\x22]", source))
        self.assertIn('self.send_header("Content-Security-Policy"', server)
        self.assertIn("script-src 'self'", server)
        self.assertNotIn("'unsafe-eval'", server)
        self.assertNotIn("'unsafe-inline'", server)
        self.assertNotIn("visualize.js", self.html)
        self.assertNotIn("visualize.js", self.js)

    def test_browser_speech_button_and_fast_web_consent_contracts(self):
        # Read aloud only on a direct click, never from a received message.
        # The browser API does not need unsafe-eval or external scripts.
        self.assertIn('new SpeechSynthesisUtterance(', self.js)
        self.assertIn('speak.addEventListener("click"', self.js)
        self.assertIn('window.speechSynthesis.cancel()', self.js)
        self.assertIn('utterance.lang = "pt-BR"', self.js)
        self.assertIn('speak.disabled = !voiceSupported', self.js)
        self.assertIn('id="webFastControl"', self.html)
        self.assertIn('id="webFastToggle"', self.html)
        self.assertIn('fast_web:fastThisSearch', self.js)
        self.assertIn('id="detailWebMs"', self.html)
        self.assertIn('id="detailInferMs"', self.html)
        self.assertIn('id="responseSize"', self.html)
        self.assertIn('value="96"', self.html)
        self.assertIn('value="256"', self.html)
        self.assertIn('response_tokens:responseTokens', self.js)
        self.assertIn('payload.needs_continuation', self.js)
        self.assertIn('continueButton.textContent = "Continuar resposta"', self.js)
        self.assertIn('className = "generation-incomplete"', self.js)

    def test_luna_hud_is_wired_without_new_automatic_permissions(self):
        hud_js = (ROOT / "chat" / "luna-hud.js").read_text(encoding="utf-8")
        hud_css = (ROOT / "chat" / "luna-hud.css").read_text(encoding="utf-8")
        server = (ROOT / "src" / "brain_ssd" / "chat" / "server.py").read_text(encoding="utf-8")
        dom_ids = set(self.inventory.ids)
        self.assertTrue({"lunaLayout", "lunaRail", "lunaRailToggle", "lunaState",
                         "lunaRailModel", "lunaQuickCopilot", "lunaQuickMetrics",
                         "lunaActivityLog"}.issubset(dom_ids))
        self.assertFalse(set(re.findall(r'element\("([A-Za-z][A-Za-z0-9_-]*)"\)', hud_js)) - dom_ids)
        for route in ('"/luna-hud.js"', '"/luna-hud.css"', '"/luna-call.js"'):
            self.assertIn(route, server)
        for event in ("luna:connection", "luna:permission", "luna:chat", "luna:microphone"):
            self.assertIn(event, self.js)
            self.assertIn(event, hud_js)
        self.assertIn("prefers-reduced-motion", hud_css)
        self.assertIn("data-luna-prompt", hud_js)
        self.assertNotIn("send();", hud_js)
        self.assertNotIn("speechRecognition.start()", hud_js)
        self.assertNotIn("getDisplayMedia", hud_js)
        self.assertNotIn("eval(", hud_js)

    def test_local_microphone_setup_never_autostarts_or_falls_back_to_cloud(self):
        for identifier in ("localMicButton", "localMicSetup", "localMicStatus",
                           "installLocalSpeech", "retryLocalSpeech"):
            self.assertIn('id="' + identifier + '"', self.html)
        self.assertIn('processLocally:true', self.js)
        self.assertIn('recognition.processLocally = true', self.js)
        self.assertIn('nativeSpeech.available(localMicLanguage)', self.js)
        self.assertIn('nativeSpeech.install(localMicLanguage)', self.js)
        self.assertIn('micState.availability !== "downloadable"', self.js)
        self.assertIn('window.confirm("Instalar o pacote pt-BR', self.js)
        self.assertIn('addEventListener("click", async () => {', self.js)
        self.assertNotIn('recognition.processLocally = false', self.js)
        # Installation needs an explicit click; no automatic download on page load.
        # The retry button also invokes checkLocalMic(). Inspect the complete
        # install call site instead of splitting at that earlier retry handler.
        self.assertEqual(self.js.count('nativeSpeech.install(localMicLanguage)'), 1)
        self.assertIn('aria-live="polite"', self.html)
        hud_style = (ROOT / "chat" / "luna-hud.css").read_text(encoding="utf-8")
        self.assertIn('.luna-mic-setup[hidden]', hud_style)

    def test_static_assets_are_local_and_no_inline_handlers(self):
        self.assertEqual(self.inventory.scripts,["/app.js", "/luna-hud.js", "/luna-call.js"])
        self.assertEqual(self.inventory.styles,["/styles.css", "/luna-hud.css"])
        self.assertFalse(self.inventory.inline_handlers)
        self.assertFalse(re.search(r'<script[^>]+src="https?://',self.html))
        self.assertTrue(CSS.is_file())
        self.assertTrue((ROOT / "chat" / "luna-hud.js").is_file())
        self.assertTrue((ROOT / "chat" / "luna-hud.css").is_file())

    def test_voice_call_is_explicit_local_and_has_manual_interrupt(self):
        call_js = (ROOT / "chat" / "luna-call.js").read_text(encoding="utf-8")
        self.assertIn('id="openVoiceCall"', self.html)
        self.assertIn('id="endVoiceCall"', self.html)
        self.assertIn('processLocally = true', call_js)
        self.assertIn('recognition.continuous = true', call_js)
        self.assertIn('window.stopVoiceCallGeneration', call_js)
        self.assertIn('window.speechSynthesis.cancel()', call_js)
        self.assertIn('Turnos alternados', self.html)
        self.assertNotIn('getUserMedia', call_js)
        self.assertNotIn('fetch(', call_js)


if __name__=="__main__":
    unittest.main()
