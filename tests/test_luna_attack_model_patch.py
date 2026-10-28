"""Verify native-model only combat patch behavior and provenance in isolation."""
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
from benchmark_luna_attack_patch import source_region,unwrap_fragment,run_trial,START,END,REQUEST

ORIGINAL="""let attackTimer=0,attackTarget=null,enemies=[];
function gameLoop(){
  // Attack
  if(isAttacking && attackTarget){attackTarget.hp-=10;enemies.splice(0,1);}
  // Enemy movement
  const n=enemies.length;
}
"""
PATCH="""if (isAttacking) {
  if (attackTimer>0) attackTimer--;
  else isAttacking=false;
  if (attackTarget) {
    if (Math.abs(attackTarget.x - player.x) < attackRange) {
      attackTarget.hp -= 10;
      if (attackTarget.hp<=0) {
        const index=enemies.indexOf(attackTarget);
        if (index>=0) enemies.splice(index,1);
      }
      attackTarget = null;
    }
  }
}"""

class AttackModelTests(unittest.TestCase):
    def test_model_receives_bug_from_real_luna_game(self):
        actual=(ROOT/"site"/"luna-created"/"game.js").read_text(encoding="utf-8")
        before,old,after=source_region(actual)
        self.assertEqual(before+old+after,actual)
        self.assertIn("attackTarget.hp -= 10;",old)
        self.assertNotIn("attackTarget = null",old)
        self.assertIn("UMA VEZ",REQUEST)

    def test_genuine_model_patch_only(self):
        received=[]
        def infer(prompt,n):
            received.append((prompt,n))
            return {"answer":PATCH,"model_generated":True}
        report,code=run_trial(ORIGINAL,infer,attempts=1,validate=lambda _:True)
        self.assertEqual(report["status"],"STATIC_PATCH_CANDIDATE")
        self.assertTrue(report["model_generated_patch"])
        self.assertFalse(report["assistant_gameplay_code_used"])
        self.assertIn("attackTarget = null",code)
        self.assertIn("TRECHO DO SEU JOGO",received[0][0])
        self.assertEqual(received[0][1],900)

    def test_invalid_and_fake_model_results_blocked(self):
        for answer,real in [(PATCH,False),("attackTarget.hp -= 10;",True),
                            ("fetch('https://foo')",True)]:
            with self.subTest(answer=answer[:30]):
                report,code=run_trial(ORIGINAL,
                  lambda *_:{"answer":answer,"model_generated":real},
                  attempts=1,validate=lambda _:True)
                self.assertIsNone(code)
                self.assertEqual(report["status"],"INCOMPLETE")

    def test_baseline_not_modifiable_without_unique_markers(self):
        with self.assertRaises(ValueError):
            source_region(ORIGINAL.replace(START,""))
        with self.assertRaises(ValueError):
            source_region(ORIGINAL+END)

if __name__=="__main__":
    unittest.main()
