"""Model-only follow-on repair contract tests (no model, no generated gameplay)."""
import pathlib,sys,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
from repair_luna_game_extra import TASKS
from repair_luna_original_targeted import region,sanitize_model_piece,generate_patches
BASE="""let enemies=[], player={x:1,hp:100}, attackTarget=null;
document.addEventListener('keydown', (e) => {
  if (e.key === 'ArrowRight'){}
  attackTarget = findClosestEnemy();
});
function start(){
  document.getElementById('hero').value = 'melee';
  gameLoop();
}
function gameLoop(){
    // Enemy movement
    for(let i=0;i<enemies.length;i++) enemies[i].x+=1;
    // Check for enemy collision
}
"""
ANSWERS=[
"document.addEventListener('keydown', (e) => {if(e.code==='Space'||e.code==='ArrowLeft'||e.code==='ArrowRight'||e.code==='KeyZ') e.preventDefault();",
"attackTarget = enemies[0] || null;",
"  if(heroSelect.value==='magic')player.hp=95;else if(heroSelect.value==='ranged')player.hp=110;else player.hp=140;",
"for(const enemy of enemies){enemy.x += Math.sign(player.x-enemy.x);enemy.x=Math.max(0,Math.min(940,enemy.x));}"
]

class SmallRefinementTests(unittest.TestCase):
    def test_four_distinct_existing_source_regions(self):
        self.assertEqual(len(TASKS),4)
        for t in TASKS:
            before,old,after=region(BASE,t)
            self.assertTrue(old)
            self.assertEqual(before+old+after,BASE)

    def test_real_model_only_four_small_patches(self):
        queue=list(ANSWERS)
        report,code=generate_patches(BASE,lambda *_:{"answer":queue.pop(0),"model_generated":True},
                                      tasks=TASKS,attempts=1,checker=lambda _:True)
        self.assertEqual(report["patches_accepted"],4)
        self.assertEqual(report["required_patches"],4)
        self.assertIsNotNone(code)
        self.assertNotIn("findClosestEnemy",code)
        self.assertNotIn(".value = 'melee'",code)
        self.assertIn("preventDefault",code)
        self.assertFalse(report["assistant_gameplay_code_used"])

    def test_fake_inference_never_credited(self):
        report,code=generate_patches(BASE,lambda *_:{"answer":ANSWERS[0],"model_generated":False},
                                     tasks=TASKS,attempts=1,checker=lambda _:True)
        self.assertEqual(report["status"],"INCOMPLETE")
        self.assertIsNone(code)
        self.assertEqual(report["patches_accepted"],0)

if __name__=="__main__":
    unittest.main()
