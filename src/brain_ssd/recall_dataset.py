from __future__ import annotations

import json
import os
from collections import defaultdict
from pathlib import Path


def _truth(manifest: dict, topics: list[str]) -> tuple[list[int], list[int], dict[str, list[int]]]:
    grouped: dict[str, list[int]] = defaultdict(list)
    for page in manifest["pages"]:
        topic = page["topics"][0]
        if topic in topics:
            grouped[topic].append(page["page_id"])
    required, optional, causes = [], [], {}
    for topic in topics:
        required.extend(grouped[topic][:2])
        optional.extend(grouped[topic][2:5])
        causes[topic] = grouped[topic][:2]
    return required, optional, causes


def generate_recall_dataset(path: Path, manifest: dict, seed: int = 20260807) -> dict:
    # Development examples calibrate transparent thresholds; holdout phrasings are disjoint.
    specs = [
        ("dev_json", "development", "single_topic", "abrir json usando python", ["python.json"], None, 0),
        ("dev_sqlite", "development", "single_topic", "salvar dados no sqlite com python", ["python.sqlite"], None, 0),
        ("dev_multi", "development", "multi_domain", "inspecionar processos e rede no linux", ["processes", "networking"], None, 0),
        ("dev_unknown", "development", "unknown", "orquestração para música barroca", [], None, 0),
        ("dev_typo", "development", "noise_typo", "pyhton json abrir!!!", ["python.json"], None, 0),
        ("h_json", "holdout", "single_topic", "decodificar um documento JSON no Python", ["python.json"], None, 0),
        ("h_files", "holdout", "single_topic", "carregar conteúdo de um caminho com pathlib", ["python.files"], None, 0),
        ("h_sql", "holdout", "single_topic", "persistir registros numa base SQLite", ["python.sqlite"], None, 0),
        ("h_async", "holdout", "paraphrase", "executar a tarefa sem bloquear", ["python.asyncio"], None, 0),
        ("h_async2", "holdout", "paraphrase", "fazer isso concorrentemente usando Python", ["python.asyncio"], None, 0),
        ("h_linux_net", "holdout", "multi_domain", "ver processos e conectividade do servidor", ["processes", "networking"], None, 0),
        ("h_storage_net", "holdout", "multi_domain", "expor dados do NVMe através de uma API HTTP", ["nvme", "http"], None, 0),
        ("h_checksum", "holdout", "single_topic", "detectar corrupção validando o hash", ["checksums"], None, 0),
        ("h_typo", "holdout", "noise_typo", "PYHTON, abriir o JsOn por favor", ["python.json"], None, 0),
        ("h_noise", "holdout", "noise_typo", "por favor talvez DNS resolver nome??? obrigado", ["dns"], None, 0),
        ("h_distractor", "holdout", "distractor", "abrir script Python sobre genes sem explicar genética", ["python.files"], None, 0),
        ("h_ambiguous", "holdout", "ambiguous", "como carregar isso", ["python.files"], None, 0),
        ("h_unknown1", "holdout", "unknown", "harmonia quartal para saxofone", [], None, 0),
        ("h_unknown2", "holdout", "unknown", "receita de pão com fermentação longa", [], None, 0),
        ("mt1", "holdout", "multi_turn", "trabalhando com arquivos em Python", ["python.files"], "python_flow", 1),
        ("mt2", "holdout", "multi_turn", "agora os dados são JSON", ["python.json"], "python_flow", 2),
        ("mt3", "holdout", "partial_cue", "e executar sem bloquear?", ["python.asyncio"], "python_flow", 3),
        ("mt4", "holdout", "partial_cue", "depois persistir no banco", ["python.sqlite"], "python_flow", 4),
        ("sw1", "holdout", "topic_switch", "usar JSON em Python", ["python.json"], "switch", 1),
        ("sw2", "holdout", "topic_switch", "agora explique DNA e herança genética", ["genetics"], "switch", 2),
        ("sw3", "holdout", "partial_cue", "voltando, salvar no SQLite", ["python.sqlite"], "switch", 3),
    ]
    topic_domain = {page["topics"][0]: page["domain"] for page in manifest["pages"]}
    queries = []
    for query_id, split, category, text, topics, sequence_id, turn in specs:
        required, optional, causes = _truth(manifest, topics)
        domains = sorted({topic_domain[topic] for topic in topics})
        queries.append({
            "query_id": query_id, "split": split, "category": category, "query": text,
            "expected_domains": domains, "expected_topics": topics,
            "required_pages": required, "optional_pages": optional,
            "required_page_causes": causes, "sequence_id": sequence_id, "turn_index": turn,
        })
    payload = {"schema_version": 1, "seed": seed, "queries": queries}
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n")
    os.replace(temporary, path)
    return payload
