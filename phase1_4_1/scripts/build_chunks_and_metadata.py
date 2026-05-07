import argparse
import csv
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple
from urllib.parse import urlparse


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Phase 1.4.1 chunk construction and metadata binding")
    parser.add_argument("--parsed", required=True, help="Parsed documents JSONL")
    parser.add_argument("--facts", required=True, help="Extracted scheme facts JSONL")
    parser.add_argument("--policy", required=True, help="Chunking policy JSON")
    parser.add_argument("--valid-out", required=True, help="Output valid chunks JSONL")
    parser.add_argument("--quarantine-out", required=True, help="Output quarantined chunks JSONL")
    parser.add_argument("--rejected-out", required=True, help="Output rejected chunks JSONL")
    parser.add_argument("--report", required=True, help="Metadata validation report CSV")
    parser.add_argument("--summary", required=True, help="Metadata summary markdown")
    return parser.parse_args()


def approx_tokens(text: str) -> int:
    return max(1, int(len(text.split()) * 1.3))


def split_into_sections(text: str, section_markers: List[str]) -> List[str]:
    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
    if not lines:
        return []
    sections: List[List[str]] = []
    current: List[str] = []
    for line in lines:
        is_marker = any(line.startswith(marker) or marker in line for marker in section_markers)
        if is_marker and current:
            sections.append(current)
            current = [line]
        else:
            current.append(line)
    if current:
        sections.append(current)
    return ["\n".join(s).strip() for s in sections if s]


def window_chunks(section: str, target_tokens: int, overlap_tokens: int, min_tokens: int) -> List[str]:
    words = section.split()
    if not words:
        return []
    step = max(1, target_tokens - overlap_tokens)
    chunks: List[str] = []
    i = 0
    while i < len(words):
        part = words[i : i + target_tokens]
        if len(part) < min_tokens and chunks:
            chunks[-1] = chunks[-1] + " " + " ".join(part)
            break
        chunks.append(" ".join(part))
        i += step
    return chunks


def load_jsonl(path: Path) -> List[Dict]:
    rows: List[Dict] = []
    with path.open("r", encoding="utf-8") as fp:
        for line in fp:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def build_metadata(doc: Dict, fact: Dict) -> Dict:
    source_url = doc["source_url"]
    parsed = urlparse(source_url)
    source_domain = parsed.netloc.lower().replace("www.", "")
    effective_date = fact.get("effective_date") or (fact.get("ingested_at") or "")[:10]
    return {
        "source_url": source_url,
        "source_domain": source_domain,
        "doc_type": doc.get("doc_type"),
        "scheme_name": doc.get("scheme_name"),
        "amc_name": fact.get("amc_name"),
        "effective_date": effective_date,
        "ingested_at": fact.get("ingested_at"),
    }


def build_fact_anchor_chunks(fact: Dict) -> List[str]:
    scheme = str(fact.get("scheme_name", "")).strip()
    if not scheme:
        return []
    anchors: List[str] = []

    if fact.get("nav_value") is not None:
        anchors.append(f"{scheme} NAV: INR {fact['nav_value']}")
    if fact.get("aum_value_cr") is not None:
        anchors.append(f"{scheme} Fund size (AUM): INR {fact['aum_value_cr']} Cr")
    if fact.get("rating_value") not in (None, ""):
        anchors.append(f"{scheme} Rating: {fact['rating_value']}")
    if fact.get("expense_ratio_percent") is not None:
        anchors.append(f"{scheme} Expense ratio: {fact['expense_ratio_percent']}%")
    if fact.get("exit_load_text") not in (None, ""):
        anchors.append(f"{scheme} Exit load: {fact['exit_load_text']}")
    if fact.get("min_sip_amount_inr") is not None:
        anchors.append(f"{scheme} Min. for SIP: INR {fact['min_sip_amount_inr']}")
    if fact.get("elss_lock_in_years") is not None:
        anchors.append(f"{scheme} Lock-in: {fact['elss_lock_in_years']} years")
    if fact.get("riskometer_label") not in (None, ""):
        anchors.append(f"{scheme} Riskometer: {fact['riskometer_label']}")
    if fact.get("benchmark_full_name") not in (None, ""):
        anchors.append(f"{scheme} Fund benchmark: {fact['benchmark_full_name']}")

    return anchors


