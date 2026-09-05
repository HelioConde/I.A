from __future__ import annotations

import hashlib
import json
import mmap
import os
import platform
import shutil
import subprocess
import threading
import time
from pathlib import Path

from brain_ssd.residency import MappedRegion, resident_bytes

MIB=1024**2
GIB=1024**3


def read_key_values(path: Path) -> dict[str,int]:
    result={}
    try: lines=path.read_text().splitlines()
    except (FileNotFoundError,PermissionError): return result
    for line in lines:
        parts=line.replace(":","").split()
        if len(parts)>=2:
            try: result[parts[0]]=int(parts[1])*(1024 if len(parts)>2 and parts[2]=="kB" else 1)
            except ValueError: pass
    return result


def command(*args: str) -> dict:
    if not shutil.which(args[0]):return {"available":False,"command":list(args)}
    run=subprocess.run(args,text=True,capture_output=True,check=False)
    return {"available":True,"command":list(args),"returncode":run.returncode,"stdout":run.stdout.strip(),"stderr":run.stderr.strip()}


def scalar(path: Path):
    try:
        value=path.read_text().strip();return value if value=="max" else int(value)
    except (FileNotFoundError,PermissionError,ValueError):return None


def storage_classification(block_devices: dict,filesystem: dict) -> dict:
    try:
        blocks=json.loads(block_devices["stdout"])["blockdevices"]
        mounts=json.loads(filesystem["stdout"])["filesystems"]
        source=mounts[0].get("source","");device_source=source.split("[",1)[0]
    except (KeyError,IndexError,TypeError,json.JSONDecodeError):return {"storage_type":"UNKNOWN","reason":"unable to correlate mount and lsblk"}
    flat=[]
    def visit(items):
        for item in items:flat.append(item);visit(item.get("children",[]))
    visit(blocks);name=Path(device_source).name
    match=next((item for item in flat if item.get("name")==name or item.get("path")==device_source),None)
    if not match:return {"storage_type":"UNKNOWN","mount_source":source,"reason":"mount source is not a directly visible block device"}
    parent=next((item for item in flat if match in item.get("children",[])),None)
    identity=parent or match
    return {"storage_type":"HDD" if identity.get("rota") else "SSD","mount_source":source,"device":identity.get("path"),"model":identity.get("model"),"interface":identity.get("tran"),"rotational":identity.get("rota")}


def physical_audit(root: Path) -> dict:
    os_release={}
    try:
        for line in Path("/etc/os-release").read_text().splitlines():
            if "=" in line:
                key,value=line.split("=",1);os_release[key]=value.strip('"')
    except (FileNotFoundError,PermissionError):pass
    thermal={}
    for zone in sorted(Path("/sys/class/thermal").glob("thermal_zone*")):
        temp=scalar(zone/"temp")
        if isinstance(temp,int):thermal[zone.name]={"type":(zone/"type").read_text().strip() if (zone/"type").exists() else None,"millidegree_c":temp}
    governors={}
    for path in sorted(Path("/sys/devices/system/cpu").glob("cpu[0-9]*/cpufreq/scaling_governor")):
        try:governors[path.parent.parent.name]=path.read_text().strip()
        except (FileNotFoundError,PermissionError):pass
    mem=read_key_values(Path("/proc/meminfo")); cgroup=Path("/sys/fs/cgroup")
    virt=command("systemd-detect-virt")
    codespace=bool(os.environ.get("CODESPACES") or Path("/.codespaces").exists())
    virtualized=virt.get("returncode")==0 and virt.get("stdout") not in ("","none")
    environment="CODESPACE_UNCONSTRAINED" if codespace else ("PHYSICAL_CONTAINER_CANDIDATE" if virtualized else "PHYSICAL_NATIVE_CANDIDATE")
    frequencies=[]
    for path in Path("/sys/devices/system/cpu").glob("cpu[0-9]*/cpufreq/scaling_cur_freq"):
        value=scalar(path)
        if isinstance(value,int):frequencies.append(value*1000)
    blocks=command("lsblk","--json","-o","NAME,PATH,TYPE,SIZE,ROTA,TRAN,FSTYPE,MOUNTPOINTS,MODEL")
    filesystem=command("findmnt","--json","-T",str(root),"-o","SOURCE,TARGET,FSTYPE,OPTIONS")
    return {"schema_version":1,"captured_utc":time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime()),
            "environment_type":environment,"hostname":platform.node(),"platform":platform.platform(),"kernel":platform.release(),
            "debian":os_release,"cpu_count":os.cpu_count(),"cpu":command("lscpu","--json"),
            "physical_ram_total_bytes":mem.get("MemTotal"),"memory_snapshot":mem,"swap":command("swapon","--show","--bytes","--output","NAME,TYPE,SIZE,USED,PRIO"),
            "block_devices":blocks,"filesystem":filesystem,"storage":storage_classification(blocks,filesystem),
            "cgroup_v2":(cgroup/"cgroup.controllers").exists(),"cgroup":{"memory_max":scalar(cgroup/"memory.max"),"memory_current":scalar(cgroup/"memory.current"),"memory_swap_max":scalar(cgroup/"memory.swap.max")},
            "temperature":thermal,"cpu_governors":governors,"cpu_frequency_hz":{"current_min":min(frequencies) if frequencies else None,"current_max":max(frequencies) if frequencies else None},"virtualization":virt,
            "gpu_disabled_by_configuration":True,"qwen_device":"none"}


