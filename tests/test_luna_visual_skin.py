"""Original visual-skin module contract: no external resources or fake authorship."""
from pathlib import Path
import sys
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
from generate_luna_visual_skin import clean_skin

GOOD="""window.LunaSkin = {
  draw(ctx, state, time) {
    ctx.fillStyle = '#14263a';
    ctx.fillRect(0, 0, 960, 540);
    ctx.fillStyle = '#f7d080';
    ctx.beginPath();
    ctx.arc(state.player.x, state.player.y, 22 + Math.sin(time/250), 0, 2 * Math.PI);
    ctx.fill();
    ctx.fillStyle = '#fff';
    ctx.fillRect(0, 440, 960, 100);
  }
};"""

def test_accept_original_canvas_renderer():
    assert clean_skin(GOOD).strip()==GOOD

def test_strip_markdown_fence():
    assert clean_skin("```javascript\n"+GOOD+"\n```").strip()==GOOD

@pytest.mark.parametrize("source",[
    GOOD+"\nfetch('/secret')",
    GOOD+"\ndocument.body.innerHTML='unsafe'",
    GOOD.replace("window.LunaSkin","window.OtherSkin"),
    GOOD.replace("draw(ctx, state, time)","draw(ctx)"),
])
def test_reject_unsafe_or_wrong_contract(source):
    with pytest.raises(ValueError):clean_skin(source)
