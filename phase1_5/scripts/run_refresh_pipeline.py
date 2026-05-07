import csv
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path


def run_step(repo_root: Path, command: list[str]) -> tuple[int, float]:
    started = datetime.now(timezone.utc)
    print(f"Running: {' '.join(command)}")
    completed = subprocess.run(command, cwd=str(repo_root), check=False)
    finished = datetime.now(timezone.utc)
    elapsed = round((finished - started).total_seconds(), 3)
    if completed.returncode != 0:
        return completed.returncode, elapsed
    return 0, elapsed


def resolve_registry_input(repo_root: Path) -> str:
    target_url = os.getenv("INGEST_TARGET_URL", "").strip().rstrip("/")
    default_registry = "phase1_1/data/source_registry_phase1_1.csv"
    if not target_url:
        return default_registry

    registry_path = repo_root / default_registry
    with open(registry_path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = list(reader.fieldnames or [])

    filtered_rows = []
    for row in rows:
        row_url = (row.get("url") or "").strip().rstrip("/")
        if row_url == target_url:
            filtered_rows.append(row)

    if not filtered_rows:
        raise SystemExit(f"INGEST_TARGET_URL not found in registry: {target_url}")

    tmp_dir = repo_root / "phase1_5" / "reports" / "tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        newline="",
        suffix=".csv",
        prefix="single_url_registry_",
        dir=tmp_dir,
        delete=False,
    ) as tmp_file:
        writer = csv.DictWriter(tmp_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(filtered_rows)
        return str(Path(tmp_file.name).relative_to(repo_root)).replace("\\", "/")


def write_full_refresh_status(repo_root: Path, started_at: datetime) -> None:
    finished_at = datetime.now(timezone.utc)
    payload = {
        "mode": "full",
        "started_at": started_at.isoformat(),
        "last_full_refresh_at": finished_at.isoformat(),
        "elapsed_seconds": round((finished_at - started_at).total_seconds(), 1),
    }
    status_path = repo_root / "phase1_5" / "reports" / "full_refresh_status.json"
    status_path.parent.mkdir(parents=True, exist_ok=True)
    with open(status_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=True, indent=2)


def write_step_timings(repo_root: Path, rows: list[dict], mode: str) -> None:
    reports_dir = repo_root / "phase1_5" / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    json_path = reports_dir / "pipeline_step_timings.json"
    csv_path = reports_dir / "pipeline_step_timings.csv"

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": mode,
        "rows": rows,
        "total_elapsed_seconds": round(sum(float(r.get("elapsed_seconds", 0.0)) for r in rows), 3),
    }
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=True, indent=2)

    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "step_number",
                "script",
                "elapsed_seconds",
                "return_code",
                "started_at",
                "finished_at",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    py = sys.executable
    started_at = datetime.now(timezone.utc)
    registry_input = resolve_registry_input(repo_root)
    is_full_refresh = "INGEST_TARGET_URL" not in os.environ or not os.getenv("INGEST_TARGET_URL", "").strip()

    steps = [
        [
            py,
            "phase1_1/scripts/validate_source_intake.py",
            "--input",
            registry_input,
            "--policy",
            "phase1_1/policy/source_intake_policy.json",
            "--report",
            "phase1_1/reports/source_validation_report.csv",
            "--summary",
            "phase1_1/reports/source_validation_summary.md",
        ],
        [
            py,
            "phase1_2/scripts/fetch_and_parse.py",
            "--input",
            registry_input,
            "--policy",
            "phase1_2/policy/fetch_parse_policy.json",
            "--report",
            "phase1_2/reports/parse_report.csv",
            "--summary",
            "phase1_2/reports/parse_summary.md",
            "--parsed",
            "phase1_2/reports/parsed/parsed_documents.jsonl",
        ],
        [
            py,
            "phase1_3/scripts/extract_fields.py",
            "--parsed",
            "phase1_2/reports/parsed/parsed_documents.jsonl",
            "--registry",
            registry_input,
            "--policy",
            "phase1_3/policy/extraction_policy.json",
            "--facts-out",
            "phase1_3/reports/extracted/scheme_facts.jsonl",
            "--process-out",
            "phase1_3/reports/extracted/scheme_process_guides.jsonl",
            "--report",
            "phase1_3/reports/extraction_report.csv",
            "--summary",
            "phase1_3/reports/extraction_summary.md",
        ],
        [
            py,
            "phase1_4_1/scripts/build_chunks_and_metadata.py",
            "--parsed",
            "phase1_2/reports/parsed/parsed_documents.jsonl",
            "--facts",
            "phase1_3/reports/extracted/scheme_facts.jsonl",
            "--policy",
            "phase1_4_1/policy/chunking_policy.json",
            "--valid-out",
            "phase1_4_1/reports/chunks/chunks_valid.jsonl",
            "--quarantine-out",
            "phase1_4_1/reports/chunks/chunks_quarantined.jsonl",
            "--rejected-out",
            "phase1_4_1/reports/chunks/chunks_rejected.jsonl",
            "--report",
            "phase1_4_1/reports/metadata_validation_report.csv",
            "--summary",
            "phase1_4_1/reports/metadata_validation_summary.md",
        ],
        [
            py,
            "phase1_4_2/scripts/generate_embeddings.py",
            "--chunks-in",
            "phase1_4_1/reports/chunks/chunks_valid.jsonl",
            "--policy",
            "phase1_4_2/policy/embedding_policy.json",
            "--embedded-out",
            "phase1_4_2/reports/embeddings/chunks_embedded.jsonl",
            "--failed-out",
            "phase1_4_2/reports/embeddings/chunks_embedding_failed.jsonl",
            "--report",
            "phase1_4_2/reports/embedding_report.csv",
            "--summary",
            "phase1_4_2/reports/embedding_summary.md",
        ],
        [
            py,
            "phase1_4_3/scripts/upsert_to_chromadb.py",
            "--embedded-in",
            "phase1_4_2/reports/embeddings/chunks_embedded.jsonl",
            "--policy",
            "phase1_4_3/policy/upsert_policy.json",
            "--upserted-out",
            "phase1_4_3/reports/upserted_chunks.jsonl",
            "--rejected-out",
            "phase1_4_3/reports/rejected_chunks.jsonl",
            "--report",
            "phase1_4_3/reports/upsert_report.csv",
            "--summary",
            "phase1_4_3/reports/upsert_summary.md",
        ],
        [
            py,
            "phase1_5/scripts/run_phase1_5_checks.py",
            "--policy",
            "phase1_5/policy/phase1_5_policy.json",
            "--source-report",
            "phase1_1/reports/source_validation_report.csv",
            "--parse-report",
            "phase1_2/reports/parse_report.csv",
            "--extraction-report",
            "phase1_3/reports/extraction_report.csv",
            "--chunk-report",
            "phase1_4_1/reports/metadata_validation_report.csv",
            "--embedding-report",
            "phase1_4_2/reports/embedding_report.csv",
            "--upsert-report",
            "phase1_4_3/reports/upsert_report.csv",
            "--smoke-out",
            "phase1_5/reports/smoke_test_report.csv",
            "--dashboard-out",
            "phase1_5/reports/phase1_quality_dashboard.md",
        ],
    ]

    timing_rows: list[dict] = []
    for index, step in enumerate(steps, start=1):
        step_started = datetime.now(timezone.utc)
        code, elapsed = run_step(repo_root, step)
        step_finished = datetime.now(timezone.utc)
        timing_rows.append(
            {
                "step_number": index,
                "script": step[1] if len(step) > 1 else "unknown",
                "elapsed_seconds": elapsed,
                "return_code": code,
                "started_at": step_started.isoformat(),
                "finished_at": step_finished.isoformat(),
            }
        )
        if code != 0:
            write_step_timings(repo_root, timing_rows, mode=("full" if is_full_refresh else "targeted"))
            raise SystemExit(code)

    if is_full_refresh:
        write_full_refresh_status(repo_root, started_at)
    write_step_timings(repo_root, timing_rows, mode=("full" if is_full_refresh else "targeted"))

    print("Refresh pipeline completed.")


if __name__ == "__main__":
    main()
