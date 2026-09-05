from __future__ import annotations
import hashlib,json
from pathlib import Path
from brain_ssd.physical_validation import GIB,SystemSampler,classify_profile,counter_delta,fadvise_drop,file_residency,physical_audit,self_counters,verify_checksum_manifest

ROOT=Path(__file__).resolve().parents[1]

def test_codespace_cannot_be_labeled_physical():
    allowed,reason=classify_profile({"environment_type":"CODESPACE_UNCONSTRAINED"},"physical_native",True)
    assert not allowed and "cannot be labeled" in reason

def test_acknowledgement_is_explicit():
    audit={"environment_type":"PHYSICAL_NATIVE_CANDIDATE","debian":{"ID":"debian"},"physical_ram_total_bytes":8*GIB,"cgroup":{"memory_max":"max"}}
    assert not classify_profile(audit,"physical_native",False)[0]
    assert classify_profile(audit,"physical_native",True)[0]

def test_hard_limit_profiles_are_proven():
    base={"environment_type":"PHYSICAL_NATIVE_CANDIDATE","debian":{"ID":"debian"},"physical_ram_total_bytes":16*GIB}
    assert classify_profile({**base,"cgroup":{"memory_max":8*GIB}},"target_8gb",True)[0]
    assert not classify_profile({**base,"cgroup":{"memory_max":"max"}},"target_8gb",True)[0]
    assert classify_profile({**base,"cgroup":{"memory_max":4*GIB}},"low_4gb",True)[0]
    container={**base,"environment_type":"PHYSICAL_CONTAINER_CANDIDATE","cgroup":{"memory_max":8*GIB}}
    assert classify_profile(container,"target_8gb",True)[0]
    assert not classify_profile(container,"physical_native",True)[0]

def test_checksum_manifest_fail_closed(tmp_path):
    payload=tmp_path/"payload";payload.write_bytes(b"brain")
    manifest=tmp_path/"checks.sha256";manifest.write_text(f"{hashlib.sha256(b'brain').hexdigest()}  payload\n")
    assert verify_checksum_manifest(tmp_path,manifest)["ok"]
    payload.write_bytes(b"changed");assert not verify_checksum_manifest(tmp_path,manifest)["ok"]

def test_residency_and_best_effort_drop_without_copy(tmp_path):
    path=tmp_path/"mapped.bin";path.write_bytes(bytes(1024*1024))
    before=file_residency(path);drop=fadvise_drop(path);after=file_residency(path)
    assert before["file_bytes"]==after["file_bytes"]==1024*1024
    assert 0<=after["resident_ratio"]<=1 and "requested" in drop

def test_audit_has_required_identity_and_gpu_disabled():
    audit=physical_audit(ROOT)
    for key in ("kernel","cpu","physical_ram_total_bytes","swap","block_devices","filesystem","storage","cgroup_v2","temperature","cpu_governors"):
        assert key in audit
    assert audit["qwen_device"]=="none" and audit["gpu_disabled_by_configuration"] is True

def test_system_sampler_reports_system_memory():
    with SystemSampler(.001) as sampler: pass
    summary=sampler.summary();assert summary["samples"]>=2 and summary["mem_available_min_bytes"]
    assert "per_core_cpu" in summary and "swap_used_peak_bytes" in summary

def test_retrieval_counters_are_separable():
    before=self_counters();after=self_counters();delta=counter_delta(before,after)
    assert set(delta)=={"minor_faults","major_faults","read_bytes"}
    assert all(value is None or value>=0 for value in delta.values())

def test_freeze_manifest_is_immutable_configuration():
    freeze=json.loads((ROOT/"results/phase4e/preparation/phase4d-freeze-manifest.json").read_text())
    config=freeze["frozen_configuration"]
    assert config["device"]=="none" and config["prefetch"] is False
    assert config["logical_page_bytes"]==1024**2 and config["storage_extent_bytes"]==4*1024**2
