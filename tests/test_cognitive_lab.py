"""Deterministic bounded experiments; do not require Qwen, GPUs or network."""
from __future__ import annotations

import sys
import contextlib
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from brain_ssd.chat.cognitive_lab import (
    select_attention, working_state, propose_associations,
    replay_preview, prediction_error, GridWorld, TabularActionLearner,
)
from brain_ssd.chat.episodic import EpisodicMemory
from brain_ssd.chat.plasticity import PlasticityLedger, PredictionJournal


class TestAttentionAndWorkingMemory(unittest.TestCase):
    def test_sparse_selection_and_abstain(self):
        rows = [
            {"id":"a","text":"Python SQL consultas"},
            {"id":"b","text":"Poesia medieval"},
            {"id":"c","text":"Python gerenciamento de arquivos"},
        ]
        result=select_attention("Python SQL",rows,max_records=1,max_bytes=200)
        self.assertEqual(result.selected_ids,("a",))
        self.assertEqual(set(result.inhibited_ids),{"b","c"})
        self.assertEqual(select_attention("Caminhão diesel",rows).selected_ids,())
        self.assertEqual(select_attention("Python SQL",rows,max_bytes=3).selected_ids,())

    def test_bad_budget_and_duplicate_blocked(self):
        with self.assertRaises(ValueError):
            select_attention("x",[],max_records=999)
        with self.assertRaises(ValueError):
            select_attention("x",[{"id":"z","text":"x"},{"id":"z","text":"y"}])

    def test_compact_recent_state_and_bounded_topics(self):
        history=[{"role":"user","content":"Banco PostgreSQL e Python"},
                 {"role":"assistant","content":"Python e SQLite"},
                 {"role":"user","content":"Preciso conectar Python com PostgreSQL"}]
        state=working_state(history,max_topics=3)
        self.assertIn("python",state.topics)
        self.assertLessEqual(len(state.topics),3)
        self.assertNotIn("Preciso conectar Python",str(state.to_dict()))
        self.assertGreater(state.approx_bytes,0)
        self.assertEqual(state.history_turns,3)


class TestMemoryReplayAndPrediction(unittest.TestCase):
    def test_associations_do_not_merge_source_memories(self):
        notes=[
            {"id":"1","content":"Reunião de Python terça na biblioteca","source":"explicit_user","confirmed":True},
            {"id":"2","content":"Reunião de Python quinta na biblioteca","source":"explicit_user","confirmed":True},
            {"id":"3","content":"Cão corre no parque","source":"explicit_user","confirmed":True},
            {"id":"4","content":"Reunião de Python sexta na biblioteca","source":"auto_generated","confirmed":True},
        ]
        links=propose_associations(notes)
        self.assertEqual(len(links),1)
        self.assertEqual({links[0].left_id,links[0].right_id},{"1","2"})
        preview=replay_preview(notes)
        self.assertFalse(preview.writes_to_model)
        self.assertEqual(set(preview.candidate_ids),{"1","2","3"})
        self.assertEqual(preview.mode,"READ_ONLY_OFFLINE_PREVIEW")

    def test_real_sqlite_episodes_are_associated_and_replayed(self):
        with tempfile.TemporaryDirectory() as folder:
            mem=EpisodicMemory(Path(folder)/"episodes.sqlite3")
            mem.add("Reunião projeto rover terça biblioteca norte")
            mem.add("Reunião projeto rover quinta biblioteca norte")
            notes=mem.list()
            self.assertTrue(all(row["confirmed"] is True for row in notes))
            self.assertEqual(len(propose_associations(notes)),1)
            self.assertEqual(len(replay_preview(notes).candidate_ids),2)

    def test_prediction_error_requires_ground_truth(self):
        good=prediction_error(.8,True)
        bad=prediction_error(.8,False)
        self.assertAlmostEqual(good.brier,.04)
        self.assertAlmostEqual(bad.brier,.64)
        for p in (float("nan"),-1.0,1.01):
            with self.assertRaises(ValueError):
                prediction_error(p,True)
        with self.assertRaises(ValueError):
            prediction_error(.5,"yes")

    def test_closed_perception_action_loop(self):
        world=GridWorld(width=3,height=3,walls=frozenset({(1,1)}),goal=(2,2))
        self.assertEqual(world.observe()["local"]["up"],"wall")
        with self.assertRaises(ValueError):
            world.step("open_browser")
        for action in ("right","right","down","down"):
            last=world.step(action)
        self.assertTrue(last["goal_reached"])
        self.assertEqual(world.position,(2,2))
        self.assertEqual(world.actions,4)
        with self.assertRaises(RuntimeError):
            world.step("left")
        wall=GridWorld(width=3,height=3,walls=frozenset({(1,1)}),goal=(2,2),position=(0,1))
        self.assertTrue(wall.step("right")["blocked"])


