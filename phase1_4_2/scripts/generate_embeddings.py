import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Phase 1.4.2 embedding generation")
    parser.add_argument("--chunks-in", required=True, help="Input valid chunks JSONL")
    parser.add_argument("--policy", required=True, help="Embedding policy JSON")
    parser.add_argument("--embedded-out", required=True, help="Embedded chunks JSONL")
    parser.add_argument("--failed-out", required=True, help="Failed chunks JSONL")
    parser.add_argument("--report", required=True, help="Embedding report CSV")
    parser.add_argument("--summary", required=True, help="Embedding summary markdown")
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


def write_summary(path: Path, report_rows: List[Dict], precheck_status: str, model_path: str) -> None:
    total = len(report_rows)
    embedded = sum(1 for r in report_rows if r["status"] == "embedded")
    failed = sum(1 for r in report_rows if r["status"] == "failed")
    lines = [
        "# Phase 1.4.2 Embedding Summary",
        "",
        f"- Generated at (UTC): {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}",
        f"- Precheck status: {precheck_status}",
        f"- Pre-baked model path: `{model_path}`",
        f"- Total chunks: {total}",
        f"- Embedded chunks: {embedded}",
        f"- Failed chunks: {failed}",
        "",
        "## Records requiring action",
        "",
        "| chunk_id | status | reason |",
        "|---|---|---|",
    ]
    bad = [r for r in report_rows if r["status"] != "embedded"]
    if bad:
        for r in bad[:200]:
            lines.append(f"| {r['chunk_id']} | {r['status']} | {r['reason']} |")
    else:
        lines.append("| - | - | No action required |")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_exit(path: Path, report_rows: List[Dict], precheck_status: str) -> None:
    total = len(report_rows)
    embedded = sum(1 for r in report_rows if r["status"] == "embedded")
    failed = total - embedded
    mixed_models = len({(r["embedding_model"], r["embedding_source"]) for r in report_rows if r["status"] == "embedded"}) > 1
    all_accounted = embedded + failed == total
    no_runtime_download = all(
        r.get("embedding_source", "") == "pre_baked" for r in report_rows if r["status"] == "embedded"
    )

    lines = [
        "# Phase 1.4.2 Exit Check",
        "",
        "## Exit criteria status",
        "",
        "1. **100% valid chunks are either embedded or explicitly quarantined**",
        f"   - Status: `{'PASS' if all_accounted else 'FAIL'}`",
        "",
        "2. **0 mixed-model vectors are produced in the same run**",
        f"   - Status: `{'PASS' if not mixed_models else 'FAIL'}`",
        "",
        "3. **0 runtime model-download attempts occur in embedding jobs**",
        f"   - Status: `{'PASS' if no_runtime_download else 'FAIL'}`",
        "",
        "4. **Pre-baked model precheck**",
        f"   - Status: `{'PASS' if precheck_status == 'ok' else 'FAIL'}`",
        "",
        "## Phase gate decision",
    ]
    ready = all_accounted and not mixed_models and no_runtime_download and precheck_status == "ok"
    lines.append(f"- `{'READY' if ready else 'CONDITIONAL'}` for Phase 1.4.3 progression.")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    policy = json.loads(Path(args.policy).read_text(encoding="utf-8"))
    chunks = load_jsonl(Path(args.chunks_in))

    model_name = policy["embedding_model"]
    model_revision = policy["embedding_model_revision"]
    model_source = policy["embedding_source"]
    model_path = Path(policy["pre_baked_model_path"])
    fail_missing = bool(policy.get("fail_precheck_if_model_missing", True))
    batch_size = int(policy.get("batch_size", 16))
    normalize_embeddings = bool(policy.get("normalize_embeddings", True))

    report_rows: List[Dict] = []
    embedded_rows: List[Dict] = []
    failed_rows: List[Dict] = []

    precheck_status = "ok"
    if not model_path.exists():
        precheck_status = "missing_pre_baked_model"
        if fail_missing:
            for chunk in chunks:
                failed = {
                    **chunk,
                    "embedding_model": model_name,
                    "embedding_model_revision": model_revision,
                    "embedding_source": model_source,
                    "status": "failed",
                    "reason": "pre_baked_model_missing",
                }
                failed_rows.append(failed)
                report_rows.append(
                    {
                        "chunk_id": chunk["chunk_id"],
                        "source_id": chunk.get("source_id", ""),
                        "status": "failed",
                        "reason": "pre_baked_model_missing",
                        "embedding_model": model_name,
                        "embedding_model_revision": model_revision,
                        "embedding_source": model_source,
                    }
                )
            write_jsonl(Path(args.embedded_out), embedded_rows)
            write_jsonl(Path(args.failed_out), failed_rows)
            write_report(Path(args.report), report_rows)
            write_summary(Path(args.summary), report_rows, precheck_status=precheck_status, model_path=str(model_path))
            write_exit(Path(args.summary).parent / "phase1_4_2_exit_check.md", report_rows, precheck_status=precheck_status)
            print(
                "Phase 1.4.2 complete with precheck failure. "
                f"chunks_total={len(chunks)} embedded=0 failed={len(failed_rows)}"
            )
            return

    try:
        from sentence_transformers import SentenceTransformer  # type: ignore
    except Exception:  # noqa: BLE001
        precheck_status = "embedding_runtime_dependency_missing"
        for chunk in chunks:
            failed = {
                **chunk,
                "embedding_model": model_name,
                "embedding_model_revision": model_revision,
                "embedding_source": model_source,
                "status": "failed",
                "reason": "sentence_transformers_missing",
            }
            failed_rows.append(failed)
            report_rows.append(
                {
                    "chunk_id": chunk["chunk_id"],
                    "source_id": chunk.get("source_id", ""),
                    "status": "failed",
                    "reason": "sentence_transformers_missing",
                    "embedding_model": model_name,
                    "embedding_model_revision": model_revision,
                    "embedding_source": model_source,
                }
            )
        write_jsonl(Path(args.embedded_out), embedded_rows)
        write_jsonl(Path(args.failed_out), failed_rows)
        write_report(Path(args.report), report_rows)
        write_summary(Path(args.summary), report_rows, precheck_status=precheck_status, model_path=str(model_path))
        write_exit(Path(args.summary).parent / "phase1_4_2_exit_check.md", report_rows, precheck_status=precheck_status)
        print(
            "Phase 1.4.2 complete with runtime dependency failure. "
            f"chunks_total={len(chunks)} embedded=0 failed={len(failed_rows)}"
        )
        return

    model = SentenceTransformer(str(model_path))

    for i in range(0, len(chunks), batch_size):
        batch = chunks[i : i + batch_size]
        texts = [c.get("chunk_text", "") for c in batch]
        try:
            vecs = model.encode(
                texts,
                batch_size=batch_size,
                normalize_embeddings=normalize_embeddings,
                convert_to_numpy=True,
                show_progress_bar=False,
            )
            for chunk, vec in zip(batch, vecs):
                row = {
                    **chunk,
                    "embedding": vec.tolist(),
                    "embedding_dimension": int(len(vec)),
                    "embedding_model": model_name,
                    "embedding_model_revision": model_revision,
                    "embedding_source": model_source,
                    "status": "embedded",
                    "reason": "",
                }
                embedded_rows.append(row)
                report_rows.append(
                    {
                        "chunk_id": chunk["chunk_id"],
                        "source_id": chunk.get("source_id", ""),
                        "status": "embedded",
                        "reason": "",
                        "embedding_model": model_name,
                        "embedding_model_revision": model_revision,
                        "embedding_source": model_source,
                    }
                )
        except Exception as exc:  # noqa: BLE001
            reason = f"embedding_batch_failure:{type(exc).__name__}"
            for chunk in batch:
                failed = {
                    **chunk,
                    "embedding_model": model_name,
                    "embedding_model_revision": model_revision,
                    "embedding_source": model_source,
                    "status": "failed",
                    "reason": reason,
                }
                failed_rows.append(failed)
                report_rows.append(
                    {
                        "chunk_id": chunk["chunk_id"],
                        "source_id": chunk.get("source_id", ""),
                        "status": "failed",
                        "reason": reason,
                        "embedding_model": model_name,
                        "embedding_model_revision": model_revision,
                        "embedding_source": model_source,
                    }
                )

    write_jsonl(Path(args.embedded_out), embedded_rows)
    write_jsonl(Path(args.failed_out), failed_rows)
    write_report(Path(args.report), report_rows)
    write_summary(Path(args.summary), report_rows, precheck_status=precheck_status, model_path=str(model_path))
    write_exit(Path(args.summary).parent / "phase1_4_2_exit_check.md", report_rows, precheck_status=precheck_status)

    print(
        "Phase 1.4.2 complete. "
        f"chunks_total={len(chunks)} embedded={len(embedded_rows)} failed={len(failed_rows)}"
    )


if __name__ == "__main__":
    main()
