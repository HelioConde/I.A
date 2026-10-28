"""Verify third stage of authentic Qwen game source repairs without running the model."""
import sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
from repair_luna_game_class_ai import agent
from repair_luna_original_targeted import region,generate_patches,sanitize_model_piece
BASE="""let player={x:10,hp:100},enemies=[{x:200,hp:10}],heroSelect={value:'melee'};
function start(){
  document.getElementById('hero').value = 'melee';
  gameLoop();
}
function gameLoop(){
    // Enemy movement
    for(let i=0;i<enemies.length;i++)enemies[i].x++;
    // Check for enemy collision
}
"""
RESULTS=[
"const heroType = heroSelect.value; if(heroType==='melee')player.hp=150;else if(heroType==='ranged')player.hp=110;else if(heroType==='magic')player.hp=90;",
"for(const enemy of enemies){enemy.x=Math.max(0,Math.min(940,enemy.x+Math.sign(player.x-enemy.x)));}"
]
class LunaClassAITests(unittest.TestCase):
    def test_markers_unique_and_attribution(self):
        self.assertEqual(len(agent.TASKS),2)
        for task in agent.TASKS:
            left,old,right=region(BASE,task)
            self.assertTrue(old)
            self.assertEqual(left+old+right,BASE)
        self.assertEqual(agent.PRIOR_PATCHES,7)
        self.assertEqual(agent.INPUT_STATUS,"STATIC_REFINED_CANDIDATE")

    def test_model_only_patch_chain(self):
        seq=list(RESULTS)
        result,code=generate_patches(BASE,lambda *_:{"answer":seq.pop(0),"model_generated":True},
                                     tasks=agent.TASKS,attempts=1,checker=lambda _:True)
        self.assertEqual(result["status"],"STATIC_PATCHED_CANDIDATE")
        self.assertEqual(result["patches_accepted"],2)
        self.assertIn("player.hp=150",code)
        self.assertNotIn("value = 'melee'",code)
        self.assertIn("Math.sign",code)
        self.assertFalse(result["assistant_gameplay_code_used"])

    def test_enemy_disappearing_without_damage_rejected(self):
        t=agent.TASKS[1]
        for raw in ["enemies.splice(0,1);player.x=2;","enemies.filter(e=>e.hp>0);player.x=2;",
                    "enemies.length=0;player.x=2;"]:
            with self.subTest(raw=raw):
                self.assertFalse(sanitize_model_piece(raw,t)[0])

if __name__=="__main__":
    unittest.main()
