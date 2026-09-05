from __future__ import annotations

import json
import os
import random
from collections import defaultdict
from pathlib import Path

TAXONOMY = {
    "programming": {
        "python.json": ["python", "json", "dados", "dicionario", "parse"],
        "python.files": ["python", "arquivo", "abrir", "ler", "pathlib"],
        "python.sqlite": ["python", "sqlite", "banco", "sql", "salvar"],
        "python.asyncio": ["python", "asyncio", "async", "await", "concorrencia"],
        "rust": ["rust", "cargo", "ownership", "borrow", "trait"],
        "cpp": ["cpp", "c++", "template", "ponteiro", "compilador"],
        "javascript": ["javascript", "js", "node", "promise", "browser"],
    },
    "math": {
        "algebra": ["algebra", "equacao", "matriz", "vetor"],
        "calculus": ["calculo", "derivada", "integral", "limite"],
        "statistics": ["estatistica", "media", "probabilidade", "distribuicao"],
        "geometry": ["geometria", "angulo", "triangulo", "area"],
    },
    "linux": {
        "files": ["linux", "arquivo", "permissao", "chmod", "diretorio"],
        "processes": ["linux", "processo", "systemd", "ps", "kill"],
        "networking": ["linux", "rede", "ip", "socket", "servidor"],
        "packages": ["linux", "pacote", "apt", "dnf", "instalar"],
    },
    "storage": {
        "mmap": ["storage", "mmap", "memoria", "pagina", "mapear"],
        "filesystems": ["filesystem", "ext4", "arquivo", "inode", "disco"],
        "nvme": ["ssd", "nvme", "armazenamento", "latencia", "io"],
        "checksums": ["checksum", "sha256", "integridade", "corrupcao"],
    },
    "networking": {
        "http": ["http", "api", "request", "response", "web"],
        "dns": ["dns", "dominio", "resolver", "nome"],
        "tcp": ["tcp", "conexao", "porta", "pacote"],
        "routing": ["roteamento", "router", "gateway", "rota", "rede"],
    },
    "3d_printing": {
        "filament": ["filamento", "pla", "petg", "temperatura"],
        "calibration": ["calibracao", "impressora", "mesa", "nivelamento"],
        "slicer": ["slicer", "fatiador", "gcode", "camada"],
        "printer": ["impressora", "bambu", "extrusor", "hotend"],
    },
    "biology": {
        "genetics": ["genetica", "dna", "gene", "heranca"],
        "ecology": ["ecologia", "especie", "habitat", "ambiente"],
        "cells": ["celula", "membrana", "mitocondria", "proteina"],
        "evolution": ["evolucao", "selecao", "organismo", "adaptacao"],
    },
    "history": {
        "ancient": ["historia", "antiga", "roma", "egito"],
        "medieval": ["medieval", "feudal", "castelo", "idade"],
        "modern": ["historia", "moderna", "revolucao", "guerra"],
        "industrial": ["industrial", "maquina", "fabrica", "vapor"],
    },
    "general_language": {
        "grammar": ["gramatica", "frase", "verbo", "texto"],
        "translation": ["traducao", "idioma", "portugues", "ingles"],
        "writing": ["escrever", "texto", "paragrafo", "revisar"],
        "summary": ["resumo", "resumir", "sintese", "texto"],
    },
}


