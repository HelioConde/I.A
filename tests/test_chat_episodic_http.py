"""Opt-in episodic notes in the real HTTP and prompt adapter (fake Core only)."""
from __future__ import annotations
import json
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from brain_ssd.chat.episodic import EpisodicMemory
from brain_ssd.chat.server import ChatEngine, create_chat_server


class FakeCore:
    def __init__(self):
        self.prompts=[]
    def generate(self,req):
        self.prompts.append(req.prompt)
        return {"return_code":0,"stdout":"Entendi o contexto.","metrics":{}}


class FakeRuntime:
    def __init__(self):
        self.core_backend=FakeCore()
        self.prompt_budget_bytes=3500
    def retrieve(self,question):
        return {"status":"UNAVAILABLE","context":{"text":""},"sources":[],"activated_pages":[]}
    def close(self):
        pass


class TestEngine(unittest.TestCase):
    def test_opt_in_recall_no_implicit_learning(self):
        with tempfile.TemporaryDirectory() as temp:
            mem=EpisodicMemory(Path(temp)/"brain.sqlite3")
            runtime=FakeRuntime()
            engine=ChatEngine(lambda:runtime,episodic_store=mem)
            engine.start()
            try:
                engine.ask("Qual é minha cor favorita?",[])
                self.assertEqual(mem.list(),[])
                self.assertNotIn("Notas episódicas",runtime.core_backend.prompts[-1])
                mem.add("Minha cor favorita é azul")
                result=engine.ask("Qual é minha cor favorita?",[])
                self.assertEqual(result["episodic_memories_used"],1)
                self.assertIn("cor favorita",runtime.core_backend.prompts[-1])
                self.assertIn("azul",runtime.core_backend.prompts[-1])
                self.assertLess(len(runtime.core_backend.prompts[-1].encode("utf-8")),3500)
                unrelated=engine.ask("Como funciona astronomia moderna?",[])
                self.assertEqual(unrelated["episodic_memories_used"],0)
                self.assertNotIn("azul",runtime.core_backend.prompts[-1])
            finally:
                engine.close()

    def test_shadow_reports_state_but_does_not_change_core_prompt(self):
        with tempfile.TemporaryDirectory() as temp:
            memory=EpisodicMemory(Path(temp)/"notes.sqlite3")
            memory.add("Meu projeto favorito é o rover azul")
            one=FakeRuntime()
            two=FakeRuntime()
            baseline=ChatEngine(lambda:one,episodic_store=memory)
            shadow=ChatEngine(lambda:two,episodic_store=memory,cognitive_shadow=True)
            baseline.start()
            shadow.start()
            try:
                b=baseline.ask("Qual meu projeto favorito?",[])
                s=shadow.ask("Qual meu projeto favorito?",[])
                self.assertEqual(one.core_backend.prompts[-1],two.core_backend.prompts[-1])
                self.assertIsNone(b["cognitive_shadow"])
                self.assertEqual(s["cognitive_shadow"]["mode"],"READ_ONLY_SHADOW")
                self.assertFalse(s["cognitive_shadow"]["changed_model_prompt"])
                self.assertEqual(shadow.status()["cognitive_shadow_enabled"],True)
            finally:
                baseline.close()
                shadow.close()

    def test_possible_weekday_disagreement_warns_without_silently_replacing(self):
        with tempfile.TemporaryDirectory() as temp:
            mem=EpisodicMemory(Path(temp)/"notes.sqlite3")
            old=mem.add("Reunião projeto rover terça biblioteca norte")
            newer=mem.add("Reunião projeto rover quinta biblioteca norte")
            runtime=FakeRuntime()
            engine=ChatEngine(lambda:runtime,episodic_store=mem)
            engine.start()
            try:
                result=engine.ask("Qual dia da reunião projeto rover biblioteca?",[])
                prompt=runtime.core_backend.prompts[-1]
                self.assertEqual(result["episodic_memories_used"],2)
                self.assertEqual(result["episodic_ambiguities_detected"],1)
                self.assertIn("Não escolha uma delas como verdade",prompt)
                self.assertIn(old["id"],prompt)
                self.assertIn(newer["id"],prompt)
                mem.delete(old["id"])
                second=engine.ask("Qual dia da reunião projeto rover biblioteca?",[])
                self.assertEqual(second["episodic_ambiguities_detected"],0)
                self.assertEqual(second["episodic_memories_used"],1)
                self.assertNotIn(old["id"],runtime.core_backend.prompts[-1])
            finally:
                engine.close()

    def test_alias_bridge_only_changes_opt_in_chat(self):
        with tempfile.TemporaryDirectory() as temp:
            store=EpisodicMemory(Path(temp)/"memory.sqlite3")
            store.add("A reunião do cachorro será no sábado")
            plain_runtime=FakeRuntime()
            alias_runtime=FakeRuntime()
            plain=ChatEngine(lambda:plain_runtime,episodic_store=store)
            enabled=ChatEngine(lambda:alias_runtime,episodic_store=store,memory_aliases=True)
            plain.start()
            enabled.start()
            try:
                prompt="Quando ocorre o encontro do cão?"
                bare=plain.ask(prompt,[])
                bridged=enabled.ask(prompt,[])
                self.assertEqual(bare["episodic_memories_used"],0)
                self.assertEqual(bare["episodic_alias_matches_used"],0)
                self.assertEqual(bridged["episodic_alias_matches_used"],1)
                self.assertEqual(bridged["episodic_memories_used"],1)
                self.assertTrue(enabled.status()["episodic_aliases_enabled"])
                self.assertIn("cachorro", alias_runtime.core_backend.prompts[-1])
                self.assertNotIn("cachorro", plain_runtime.core_backend.prompts[-1])
            finally:
                plain.close()
                enabled.close()

    def test_alias_bridge_requires_explicit_store(self):
        with self.assertRaises(ValueError):
            ChatEngine(FakeRuntime,memory_aliases=True)

    def test_prices_warn_with_two_confirmed_notes_in_prompt(self):
        with tempfile.TemporaryDirectory() as temp:
            mem=EpisodicMemory(Path(temp)/"notes.sqlite3")
            first=mem.add("Preço arroz integral marca norte R$ 12,50")
            second=mem.add("Preço arroz integral marca norte R$ 13,90")
            core=FakeRuntime()
            engine=ChatEngine(lambda:core,episodic_store=mem)
            engine.start()
            try:
                result=engine.ask("Qual preço arroz integral marca norte?",[])
                self.assertEqual(result["episodic_ambiguities_detected"],1)
                text=core.core_backend.prompts[-1]
                self.assertIn("preços diferentes",text)
                self.assertIn(first["id"],text)
                self.assertIn(second["id"],text)
            finally:
                engine.close()

    def test_conflicting_notes_are_withheld_if_warning_cannot_fit(self):
        with tempfile.TemporaryDirectory() as temp:
            store=EpisodicMemory(Path(temp)/"memory.sqlite3")
            long_tail=" detalhes" * 42
            a=store.add("Reunião projeto rover terça biblioteca norte" + long_tail)
            b=store.add("Reunião projeto rover quinta biblioteca norte" + long_tail)
            runtime=FakeRuntime()
            runtime.prompt_budget_bytes=950
            engine=ChatEngine(lambda:runtime,episodic_store=store)
            engine.start()
            try:
                result=engine.ask("Qual dia da reunião projeto rover biblioteca?",[])
                prompt=runtime.core_backend.prompts[-1]
                self.assertEqual(result["episodic_ambiguities_detected"],1)
                self.assertTrue(result["episodic_ambiguities_withheld"])
                self.assertNotIn(a["id"],prompt)
                self.assertNotIn(b["id"],prompt)
                self.assertEqual(result["episodic_memories_used"],0)
                self.assertLessEqual(len(prompt.encode("utf-8")),950)
            finally:
                engine.close()

    def test_persisted_alias_memory_survives_engine_restart_and_deletion(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/"episodic.sqlite3"
            first_store=EpisodicMemory(path)
            item=first_store.add("A reunião do cachorro será no sábado")
            engine1=ChatEngine(FakeRuntime,episodic_store=first_store,memory_aliases=True)
            engine1.start()
            self.assertEqual(engine1.ask("Quando é o encontro do cão?",[])["episodic_memories_used"],1)
            engine1.close()
            reopened=EpisodicMemory(path)
            second_runtime=FakeRuntime()
            engine2=ChatEngine(lambda:second_runtime,episodic_store=reopened,memory_aliases=True)
            engine2.start()
            try:
                result=engine2.ask("Quando é o encontro do cão?",[])
                self.assertEqual(result["episodic_memories_used"],1)
                self.assertIn(item["id"],second_runtime.core_backend.prompts[-1])
                self.assertTrue(reopened.delete(item["id"]))
                later=engine2.ask("Quando é o encontro do cão?",[])
                self.assertEqual(later["episodic_memories_used"],0)
                self.assertNotIn(item["id"],second_runtime.core_backend.prompts[-1])
            finally:
                engine2.close()

    def test_disabled_by_default(self):
        engine=ChatEngine(FakeRuntime)
        engine.start()
        self.assertFalse(engine.status()["episodic_memory_enabled"])
        engine.close()


class TestHttp(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.memory=EpisodicMemory(Path(self.temp.name)/"episodes.sqlite3")
        self.engine=ChatEngine(FakeRuntime,episodic_store=self.memory)
        self.engine.start()
        self.server=create_chat_server(self.engine,ROOT/"chat",port=0,episodic_store=self.memory)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()
        self.url=f"http://127.0.0.1:{self.server.server_address[1]}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)
        self.engine.close()
        self.temp.cleanup()

    def call(self,verb,path,body=None,origin=None):
        data=json.dumps(body or {}).encode("utf-8") if verb=="POST" else None
        req=urllib.request.Request(self.url+path,method=verb,data=data,
            headers={"Origin":origin or self.url,"Content-Type":"application/json"})
        with urllib.request.urlopen(req,timeout=5) as reply:
            return json.loads(reply.read())

    def test_add_list_delete_and_privacy(self):
        self.assertTrue(self.call("GET","/api/memories")["enabled"])
        item=self.call("POST","/api/memories",{"content":"Minha pasta de pesquisa é Estudos"})["memory"]
        self.assertEqual(len(self.call("GET","/api/memories")["memories"]),1)
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self.call("DELETE","/api/memories/"+item["id"],origin="https://outside.invalid")
        self.assertEqual(ctx.exception.code,403)
        self.assertTrue(self.call("DELETE","/api/memories/"+item["id"])["deleted"])
        self.assertEqual(self.call("GET","/api/memories")["memories"],[])

    def test_explicit_edit_restore_and_origin_protection(self):
        old=self.call("POST","/api/memories",{"content":"Projeto rover terça biblioteca"})["memory"]
        endpoint="/api/memories/"+old["id"]
        update={"content":"Projeto rover quinta biblioteca",
                "expected_content":old["content"]}
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self.call("POST",endpoint+"/edit",update,origin="https://attacker.invalid")
        self.assertEqual(ctx.exception.code,403)
        newer=self.call("POST",endpoint+"/edit",update)["memory"]
        self.assertTrue(newer["changed"])
        self.assertEqual(newer["id"],old["id"])
        self.assertEqual(len(self.memory.recall("projeto rover terça")),0)
        self.assertEqual(self.memory.recall("projeto rover quinta")[0]["id"],old["id"])
        revisions=self.call("GET",endpoint+"/revisions")["revisions"]
        self.assertEqual(len(revisions),1)
        self.assertEqual(revisions[0]["old_content"],old["content"])
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self.call("POST",endpoint+"/edit",update)
        self.assertEqual(ctx.exception.code,400)
        restored=self.call("POST",endpoint+"/restore",{
            "revision_id":revisions[0]["id"],
            "expected_content":newer["content"]
        })["memory"]
        self.assertEqual(restored["content"],old["content"])
        self.assertEqual(self.memory.recall("projeto rover terça")[0]["id"],old["id"])
        self.assertTrue(self.call("DELETE",endpoint)["deleted"])
        self.assertEqual(self.call("GET",endpoint+"/revisions")["revisions"],[])

    def test_reject_oversized_or_cross_origin_memory(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self.call("POST","/api/memories",{"content":"x"*501})
        self.assertEqual(ctx.exception.code,400)
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self.call("POST","/api/memories",{"content":"Minha cidade é Recife"},
                      origin="https://outside.invalid")
        self.assertEqual(ctx.exception.code,403)
        self.assertEqual(self.memory.list(),[])


if __name__=="__main__":
    unittest.main()
