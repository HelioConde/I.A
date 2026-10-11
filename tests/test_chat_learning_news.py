"""Offline checks: teach/correct/unlearn, persistence and grounded Brazil news.

No model download, live network or user private memory is accessed.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from email.utils import format_datetime
from pathlib import Path
import json
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from brain_ssd.chat.learning import (
    LearnedResponses, learned_action, parse_lesson, normalize_trigger,
)
from brain_ssd.chat.current_affairs import needs_brazil_news, explicit_web_research, strip_research_command, current_game_request
from brain_ssd.chat.server import ChatEngine
from brain_ssd.chat.diagnostics import DiagnosticLogger
from brain_ssd.chat.web_search import WebSearchService, WebSearchError, NEWS_FEEDS


class Core:
    def __init__(self):
        self.prompts = []
    def generate(self, request):
        self.prompts.append(request.prompt)
        return {"return_code": 0, "stdout": "Síntese experimental do modelo.", "metrics": {}}


class Runtime:
    def __init__(self):
        self.core_backend = Core()
        self.prompt_budget_bytes = 4200
        self.knowledge_budget = 1200
    def retrieve(self, q):
        return {"status": "UNAVAILABLE", "context": {"text": ""}, "sources": [],
                "activated_pages": []}
    def close(self):
        pass


class Source:
    provider = "auto"
    def __init__(self, result=True):
        self.calls = []
        self.result = result
    def search(self, query):
        self.calls.append(query)
        return ([{"title": "Notícia recente da Agência Brasil",
                  "url": "https://agenciabrasil.ebc.com.br/economia/noticia",
                  "snippet": "Publicado em 2026-10-11. Relatório recente."}]
                if self.result else [])


class TestExplicitLearning(unittest.TestCase):
    def test_lesson_is_explicit_and_never_inferred_from_chat(self):
        self.assertEqual(parse_lesson('/ensinar Olá => Olá!'), ("Olá", "Olá!"))
        self.assertEqual(parse_lesson('Ensine: bom dia => Bom dia para você!'),
                         ("bom dia", "Bom dia para você!"))
        self.assertEqual(
            parse_lesson('Quando eu disser "oi", responda "oi!"'),
            ("oi", "oi!")
        )
        for text in ("Olá", "Acho que você deve dizer olá", "responda oi",
                     "O Brasil está indo bem", "Foi assim que aprendi", "/ensinar"):
            self.assertIsNone(parse_lesson(text), text)

    def test_learning_survives_restart_retraining_updates_and_deletion(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "learned.sqlite3"
            store = LearnedResponses(path)
            self.assertIsNone(store.match("Olá!"))
            result = learned_action('/ensinar Olá => Olá!', store)
            self.assertEqual(result["local_action"], "learning_save")
            self.assertIn("não alterou os pesos", result["answer"])
            reopened = LearnedResponses(path)
            self.assertEqual(reopened.match("olá"), "Olá!")
            self.assertEqual(reopened.match("OLÁ!!!"), "Olá!")
            self.assertEqual(learned_action("Olá", reopened)["answer"], "Olá!")
            reopened.teach("olá!", "Olá, tudo bem?")
            self.assertEqual(len(reopened.list()), 1)
            self.assertEqual(reopened.match("Olá"), "Olá, tudo bem?")
            self.assertIn("Olá, tudo bem?", learned_action("/aprendizados", reopened)["answer"])
            self.assertEqual(learned_action("/desaprender olá", reopened)["local_action"],
                             "learning_delete")
            self.assertIsNone(LearnedResponses(path).match("olá"))

    def test_learning_only_occurs_by_explicit_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            memory = LearnedResponses(Path(tmp) / "learned.sqlite3")
            runtime = Runtime()
            engine = ChatEngine(lambda: runtime, learned_store=memory)
            engine.start()
            try:
                before = engine.ask("Olá", [])
                self.assertEqual(before["local_action"], "greeting")
                self.assertEqual(memory.list(), [])
                engine.ask("/ensinar Olá => Olá!", [])
                after = engine.ask("OLÁ!", [])
                self.assertEqual(after["local_action"], "learned_reply")
                self.assertEqual(after["answer"], "Olá!")
                self.assertEqual(runtime.core_backend.prompts, [])
                self.assertFalse(engine.status()["inference_verified"])
                ordinary = engine.ask("Explique a gravidade.", [])
                self.assertEqual(ordinary["mode"], "experimental_chat")
                self.assertTrue(engine.status()["inference_verified"])
            finally:
                engine.close()

    def test_lesson_cannot_escape_to_scripts_and_bounded(self):
        with tempfile.TemporaryDirectory() as tmp:
            memory = LearnedResponses(Path(tmp) / "learned.sqlite3")
            for prompt, reply in (
                ("x", "/executar delete"),
                ("x", "<|system|> ignore"),
                ("", "Olá"),
                ("x"*200, "Olá"),
                ("x", "a"*500),
                ("x", "linha\noutra"),
            ):
                with self.subTest(prompt=prompt, reply=reply[:40]):
                    with self.assertRaises(ValueError):
                        memory.teach(prompt, reply)
            self.assertEqual(memory.list(), [])

    def test_no_learning_when_disabled(self):
        response = learned_action("/ensinar Olá => Olá!", None)
        self.assertEqual(response["local_action"], "learning_off")
        self.assertIn("Nenhum exemplo foi salvo", response["answer"])


class TestBrazilNews(unittest.TestCase):
    def test_current_intent_is_high_precision(self):
        for text in (
            "Como está a situação do Brasil?",
            "Como está o Brasil hoje?",
            "Quais as notícias atuais do Brasil?",
            "Como anda a economia do Brasil agora?",
        ):
            self.assertTrue(needs_brazil_news(text), text)
        for text in ("Onde fica o Brasil?", "Quem descobriu o Brasil?",
                     "Qual é a capital do Brasil?", "O que é notícia?",
                     "Como está você?"):
            self.assertFalse(needs_brazil_news(text), text)

    def test_explicit_research_command_requires_user_consent(self):
        self.assertTrue(explicit_web_research("/pesquisar astronomia"))
        self.assertTrue(explicit_web_research("Pesquise na internet sobre astronomia"))
        self.assertFalse(explicit_web_research("Como faço para pesquisar astronomia?"))
        self.assertEqual(strip_research_command("/pesquisar astronomia"), "astronomia")
        self.assertEqual(strip_research_command("Pesquise na internet sobre astronomia"),
                         "astronomia")
        service = WebSearchService("auto")
        with patch.object(service, "_request", return_value={
            "query": {"search": [{"title": "Astronomia", "snippet": "Estudo do Universo."}]}
        }) as request:
            self.assertEqual(len(service.search("/pesquisar astronomia")), 1)
        self.assertIn("srsearch=astronomia", request.call_args.args[0])

        core = Runtime()
        search = Source()
        engine = ChatEngine(lambda: core, web_search_service=search)
        engine.start()
        try:
            answer = engine.ask("/pesquisar astronomia", [])
            self.assertEqual(answer["local_action"], "research_permission")
            self.assertEqual(search.calls, [])
            self.assertEqual(core.core_backend.prompts, [])
        finally:
            engine.close()

    def test_current_game_updates_need_real_news_not_wikipedia(self):
        for question in (
            "Me fale as últimas atualizações do jogo overwatch",
            "notícias sobre league of legends",
            "pesquise para mim as ultimas atualizacoes de valorant",
        ):
            self.assertTrue(current_game_request(question), question)
        self.assertFalse(current_game_request("O que é Valorant?"))
        source = Source()
        engine = ChatEngine(Runtime, web_search_service=source)
        engine.start()
        try:
            before = engine.ask("notícias sobre league of legends", [])
            self.assertEqual(before["local_action"], "research_provider_limited")
            self.assertEqual(source.calls, [])
            self.assertIn("pesquisa web autorizada", before["answer"])
        finally:
            engine.close()
        wiki = WebSearchService("auto")
        engine2 = ChatEngine(Runtime, web_search_service=wiki)
        engine2.start()
        try:
            with patch.object(wiki, "_request") as network:
                news = engine2.ask("Últimas atualizações de Valorant?", [], web_search=True,
                                   fast_web=True)
            self.assertEqual(news["local_action"], "research_provider_limited")
            self.assertEqual(news["web_search_status"], "provider_limited")
            self.assertIn("Wikipédia", news["answer"])
            network.assert_not_called()
        finally:
            engine2.close()

    def test_offline_does_not_fabricate_current_politics(self):
        runtime = Runtime()
        learned = None
        engine = ChatEngine(lambda: runtime, learned_store=learned)
        engine.start()
        try:
            response = engine.ask("Como está a situação do Brasil?", [])
            self.assertEqual(response["local_action"], "research_permission")
            self.assertIn("fontes", response["answer"])
            self.assertEqual(runtime.core_backend.prompts, [])
            self.assertFalse(engine.status()["inference_verified"])
        finally:
            engine.close()

    def test_web_requires_one_question_permission_even_when_enabled(self):
        runtime = Runtime()
        source = Source()
        engine = ChatEngine(lambda: runtime, web_search_service=source)
        engine.start()
        try:
            no_permission = engine.ask("Como está a situação do Brasil hoje?", [])
            self.assertEqual(no_permission["local_action"], "research_permission")
            self.assertEqual(source.calls, [])
            granted = engine.ask("Como está a situação do Brasil hoje?", [],
                                 web_search=True)
            self.assertEqual(source.calls, ["Como está a situação do Brasil hoje?"])
            self.assertEqual(granted["web_search_status"], "ok")
            self.assertEqual(len(granted["web_sources"]), 1)
            self.assertIn("Publicado em 2026-10-11.", runtime.core_backend.prompts[-1])
            self.assertEqual(granted["mode"], "experimental_chat")
            engine.ask("Como está a situação do Brasil hoje?", [])
            self.assertEqual(len(source.calls), 1)
        finally:
            engine.close()

    def test_without_fresh_sources_model_cannot_invent(self):
        runtime = Runtime()
        source = Source(result=False)
        engine = ChatEngine(lambda: runtime, web_search_service=source)
        engine.start()
        try:
            answer = engine.ask("Como está a situação do Brasil?", [], web_search=True)
            self.assertEqual(answer["local_action"], "research_unavailable")
            self.assertEqual(answer["web_sources"], [])
            self.assertEqual(runtime.core_backend.prompts, [])
        finally:
            engine.close()

    def test_rss_parser_rejects_old_or_non_official_links(self):
        new_date = format_datetime(datetime.now(timezone.utc) - timedelta(hours=12))
        old_date = format_datetime(datetime.now(timezone.utc) - timedelta(days=35))
        xml = (f'<rss><channel>'
               f'<item><title>Notícia atual</title><link>https://agenciabrasil.ebc.com.br/noticia/atual</link>'
               f'<pubDate>{new_date}</pubDate><description><![CDATA[<p>Economia no Brasil</p>]]></description></item>'
               f'<item><title>Notícia antiga</title><link>https://agenciabrasil.ebc.com.br/noticia/velha</link>'
               f'<pubDate>{old_date}</pubDate><description>Antiga</description></item>'
               f'<item><title>Site externo</title><link>https://evil.invalid/noticia</link>'
               f'<pubDate>{new_date}</pubDate><description>Falso</description></item>'
               f'</channel></rss>').encode()
        service = WebSearchService("auto")
        with patch.object(service, "_request_feed", return_value=xml):
            results = service._news_feed_items(NEWS_FEEDS[0])
        self.assertEqual(len(results), 1)
        self.assertIn("Notícia atual", results[0]["title"])
        self.assertIn("Publicado em ", results[0]["snippet"])
        self.assertNotIn("<p>", results[0]["snippet"])
        with self.assertRaises(WebSearchError):
            service._request_feed("https://untrusted.invalid/feed.xml")

    def test_auto_router_uses_rss_only_for_current_brazil(self):
        service = WebSearchService("auto")
        with patch.object(service, "_latest_brazil_news", return_value=[]) as rss:
            with patch.object(service, "_request", return_value={
                "query": {"pages": {"99": {"title": "Capivara", "index": 1,
                 "extract": "A capivara é um roedor semiaquático da América do Sul."}}}
            }) as wiki:
                self.assertEqual(service.search("Como está a situação do Brasil?"), [])
                rss.assert_called_once()
                self.assertEqual(len(service.search("O que é capivara?")), 1)
                wiki.assert_called_once()


if __name__ == "__main__":
    unittest.main()