def _atomic_json(path: Path, payload: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n")
    os.replace(temporary, path)


def generate_semantic_manifest(path: Path, page_count: int = 1024, seed: int = 20260807) -> dict:
    topics = [(domain, topic, keywords) for domain, domain_topics in TAXONOMY.items() for topic, keywords in domain_topics.items()]
    assignments: dict[tuple[str, str], list[int]] = defaultdict(list)
    for page_id in range(page_count):
        domain, topic, _ = topics[page_id % len(topics)]
        assignments[(domain, topic)].append(page_id)
    domains = list(TAXONOMY)
    pages = []
    for page_id in range(page_count):
        domain, topic, keywords = topics[page_id % len(topics)]
        peers = assignments[(domain, topic)]
        position = peers.index(page_id)
        related = [peers[(position + offset) % len(peers)] for offset in (1, 2, -1)]
        rng = random.Random(seed ^ page_id)
        inhibited = rng.sample([item for item in domains if item != domain], 2)
        pages.append({
            "page_id": page_id, "domain": domain, "topics": [topic],
            "keywords": sorted(set([domain, *topic.split("."), *keywords])),
            "related_pages": related, "inhibitory_tags": inhibited,
            "importance": round(0.5 + (page_id % 11) / 20, 3),
        })
    payload = {"schema_version": 1, "seed": seed, "page_count": page_count, "page_size_bytes": 1024**2, "taxonomy": TAXONOMY, "pages": pages}
    path.parent.mkdir(parents=True, exist_ok=True)
    _atomic_json(path, payload)
    return payload


def _truth(manifest: dict, topic_names: list[str]) -> tuple[list[int], list[int]]:
    matches = [page["page_id"] for page in manifest["pages"] if page["topics"][0] in topic_names]
    by_topic = defaultdict(list)
    for page in manifest["pages"]:
        if page["topics"][0] in topic_names:
            by_topic[page["topics"][0]].append(page["page_id"])
    required, optional = [], []
    for topic in topic_names:
        required.extend(by_topic[topic][:2])
        optional.extend(by_topic[topic][2:5])
    return required, optional


def generate_query_dataset(path: Path, manifest: dict, seed: int = 20260807) -> dict:
    specs = [
        ("easy_json", "easy_single_topic", "como abrir json em python", "programming", ["python.json"], None, 0),
        ("easy_mmap", "easy_single_topic", "como mapear arquivo com mmap", "storage", ["mmap"], None, 0),
        ("easy_dns", "easy_single_topic", "como resolver um nome dns", "networking", ["dns"], None, 0),
        ("easy_genetics", "easy_single_topic", "o que é herança genética e dna", "biology", ["genetics"], None, 0),
        ("multi_json_sqlite", "multi_topic", "ler json e salvar os dados em sqlite usando python", "programming", ["python.json", "python.sqlite"], None, 0),
        ("multi_linux_net", "multi_topic", "diagnosticar processo e rede no servidor linux", "linux", ["processes", "networking"], None, 0),
        ("ambiguous_file", "ambiguous", "como abrir o arquivo", "programming", ["python.files"], None, 0),
        ("ambiguous_port", "ambiguous", "a porta não abre", "networking", ["tcp"], None, 0),
        ("distractor_python_bio", "distractor", "em python modele uma célula sem explicar biologia", "programming", ["python.files"], None, 0),
        ("distractor_linux_history", "distractor", "no linux arquive documentos de história", "linux", ["files"], None, 0),
        ("unknown_quantum", "unknown", "configure um computador quântico topológico", None, [], None, 0),
        ("unknown_music", "unknown", "harmonia modal para saxofone", None, [], None, 0),
    ]
    # Continuation: explicit start followed by partial cues.
    specs += [
        ("cont_py_1", "topic_continuation", "estou trabalhando com json em python", "programming", ["python.json"], "cont_py", 1),
        ("cont_py_2", "topic_continuation", "e para abrir o arquivo", "programming", ["python.files"], "cont_py", 2),
        ("cont_py_3", "partial_cue", "e salvar no banco", "programming", ["python.sqlite"], "cont_py", 3),
        ("cont_py_4", "partial_cue", "e fazer isso de forma assíncrona", "programming", ["python.asyncio"], "cont_py", 4),
    ]
    # Canonical A A A A -> B B B -> A A switch.
    switch_queries = [
        ("sw_1", "json em python", "programming", ["python.json"]),
        ("sw_2", "abrir os arquivos", "programming", ["python.files"]),
        ("sw_3", "salvar com sqlite", "programming", ["python.sqlite"]),
        ("sw_4", "usar asyncio também", "programming", ["python.asyncio"]),
        ("sw_5", "agora processos no linux", "linux", ["processes"]),
        ("sw_6", "pacotes apt no servidor", "linux", ["packages"]),
        ("sw_7", "permissões de arquivo linux", "linux", ["files"]),
        ("sw_8", "voltando ao json", "programming", ["python.json"]),
        ("sw_9", "e ao sqlite em python", "programming", ["python.sqlite"]),
    ]
    specs += [(qid, "topic_switch" if turn in (1, 5, 8) else "partial_cue", query, domain, topics, "switch", turn) for turn, (qid, query, domain, topics) in enumerate(switch_queries, 1)]
    queries = []
    for query_id, category, text, domain, topics, sequence_id, turn in specs:
        required, optional = _truth(manifest, topics) if topics else ([], [])
        queries.append({
            "query_id": query_id, "category": category, "query": text,
            "expected_domain": domain, "expected_topics": topics,
            "required_pages": required, "optional_pages": optional,
            "sequence_id": sequence_id, "turn_index": turn,
        })
    payload = {"schema_version": 1, "seed": seed, "queries": queries}
    path.parent.mkdir(parents=True, exist_ok=True)
    _atomic_json(path, payload)
    return payload

