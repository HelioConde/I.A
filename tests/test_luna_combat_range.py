"""Three Qwen-authored numeric combat-range changes (no handcrafted replacement in production)."""
from pathlib import Path
import sys,unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
from repair_luna_game_combat_range import agent
from repair_luna_original_targeted import region,generate_patches,sanitize_model_piece
BASE="""function start(){
const heroType = heroSelect.value;
if(heroType==='melee'){player.hp=100;attackRange = 1;}
else if(heroType==='ranged'){player.hp=80;attackRange = 3;}
else if(heroType==='magic'){player.hp=120;attackRange = 0;}
  gameLoop();
}
"""
ANSWERS=["attackRange = 110;","attackRange = 180;","attackRange = 160;"]

class RangeTests(unittest.TestCase):
    def test_original_three_ranges_in_game_source(self):
        self.assertEqual(len(agent.TASKS),3)
        for task in agent.TASKS:
            a,b,c=region(BASE,task)
            self.assertEqual(a+b+c,BASE)
            self.assertIn("attackRange",b)

    def test_all_three_genuine_model_patches_valid(self):
        responses=list(ANSWERS)
        report,code=generate_patches(BASE,lambda *_:{"answer":responses.pop(0),"model_generated":True},
                                     tasks=agent.TASKS,attempts=1,checker=lambda _:True)
        self.assertEqual(report["patches_accepted"],3)
        self.assertIn("attackRange = 110",code)
        self.assertIn("attackRange = 180",code)
        self.assertIn("attackRange = 160",code)
        self.assertFalse(report["assistant_gameplay_code_used"])

    def test_rejects_zero_and_tiny_ranges(self):
        for task in agent.TASKS:
            self.assertFalse(sanitize_model_piece("attackRange = 1;",task)[0])
        result,code=generate_patches(BASE,lambda *_:{"answer":ANSWERS[0],"model_generated":False},
                                     tasks=agent.TASKS,attempts=1,checker=lambda _:True)
        self.assertIsNone(code)

if __name__=="__main__":
    unittest.main()
