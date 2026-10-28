"""Smoke actual MiniCoder incremental training using only invented synthetic Lua."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

LAB=Path(__file__).resolve().parents[1]/"experiments"/"luna-forge-zero"
sys.path.insert(0,str(LAB))
import torch
from luna_codegen_model import Config,LunaMiniCoder
import train_private_lua
import preview_private_lua

CODE=(
    "local function update_actor(actor, axis, dt)\n"
    "  if axis < 0 then actor.x = actor.x - dt end\n"
    "  if axis > 0 then actor.x = actor.x + dt end\n"
    "  return actor\n"
    "end\n"
)*12

class RuntimeTrainPrivateLuaTests(unittest.TestCase):
    def test_real_cpu_train_and_private_sha_verified(self):
        with tempfile.TemporaryDirectory(prefix="luna_runtime_") as tmp:
            root=Path(tmp)
            game=root/"game_files"
            game.mkdir()
            for i in range(50):
                (game/f"game_{i:03d}.lua").write_text(CODE,encoding="utf-8")
            parents=root/"parent"
            source=parents/"local-candidate-synthetic"
            source.mkdir(parents=True)
            weights=source/"weights.pt"
            cfg=Config()
            torch.save(LunaMiniCoder(cfg).state_dict(),weights)
            sha=hashlib.sha256(weights.read_bytes()).hexdigest()
            (source/"report.json").write_text(json.dumps({
                "status":"experiment_not_promoted",
                "promotion_allowed":False,
                "grandchase_raw_repositories_in_training":0,
                "weights_sha256":sha,
                "config":dict(vars(cfg)),
            }),encoding="utf-8")
            output=root/"private_lua_training"
            with patch.object(train_private_lua,"PARENT_MODELS",parents), \
                 patch.object(train_private_lua,"OUTPUT_ROOT",output):
                report=train_private_lua.train(game,max_mib=1,steps=2,batch=2,threads=2)
            self.assertEqual(report["status"],"private_experimental_checkpoint_not_promoted")
            self.assertGreater(report["sampled_files"],20)
            self.assertGreater(report["heldout_files"],1)
            self.assertEqual(report["network_requests"],0)
            self.assertEqual(report["source_files_exported"],0)
            self.assertFalse(report["model_promotion_allowed"])
            self.assertEqual(len(list(output.glob("private-lua-*/weights.pt"))),1)
            private_dir=next(output.glob("private-lua-*"))
            with patch.object(preview_private_lua,"OUTPUT_ROOT",output):
                verified,stored=preview_private_lua.verify_checkpoint(private_dir)
            self.assertEqual(verified["parent_weights_sha256"],sha)
            self.assertEqual(stored,private_dir/"weights.pt")
            self.assertNotIn(str(game),json.dumps(verified))
            self.assertNotIn("game_000.lua",json.dumps(verified))

if __name__=="__main__":
    unittest.main()