class TestReversiblePlasticity(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        root=Path(self.tmp.name)
        self.episodes=EpisodicMemory(root/"episodes.sqlite3")
        self.ledger=PlasticityLedger(root/"feedback.sqlite3",self.episodes)
        self.a=self.episodes.add("Meu projeto de Python usa SQLite")

    def tearDown(self):
        self.tmp.cleanup()

    def test_feedback_min_support_decay_and_rollback(self):
        event1=self.ledger.add_feedback(self.a["id"],1)
        event2=self.ledger.add_feedback(self.a["id"],1)
        self.assertEqual(self.ledger.shadow_bias(self.a["id"])["bias"],0)
        event3=self.ledger.add_feedback(self.a["id"],1)
        current=self.ledger.shadow_bias(self.a["id"])
        self.assertGreater(current["bias"],0)
        self.assertLessEqual(current["bias"],.15)
        self.assertEqual(current["status"],"SHADOW_ONLY")
        self.assertTrue(self.ledger.revoke(event1))
        self.assertEqual(self.ledger.shadow_bias(self.a["id"])["bias"],0)
        self.assertFalse(self.ledger.revoke(event1))
        self.assertEqual(len(self.ledger.list_feedback()),3)
        self.assertTrue(self.ledger.revoke(event2))
        self.assertTrue(self.ledger.revoke(event3))

    def test_deleted_source_can_never_bias_ranking(self):
        for _ in range(3):
            self.ledger.add_feedback(self.a["id"],1)
        self.assertGreater(self.ledger.shadow_bias(self.a["id"])["bias"],0)
        self.assertTrue(self.episodes.delete(self.a["id"]))
        result=self.ledger.shadow_bias(self.a["id"])
        self.assertEqual(result["bias"],0.0)
        self.assertEqual(result["active_support"],0)
        self.assertEqual(result["status"],"SOURCE_DELETED")
        with self.assertRaises(ValueError):
            self.ledger.add_feedback(self.a["id"],1)

    def test_feedback_follows_exact_revision_and_restore_does_not_reactivate(self):
        for _ in range(3):
            self.ledger.add_feedback(self.a["id"],1)
        self.assertGreater(self.ledger.shadow_bias(self.a["id"])["bias"],0)
        corrected=self.episodes.replace(
            self.a["id"], "Meu projeto Python usa PostgreSQL",
            expected_content=self.a["content"])
        self.assertEqual(corrected["id"],self.a["id"])
        self.assertEqual(self.ledger.shadow_bias(self.a["id"])["active_support"],0)
        self.assertEqual(self.ledger.shadow_bias(self.a["id"])["bias"],0)
        for _ in range(3):
            self.ledger.add_feedback(self.a["id"],-1)
        self.assertLess(self.ledger.shadow_bias(self.a["id"])["bias"],0)
        # Returning to exactly the old text is a NEW revision. Old evidence
        # must remain inactive until the user explicitly evaluates it again.
        item=self.episodes.restore(
            self.a["id"], self.episodes.revisions(self.a["id"])[0]["id"],
            expected_content=corrected["content"])
        self.assertEqual(item["content"],self.a["content"])
        self.assertEqual(self.ledger.shadow_bias(self.a["id"])["bias"],0)

    def test_migrated_unversioned_ledger_is_conservatively_ignored(self):
        import sqlite3
        # Old feedback rows created by earlier releases contain no
        # revision identifier; never attach them to an edited note.
        with self.ledger._connect() as db:
            db.execute("INSERT INTO feedback (id,episode_id,signal,created_at,revoked_at) VALUES (?,?,?,?,NULL)",
                       ("11111111-1111-4111-8111-111111111111", self.a["id"],1,int(time.time())))
        self.assertEqual(self.ledger.shadow_bias(self.a["id"])["active_support"],0)

    def test_preexisting_feedback_database_migrates_without_reusing_old_signals(self):
        import sqlite3
        import uuid
        legacy=Path(self.tmp.name)/"legacy-feedback.sqlite3"
        with contextlib.closing(sqlite3.connect(legacy)) as db:
            db.execute("CREATE TABLE feedback (id TEXT PRIMARY KEY, episode_id TEXT NOT NULL, "
                       "signal INTEGER NOT NULL, created_at INTEGER NOT NULL, revoked_at INTEGER)")
            db.execute("INSERT INTO feedback VALUES (?,?,?,?,NULL)",
                       (str(uuid.uuid4()),self.a["id"],1,int(time.time())))
            db.commit()
        migrated=PlasticityLedger(legacy,self.episodes)
        assert migrated.shadow_bias(self.a["id"])["active_support"] == 0
        for _ in range(3):
            migrated.add_feedback(self.a["id"],-1)
        self.assertLess(migrated.shadow_bias(self.a["id"])["bias"],0)
        with contextlib.closing(sqlite3.connect(legacy)) as db:
            self.assertIn("source_version",{row[1] for row in db.execute("PRAGMA table_info(feedback)")})

    def test_bad_feedback_and_unknown_memory(self):
        with self.assertRaises(ValueError):
            self.ledger.add_feedback(self.a["id"],True)
        with self.assertRaises(ValueError):
            self.ledger.add_feedback(self.a["id"],0)
        with self.assertRaises(ValueError):
            self.ledger.add_feedback("00000000-0000-0000-0000-000000000000",1)
        with self.assertRaises(ValueError):
            self.ledger.revoke("../../relative")

    def test_persistence_and_no_weight_updates(self):
        self.ledger.add_feedback(self.a["id"],-1)
        root=Path(self.tmp.name)
        reopened=PlasticityLedger(root/"feedback.sqlite3",self.episodes)
        self.assertEqual(reopened.shadow_bias(self.a["id"])["active_support"],1)
        self.assertEqual(self.episodes.list()[0]["content"],self.a["content"])


if __name__=="__main__":
    unittest.main()


class TestPredictionJournal(unittest.TestCase):
    def test_feedback_changes_only_task_probability_and_is_reversible(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"predictions.sqlite3"
            journal=PredictionJournal(path)
            first=journal.predict("grid_reach_goal")
            self.assertEqual(first["probability"],0.5)
            observed=journal.observe("grid_reach_goal",True)
            self.assertEqual(observed["prediction_error"],0.5)
            self.assertEqual(observed["brier"],0.25)
            self.assertAlmostEqual(journal.predict("grid_reach_goal")["probability"],0.666667)
            journal.observe("grid_reach_goal",True)
            self.assertEqual(journal.predict("grid_reach_goal")["probability"],0.75)
            self.assertEqual(journal.predict("other_task")["probability"],0.5)
            self.assertTrue(journal.revoke(observed["id"]))
            self.assertEqual(journal.predict("grid_reach_goal")["probability"],0.666667)
            self.assertFalse(journal.revoke(observed["id"]))
            reopened=PredictionJournal(path)
            self.assertEqual(reopened.predict("grid_reach_goal")["observations"],1)

    def test_ground_truth_and_keys_must_be_verified(self):
        with tempfile.TemporaryDirectory() as directory:
            journal=PredictionJournal(Path(directory)/"predictions.sqlite3")
            with self.assertRaises(ValueError):
                journal.observe("grid_reach_goal","yes")
            with self.assertRaises(ValueError):
                journal.observe("my password is 123", True)
            self.assertEqual(journal.predict("grid_reach_goal")["observations"],0)


class TestLearningInClosedWorld(unittest.TestCase):
    def test_updates_prediction_error_and_learns_greedy_policy(self):
        agent=TabularActionLearner(seed=17)
        baseline=agent.evaluate()
        trained=agent.train(episodes=400,epsilon=.3)
        after=agent.evaluate()
        self.assertGreater(trained["reached_goal"],0)
        self.assertGreater(trained["updates"],0)
        self.assertLessEqual(trained["q_values"],30*30*4)
        self.assertTrue(after["goal_reached"])
        self.assertLessEqual(after["steps"],20)
        self.assertFalse(trained["model_weights_changed"])
        self.assertEqual(after["q_updates_during_evaluation"],0)

    def test_invalid_learning_outcomes_are_rejected(self):
        agent=TabularActionLearner()
        world=GridWorld()
        before=world.observe()
        with self.assertRaises(ValueError):
            agent.learn(before,"open_web_browser",1,before,False)
        with self.assertRaises(ValueError):
            agent.learn(before,"up",float("nan"),before,False)
        with self.assertRaises(ValueError):
            agent.train(episodes=10000)
