#!/usr/bin/env python3
"""Run Luna from persistent, user-editable private LUNA.ini (no shell eval).

First run copies LUNA.exemplo.ini into LUNA.ini (excluded from Git). All
permissions are still enforced by the Copilot backend; each sensitive
operation retains its individual UI confirmation.
"""
from __future__ import annotations

import argparse
import configparser
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INI = ROOT / "LUNA.ini"
EXAMPLE = ROOT / "LUNA.exemplo.ini"
VALID_PROFILES = {"economia", "equilibrado", "rapido"}
VALID_CORE_MODES = {"", "subprocess", "persistent", "auto"}
VALID_PROVIDERS = {"auto", "wikipedia", "google", "brave", "searxng"}


@dataclass(frozen=True)
class LunaConfig:
    profile: str
    core_mode: str
    model_file: str
    port: int
    open_browser: bool
    episodic_memory: bool
    cognitive_shadow: bool
    memory_aliases: bool
    web_search: bool
    web_provider: str
    roots: tuple[Path, ...]
    screen: bool
    apps: bool
    launch: bool
    edit: bool
    godot_validate: bool
    godot_path: str


def ensure_config(path: Path, example: Path = EXAMPLE) -> bool:
    """Copy defaults once. No overwrite of existing local user choices."""
    if path.is_file():
        return False
    if path.exists():
        raise ValueError("LUNA.ini deve ser arquivo, nao uma pasta.")
    if not example.is_file():
        raise FileNotFoundError("Modelo LUNA.exemplo.ini nao encontrado.")
    # x mode protects independently edited configuration on concurrent starts.
    try:
        with path.open("x", encoding="utf-8") as target:
            target.write(example.read_text(encoding="utf-8-sig"))
    except FileExistsError:
        return False
    return True


def read_config(path: Path) -> LunaConfig:
    parser = configparser.ConfigParser(interpolation=None, inline_comment_prefixes=None)
    with path.open("r", encoding="utf-8-sig") as source:
        parser.read_file(source)
    if not parser.has_section("luna") or not parser.has_section("copilot"):
        raise ValueError("LUNA.ini exige as secoes [luna] e [copilot].")
    def option(section: str, name: str) -> str:
        if not parser.has_option(section, name):
            raise ValueError(f"Falta opcao [{section}] {name} em LUNA.ini.")
        return parser.get(section, name).strip()
    def flag(section: str, name: str) -> bool:
        try:
            return parser.getboolean(section, name)
        except (ValueError, configparser.NoOptionError) as exc:
            raise ValueError(f"Use true/false em [{section}] {name}.") from exc

    profile = option("luna", "profile")
    core_mode = option("luna", "core_mode")
    provider = option("luna", "web_provider")
    if profile not in VALID_PROFILES or core_mode not in VALID_CORE_MODES:
        raise ValueError("Perfil ou modo de Core invalido em [luna].")
    if provider not in VALID_PROVIDERS:
        raise ValueError("Provedor de pesquisa invalido em [luna].")
    try:
        port = int(option("luna", "port"))
    except ValueError as exc:
        raise ValueError("[luna] port deve ser inteiro entre 1 e 65535.") from exc
    if not 1 <= port <= 65535:
        raise ValueError("[luna] port deve estar entre 1 e 65535.")

    paths = [option("copilot", "root")]
    paths.extend(option("copilot", "extra_roots").split(";"))
    roots = []
    for raw in paths:
        raw = raw.strip()
        if not raw:
            continue
        # No environment-variable substitution or shell parsing of paths.
        candidate = Path(raw).expanduser()
        if not candidate.is_dir():
            raise ValueError("Pasta autorizada nao existe: " + raw)
        resolved = candidate.resolve(strict=True)
        if resolved not in roots:
            roots.append(resolved)

    model_file = option("luna", "model_file")
    if model_file and (Path(model_file).name != model_file or
                       not model_file.casefold().endswith(".gguf")):
        raise ValueError("[luna] model_file deve ser apenas o nome de um GGUF.")
    episodic = flag("luna", "episodic_memory")
    aliases = flag("luna", "memory_aliases")
    if aliases and not episodic:
        raise ValueError("memory_aliases exige episodic_memory = true.")
    edit = flag("copilot", "edit")
    validate = flag("copilot", "godot_validate")
    if (edit or validate) and not roots:
        raise ValueError("Edicao/validacao Godot exigem ao menos uma raiz autorizada.")
    return LunaConfig(
        profile=profile, core_mode=core_mode, model_file=model_file,
        port=port, open_browser=flag("luna", "open_browser"),
        episodic_memory=episodic,
        cognitive_shadow=flag("luna", "cognitive_shadow"),
        memory_aliases=aliases, web_search=flag("luna", "web_search"),
        web_provider=provider, roots=tuple(roots),
        screen=flag("copilot", "screen"), apps=flag("copilot", "apps"),
        launch=flag("copilot", "launch"), edit=edit, godot_validate=validate,
        godot_path=option("copilot", "godot_path"),
    )


