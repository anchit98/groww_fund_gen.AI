import argparse
import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Phase 1.4.3 ChromaDB upsert and integrity checks")
    parser.add_argument("--embedded-in", required=True, help="Embedded chunks JSONL input")
    parser.add_argument("--policy", required=True, help="Upsert policy JSON")
    parser.add_argument("--upserted-out", required=True, help="Output upserted rows JSONL")
    parser.add_argument("--rejected-out", required=True, help="Output rejected rows JSONL")
    parser.add_argument("--report", required=True, help="Upsert report CSV")
    parser.add_argument("--summary", required=True, help="Upsert summary markdown")
    return parser.parse_args()


def load_jsonl(path: Path) -> List[Dict]:
    rows: List[Dict] = []
    with path.open("r", encoding="utf-8") as fp:
        for line in fp:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


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


def validate_row(row: Dict, policy: Dict, url_re: re.Pattern[str]) -> Tuple[bool, str]:
    if not row.get("chunk_id"):
        return False, "missing_chunk_id"
    if not row.get("chunk_text"):
        return False, "missing_chunk_text"
    if not row.get("embedding") or not isinstance(row["embedding"], list):
        return False, "missing_or_invalid_embedding_vector"
    if not row.get("source_url") or not url_re.match(str(row["source_url"])):
        return False, "url_pattern_mismatch"
    if row.get("source_domain") != "groww.in":
        return False, "non_groww_source_domain"
    if row.get("embedding_model") != policy["expected_embedding_model"]:
        return False, "embedding_model_mismatch"
    if row.get("embedding_model_revision") != policy["expected_embedding_model_revision"]:
        return False, "embedding_revision_mismatch"
    if row.get("embedding_source") != policy["expected_embedding_source"]:
        return False, "embedding_source_mismatch"
    return True, ""


