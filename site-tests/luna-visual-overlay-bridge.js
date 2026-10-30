/* Integration UI only: renders authentic Luna visual.js over unchanged Qwen gameplay. */
(() => {
  const base = document.getElementById('game');
  if (!base) return;
  const wrap = document.createElement('div');
  wrap.id = 'luna-visual-stage';
  wrap.style.cssText = 'position:relative;width:100%;max-width:960px;line-height:0;';
  base.parentNode.insertBefore(wrap, base);
  wrap.appendChild(base);
  base.style.display = 'block';
  const overlay = document.createElement('canvas');
  overlay.id = 'luna-skin-overlay';
  overlay.width = base.width;
  overlay.height = base.height;
  overlay.setAttribute('aria-hidden', 'true');
  overlay.style.cssText = 'position:absolute;top:0;left:0;width:100%;height:100%;pointer-events:none;max-width:none;border:0;box-shadow:none;background:transparent;';
  wrap.appendChild(overlay);
  const ctx = overlay.getContext('2d');
  let frames = 0;
  function paint(time) {
    if (overlay.dataset.visualStatus !== 'error') {
      try {
        const snap = window.__LUNA_ORIGINAL_QA__?.snapshot?.();
        const skin = window.LunaSkin;
        if (snap && skin && typeof skin.draw === 'function') {
          skin.draw(ctx, { ...snap, hero: document.getElementById('hero')?.value || 'melee' }, time);
          frames++;
          overlay.dataset.frames = String(frames);
          overlay.dataset.visualStatus = 'rendering';
        }
      } catch (error) {
        overlay.dataset.visualStatus = 'error';
        overlay.style.display = 'none';
        console.error('Luna visual skin failed:', error);
      }
    }
    requestAnimationFrame(paint);
  }
  requestAnimationFrame(paint);
})();