def verify_checksum_manifest(root: Path, manifest: Path) -> dict:
    checked=[];errors=[]
    for number,line in enumerate(manifest.read_text().splitlines(),1):
        if not line.strip():continue
        parts=line.split(maxsplit=1)
        if len(parts)!=2:
            errors.append({"line":number,"reason":"parse"});continue
        digest=parts[0];relative=parts[1].strip().lstrip("*")
        path=root/relative
        actual=hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
        row={"path":relative,"expected":digest,"actual":actual,"ok":actual==digest};checked.append(row)
        if not row["ok"]:errors.append(row)
    return {"manifest":str(manifest.relative_to(root)),"ok":not errors,"checked":len(checked),"errors":errors}


def fadvise_drop(path: Path) -> dict:
    if not hasattr(os,"posix_fadvise") or not hasattr(os,"POSIX_FADV_DONTNEED"):
        return {"supported":False,"requested":False}
    with path.open("rb") as stream:os.posix_fadvise(stream.fileno(),0,0,os.POSIX_FADV_DONTNEED)
    return {"supported":True,"requested":True}


def file_residency(path: Path) -> dict:
    with path.open("rb") as stream:
        mapping=mmap.mmap(stream.fileno(),0,access=mmap.ACCESS_READ);region=MappedRegion.borrow(mapping,stream.fileno())
        try:value=resident_bytes(region)
        finally:region.release();mapping.close()
    return {"file_bytes":path.stat().st_size,"resident_bytes":value,"resident_ratio":value/path.stat().st_size if path.stat().st_size else 0.0}


def classify_profile(audit: dict,profile: str,acknowledged: bool) -> tuple[bool,str]:
    environment=audit["environment_type"]
    if environment=="CODESPACE_UNCONSTRAINED":return False,"Codespace host cannot be labeled as a physical result"
    if profile=="physical_native" and environment!="PHYSICAL_NATIVE_CANDIDATE":return False,"virtualized/container environment cannot be labeled PHYSICAL_NATIVE"
    if not acknowledged:return False,"--acknowledge-physical-native is required"
    if audit.get("debian",{}).get("ID")!="debian":return False,"Debian physical host required"
    total=audit.get("physical_ram_total_bytes") or 0;limit=audit.get("cgroup",{}).get("memory_max")
    if profile=="physical_native":return True,"native Debian acknowledged"
    target=8*GIB if profile=="target_8gb" else 4*GIB
    if total<=target*1.08 and profile=="target_8gb":return True,"native RAM is approximately 8 GiB"
    if limit==target:return True,"verified cgroup hard limit"
    return False,f"profile requires verified memory.max={target} or native approximately {target//GIB} GiB"