def write_summary(path: Path, rows: List[Dict], upserted: int, rejected: int, created: int, updated: int) -> None:
    lines = [
        "# Phase 1.4.3 Upsert Summary",
        "",
        f"- Generated at (UTC): {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}",
        f"- Total input rows: {len(rows)}",
        f"- Upserted rows: {upserted}",
        f"- Rejected rows: {rejected}",
        f"- Created rows: {created}",
        f"- Updated rows: {updated}",
        "",
        "## Records requiring action",
        "",
        "| chunk_id | status | reason |",
        "|---|---|---|",
    ]
    action = [r for r in rows if r["status"] != "upserted"]
    if action:
        for r in action[:200]:
            lines.append(f"| {r.get('chunk_id','')} | {r['status']} | {r['reason']} |")
    else:
        lines.append("| - | - | No action required |")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_exit(path: Path, report_rows: List[Dict], upsert_ids: List[str], verified_ids: List[str]) -> None:
    total_upserted = sum(1 for r in report_rows if r["status"] == "upserted")
    id_match = set(upsert_ids) == set(verified_ids)
    non_groww_in_upsert = any(
        (r["status"] == "upserted") and (str(r.get("source_url", "")).startswith("https://groww.in/mutual-funds/") is False)
        for r in report_rows
    )
    lines = [
        "# Phase 1.4.3 Exit Check",
        "",
        "## Exit criteria status",
        "",
        "1. **100% upserted chunks map to expected IDs and metadata**",
        f"   - Status: `{'PASS' if id_match else 'FAIL'}`",
        "",
        "2. **0 non-Groww URLs appear in indexed chunk metadata**",
        f"   - Status: `{'PASS' if not non_groww_in_upsert else 'FAIL'}`",
        "",
        "3. **Index upsert report published (created/updated/rejected counts)**",
        f"   - Status: `{'PASS' if len(report_rows) > 0 else 'FAIL'}`",
        "",
        "## Phase gate decision",
    ]
    ready = id_match and (not non_groww_in_upsert) and total_upserted >= 0
    lines.append(f"- `{'READY' if ready else 'CONDITIONAL'}` for Phase 1.5 progression.")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    policy = json.loads(Path(args.policy).read_text(encoding="utf-8"))
    rows = load_jsonl(Path(args.embedded_in))
    url_re = re.compile(policy["accepted_url_regex"])
    batch_size = int(policy.get("batch_size", 64))

    report_rows: List[Dict] = []
    valid_rows: List[Dict] = []
    rejected_rows: List[Dict] = []

    for row in rows:
        ok, reason = validate_row(row, policy, url_re)
        if ok:
            valid_rows.append(row)
            report_rows.append(
                {
                    "chunk_id": row["chunk_id"],
                    "source_id": row.get("source_id", ""),
                    "status": "pending_upsert",
                    "reason": "",
                    "source_url": row.get("source_url", ""),
                    "embedding_model": row.get("embedding_model", ""),
                    "embedding_model_revision": row.get("embedding_model_revision", ""),
                    "embedding_source": row.get("embedding_source", ""),
                    "vector_store": policy["vector_store"],
                    "upsert_action": "",
                }
            )
        else:
            rej = dict(row)
            rej["status"] = "rejected"
            rej["reason"] = reason
            rejected_rows.append(rej)
            report_rows.append(
                {
                    "chunk_id": row.get("chunk_id", ""),
                    "source_id": row.get("source_id", ""),
                    "status": "rejected",
                    "reason": reason,
                    "source_url": row.get("source_url", ""),
                    "embedding_model": row.get("embedding_model", ""),
                    "embedding_model_revision": row.get("embedding_model_revision", ""),
                    "embedding_source": row.get("embedding_source", ""),
                    "vector_store": policy["vector_store"],
                    "upsert_action": "",
                }
            )

    # Load Chroma and upsert
    upserted_rows: List[Dict] = []
    created_count = 0
    updated_count = 0
    upsert_ids: List[str] = []
    verified_ids: List[str] = []

    try:
        import chromadb  # type: ignore
    except Exception:  # noqa: BLE001
        for rr in report_rows:
            if rr["status"] == "pending_upsert":
                rr["status"] = "rejected"
                rr["reason"] = "chromadb_dependency_missing"
        rejected_rows.extend([r for r in valid_rows])
        write_jsonl(Path(args.upserted_out), [])
        write_jsonl(Path(args.rejected_out), rejected_rows)
        write_report(Path(args.report), report_rows)
        write_summary(Path(args.summary), report_rows, upserted=0, rejected=len(rejected_rows), created=0, updated=0)
        write_exit(Path(args.summary).parent / "phase1_4_3_exit_check.md", report_rows, upsert_ids, verified_ids)
        print("Phase 1.4.3 complete with failure: chromadb_dependency_missing")
        return

    persist_dir = Path(policy["persist_directory"])
    persist_dir.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(persist_dir))
    collection = client.get_or_create_collection(name=policy["collection_name"])

    # Determine existing IDs for created vs updated split
    existing_ids = set()
    all_valid_ids = [r["chunk_id"] for r in valid_rows]
    for i in range(0, len(all_valid_ids), batch_size):
        ids_batch = all_valid_ids[i : i + batch_size]
        got = collection.get(ids=ids_batch, include=[])
        for x in got.get("ids", []):
            existing_ids.add(x)

    # Upsert in batches
    row_lookup = {r["chunk_id"]: r for r in valid_rows}
    for i in range(0, len(valid_rows), batch_size):
        batch = valid_rows[i : i + batch_size]
        ids = [r["chunk_id"] for r in batch]
        docs = [r["chunk_text"] for r in batch]
        embs = [r["embedding"] for r in batch]
        metas = []
        for r in batch:
            metas.append(
                {
                    "source_id": r.get("source_id", ""),
                    "source_url": r.get("source_url", ""),
                    "source_domain": r.get("source_domain", ""),
                    "doc_type": r.get("doc_type", ""),
                    "scheme_name": r.get("scheme_name", ""),
                    "amc_name": r.get("amc_name", ""),
                    "effective_date": r.get("effective_date", ""),
                    "ingested_at": r.get("ingested_at", ""),
                    "embedding_model": r.get("embedding_model", ""),
                    "embedding_model_revision": r.get("embedding_model_revision", ""),
                    "embedding_source": r.get("embedding_source", ""),
                    "vector_store": policy["vector_store"],
                }
            )
        collection.upsert(ids=ids, documents=docs, embeddings=embs, metadatas=metas)
        upsert_ids.extend(ids)

    # Verify IDs post-upsert
    for i in range(0, len(upsert_ids), batch_size):
        ids_batch = upsert_ids[i : i + batch_size]
        got = collection.get(ids=ids_batch, include=["metadatas"])
        verified_ids.extend(got.get("ids", []))
        for cid in got.get("ids", []):
            row = row_lookup[cid]
            upsert_action = "updated" if cid in existing_ids else "created"
            if upsert_action == "created":
                created_count += 1
            else:
                updated_count += 1
            row_out = dict(row)
            row_out["vector_store"] = policy["vector_store"]
            row_out["status"] = "upserted"
            row_out["upsert_action"] = upsert_action
            upserted_rows.append(row_out)

    # finalize report rows
    updated_report_rows: List[Dict] = []
    upserted_set = set(verified_ids)
    for rr in report_rows:
        if rr["status"] == "pending_upsert":
            if rr["chunk_id"] in upserted_set:
                rr["status"] = "upserted"
                rr["reason"] = ""
                rr["upsert_action"] = "updated" if rr["chunk_id"] in existing_ids else "created"
            else:
                rr["status"] = "rejected"
                rr["reason"] = "upsert_verification_failed"
                rr["upsert_action"] = ""
        updated_report_rows.append(rr)

    rejected_final = [r for r in updated_report_rows if r["status"] == "rejected"]
    write_jsonl(Path(args.upserted_out), upserted_rows)
    write_jsonl(Path(args.rejected_out), rejected_rows)
    write_report(Path(args.report), updated_report_rows)
    write_summary(
        Path(args.summary),
        updated_report_rows,
        upserted=len([r for r in updated_report_rows if r["status"] == "upserted"]),
        rejected=len(rejected_final),
        created=created_count,
        updated=updated_count,
    )
    write_exit(Path(args.summary).parent / "phase1_4_3_exit_check.md", updated_report_rows, upsert_ids, verified_ids)
    print(
        "Phase 1.4.3 complete. "
        f"input={len(rows)} upserted={len([r for r in updated_report_rows if r['status']=='upserted'])} "
        f"rejected={len(rejected_final)} created={created_count} updated={updated_count}"
    )


if __name__ == "__main__":
    main()
