from __future__ import annotations

import json
import os
from pathlib import Path

from brain_ssd.recall_dataset import _truth, generate_recall_dataset


def generate_semantic_rescue_dataset(path: Path, manifest: dict, seed: int = 20260807) -> dict:
    base = generate_recall_dataset(path.with_name(".phase35-base.tmp.json"), manifest, seed)
    holdout = [dict(item) for item in base["queries"] if item["split"] == "holdout"]
    mt4_index = next(index for index, item in enumerate(holdout) if item["query_id"] == "mt4")
    required, optional, causes = _truth(manifest, ["python.sqlite"])
    holdout.insert(mt4_index + 1, {
        "query_id": "mt5", "split": "holdout", "category": "partial_cue", "query": "e depois?",
        "expected_domains": ["programming"], "expected_topics": ["python.sqlite"],
        "required_pages": required, "optional_pages": optional, "required_page_causes": causes,
        "sequence_id": "python_flow", "turn_index": 5,
    })
    development_specs = [
        ("d_exact_json", "single_topic", "abrir JSON em Python", ["python.json"], None, 0),
        ("d_multi", "multi_domain", "processos e rede no Linux", ["processes", "networking"], None, 0),
        ("d_fuzzy", "noise_typo", "pythno jsom abrir", ["python.json"], None, 0),
        ("d_sem_async", "semantic_paraphrase", "rotina cooperativa sem espera", ["python.asyncio"], None, 0),
        ("d_sem_dns", "semantic_paraphrase", "localizar endereço de um site pelo nome", ["dns"], None, 0),
        ("d_partial1", "multi_turn", "arquivos Python", ["python.files"], "dev_context", 1),
        ("d_partial2", "partial_cue", "e sem bloquear?", ["python.asyncio"], "dev_context", 2),
        ("d_switch", "topic_switch", "agora explique genes e DNA", ["genetics"], "dev_context", 3),
        ("d_ood", "unknown", "acordes para violoncelo barroco", [], None, 0),
        ("d_nn_trap", "nearest_neighbor_trap", "rede de acordes para composição musical", [], None, 0),
        ("d_server_trap", "nearest_neighbor_trap", "servidor de receitas culinárias", [], None, 0),
    ]
    holdout_specs = [
        ("hs_sem_async", "semantic_paraphrase", "execução cooperativa não bloqueante", ["python.asyncio"], None, 0),
        ("hs_sem_json", "semantic_paraphrase", "transformar texto estruturado em objetos", ["python.json"], None, 0),
        ("hs_sem_nvme", "semantic_paraphrase", "armazenamento flash com baixa latência", ["nvme"], None, 0),
        ("hs_sem_checksum", "semantic_paraphrase", "verificar soma criptográfica contra dano", ["checksums"], None, 0),
        ("hs_sem_dns", "semantic_paraphrase", "resolver endereço de internet pelo nome", ["dns"], None, 0),
        ("hs_typo", "noise_typo", "pythn assicrono sem bloqear", ["python.asyncio"], None, 0),
        ("hs_nn_trap", "nearest_neighbor_trap", "rede harmônica para improvisação musical", [], None, 0),
        ("hs_server_trap", "nearest_neighbor_trap", "servidor doméstico de receitas", [], None, 0),
        ("adv1", "adversarial_context", "arquivos Python", ["python.files"], "adversarial", 1),
        ("adv2", "adversarial_context", "JSON Python", ["python.json"], "adversarial", 2),
        ("adv3", "adversarial_context", "SQLite Python", ["python.sqlite"], "adversarial", 3),
        ("adv4", "adversarial_context", "asyncio Python", ["python.asyncio"], "adversarial", 4),
        ("adv5", "adversarial_context", "pathlib arquivos Python", ["python.files"], "adversarial", 5),
        ("adv6", "adversarial_context", "explique completamente DNA genes e herança", ["genetics"], "adversarial", 6),
    ]
    topic_domain = {page["topics"][0]: page["domain"] for page in manifest["pages"]}

    def materialize(specs, split):
        rows = []
        for query_id, category, query, topics, sequence_id, turn in specs:
            required, optional, causes = _truth(manifest, topics)
            rows.append({
                "query_id": query_id, "split": split, "category": category, "query": query,
                "expected_domains": sorted({topic_domain[topic] for topic in topics}),
                "expected_topics": topics, "required_pages": required, "optional_pages": optional,
                "required_page_causes": causes, "sequence_id": sequence_id, "turn_index": turn,
            })
        return rows

    queries = materialize(development_specs, "development") + holdout + materialize(holdout_specs, "holdout")
    payload = {"schema_version": 1, "seed": seed, "development_count": len(development_specs), "holdout_count": len(holdout) + len(holdout_specs), "queries": queries}
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n")
    os.replace(temporary, path)
    path.with_name(".phase35-base.tmp.json").unlink(missing_ok=True)
    return payload
