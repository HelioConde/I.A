"""Opt-in episodic memory checks: privacy, separation, negative controls."""
from __future__ import annotations
import sys
import tempfile
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from brain_ssd.chat.episodic import EpisodicMemory, words


class EpisodicTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.file = Path(self.dir.name)/"mem.sqlite3"
        self.mem = EpisodicMemory(self.file)

    def tearDown(self):
        self.dir.cleanup()

    def test_explicit_only_and_persistent(self):
        self.assertEqual(self.mem.list(), [])
        one=self.mem.add("Meu projeto favorito é o Brain-SSD")
        self.assertTrue(one["confirmed"])
        self.assertEqual(one["source"],"explicit_user")
        reopened=EpisodicMemory(self.file)
        self.assertEqual(len(reopened.list()),1)
        self.assertEqual(len(reopened.recall("Qual o meu projeto favorito?")),1)
        self.assertTrue(reopened.delete(one["id"]))
        self.assertEqual(reopened.list(),[])
        self.assertEqual(reopened.recall("projeto favorito"),[])

    def test_abstain_on_unrelated_and_insufficient_cue(self):
        self.mem.add("O tutorial de Python está na pasta pesquisa")
        self.assertEqual(self.mem.recall("O Palmeiras ganhou ontem?"),[])
        self.assertEqual(self.mem.recall("qual foi"),[])
        self.assertEqual(self.mem.recall("tutorial python")[0]["matched_terms"],["python","tutorial"])

    def test_distinct_similar_episodes_not_overwritten(self):
        self.mem.add("A reunião sobre Python será na terça")
        self.mem.add("A reunião sobre Python será na quinta")
        hits=self.mem.recall("reunião Python")
        self.assertEqual(len(hits),2)
        self.assertNotEqual(hits[0]["id"],hits[1]["id"])

    def test_sqlite_confirmed_field_is_boolean_after_reopen(self):
        self.mem.add("Reunião do projeto rover terça na biblioteca")
        self.mem.add("Reunião do projeto rover quinta na biblioteca")
        reopened=EpisodicMemory(self.file)
        listed=reopened.list()
        self.assertEqual(len(listed),2)
        self.assertTrue(all(row["confirmed"] is True for row in listed))
        from brain_ssd.chat.cognitive_lab import replay_preview, propose_associations
        preview=replay_preview(listed)
        self.assertEqual(len(preview.candidate_ids),2)
        self.assertEqual(len(propose_associations(listed)),1)

    def test_long_question_prioritizes_recent_unique_cues(self):
        note=self.mem.add("Projeto rover biblioteca norte")
        filler=" ".join("termo"+str(i).zfill(3) for i in range(45))
        found=self.mem.recall(filler+" projeto rover biblioteca")
        self.assertEqual(len(found),1)
        self.assertEqual(found[0]["id"],note["id"])

    def test_invalid_and_long_note_rejected(self):
        for note in ("  ","A"*501, {"text":"x"}):
            with self.assertRaises(ValueError):
                self.mem.add(note)
        with self.assertRaises(ValueError):
            self.mem.delete("../../secret")
        self.assertEqual(words("MemÓria de Pesquisa"),frozenset({"memoria","pesquisa"}))

    def test_explicit_correction_rebuilds_index_and_can_be_restored(self):
        first = self.mem.add("Visita ao museu marcada para terça")
        self.assertEqual(self.mem.recall("visita museu terça")[0]["id"],first["id"])
        revised = self.mem.replace(
            first["id"],"Visita ao museu remarcada para quinta",
            expected_content=first["content"]
        )
        self.assertTrue(revised["changed"])
        self.assertEqual(self.mem.recall("visita museu terça"),[])
        self.assertEqual(self.mem.recall("visita museu quinta")[0]["id"],first["id"])
        history = self.mem.revisions(first["id"])
        self.assertEqual(history[0]["old_content"],first["content"])
        self.assertEqual(history[0]["operation"],"EDIT")
        reopened = EpisodicMemory(self.file)
        self.assertEqual(len(reopened.revisions(first["id"])),1)
        restored = reopened.restore(first["id"],history[0]["id"],
                                    expected_content=revised["content"])
        self.assertTrue(restored["changed"])
        self.assertEqual(reopened.recall("visita museu terça")[0]["id"],first["id"])
        self.assertEqual(reopened.recall("visita museu quinta"),[])
        self.assertEqual(reopened.revisions(first["id"])[0]["operation"],"RESTORE")
        self.assertEqual(len(reopened.revisions(first["id"])),2)

    def test_stale_editor_is_rejected_and_both_versions_remain_intact(self):
        original=self.mem.add("Projeto rover azul guardado na garagem")
        self.mem.replace(original["id"],"Projeto rover verde guardado na garagem",
                         expected_content=original["content"])
        with self.assertRaisesRegex(ValueError,"outra janela"):
            self.mem.replace(original["id"],"Projeto rover vermelho guardado na garagem",
                             expected_content=original["content"])
        self.assertEqual(self.mem.list()[0]["content"],"Projeto rover verde guardado na garagem")
        self.assertEqual(len(self.mem.revisions(original["id"])),1)
        with self.assertRaises(ValueError):
            self.mem.restore(original["id"],"00000000-0000-0000-0000-000000000000",
                             expected_content=self.mem.list()[0]["content"])

    def test_delete_purges_local_index_and_revision_history(self):
        note=self.mem.add("Meu computador está com defeito")
        self.mem.replace(note["id"],"Meu notebook foi consertado",
                         expected_content=note["content"])
        self.assertEqual(len(self.mem.revisions(note["id"])),1)
        self.assertTrue(self.mem.delete(note["id"]))
        self.assertEqual(self.mem.revisions(note["id"]),[])
        self.assertEqual(self.mem.recall("notebook consertado"),[])
        with self.assertRaises(ValueError):
            self.mem.replace(note["id"],"Texto novo",expected_content="Outro")

    def test_revisions_bounded_to_twenty_and_last_is_deterministic(self):
        note=self.mem.add("Revisão projeto rover versão inicial")
        prev=note["content"]
        for i in range(26):
            nxt=f"Revisão projeto rover versão atualizada {i}"
            self.mem.replace(note["id"],nxt,expected_content=prev)
            prev=nxt
        history=self.mem.revisions(note["id"],limit=100)
        self.assertEqual(len(history),20)
        self.assertEqual(history[0]["new_content"],prev)
        self.assertEqual(history[-1]["new_content"],"Revisão projeto rover versão atualizada 6")
        restored=self.mem.restore(note["id"],history[-1]["id"],expected_content=prev)
        self.assertEqual(restored["content"],"Revisão projeto rover versão atualizada 5")
        self.assertEqual(len(self.mem.revisions(note["id"])),20)

    def test_noop_correction_keeps_version_history_empty(self):
        note=self.mem.add("Minha pasta favorita é estudos")
        same=self.mem.replace(note["id"],"  Minha pasta favorita é estudos ",
                              expected_content=note["content"])
        self.assertFalse(same["changed"])
        self.assertEqual(self.mem.revisions(note["id"]),[])

    def test_offline_replay_only_returns_candidates(self):
        note=self.mem.add("Planejamento de tarefas para o Brain-SSD")
        self.assertEqual(self.mem.replay_candidates()[0]["id"],note["id"])
        self.assertEqual(self.mem.list()[0]["content"],note["content"])

if __name__=="__main__":
    unittest.main()
