"""Qwen-authored combat range balancing contract tests."""
from pathlib import Path
import sys,unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
from repair_luna_game_combat_range import agent
from repair_luna_original_targeted import region,generate_patches,sanitize_model_piece
BASE="""function start(){
const heroType = heroSelect.value;
if(heroType==='melee'){player.hp=100;attackRange=1;}
else if(heroType==='ranged'){player.hp=80;attackRange=3;}
else if(heroType==='magic'){player.hp=120;attackRange=0;}
  gameLoop();
}
"""
PATCH="""const heroType = heroSelect.value;
if(heroType==='melee'){player.hp=100;attackRange=110;}
else if(heroType==='ranged'){player.hp=80;attackRange=180;}
else if(heroType==='magic'){player.hp=120;attackRange=160;}
"""
class RangeTests(unittest.TestCase):
    def test_region_replaces_qwen_only(self):
        self.assertEqual(len(agent.TASKS),1)
        left,old,right=region(BASE,agent.TASKS[0])
        self.assertEqual(left+old+right,BASE)
        self.assertIn("attackRange=1",old)

    def test_valid_native_model_range_is_accepted(self):
        result,code=generate_patches(BASE,lambda *_:{"answer":PATCH,"model_generated":True},
                                     tasks=agent.TASKS,attempts=1,checker=lambda _:True)
        self.assertEqual(result["patches_accepted"],1)
        self.assertIn("attackRange=180",code)
        self.assertFalse(result["assistant_gameplay_code_used"])

    def test_rejects_tiny_or_fake_ranges(self):
        bad=PATCH.replace("attackRange=110","attackRange=1")
        self.assertFalse(sanitize_model_piece(bad,agent.TASKS[0])[0])
        bad=PATCH.replace("attackRange=160","attackRange=110")
        self.assertTrue(sanitize_model_piece(bad,agent.TASKS[0])[0])
        result,code=generate_patches(BASE,lambda *_:{"answer":PATCH,"model_generated":False},
                                     tasks=agent.TASKS,attempts=1,checker=lambda _:True)
        self.assertIsNone(code)

if __name__=="__main__":
    unittest.main()
