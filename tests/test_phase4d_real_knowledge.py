from __future__ import annotations

import hashlib
import json
import mmap
from pathlib import Path

import pytest

from brain_ssd.real_knowledge import PAGE_SIZE, extract_record
from brain_ssd.record_retrieval import ContextBuilder, RealKnowledgeIndex, build_prompt, retrieve
from brain_ssd.storage import MMapStorageBackend

ROOT=Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def manifest():
    return json.loads((ROOT/"brain_data/real_knowledge/semantic/manifest.json").read_text())


def test_source_manifest_hashes_and_provenance():
    source_manifest=json.loads((ROOT/"brain_data/real_knowledge/source-manifest.json").read_text())
    assert source_manifest["sources"]
    for source in source_manifest["sources"]:
        payload=(ROOT/"brain_data/real_knowledge"/source["archive"]).read_bytes()
        assert hashlib.sha256(payload).hexdigest()==source["sha256"]
        assert source["origin"].startswith("https://") and source["license"]


def test_record_to_page_offsets_checksums_and_no_overlap(manifest):
    by_page={page["page_id"]:page for page in manifest["pages"]}
    spans={}
    with (ROOT/"brain_data/real_knowledge/semantic/brain.dat").open("rb") as stream:
        mapping=mmap.mmap(stream.fileno(),0,access=mmap.ACCESS_READ)
        for record in manifest["records"]:
            assert 0<=record["offset"]<PAGE_SIZE
            assert record["offset"]+record["length"]<=by_page[record["page_id"]]["used_bytes"]
            text=extract_record(mapping,record); assert text==record["text"]
            spans.setdefault(record["page_id"],[]).append((record["offset"],record["offset"]+record["length"]))
        mapping.close()
    for page_spans in spans.values():
        ordered=sorted(page_spans); assert all(a[1]<=b[0] for a,b in zip(ordered,ordered[1:]))


def test_semantic_and_random_layout_are_reproducible_and_same_records():
    semantic=json.loads((ROOT/"brain_data/real_knowledge/semantic/manifest.json").read_text())
    random_layout=json.loads((ROOT/"brain_data/real_knowledge/random/manifest.json").read_text())
    assert {r["record_id"] for r in semantic["records"]}=={r["record_id"] for r in random_layout["records"]}
    assert any(a["page_id"]!=b["page_id"] for a,b in zip(semantic["records"],random_layout["records"]))
    assert semantic["page_size_bytes"]==random_layout["page_size_bytes"]==PAGE_SIZE


def test_index_load_retrieval_unknown_and_determinism(manifest):
    index=RealKnowledgeIndex.load(ROOT/"brain_data/real_knowledge/index/record-index.json.gz",manifest["records"])
    records={r["record_id"]:r for r in manifest["records"]}
    query="Why can repeated json.dump calls create invalid JSON?"
    first=retrieve(index,query,records); second=retrieve(index,query,records)
    assert first==second and first.records
    unknown=retrieve(index,"What cache size does the OrionDB driver use?",records)
    assert unknown.status=="NO_KNOWLEDGE" and not unknown.records


def test_storage_extracts_each_selected_page_once(manifest):
    selected=manifest["records"][:5]; page_ids={r["page_id"] for r in selected}
    backend=MMapStorageBackend(ROOT/"brain_data/real_knowledge/semantic/manifest.json");backend.open_brain()
    try:
        for page_id in page_ids:
            page=backend.get_page(page_id,validate="first");backend.release_page(page)
        assert backend.stats()["accesses"]==len(page_ids)
    finally: backend.close_brain()


def test_context_budget_sources_and_untrusted_document_boundary(manifest):
    context=ContextBuilder(512).build(manifest["records"][:10])
    assert context["estimated_tokens"]<=512 and context["source_ids"]
    prompt=build_prompt("test question",context)
    assert "untrusted data" in prompt and "[SOURCE:" in prompt and "test question" in prompt


def test_corrupt_record_fails(tmp_path,manifest):
    original=ROOT/"brain_data/real_knowledge/semantic/brain.dat"; target=tmp_path/"brain.dat";target.write_bytes(original.read_bytes())
    data=bytearray(target.read_bytes());data[0]^=1;target.write_bytes(data)
    record=min(manifest["records"],key=lambda r:(r["page_id"],r["offset"]))
    with target.open("rb") as stream:
        mapping=mmap.mmap(stream.fileno(),0,access=mmap.ACCESS_READ)
        with pytest.raises(ValueError,match="checksum mismatch"):extract_record(mapping,record)
        mapping.close()
