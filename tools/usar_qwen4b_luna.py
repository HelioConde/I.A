#!/usr/bin/env python3
"""Install and select the pinned official Qwen3-4B Q8_0 for local Luna.

Does not fetch weights unless --install-activate is explicitly requested.
Never replaces a GGUF; preserves user LUNA.ini comments, paths and permissions.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from launch_luna import ensure_config, read_config, INI
from test_luna_models import (
    CANDIDATE, CANDIDATE_SHA256, BASELINE, MIN_4B,
    local_model_status, download_candidate, sha256_file,
)
from doctor_chat import inspect_installation

def verified_4b(models: Path) -> tuple[bool, str]:
    target = models / CANDIDATE
    if target.is_symlink() or not target.is_file():
        return False, "O Qwen3-4B Q8_0 ainda nao esta instalado."
    status = local_model_status(models)[CANDIDATE]
    if not status["header_gguf"] or status["bytes"] < MIN_4B:
        return False, "GGUF 4B incompleto ou com assinatura invalida. Nenhum arquivo sera sobrescrito."
    if sha256_file(target).lower() != CANDIDATE_SHA256:
        return False, "SHA-256 do GGUF 4B nao corresponde ao download oficial fixado."
    return True, "Qwen3-4B Q8_0 verificado por tamanho, assinatura GGUF e SHA-256."

def select_ini_model(path: Path, *, large: bool) -> None:
    """Atomic, targeted edits in [luna]; preserve unrelated permissions/comments."""
    if not path.is_file() or path.is_symlink():
        raise ValueError("LUNA.ini precisa ser um arquivo local comum.")
    original = path.read_bytes()
    bom = original.startswith(b"\xef\xbb\xbf")
    content = original.decode("utf-8-sig")
    newline = "\r\n" if "\r\n" in content else "\n"
    lines = content.splitlines(keepends=True)
    edits = {
        "model_file": CANDIDATE if large else "",
        "profile": "equilibrado" if large else "economia",
        "core_mode": "auto" if large else "",
    }
    inside = False
    found_section = False
    found: set[str] = set()
    output: list[str] = []
    def missing_entries() -> None:
        for key, value in edits.items():
            if key not in found:
                output.append(f"{key} = {value}" + newline)
                found.add(key)
    for line in lines:
        stripped = line.strip()
        section = re.fullmatch(r"\[([^\]]+)\]", stripped)
        if section:
            if inside:
                missing_entries()
            inside = section.group(1).casefold() == "luna"
            found_section = found_section or inside
            output.append(line)
            continue
        if inside and not stripped.startswith((";", "#")):
            match = re.match(r"^(\s*)([A-Za-z_]+)(\s*=).*?(\r?\n)?$", line)
            if match and match.group(2).casefold() in edits:
                key = match.group(2).casefold()
                if key in found:
                    raise ValueError(f"Opcao duplicada [{key}] em LUNA.ini; ajuste manualmente.")
                found.add(key)
                output.append(match.group(1) + match.group(2) + match.group(3)
                              + " " + edits[key] + (match.group(4) or ""))
                continue
        output.append(line)
    if not found_section:
        raise ValueError("Secao [luna] nao encontrada; nao alterei o INI.")
    if inside:
        missing_entries()
    updated = ("\ufeff" if bom else "") + "".join(output)
    if updated.encode("utf-8") == original:
        return
    fd, tempname = tempfile.mkstemp(prefix=".luna-model-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(updated.encode("utf-8"))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tempname, path)
    finally:
        try:
            Path(tempname).unlink(missing_ok=True)
        except OSError:
            pass

def install_activate(config_path: Path, *, download: bool, models: Path = ROOT / "models") -> None:
    ensure_config(config_path)
    # Verify the local options, including authorized roots, before downloading.
    read_config(config_path)
    candidate = models / CANDIDATE
    if not candidate.exists() and not candidate.is_symlink():
        if not download:
            raise ValueError("Modelo 4B ausente. Use --install-activate para baixar e ativar.")
        download_candidate(models)
    valid, message = verified_4b(models)
    if not valid:
        raise ValueError(message)
    print(message, flush=True)
    # Preflight tests native CPU runtime and selected GGUF without generating tokens.
    readiness = inspect_installation(ROOT, profile="equilibrado", probe=True, model_file=CANDIDATE)
    if not readiness["ready_for_test"]:
        raise ValueError("Runtime CPU nao pronto para o Qwen3-4B: " +
                         "; ".join(readiness.get("recommendations", []))[:350])
    select_ini_model(config_path, large=True)
    selected = read_config(config_path)
    if selected.model_file != CANDIDATE or selected.profile != "equilibrado":
        raise ValueError("Configuracao local nao foi aplicada corretamente.")
    print("LUNA.ini atualizado: Qwen3-4B Q8_0, perfil equilibrado, core auto.", flush=True)
    print("O Qwen3-0.6B anterior foi preservado. Encerre a Luna antiga e inicie novamente.", flush=True)

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--install-activate", action="store_true", help="Baixar ~4,28 GB se faltar e ativar 4B")
    action.add_argument("--activate", action="store_true", help="Ativar o 4B oficial ja instalado")
    action.add_argument("--restore-06b", action="store_true", help="Voltar para Qwen3 0.6B, sem apagar nenhum GGUF")
    action.add_argument("--status", action="store_true", help="Verificar arquivos locais sem baixar nada")
    parser.add_argument("--config", type=Path, default=INI)
                        help="INI local alternativo para testes (padrao: LUNA.ini)")
    args = parser.parse_args(argv)
    try:
        cfg = args.config.expanduser().resolve()
        if args.restore_06b:
            ensure_config(cfg)
            read_config(cfg)
            select_ini_model(cfg, large=False)
            print("Luna voltou ao Qwen3-0.6B padrao. Reinicie a Luna; nenhum GGUF foi removido.")
        elif args.install_activate or args.activate:
            install_activate(cfg, download=args.install_activate)
        else:
            if cfg.exists():
                current = read_config(cfg).model_file or BASELINE
            else:
                current = BASELINE
            installed = local_model_status(ROOT / "models")
            print("Modelo ativo no LUNA.ini: " + current)
            for key, val in installed.items():
                print(f"- {key}: " + ("presente" if val["present"] else "ausente") +
                      f", tamanho={val['bytes']} bytes (integridade so no --activate)")
            print("Nenhum download nem alteracao de configuracao executados.")
        return 0
    except (OSError, ValueError, RuntimeError) as exc:
        print("Nao foi possivel configurar o modelo da Luna: " + str(exc), file=sys.stderr)
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