def mandatory_missing(metadata: Dict, required_fields: List[str]) -> List[str]:
    missing = []
    for f in required_fields:
        value = metadata.get(f)
        if value is None or str(value).strip() == "":
            missing.append(f)
    return missing


def write_jsonl(path: Path, rows: List[Dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fp:
        for row in rows:
            fp.write(json.dumps(row, ensure_ascii=True) + "\n")


def write_report(path: Path, rows: List[Dict]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_summary(path: Path, report_rows: List[Dict]) -> None:
    total = len(report_rows)
    valid = sum(1 for r in report_rows if r["status"] == "valid")
    quarantined = sum(1 for r in report_rows if r["status"] == "quarantined")
    rejected = sum(1 for r in report_rows if r["status"] == "rejected")
    lines = [
        "# Phase 1.4.1 Metadata Validation Summary",
        "",
        f"- Generated at (UTC): {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}",
        f"- Total chunks: {total}",
        f"- Valid chunks: {valid}",
        f"- Quarantined chunks: {quarantined}",
        f"- Rejected chunks: {rejected}",
        "",
        "## Records requiring action",
        "",
        "| chunk_id | status | reason |",
        "|---|---|---|",
    ]
    action_rows = [r for r in report_rows if r["status"] != "valid"]
    if action_rows:
        for r in action_rows[:200]:
            lines.append(f"| {r['chunk_id']} | {r['status']} | {r['reason']} |")
    else:
        lines.append("| - | - | No action required |")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_exit(path: Path, report_rows: List[Dict], required_fields: List[str]) -> None:
    total = len(report_rows)
    valid = [r for r in report_rows if r["status"] == "valid"]
    complete_metadata = total > 0 and len(valid) == total
    report_published = total > 0
    lines = [
        "# Phase 1.4.1 Exit Check",
        "",
        "## Exit criteria status",
        "",
        "1. **100% generated chunks include mandatory metadata**",
        f"   - Status: `{'PASS' if complete_metadata else 'CONDITIONAL'}`",
        f"   - Mandatory fields: {', '.join(required_fields)}",
        "",
        "2. **Metadata validation report published (valid/rejected/quarantined counts)**",
        f"   - Status: `{'PASS' if report_published else 'FAIL'}`",
        "",
        "## Phase gate decision",
        f"- `{'READY' if complete_metadata else 'CONDITIONAL'}` for Phase 1.4.2 progression.",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    policy = json.loads(Path(args.policy).read_text(encoding="utf-8"))
    url_re = re.compile(policy["accepted_url_regex"])
    target_tokens = int(policy["chunking"]["target_tokens"])
    overlap_tokens = int(policy["chunking"]["overlap_tokens"])
    min_tokens = int(policy["chunking"]["min_tokens"])
    required_fields = policy["mandatory_metadata_fields"]
    section_markers = policy["section_markers"]

    parsed_docs = load_jsonl(Path(args.parsed))
    fact_rows = load_jsonl(Path(args.facts))
    fact_by_source = {f["source_id"]: f for f in fact_rows}

    valid_chunks: List[Dict] = []
    quarantined_chunks: List[Dict] = []
    rejected_chunks: List[Dict] = []
    report_rows: List[Dict] = []

    for doc in parsed_docs:
        if doc.get("parse_status") != "parsed":
            continue
        source_id = doc["source_id"]
        source_url = doc.get("source_url", "")
        if not url_re.match(source_url):
            continue
        if source_id not in fact_by_source:
            continue

        metadata = build_metadata(doc, fact_by_source[source_id])
        text = doc.get("parsed_text", "")
        sections = split_into_sections(text, section_markers)
        if not sections:
            sections = [text]

        chunk_index = 0
        for section in sections:
            for chunk_text in window_chunks(section, target_tokens, overlap_tokens, min_tokens):
                if not chunk_text.strip():
                    continue
                digest = hashlib.sha1(f"{source_id}:{chunk_index}:{chunk_text}".encode("utf-8")).hexdigest()[:16]
                chunk_id = f"chk-{source_id}-{chunk_index}-{digest}"
                tok = approx_tokens(chunk_text)
                record = {
                    "chunk_id": chunk_id,
                    "source_id": source_id,
                    "chunk_index": chunk_index,
                    "chunk_token_count": tok,
                    "chunk_text": chunk_text,
                    **metadata,
                }

                missing = mandatory_missing(metadata, required_fields)
                status = "valid"
                reason = ""
                if missing:
                    status = "rejected"
                    reason = f"missing_metadata:{','.join(missing)}"
                    rejected_chunks.append(record)
                elif not metadata.get("effective_date"):
                    status = "quarantined"
                    reason = "effective_date_missing_after_fallback"
                    quarantined_chunks.append(record)
                else:
                    valid_chunks.append(record)

                report_rows.append(
                    {
                        "chunk_id": chunk_id,
                        "source_id": source_id,
                        "status": status,
                        "reason": reason,
                        "source_url": metadata.get("source_url", ""),
                        "doc_type": metadata.get("doc_type", ""),
                        "scheme_name": metadata.get("scheme_name", ""),
                        "effective_date": metadata.get("effective_date", ""),
                        "ingested_at": metadata.get("ingested_at", ""),
                    }
                )
                chunk_index += 1

        # Hardening pass: add compact field-anchor chunks from extracted facts.
        # This improves retrieval reliability for direct factual queries.
        for anchor_text in build_fact_anchor_chunks(fact_by_source[source_id]):
            digest = hashlib.sha1(f"{source_id}:anchor:{chunk_index}:{anchor_text}".encode("utf-8")).hexdigest()[:16]
            chunk_id = f"chk-{source_id}-{chunk_index}-{digest}"
            record = {
                "chunk_id": chunk_id,
                "source_id": source_id,
                "chunk_index": chunk_index,
                "chunk_token_count": approx_tokens(anchor_text),
                "chunk_text": anchor_text,
                "chunk_kind": "fact_anchor",
                **metadata,
            }
            missing = mandatory_missing(metadata, required_fields)
            status = "valid"
            reason = ""
            if missing:
                status = "rejected"
                reason = f"missing_metadata:{','.join(missing)}"
                rejected_chunks.append(record)
            else:
                valid_chunks.append(record)

            report_rows.append(
                {
                    "chunk_id": chunk_id,
                    "source_id": source_id,
                    "status": status,
                    "reason": reason,
                    "source_url": metadata.get("source_url", ""),
                    "doc_type": metadata.get("doc_type", ""),
                    "scheme_name": metadata.get("scheme_name", ""),
                    "effective_date": metadata.get("effective_date", ""),
                    "ingested_at": metadata.get("ingested_at", ""),
                }
            )
            chunk_index += 1

    write_jsonl(Path(args.valid_out), valid_chunks)
    write_jsonl(Path(args.quarantine_out), quarantined_chunks)
    write_jsonl(Path(args.rejected_out), rejected_chunks)
    write_report(Path(args.report), report_rows)
    write_summary(Path(args.summary), report_rows)
    write_exit(Path(args.summary).parent / "phase1_4_1_exit_check.md", report_rows, required_fields)

    print(
        "Phase 1.4.1 complete. "
        f"chunks_total={len(report_rows)} valid={len(valid_chunks)} "
        f"quarantined={len(quarantined_chunks)} rejected={len(rejected_chunks)}"
    )


if __name__ == "__main__":
    main()