def system_snapshot() -> dict:
    mem=read_key_values(Path("/proc/meminfo"));load=os.getloadavg()
    temps=[]
    for path in Path("/sys/class/thermal").glob("thermal_zone*/temp"):
        value=scalar(path)
        if isinstance(value,int):temps.append(value)
    cpu=[]
    try:
        for line in Path("/proc/stat").read_text().splitlines():
            parts=line.split()
            if parts and parts[0].startswith("cpu") and parts[0]!="cpu":cpu.append({"cpu":parts[0],"ticks":[int(v) for v in parts[1:]]})
    except (FileNotFoundError,PermissionError,ValueError):pass
    cgroup=read_key_values(Path("/sys/fs/cgroup/memory.stat"))
    return {"monotonic_s":time.monotonic(),"mem_total":mem.get("MemTotal"),"mem_available":mem.get("MemAvailable"),"cached":mem.get("Cached"),
            "active_file":mem.get("Active(file)"),"inactive_file":mem.get("Inactive(file)"),"swap_free":mem.get("SwapFree"),
            "swap_total":mem.get("SwapTotal"),"load1":load[0],"load5":load[1],"load15":load[2],
            "max_temperature_millidegree_c":max(temps) if temps else None,"per_cpu_ticks":cpu,
            "cgroup_memory_current":scalar(Path("/sys/fs/cgroup/memory.current")),"cgroup_anon":cgroup.get("anon"),"cgroup_file":cgroup.get("file")}


class SystemSampler:
    def __init__(self,interval_s:float=.1):self.interval_s=interval_s;self.samples=[];self._stop=threading.Event();self._thread=None
    def __enter__(self):
        self.samples.append(system_snapshot());self._thread=threading.Thread(target=self._run,daemon=True);self._thread.start();return self
    def _run(self):
        while not self._stop.wait(self.interval_s):self.samples.append(system_snapshot())
    def __exit__(self,*_):self._stop.set();self._thread.join();self.samples.append(system_snapshot())
    def summary(self):
        def values(key):return [s[key] for s in self.samples if isinstance(s.get(key),(int,float))]
        total=max(values("mem_total"),default=0);minimum=min(values("mem_available"),default=0)
        per_core=[]
        if len(self.samples)>=2:
            first={r["cpu"]:r["ticks"] for r in self.samples[0].get("per_cpu_ticks",[])};last={r["cpu"]:r["ticks"] for r in self.samples[-1].get("per_cpu_ticks",[])}
            for cpu,start in first.items():
                end=last.get(cpu)
                if end:
                    total_ticks=sum(end)-sum(start);idle=(end[3]+(end[4] if len(end)>4 else 0))-(start[3]+(start[4] if len(start)>4 else 0))
                    per_core.append({"cpu":cpu,"utilization_percent":100*(total_ticks-idle)/total_ticks if total_ticks>0 else None})
        swap_total=max(values("swap_total"),default=0);swap_free=min(values("swap_free"),default=0)
        return {"samples":len(self.samples),"system_ram_used_peak_bytes":total-minimum if total and minimum else None,"mem_available_min_bytes":minimum or None,
                "cached_max_bytes":max(values("cached"),default=None),"active_file_max_bytes":max(values("active_file"),default=None),
                "inactive_file_max_bytes":max(values("inactive_file"),default=None),"swap_free_min_bytes":swap_free,
                "swap_used_peak_bytes":max(0,swap_total-swap_free),"temperature_max_millidegree_c":max(values("max_temperature_millidegree_c"),default=None),
                "load1_max":max(values("load1"),default=None),"per_core_cpu":per_core,
                "cgroup_memory_current_peak_bytes":max(values("cgroup_memory_current"),default=None),
                "cgroup_anon_peak_bytes":max(values("cgroup_anon"),default=None),"cgroup_file_peak_bytes":max(values("cgroup_file"),default=None)}


def self_counters() -> dict:
    """Counters around in-process retrieval, separate from the llama child."""
    try:stat=Path("/proc/self/stat").read_text().split()
    except (FileNotFoundError,PermissionError):stat=[]
    io=read_key_values(Path("/proc/self/io"))
    return {"minor_faults":int(stat[9]) if len(stat)>11 else None,"major_faults":int(stat[11]) if len(stat)>11 else None,
            "read_bytes":io.get("read_bytes")}


def counter_delta(before: dict,after: dict) -> dict:
    return {key:(max(0,after[key]-value) if isinstance(value,int) and isinstance(after.get(key),int) else None) for key,value in before.items()}
