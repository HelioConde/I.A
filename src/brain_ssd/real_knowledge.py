from __future__ import annotations

import hashlib
import html
import json
import math
import random
import re
import statistics
import zipfile
from dataclasses import asdict, dataclass
from html.parser import HTMLParser
from pathlib import Path


MIB = 1024**2
PAGE_SIZE = MIB
EXTENT_SIZE = 4 * MIB
TOKEN_RE = re.compile(r"[a-zA-ZÀ-ÿ_][\wÀ-ÿ.-]{1,}", re.UNICODE)


def sha256_bytes(data: bytes) -> str: return hashlib.sha256(data).hexdigest()
def normalize(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\x00", "")
    return re.sub(r"[ \t]+", " ", text).strip()
def terms(text: str) -> tuple[str, ...]: return tuple(sorted(set(token.casefold().strip("._-") for token in TOKEN_RE.findall(text) if len(token) > 2)))


@dataclass(frozen=True)
class KnowledgeRecord:
    record_id: str
    source_id: str
    title: str
    section: str
    text: str
    domain: str
    terms: tuple[str, ...]
    page_id: int = -1
    offset: int = -1
    length: int = 0
    checksum: str = ""
    document: str = ""


class _TextHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__(); self.parts=[]; self.skip=0
    def handle_starttag(self, tag, attrs):
        if tag in {"script","style","svg","nav"}: self.skip += 1
        elif not self.skip and tag in {"p","div","section","article","li","h1","h2","h3","h4","pre","tr","br"}: self.parts.append("\n")
    def handle_endtag(self, tag):
        if tag in {"script","style","svg","nav"} and self.skip: self.skip -= 1
        elif not self.skip and tag in {"p","div","section","article","li","h1","h2","h3","h4","pre","tr"}: self.parts.append("\n")
    def handle_data(self, data):
        if not self.skip: self.parts.append(data)
    def text(self): return html.unescape("".join(self.parts))


def _paragraphs(text: str) -> list[str]:
    return [normalize(part) for part in re.split(r"\n\s*\n+", text) if len(normalize(part)) >= 80]


def _chunks(text: str, minimum: int = 500, target: int = 1400, maximum: int = 2800) -> list[str]:
    chunks=[]; current=[]; size=0
    for paragraph in _paragraphs(text):
        encoded=len(paragraph.encode())
        if current and size + encoded > target and size >= minimum:
            chunks.append("\n\n".join(current)); current=[]; size=0
        if encoded > maximum:
            sentences=re.split(r"(?<=[.!?])\s+",paragraph)
        else: sentences=[paragraph]
        for sentence in sentences:
            if current and size + len(sentence.encode()) > maximum:
                chunks.append("\n\n".join(current)); current=[]; size=0
            current.append(sentence); size += len(sentence.encode()) + 2
    if current: chunks.append("\n\n".join(current))
    return [chunk for chunk in chunks if len(chunk.encode()) >= 120]


def _record(source_id: str, document: str, title: str, section: str, text: str, domain: str, index: int) -> KnowledgeRecord:
    payload=text.encode(); rid=hashlib.sha256(f"{source_id}\0{document}\0{index}\0".encode()+payload).hexdigest()[:24]
    return KnowledgeRecord(rid,source_id,title,section,text,domain,terms(f"{title} {section} {text}"),length=len(payload),checksum=sha256_bytes(payload),document=document)


def ingest_sources(root: Path, source_manifest_path: Path) -> tuple[list[KnowledgeRecord],dict]:
    source_manifest=json.loads(source_manifest_path.read_text()); records=[]; source_stats=[]
    for source in source_manifest["sources"]:
        archive=root/source["archive"]
        if hashlib.sha256(archive.read_bytes()).hexdigest()!=source["sha256"]: raise ValueError(f"source checksum mismatch: {archive}")
        source_records=0; normalized_bytes=0
        with zipfile.ZipFile(archive) as bundle:
            for name in sorted(bundle.namelist()):
                lower=name.lower()
                if source["source_id"].startswith("python"):
                    if not lower.endswith(".txt") or "whatsnew/changelog" in lower: continue
                    raw=bundle.read(name).decode("utf-8",errors="replace"); domain="python"
                else:
                    if not lower.endswith(".html") or any(part in lower for part in ("/search","/images/","/matrix/")): continue
                    parser=_TextHTMLParser(); parser.feed(bundle.read(name).decode("utf-8",errors="replace")); raw=parser.text(); domain="sqlite"
                clean=normalize(raw); title=Path(name).stem.replace("_"," "); chunks=_chunks(clean)
                for index,chunk in enumerate(chunks): records.append(_record(source["source_id"],name,title,title,chunk,domain,index))
                source_records += len(chunks); normalized_bytes += sum(len(chunk.encode()) for chunk in chunks)
        source_stats.append({"source_id":source["source_id"],"record_count":source_records,"normalized_record_bytes":normalized_bytes})
    return records,{"sources":source_stats,"record_count":len(records),"record_bytes":sum(record.length for record in records)}


def pack_records(records: list[KnowledgeRecord], output: Path, layout: str, seed: int = 20260807) -> dict:
    if layout not in {"semantic","random"}: raise ValueError(layout)
    ordered=sorted(records,key=lambda r:(r.domain,r.source_id,r.document,r.section,r.record_id))
    if layout=="random": random.Random(seed).shuffle(ordered)
    packed=[]; pages=[]; page=bytearray(); page_records=[]; page_id=0
    def flush():
        nonlocal page,page_records,page_id
        if not page_records:return
        used=len(page); padded=bytes(page)+bytes(PAGE_SIZE-used)
        pages.append({"page_id":page_id,"version":1,"offset":page_id*PAGE_SIZE,"size":PAGE_SIZE,
                      "used_bytes":used,"padding_bytes":PAGE_SIZE-used,"record_ids":list(page_records),
                      "checksum":sha256_bytes(padded),"related_pages":[],"extent_id":page_id//4})
        page=bytearray();page_records=[];page_id+=1
    for record in ordered:
        payload=record.text.encode()
        if len(payload)>PAGE_SIZE: raise ValueError(f"record too large: {record.record_id}")
        if page and len(page)+len(payload)>PAGE_SIZE: flush()
        offset=len(page);page.extend(payload);page_records.append(record.record_id)
        packed.append(KnowledgeRecord(**{**asdict(record),"page_id":page_id,"offset":offset,"length":len(payload)}))
    flush()
    for index,item in enumerate(pages):
        related=[]
        for neighbor in (index-1,index+1):
            if 0<=neighbor<len(pages) and pages[neighbor]["extent_id"]==item["extent_id"]: related.append(neighbor)
        item["related_pages"]=related
    output.mkdir(parents=True,exist_ok=True); data_path=output/"brain.dat"
    by_id={record.record_id:record for record in packed}
    with data_path.open("wb") as stream:
        for page_meta in pages:
            payload=b"".join(by_id[rid].text.encode() for rid in page_meta["record_ids"])
            stream.write(payload);stream.write(bytes(PAGE_SIZE-len(payload)))
    utilization=[page["used_bytes"]/PAGE_SIZE for page in pages]
    manifest={"schema_version":1,"format":"brain-ssd-real-knowledge-v1","layout":layout,"seed":seed,
              "data_file":"brain.dat","corpus_size_bytes":len(pages)*PAGE_SIZE,"page_size_bytes":PAGE_SIZE,
              "storage_extent_bytes":EXTENT_SIZE,"page_count":len(pages),"pages":pages,
              "records":[asdict(record) for record in sorted(packed,key=lambda r:r.record_id)],
              "stats":{"record_count":len(packed),"record_bytes":sum(r.length for r in packed),
                       "page_utilization_mean":statistics.mean(utilization),"page_utilization_median":statistics.median(utilization),
                       "page_utilization_p95":sorted(utilization)[round((len(utilization)-1)*.95)],
                       "records_per_page_mean":len(packed)/len(pages)}}
    (output/"manifest.json").write_text(json.dumps(manifest,indent=2,sort_keys=True)+"\n")
    return manifest


def extract_record(mapping, record: dict) -> str:
    start=record["page_id"]*PAGE_SIZE+record["offset"]; payload=bytes(mapping[start:start+record["length"]])
    if sha256_bytes(payload)!=record["checksum"]: raise ValueError(f"record checksum mismatch: {record['record_id']}")
    return payload.decode("utf-8")
