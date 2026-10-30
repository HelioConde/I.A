"""True CPU test of scratch Luna V2, with only existing original Lua examples."""
from __future__ import annotations
import json
import sys
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

HERE=Path(__file__).resolve().parents[1]/"experiments"/"luna-forge-zero"
sys.path.insert(0,str(HERE))
import torch
import train_original_lua_v2 as v2
import benchmark_original_lua_v2 as probe_v2
from original_lua_lessons import HOLDOUT

class LunaOriginalLuaV2Tests(unittest.TestCase):
    def test_source_is_original_only_and_holdouts_excluded(self):
        items=v2.samples()
        self.assertEqual(len(items),24)
        self.assertEqual(len(set(x["task"] for x in items)),6)
        self.assertEqual(len(HOLDOUT),3)
        texts="\n".join(x["prefix"]+x["code"] for x in items)
        for holdout in HOLDOUT:
            self.assertIsNone(holdout["answer"])
            self.assertNotIn(holdout["objective"],texts)
        self.assertNotIn("grand chase files",texts.lower())
        self.assertNotIn("elsword",texts.lower())

    def test_masked_model_training_batch_has_valid_targets(self):
        import random
        cfg=v2.model_config()
        self.assertGreaterEqual(cfg.block,256)
        self.assertGreater(cfg.width,64)
        batch_x,batch_y=v2.sample_batch(v2.encode_corpus(v2.samples()),
                                         cfg,4,random.Random(42))
        self.assertEqual(tuple(batch_x.shape),(4,cfg.block))
        self.assertEqual(tuple(batch_y.shape),(4,cfg.block))
        self.assertTrue(bool((batch_y!=-100).any()))
        self.assertTrue(bool((batch_y==-100).any()))
        self.assertGreaterEqual(int(batch_y.min()),-100)
        self.assertLessEqual(int(batch_y.max()),127)

    def test_real_scratch_cpu_step_and_checksum_and_holdout_probe(self):
        with tempfile.TemporaryDirectory(prefix="luna_lua_v2_") as tmp:
            root=Path(tmp)
            out=root/"lua-v2-test"
            with patch.object(v2,"DEST_ROOT",root), \
                 patch.object(probe_v2,"DEST_ROOT",root):
                report=v2.train(steps=2,batch=2,threads=2,eval_steps=1,out=out)
                self.assertEqual(report["source"],"original_lua_gameplay.lua; reviewed project-original Lua lessons")
                self.assertEqual(report["commercial_lua_files_used"],0)
                self.assertEqual(report["grandchase_raw_repositories_in_training"],0)
                self.assertEqual(report["holdout_code_examples_in_training"],0)
                self.assertEqual(report["prompt_variant_examples"],24)
                self.assertTrue(report["pretrained_weights_used"] is False)
                self.assertFalse(report["model_promotion_allowed"])
                self.assertEqual(report["config"]["block"],256)
                self.assertGreater(report["parameters"],116480)
                verified,path=probe_v2.verified(out)
                self.assertEqual(verified["weights_sha256"],report["weights_sha256"])
                self.assertTrue(path.is_file())
                candidate=probe_v2.probe(ckpt=out,chars=2,include_output=False)
                self.assertEqual(candidate["holdout_prompts"],3)
                self.assertEqual(candidate["holdout_syntax"],"NOT_TESTED")
                self.assertEqual(candidate["holdout_gameplay"],"NOT_TESTED")
                self.assertFalse(candidate["code_executed"])
                self.assertNotIn("raw_generated_text",str(candidate))
                greedy=probe_v2.probe(ckpt=out,chars=2,decode="greedy",
                                      calibrate=True,include_output=False)
                self.assertEqual(greedy["decode_mode"],"greedy")
                self.assertEqual(greedy["generation_temperature"],0)
                self.assertEqual(greedy["holdout_prompts"],3)
                self.assertTrue(greedy["training_prompt_calibration"]["brief_was_present_in_training"])
                self.assertNotIn("raw_generated_text",str(greedy))
            self.assertEqual(len(list(root.glob("lua-v2-*/weights.pt"))),1)

    def test_training_terminators_are_not_treated_as_lua_code(self):
        self.assertEqual(probe_v2.remove_training_terminator(
            "function f() end\nEND\n"),"function f() end")
        self.assertEqual(probe_v2.remove_training_terminator(
            "function f() end\nFIM"),"function f() end")
        self.assertEqual(probe_v2.remove_training_terminator(
            "function f() end"),"function f() end")

    def test_refuses_unauthorized_checkpoint_path_and_invalid_budgets(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad=Path(tmp)/"unknown"
            with self.assertRaisesRegex(ValueError,"ignored external_data"):
                probe_v2.verified(bad)
            with self.assertRaisesRegex(ValueError,"Output must be"):
                v2.train(steps=1,batch=1,threads=1,eval_steps=1,out=bad)
        for invalid in (0,3001):
            with self.assertRaises(ValueError):
                v2.train(steps=invalid)
        with self.assertRaises(ValueError):
            probe_v2.probe(chars=961)
        with self.assertRaises(ValueError):
            probe_v2.probe(decode="unknown")

if __name__=="__main__":
    unittest.main()
