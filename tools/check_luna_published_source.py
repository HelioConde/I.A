#!/usr/bin/env python3
"""Fail closed unless the published game is exactly the independently authored Qwen files.

The manifest is provenance metadata authored by the integration system; the game
HTML/CSS/JS bytes must be identical to the model-generated artifacts.
"""
from __future__ import annotations
from hashlib import sha256
import json
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]
GAME=ROOT/"site"/"luna-created"
EXPECTED=("index.html","styles.css","game.js")
BANNED_SOURCE=re.compile(r"\b(?:fetch|eval|Function|WebSocket|XMLHttpRequest|Worker|importScripts)\s*\("
                         r"|\brequire\s*\(|\bimport\s*\(|\b(?:localStorage|indexedDB)\b|https?://",re.I)

def validate() -> dict:
    manifest_path=GAME/"provenance.json"
    if not manifest_path.is_file():
        raise ValueError("missing_provenance")
    manifest=json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("model")!="Qwen3-4B-Q4_K_M.gguf":
        raise ValueError("unverified_model_identity")
    if manifest.get("game_code_author")!="Luna Qwen3-4B" or manifest.get("assistant_gameplay_code_used") is not False:
        raise ValueError("misattributed_game_code")
    if manifest.get("source_original_run")!=40636116071:
        raise ValueError("missing_original_game_generation_evidence")
    if not isinstance(manifest.get("source_runs"),list) or len(manifest["source_runs"])<3:
        raise ValueError("incomplete_source_provenance")
    for name in EXPECTED:
        item=manifest.get("files",{}).get(name,{})
        if not isinstance(item.get("source_run"),int) or item["source_run"]<1:
            raise ValueError("no_model_source_run:"+name)
        raw=(GAME/name).read_bytes()
        if sha256(raw).hexdigest()!=item.get("sha256"):
            raise ValueError("unverified_qwen_source_bytes:"+name)
        if BANNED_SOURCE.search(raw.decode("utf-8")):
            raise ValueError("network_or_dynamic_code:"+name)
    html=(GAME/"index.html").read_text(encoding="utf-8")
    if re.search(r"<script[^>]*\bsrc\s*=\s*['\"]https?://",html,re.I):
        raise ValueError("external_script")
    for ref in ('id="game"','id="start"','id="hero"','id="status"'):
        if ref not in html:
            raise ValueError("missing_original_game_interface:"+ref)
    print("PASS: Qwen-only HTML CSS JS source provenance, SHA-256 and no network runtime")
    return manifest

if __name__=="__main__":
    validate()