def resolve_godot(path_text: str) -> tuple[Path | None, str]:
    """Only explicit executable or small non-recursive directory search."""
    if not path_text:
        return None, "Caminho do Godot vazio; validacao opcional desligada."
    candidate = Path(path_text).expanduser()
    if candidate.is_file():
        possibilities = [candidate]
    elif candidate.is_dir():
        possibilities = sorted(
            (p for parent in (candidate, candidate / "bin")
             if parent.is_dir() for p in parent.glob("*.exe")
             if "godot" in p.stem.casefold()),
            key=lambda p: p.name.casefold(),
        )
    else:
        return None, "Godot nao encontrado em " + path_text + "; validacao desligada."
    good = [p for p in possibilities if not p.is_symlink() and
            p.suffix.casefold() == ".exe" and "godot" in p.stem.casefold()]
    if not good:
        return None, "Nenhum executavel Godot*.exe encontrado em " + path_text + "; validacao desligada."
    if len(good) > 1:
        return None, "Multiplos executaveis Godot encontrados; informe o caminho completo de um .exe."
    return good[0].resolve(strict=True), ""


def build_chat_args(config: LunaConfig) -> tuple[list[str], list[str]]:
    args = [sys.executable, str(ROOT / "tools" / "run_chat.py"),
            "--profile", config.profile, "--port", str(config.port)]
    messages = []
    if config.core_mode:
        args.extend(("--core-mode", config.core_mode))
    if config.model_file:
        args.extend(("--model-file", config.model_file))
    if not config.open_browser:
        args.append("--no-open-browser")
    for name, enabled in (
        ("episodic-memory", config.episodic_memory),
        ("cognitive-shadow", config.cognitive_shadow),
        ("memory-aliases", config.memory_aliases),
        ("web-search", config.web_search),
    ):
        if enabled:
            args.append("--" + name)
    if config.web_search:
        args.extend(("--web-provider", config.web_provider))
    for root in config.roots:
        args.extend(("--copilot-root", str(root)))
    for name, enabled in (
        ("screen", config.screen), ("apps", config.apps),
        ("launch", config.launch), ("edit", config.edit),
    ):
        if enabled:
            args.append("--copilot-" + name)
    if config.godot_validate:
        godot, warning = resolve_godot(config.godot_path)
        if godot:
            args.extend(("--copilot-godot-bin", str(godot)))
        elif warning:
            messages.append("AVISO: " + warning)
    if config.roots:
        for root in config.roots:
            if root == Path(root.anchor):
                messages.append(
                    "ATENCAO: voce autorizou a unidade inteira " + str(root) +
                    ". Prefira uma pasta especifica se nao precisar do disco todo."
                )
    return args, messages


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=INI)
    operation = parser.add_mutually_exclusive_group()
    operation.add_argument("--check", action="store_true", help="Validar INI sem iniciar o modelo")
    operation.add_argument("--init-only", action="store_true", help="Criar INI e sair")
    operation.add_argument("--run", action="store_true", help="Verificar Qwen e iniciar Luna")
    args = parser.parse_args(argv)
    try:
        cfg_path = args.config.expanduser().resolve()
        if ensure_config(cfg_path):
            print(f"Configuracao local criada: {cfg_path}")
        else:
            print(f"Configuracao local existente: {cfg_path}")
        if args.init_only:
            return 0
        config = read_config(cfg_path)
        command, warnings = build_chat_args(config)
        for warning in warnings:
            print(warning, flush=True)
        print("Configuracao: " + config.profile + " | " +
              f"{len(config.roots)} raiz(es) | " +
              ("Godot opcional" if config.godot_validate else "Godot desligado") +
              " | web opt-in por pergunta", flush=True)
        if args.check:
            print("LUNA.ini valido. Nenhum programa foi iniciado.")
            return 0
        if not args.run:
            parser.error("Escolha --run ou --check.")
        doctor_command = [
            sys.executable, str(ROOT / "tools" / "doctor_chat.py"),
            "--profile", config.profile, "--probe",
        ]
        # Diagnose the ACTUALLY selected GGUF, not the fallback 0.6B.
        if config.model_file:
            doctor_command.extend(("--model-file", config.model_file))
        preflight = subprocess.run(
            doctor_command, cwd=ROOT, check=False, shell=False,
        )
        if preflight.returncode:
            print("Qwen nao pronto; execute o instalador INICIAR-BRAIN-SSD.bat.", file=sys.stderr)
            return 3
        print("Iniciando Luna (Qwen local; pesquisa externa opt-in).", flush=True)
        return subprocess.call(command, cwd=ROOT, shell=False)
    except (OSError, ValueError, configparser.Error) as exc:
        print("ERRO LUNA.ini: " + str(exc), file=sys.stderr)
        print("Edite LUNA.ini ou restaure as opcoes a partir de LUNA.exemplo.ini.",
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
