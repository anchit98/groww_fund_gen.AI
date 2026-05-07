import argparse
import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple

import chromadb
from sentence_transformers import SentenceTransformer


def load_csv(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def parse_checked_at(value: str) -> datetime:
    value = (value or "").strip()
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    return datetime.fromisoformat(value).astimezone(timezone.utc)


def summarize_sources(rows: List[Dict[str, str]], url_regex: re.Pattern, sla_days: int) -> Dict[str, object]:
    total = len(rows)
    broken = 0
    invalid_url = 0
    latest_check = None

    for row in rows:
        url = (row.get("url") or row.get("source_url") or "").strip()
        status = (row.get("validation_status") or "").strip().lower()
        http_status = (row.get("http_status") or "").strip()
        checked_at = (row.get("checked_at") or "").strip()

        if not url_regex.match(url):
            invalid_url += 1
        if status != "pass" or not http_status.startswith("2"):
            broken += 1
        if checked_at:
            dt = parse_checked_at(checked_at)
            latest_check = dt if latest_check is None or dt > latest_check else latest_check

    now = datetime.now(timezone.utc)
    age_days = None if latest_check is None else (now - latest_check).days
    freshness_ok = age_days is not None and age_days <= sla_days

    return {
        "total_sources": total,
        "broken_urls": broken,
        "invalid_url_count": invalid_url,
        "latest_check_utc": latest_check.isoformat() if latest_check else "",
        "source_age_days": age_days if age_days is not None else -1,
        "freshness_ok": freshness_ok,
    }


def ratio_ok(rows: List[Dict[str, str]], status_field: str, pass_values: Tuple[str, ...]) -> Tuple[int, int, float]:
    total = len(rows)
    passed = sum(1 for r in rows if (r.get(status_field) or "").strip().lower() in pass_values)
    rate = (passed / total) if total else 0.0
    return passed, total, rate


def ratio_present(rows: List[Dict[str, str]], field: str) -> Tuple[int, int, float]:
    total = len(rows)
    present = sum(1 for r in rows if (r.get(field) or "").strip().lower() in {"available"})
    rate = (present / total) if total else 0.0
    return present, total, rate


def run_smoke_tests(policy: Dict, project_root: Path) -> List[Dict[str, str]]:
    chroma_cfg = policy["chroma"]
    persist_dir = project_root / chroma_cfg["persist_directory"]
    collection_name = chroma_cfg["collection_name"]

    model = SentenceTransformer(str(project_root / "models" / "bge-small-en"))
    client = chromadb.PersistentClient(path=str(persist_dir))
    collection = client.get_collection(collection_name)

    results = []
    for test in policy["smoke_tests"]:
        query = test["query"]
        expected_patterns = [p.lower() for p in test["expected_patterns"]]
        q_emb = model.encode([query], normalize_embeddings=True).tolist()
        res = collection.query(query_embeddings=q_emb, n_results=3, include=["documents", "metadatas"])
        docs = res.get("documents", [[]])[0]
        urls = []
        for m in res.get("metadatas", [[]])[0]:
            urls.append(m.get("citation_url", "") or m.get("source_url", ""))
        joined = " ".join(docs).lower()

        matched = any(p in joined for p in expected_patterns)
        results.append(
            {
                "test_name": test["name"],
                "query": query,
                "status": "pass" if matched else "fail",
                "matched_patterns": "; ".join([p for p in expected_patterns if p in joined]),
                "top_citation_urls": " | ".join(urls),
            }
        )
    return results


def atomic_ingestion_check(
    parse_rows: List[Dict[str, str]],
    extraction_rows: List[Dict[str, str]],
    upsert_rows: List[Dict[str, str]],
) -> Tuple[bool, List[str]]:
    parse_by_source = {r["source_id"]: (r.get("parse_status") or "").strip().lower() for r in parse_rows}
    extraction_by_source = {r["source_id"]: (r.get("availability_status") or "").strip().lower() for r in extraction_rows}
    upsert_count_by_source: Dict[str, int] = {}
    for r in upsert_rows:
        if (r.get("status") or "").strip().lower() == "upserted":
            sid = r.get("source_id", "")
            upsert_count_by_source[sid] = upsert_count_by_source.get(sid, 0) + 1

    failures: List[str] = []
    all_sources = sorted(set(parse_by_source.keys()) | set(extraction_by_source.keys()))
    for source_id in all_sources:
        parse_ok = parse_by_source.get(source_id) == "parsed"
        extract_ok = extraction_by_source.get(source_id) == "available"
        upsert_ok = upsert_count_by_source.get(source_id, 0) > 0
        if not (parse_ok and extract_ok and upsert_ok):
            failures.append(source_id)
    return len(failures) == 0, failures


def write_csv(path: Path, rows: List[Dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys()) if rows else []
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", required=True)
    parser.add_argument("--source-report", required=True)
    parser.add_argument("--parse-report", required=True)
    parser.add_argument("--extraction-report", required=True)
    parser.add_argument("--chunk-report", required=True)
    parser.add_argument("--embedding-report", required=True)
    parser.add_argument("--upsert-report", required=True)
    parser.add_argument("--smoke-out", required=True)
    parser.add_argument("--dashboard-out", required=True)
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parents[2]
    policy = json.loads((project_root / args.policy).read_text(encoding="utf-8"))
    url_regex = re.compile(policy["accepted_url_regex"])
    sla_days = int(policy["freshness_sla_days"])

    source_rows = load_csv(project_root / args.source_report)
    parse_rows = load_csv(project_root / args.parse_report)
    extraction_rows = load_csv(project_root / args.extraction_report)
    chunk_rows = load_csv(project_root / args.chunk_report)
    embedding_rows = load_csv(project_root / args.embedding_report)
    upsert_rows = load_csv(project_root / args.upsert_report)

    source_summary = summarize_sources(source_rows, url_regex, sla_days)
    parse_ok = ratio_ok(parse_rows, "parse_status", ("parsed",))
    extraction_ok = ratio_ok(extraction_rows, "availability_status", ("available",))
    chunk_ok = ratio_ok(chunk_rows, "status", ("valid",))
    embedding_ok = ratio_ok(embedding_rows, "status", ("embedded",))
    upsert_ok = ratio_ok(upsert_rows, "status", ("upserted",))

    completeness_fields = [
        "nav_status",
        "aum_status",
        "rating_status",
        "expense_ratio_status",
        "exit_load_status",
        "minimum_sip_status",
        "riskometer_status",
        "benchmark_status",
    ]
    completeness = {field: ratio_present(extraction_rows, field) for field in completeness_fields}

    smoke_results = run_smoke_tests(policy, project_root)
    write_csv(project_root / args.smoke_out, smoke_results)
    smoke_pass = all(r["status"] == "pass" for r in smoke_results)

    atomic_ok, atomic_fail_sources = atomic_ingestion_check(parse_rows, extraction_rows, upsert_rows)

    exit_pass = (
        source_summary["broken_urls"] == 0
        and source_summary["invalid_url_count"] == 0
        and source_summary["freshness_ok"]
        and smoke_pass
        and atomic_ok
    )

    dashboard_path = project_root / args.dashboard_out
    dashboard_path.parent.mkdir(parents=True, exist_ok=True)
    with dashboard_path.open("w", encoding="utf-8") as f:
        f.write("# Phase 1 Quality Dashboard\n\n")
        f.write("## Source Freshness\n")
        f.write(f"- Total sources: {source_summary['total_sources']}\n")
        f.write(f"- Broken URLs: {source_summary['broken_urls']}\n")
        f.write(f"- Invalid URL pattern count: {source_summary['invalid_url_count']}\n")
        f.write(f"- Latest check (UTC): {source_summary['latest_check_utc']}\n")
        f.write(f"- Source age (days): {source_summary['source_age_days']} (SLA <= {sla_days})\n")
        f.write(f"- Freshness status: {'pass' if source_summary['freshness_ok'] else 'fail'}\n\n")

        f.write("## Pipeline Success Rates\n")
        f.write(f"- Parse success rate: {parse_ok[0]}/{parse_ok[1]} ({parse_ok[2]:.2%})\n")
        f.write(f"- Extraction success rate: {extraction_ok[0]}/{extraction_ok[1]} ({extraction_ok[2]:.2%})\n")
        f.write(f"- Chunk readiness rate: {chunk_ok[0]}/{chunk_ok[1]} ({chunk_ok[2]:.2%})\n")
        f.write(f"- Embedding success rate: {embedding_ok[0]}/{embedding_ok[1]} ({embedding_ok[2]:.2%})\n")
        f.write(f"- Upsert success rate: {upsert_ok[0]}/{upsert_ok[1]} ({upsert_ok[2]:.2%})\n")
        f.write(f"- Atomic ingestion status: {'pass' if atomic_ok else 'fail'}\n")
        f.write(
            f"- Atomic ingestion failures: {', '.join(atomic_fail_sources) if atomic_fail_sources else 'none'}\n\n"
        )

        f.write("## Extraction Completeness\n")
        for field, (present, total, rate) in completeness.items():
            f.write(f"- {field}: {present}/{total} ({rate:.2%})\n")
        f.write("\n")

        f.write("## Retrieval Smoke Tests\n")
        for r in smoke_results:
            f.write(
                f"- {r['test_name']}: {r['status']} | matched: {r['matched_patterns']} | urls: {r['top_citation_urls']}\n"
            )
        f.write("\n")

        f.write("## Phase 1.5 Gate\n")
        f.write(f"- Exit gate: {'pass' if exit_pass else 'fail'}\n")
        f.write("- Gate rules: no broken URLs, freshness SLA pass, atomic ingestion, smoke tests pass.\n")

    exit_file = project_root / "phase1_5" / "reports" / "phase1_5_exit_check.md"
    with exit_file.open("w", encoding="utf-8") as f:
        f.write("# Phase 1.5 Exit Check\n\n")
        f.write(f"- Exit gate: {'pass' if exit_pass else 'fail'}\n")
        f.write(f"- Broken URLs: {source_summary['broken_urls']}\n")
        f.write(f"- Freshness SLA: {'pass' if source_summary['freshness_ok'] else 'fail'}\n")
        f.write(f"- Atomic ingestion: {'pass' if atomic_ok else 'fail'}\n")
        f.write(f"- Retrieval smoke tests: {'pass' if smoke_pass else 'fail'}\n")


if __name__ == "__main__":
    main()

