"""Regression tests for opt-in research memory, freshness, provenance and SSE.

Real user notes and Internet are NEVER used here. All sources are synthetic,
with temporary SQLite databases and fake on-device Qwen generation.
"""
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
import json
import sys
import tempfile
import threading
import time
import unittest
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from brain_ssd.chat.web_knowledge import WebKnowledge, terms
from brain_ssd.chat.server import ChatEngine, create_chat_server
from brain_ssd.chat.diagnostics import DiagnosticLogger


class FakeCore:
    def __init__(self):
        self.prompts = []
    def generate(self, request):
        self.prompts.append(request.prompt)
        return {"return_code": 0, "stdout": "Resposta baseada nas fontes.", "metrics": {}}


class FakeRuntime:
    def __init__(self):
        self.core_backend = FakeCore()
        self.prompt_budget_bytes = 6000
    def retrieve(self, question):
        return {"status": "UNAVAILABLE", "context": {"text": ""}, "sources": [],
                "activated_pages": []}
    def close(self):
        pass


class FakeSearch:
    provider = "auto"
    def __init__(self, sources):
        self.sources = sources
        self.queries = []
    def search(self, question):
        self.queries.append(question)
        return self.sources


def wiki_sources():
    return [
        {"title": "Estrelas e astronomia",
         "url": "https://pt.wikipedia.org/wiki/Estrela",
         "snippet": "Uma estrela é uma esfera luminosa de plasma que possui gravidade."},
        {"title": "Galáxias e astronomia",
         "url": "https://pt.wikipedia.org/wiki/Gal%C3%A1xia",
         "snippet": "Uma galáxia contém estrelas, planetas, gás interestelar e poeira."}
    ]


def dated_news():
    today = datetime.now(timezone.utc).date().isoformat()
    return [
        {"title": "Economia do Brasil",
         "url": "https://agenciabrasil.ebc.com.br/economia/noticia/2026/noticia",
         "snippet": f"Publicado em {today}. Notícia pública sintética sobre a economia brasileira."}
    ]


