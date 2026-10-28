"""Verify targeted Qwen-only game repair orchestration; no native model needed."""
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
from repair_luna_original_targeted import TASKS, region, sanitize_model_piece, generate_patches

BASE="""const canvas=document.getElementById('game'); let player={x:1,y:2}, enemies=[], wave=0, mode='game';
const e={key:'Space',code:'Space'}; const a=e.key === 'Space'; const b=e.key === 'KeyZ';
function gameLoop(){
    // Attack
    if (isAttacking){if(attackTarget){attackTarget.hp-=10;enemies.splice(i,1)}}
    // Enemy movement
    enemies.forEach(e=>e.x++);
    // Check for victory
    if (enemies.length === 0 && wave < 2){wave++;}
    // Check for defeat
    if (player.hp<=0)mode='defeat';
    // Check for victory
    if (enemies.length === 0 && wave === 2){mode='victory';return;}
    // Update status
}
"""
RESPONSES=[
    "e.code === 'Space'",
    "e.code === 'KeyZ'",
    "if(isAttacking && attackTarget){attackTimer--;if(attackTimer<=0){attackTarget.hp-=10;if(attackTarget.hp<=0)enemies=enemies.filter(e=>e!==attackTarget);isAttacking=false;}}",
    "if(enemies.length===0&&wave<3){wave++;if(wave===3){enemies.push({x:400,y:420,hp:200,boss:true});}else{enemies.push({x:180,y:420,hp:30,boss:false});}}",
    "if(wave===3&&enemies.length===0){mode='victory';status.textContent='VITÓRIA';return;}"
]


class LunaTargetRepairTests(unittest.TestCase):
    def test_extracts_each_region_without_editing_reference(self):
        original=BASE
        for task in TASKS[:3]:
            before,mid,after=region(original,task)
            self.assertEqual(before+mid+after,original)
        self.assertEqual(region(BASE,TASKS[3])[1].count("wave < 2"),1)

    def test_rejects_replacement_that_is_not_model_supplied_and_unsafe(self):
        for task,raw in [(TASKS[0],"e.key === 'Space'"),
                         (TASKS[2],"fetch('https://example.com')"),
                         (TASKS[3],"mode='victory'; enemies.push({boss:true})")]:
            ok,_,_=sanitize_model_piece(raw,task)
            self.assertFalse(ok)

    def test_all_five_patches_model_generated_and_provenance_kept(self):
        queue=list(RESPONSES)
        seen=[]
        def infer(prompt,tokens):
            seen.append((prompt,tokens))
            return {"answer":queue.pop(0),"model_generated":True}
        report,game=generate_patches(BASE,infer,attempts=1,checker=lambda _:True)
        self.assertEqual(report["status"],"STATIC_PATCHED_CANDIDATE")
        self.assertEqual(report["patches_accepted"],5)
        self.assertEqual(len(seen),5)
        self.assertFalse(report["assistant_gameplay_code_used"])
        self.assertIn("wave===3",game)
        self.assertIn("e.code === 'Space'",game)
        self.assertNotIn("splice(i,1)",game)
        self.assertIn("VITÓRIA",game)

    def test_fake_inference_rejected_with_no_complete_game(self):
        report,game=generate_patches(BASE,lambda *_:{"answer":RESPONSES[0],"model_generated":False},
                                     attempts=1,checker=lambda _:True)
        self.assertIsNone(game)
        self.assertEqual(report["status"],"INCOMPLETE")
        self.assertEqual(report["patches_accepted"],0)

    def test_syntax_failure_returns_incomplete(self):
        report,game=generate_patches(BASE,lambda *_:{"answer":RESPONSES[0],"model_generated":True},
                                     attempts=1,checker=lambda _:False)
        self.assertIsNone(game)
        self.assertEqual(report["tasks"][0]["attempts"][0]["reason"],"javascript_syntax_error")


if __name__=="__main__":
    unittest.main()
