"""Captura passiva; sem cliques, compras, senhas, interceptação ou bots."""
import argparse
import time
from datetime import datetime, timezone
from pathlib import Path

URLS = {
    "world": "https://poke.idleworld.online/",  # só landing pública, sem login
    "io": "https://pokeidle.io/",                # interação exclusivamente manual
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--game", required=True, choices=URLS)
    parser.add_argument("--seconds", type=int, default=30)
    parser.add_argument("--interval", type=int, default=10)
    parser.add_argument("--out", type=Path, default=Path("captures"))
    args = parser.parse_args()
    if not 1 <= args.seconds <= 300 or not 2 <= args.interval <= 60:
        parser.error("seconds 1..300; interval 2..60")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        parser.error("Instale Playwright e Chromium (veja README)")
    args.out.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        if args.game == "world":
            browser = p.chromium.launch(headless=True)
            ctx = browser.new_context(viewport={"width": 1280, "height": 900})
        else:
            # Perfil local do IO; login humano na janela, se desejado.
            ctx = p.chromium.launch_persistent_context(
                user_data_dir=str(Path(".local-io-profile").resolve()),
                headless=False, viewport={"width": 1280, "height": 900})
        try:
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            page.goto(URLS[args.game], wait_until="domcontentloaded", timeout=30000)
            elapsed, i = 0, 0
            while elapsed < args.seconds:
                date = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
                path = args.out / "{}-{}-{:03d}.png".format(args.game, date, i)
                page.screenshot(path=str(path), full_page=False)
                print("Captura local:", path)
                i += 1
                pause = min(args.interval, args.seconds - elapsed)
                time.sleep(pause)
                elapsed += pause
        finally:
            ctx.close()


if __name__ == "__main__":
    main()