class TestWebKnowledgeStore(unittest.TestCase):
    def test_records_survive_restart_and_match_related_question(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "research.sqlite3"
            store = WebKnowledge(p)
            self.assertEqual(store.save("Explique astronomia e estrelas", "auto", wiki_sources()), 2)
            reopened = WebKnowledge(p)
            rows = reopened.retrieve("Fale sobre astronomia e estrelas")
            self.assertEqual(len(rows), 2)
            self.assertTrue(all(x["url"].startswith("https://") for x in rows))
            self.assertEqual(reopened.count(), 2)

    def test_research_only_saves_public_attributed_excerpts_and_blocks_secrets(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = WebKnowledge(Path(tmp) / "research.sqlite3")
            self.assertEqual(store.save("Minha senha secreta é 123, pesquise estrelas", "auto", wiki_sources()), 0)
            wrong = [{"title": "Exemplo", "url": "http://127.0.0.1/", "snippet": "Texto com no mínimo vinte e cinco caracteres."}]
            self.assertEqual(store.save("Explique astronomia", "auto", wrong), 0)
            self.assertEqual(store.count(), 0)

    def test_expired_or_unrelated_documents_do_not_appear(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = WebKnowledge(Path(tmp) / "research.sqlite3")
            store.save("Explique astronomia e estrelas", "auto", wiki_sources())
            self.assertEqual(store.retrieve("O que é microbiologia?"), [])
            with store._connect() as db:
                db.execute("UPDATE web_knowledge SET expires_at=?", (int(time.time()) - 1,))
            self.assertEqual(store.retrieve("Explique astronomia e estrelas"), [])
            self.assertEqual(store.count(), 2)  # never erase user data just because TTL expired

    def test_current_news_cannot_be_treated_as_evergreen_or_undated(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = WebKnowledge(Path(tmp) / "research.sqlite3")
            self.assertEqual(store.save("Como está a situação do Brasil hoje?", "auto",
                                        wiki_sources(), current=True), 0)
            self.assertEqual(store.save("Como está a situação do Brasil hoje?", "auto",
                                        dated_news(), current=True), 1)
            self.assertEqual(len(store.retrieve("Como está a situação do Brasil hoje?", current=True)), 1)
            with store._connect() as db:
                db.execute("UPDATE web_knowledge SET expires_at=?", (int(time.time()) - 1,))
            self.assertEqual(store.retrieve("Como está a situação do Brasil?", current=True), [])

    def test_forget_by_topic_does_not_delete_other_topics(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = WebKnowledge(Path(tmp) / "research.sqlite3")
            store.save("Explique astronomia e estrelas", "auto", wiki_sources())
            store.save("Situação de Python", "auto", [
                {"title": "Python Programming", "url": "https://pt.wikipedia.org/wiki/Python",
                 "snippet": "Python é uma linguagem de programação interpretada e popular."}
            ])
            self.assertEqual(store.forget("Explique astronomia e estrelas"), 2)
            self.assertEqual(store.count(), 1)


class TestResearchInChat(unittest.TestCase):
    def test_explicit_save_then_reuse_without_network_or_model_retraining(self):
        with tempfile.TemporaryDirectory() as tmp:
            location = Path(tmp) / "research.sqlite3"
            store = WebKnowledge(location)
            provider = FakeSearch(wiki_sources())
            runtime = FakeRuntime()
            engine = ChatEngine(lambda: runtime, web_search_service=provider,
                                web_knowledge=store)
            engine.start()
            try:
                first = engine.ask("Explique astronomia e estrelas", [], web_search=True,
                                   remember_web=True)
                self.assertEqual(provider.queries, ["Explique astronomia e estrelas"])
                self.assertEqual(first["research_saved_sources"], 2)
                self.assertEqual(len(first["web_sources"]), 2)
                self.assertEqual(store.count(), 2)
                second = engine.ask("Fale sobre astronomia e estrelas", [])
                self.assertEqual(len(provider.queries), 1)
                self.assertEqual(second["research_status"], "archived")
                self.assertGreaterEqual(len(second["research_used_sources"]), 1)
                self.assertIn("consultado em", runtime.core_backend.prompts[-1])
            finally:
                engine.close()

            # New session, same SQLite. No secrets or Qwen weights were changed.
            runtime2 = FakeRuntime()
            engine2 = ChatEngine(lambda: runtime2, web_knowledge=WebKnowledge(location))
            engine2.start()
            try:
                third = engine2.ask("Fale sobre astronomia e estrelas", [])
                self.assertEqual(third["research_status"], "archived")
                self.assertTrue(third["research_used_sources"])
                self.assertEqual(engine2.status()["research_memory_sources"], 2)
                self.assertIn("Estrelas e astronomia", engine2.ask("/conhecimento", [])["answer"])
                self.assertIn("2 fonte(s) apagada(s)", engine2.ask(
                    "/esquecer-pesquisa Explique astronomia e estrelas", [])["answer"])
                self.assertEqual(engine2.status()["research_memory_sources"], 0)
            finally:
                engine2.close()

    def test_no_save_without_approval_even_if_lookup_enabled(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = WebKnowledge(Path(tmp) / "research.sqlite3")
            engine = ChatEngine(FakeRuntime, web_search_service=FakeSearch(wiki_sources()),
                                web_knowledge=store)
            engine.start()
            try:
                result = engine.ask("Explique astronomia e estrelas", [], web_search=True)
                self.assertEqual(result["research_saved_sources"], 0)
                self.assertEqual(store.count(), 0)
                with self.assertRaises(ValueError):
                    engine.ask("Explique astronomia e estrelas", [], remember_web=True)
                with self.assertRaises(ValueError):
                    engine.ask("Explique astronomia e estrelas", [], web_search=True,
                               remember_web="yes")
                self.assertEqual(store.count(), 0)
            finally:
                engine.close()

    def test_unavailable_research_store_refuses_save_instead_of_fake_success(self):
        engine = ChatEngine(FakeRuntime, web_search_service=FakeSearch(wiki_sources()))
        engine.start()
        try:
            with self.assertRaises(ValueError):
                engine.ask("Pesquise astronomia", [], web_search=True, remember_web=True)
        finally:
            engine.close()

    def test_fresh_brazil_news_cache_can_answer_without_second_web_request(self):
        with tempfile.TemporaryDirectory() as tmp:
            memory = WebKnowledge(Path(tmp) / "research.sqlite3")
            provider = FakeSearch(dated_news())
            core = FakeRuntime()
            engine = ChatEngine(lambda: core, web_search_service=provider,
                                web_knowledge=memory)
            engine.start()
            try:
                first = engine.ask("Como está a situação do Brasil hoje?", [],
                                   web_search=True, remember_web=True)
                self.assertEqual(first["research_saved_sources"], 1)
                second = engine.ask("Como está a situação do Brasil hoje?", [])
                self.assertEqual(len(provider.queries), 1)
                self.assertEqual(second["research_status"], "archived")
                self.assertIn("consultado em", core.core_backend.prompts[-1])
            finally:
                engine.close()

    def test_streaming_saves_sources_after_completed_generation(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = WebKnowledge(Path(tmp) / "research.sqlite3")
            engine = ChatEngine(FakeRuntime, web_search_service=FakeSearch(wiki_sources()),
                                web_knowledge=store,
                                diagnostics=DiagnosticLogger(Path(tmp) / "diagnostics"))
            engine.start()
            server = create_chat_server(engine, ROOT / "chat", port=0)
            task = threading.Thread(target=server.serve_forever, daemon=True)
            task.start()
            base = f"http://127.0.0.1:{server.server_address[1]}"
            try:
                payload = {
                    "message": "Explique astronomia e estrelas",
                    "request_id": str(uuid.uuid4()),
                    "web_search": True, "remember_web": True,
                }
                request = urllib.request.Request(
                    base + "/api/chat/stream",
                    headers={"Content-Type": "application/json", "Origin": base},
                    data=json.dumps(payload).encode("utf-8"), method="POST",
                )
                with urllib.request.urlopen(request, timeout=5) as response:
                    events = response.read().decode("utf-8")
                self.assertIn('"research_saved_sources":2', events)
                self.assertIn('"research_status":"new_sources"', events)
                self.assertEqual(store.count(), 2)
            finally:
                server.shutdown()
                server.server_close()
                task.join(timeout=4)
                engine.close()


if __name__ == "__main__":
    unittest.main()
