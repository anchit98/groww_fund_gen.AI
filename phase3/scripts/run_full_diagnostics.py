import argparse
import csv
import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple

import chromadb
from sentence_transformers import SentenceTransformer


FIELD_SPECS = [
    ("expense_ratio", "expense_ratio_percent", ["expense ratio"]),
    ("exit_load", "exit_load_text", ["exit load"]),
    ("minimum_sip", "min_sip_amount_inr", ["min. for sip", "minimum sip"]),
    ("benchmark", "benchmark_full_name", ["fund benchmark", "benchmark"]),
    ("riskometer", "riskometer_label", ["riskometer", "rated very high risk", "risk"]),
    ("nav", "nav_value", ["nav:"]),
    ("aum", "aum_value_cr", ["fund size (aum)", "aum"]),
    ("rating", "rating_value", ["rating"]),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Full diagnostics for extraction, chunking, and answerability.")
    parser.add_argument("--facts", required=True, help="Path to scheme_facts.jsonl")
    parser.add_argument("--chunks", required=True, help="Path to valid chunks jsonl")
    parser.add_argument("--policy", required=True, help="Phase 3 policy json")
    parser.add_argument("--out-report", required=True, help="Detailed diagnostics CSV output")
    parser.add_argument("--out-summary", required=True, help="Diagnostics markdown summary output")
    return parser.parse_args()


def load_jsonl(path: Path) -> List[Dict]:
    rows: List[Dict] = []
    with path.open("r", encoding="utf-8") as fp:
        for line in fp:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def detect_field_in_chunks(chunks: List[Dict], markers: List[str]) -> bool:
    for c in chunks:
        txt = str(c.get("chunk_text", "")).lower()
        if any(m in txt for m in markers):
            return True
    return False


def retrieve_hit(query: str, scheme: str, collection, model, top_k: int) -> Tuple[bool, str]:
    q_emb = model.encode([query], normalize_embeddings=True).tolist()
    res = collection.query(query_embeddings=q_emb, n_results=top_k, include=["metadatas"])
    metas = res.get("metadatas", [[]])[0]
    for m in metas:
        meta = m or {}
        s = str(meta.get("scheme_name", ""))
        u = str(meta.get("source_url", "") or meta.get("citation_url", ""))
        if s.lower() == scheme.lower():
            return True, u
    return False, ""


def main() -> None:
    args = parse_args()
    root = Path(__file__).resolve().parents[2]
    facts = load_jsonl(root / args.facts)
    chunks = load_jsonl(root / args.chunks)
    policy = json.loads((root / args.policy).read_text(encoding="utf-8"))

    chunks_by_scheme: Dict[str, List[Dict]] = defaultdict(list)
    for c in chunks:
        chunks_by_scheme[str(c.get("scheme_name", ""))].append(c)

    client = chromadb.PersistentClient(path=str(root / policy["chroma"]["persist_directory"]))
    collection = client.get_collection(policy["chroma"]["collection_name"])
    model = SentenceTransformer(str(root / policy["embedding"]["model_path"]))
    top_k = int(policy.get("retrieval", {}).get("top_k", 6))

    detailed_rows: List[Dict] = []
    totals = {
        "extracted_available": 0,
        "chunk_marker_present": 0,
        "retrieval_hit": 0,
        "total_checks": 0,
    }

    for fact in facts:
        scheme = str(fact.get("scheme_name", ""))
        status_map = fact.get("field_statuses", {}) or {}
        scheme_chunks = chunks_by_scheme.get(scheme, [])

        for field_name, value_key, markers in FIELD_SPECS:
            available = str(status_map.get(field_name, "")).lower() == "available"
            if not available:
                continue

            totals["total_checks"] += 1
            totals["extracted_available"] += 1
            value_present = fact.get(value_key) not in (None, "", "not_available")
            chunk_marker = detect_field_in_chunks(scheme_chunks, markers)
            if chunk_marker:
                totals["chunk_marker_present"] += 1

            query = f"What is the {field_name.replace('_', ' ')} of {scheme}?"
            retrieval_ok, top_url = retrieve_hit(query, scheme, collection, model, top_k)
            if retrieval_ok:
                totals["retrieval_hit"] += 1

            detailed_rows.append(
                {
                    "scheme_name": scheme,
                    "field_name": field_name,
                    "extraction_available": "yes" if available else "no",
                    "extracted_value_present": "yes" if value_present else "no",
                    "valid_chunk_count_for_scheme": len(scheme_chunks),
                    "field_marker_found_in_valid_chunks": "yes" if chunk_marker else "no",
                    "retrieval_topk_contains_scheme": "yes" if retrieval_ok else "no",
                    "retrieval_reference_url": top_url,
                    "diagnostic_status": "ok" if (value_present and chunk_marker and retrieval_ok) else "needs_attention",
                }
            )

    out_report = root / args.out_report
    out_report.parent.mkdir(parents=True, exist_ok=True)
    with out_report.open("w", encoding="utf-8", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=list(detailed_rows[0].keys()))
        writer.writeheader()
        writer.writerows(detailed_rows)

    total = max(1, totals["total_checks"])
    extract_rate = totals["extracted_available"] / total
    chunk_rate = totals["chunk_marker_present"] / total
    retrieval_rate = totals["retrieval_hit"] / total
    attention = [r for r in detailed_rows if r["diagnostic_status"] != "ok"]

    summary_lines = [
        "# Full Diagnostics Summary",
        "",
        f"- Generated at (UTC): {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}",
        f"- Total field checks: {totals['total_checks']}",
        f"- Extraction availability rate: {extract_rate:.2%}",
        f"- Field marker presence in valid chunks: {chunk_rate:.2%}",
        f"- Retrieval top-k scheme hit rate: {retrieval_rate:.2%}",
        f"- Checks needing attention: {len(attention)}",
        "",
        "## Notes",
        "- This validates extraction completeness, chunk evidence presence, and retrieval discoverability per scheme-field pair.",
        "- `needs_attention` indicates at least one failure in value presence, chunk marker presence, or retrieval hit.",
        "",
    ]
    if attention:
        summary_lines.extend(
            [
                "## Attention items",
                "",
                "| scheme | field | issue |",
                "|---|---|---|",
            ]
        )
        for row in attention[:60]:
            issues = []
            if row["extracted_value_present"] != "yes":
                issues.append("missing_extracted_value")
            if row["field_marker_found_in_valid_chunks"] != "yes":
                issues.append("no_chunk_marker")
            if row["retrieval_topk_contains_scheme"] != "yes":
                issues.append("no_retrieval_hit")
            summary_lines.append(f"| {row['scheme_name']} | {row['field_name']} | {', '.join(issues)} |")

    out_summary = root / args.out_summary
    out_summary.parent.mkdir(parents=True, exist_ok=True)
    out_summary.write_text("\n".join(summary_lines) + "\n", encoding="utf-8")

    print(
        f"Diagnostics complete. checks={totals['total_checks']} "
        f"chunk_marker_rate={chunk_rate:.2%} retrieval_hit_rate={retrieval_rate:.2%} "
        f"needs_attention={len(attention)}"
    )


if __name__ == "__main__":
    main()
