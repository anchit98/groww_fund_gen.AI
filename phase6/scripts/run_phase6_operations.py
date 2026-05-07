import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Phase 6 operations and continuous refresh checks")
    parser.add_argument("--policy", required=True, help="Path to phase6 operations policy JSON")
    parser.add_argument("--status-out", required=True, help="Output JSON status file")
    parser.add_argument("--summary-out", required=True, help="Output markdown summary file")
    parser.add_argument("--change-log-out", required=True, help="Output markdown source change log")
    parser.add_argument(
        "--update-baseline",
        action="store_true",
        help="Update drift baseline with latest phase5 evaluation metrics",
    )
    return parser.parse_args()


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_csv_rows(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as fp:
        return list(csv.DictReader(fp))


def parse_dt(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:  # noqa: BLE001
        return None


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:  # noqa: BLE001
        return default


def compute_phase5_metrics(report_rows: List[Dict[str, str]]) -> Dict[str, float]:
    total = len(report_rows)
    if total == 0:
        return {
            "contract_rate": 0.0,
            "citation_rate": 0.0,
            "factual_rate": 0.0,
            "refusal_precision": 0.0,
            "refusal_recall": 0.0,
            "no_answer_rate": 0.0,
        }

    contract_ok = sum(1 for r in report_rows if r.get("contract_ok") == "yes")
    citation_ok = sum(1 for r in report_rows if r.get("citation_ok") == "yes")
    factual_rows = [r for r in report_rows if r.get("expected_refusal") == "no"]
    factual_ok = sum(1 for r in factual_rows if r.get("factual_ok") == "yes")

    tp = sum(1 for r in report_rows if r.get("expected_refusal") == "yes" and r.get("predicted_refusal") == "yes")
    fp = sum(1 for r in report_rows if r.get("expected_refusal") == "no" and r.get("predicted_refusal") == "yes")
    fn = sum(1 for r in report_rows if r.get("expected_refusal") == "yes" and r.get("predicted_refusal") == "no")
    refusal_precision = tp / (tp + fp) if (tp + fp) else 0.0
    refusal_recall = tp / (tp + fn) if (tp + fn) else 0.0

    no_answer_count = 0
    for row in report_rows:
        response = (row.get("response") or "").strip().lower()
        if response.startswith("information unavailable"):
            no_answer_count += 1

    return {
        "contract_rate": contract_ok / total,
        "citation_rate": citation_ok / total,
        "factual_rate": factual_ok / len(factual_rows) if factual_rows else 0.0,
        "refusal_precision": refusal_precision,
        "refusal_recall": refusal_recall,
        "no_answer_rate": no_answer_count / total,
    }


def extract_recent_ingestion_failures(log_path: Path) -> Tuple[int, List[str]]:
    if not log_path.exists():
        return 0, []
    lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    failures = [line for line in lines if "traceback" in line.lower() or "error" in line.lower() or "failed" in line.lower()]
    return len(failures), failures[-10:]


def read_registry_urls(path: Path) -> List[str]:
    rows = load_csv_rows(path)
    urls = []
    for row in rows:
        url = (row.get("url") or "").strip().rstrip("/")
        if url:
            urls.append(url)
    return sorted(set(urls))


def build_change_log(current_urls: List[str], snapshot_path: Path) -> Dict[str, List[str]]:
    previous: List[str] = []
    if snapshot_path.exists():
        try:
            previous = json.loads(snapshot_path.read_text(encoding="utf-8")).get("urls", [])
        except Exception:  # noqa: BLE001
            previous = []
    prev_set = set(previous)
    curr_set = set(current_urls)
    added = sorted(curr_set - prev_set)
    removed = sorted(prev_set - curr_set)
    payload = {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "urls": current_urls,
    }
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
    return {"added": added, "removed": removed}


def main() -> None:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[2]
    policy = load_json(repo_root / args.policy)

    full_refresh_path = repo_root / "phase1_5/reports/full_refresh_status.json"
    smoke_path = repo_root / "phase1_5/reports/smoke_test_report.csv"
    manual_log_path = repo_root / "logs/manual_ingestion.log"
    phase5_report_path = repo_root / "phase5/reports/evaluation_report.csv"
    baseline_path = repo_root / "phase6/reports/drift_baseline.json"
    registry_path = repo_root / "phase1_1/data/source_registry_phase1_1.csv"
    source_snapshot_path = repo_root / "phase6/reports/source_registry_snapshot.json"

    now = datetime.now(timezone.utc)
    alerts: List[str] = []

    last_full_refresh_at = None
    elapsed_since_refresh_hours = None
    if full_refresh_path.exists():
        refresh_payload = load_json(full_refresh_path)
        last_full_refresh_at = parse_dt(str(refresh_payload.get("last_full_refresh_at", "")))
    if last_full_refresh_at:
        elapsed_since_refresh_hours = (now - last_full_refresh_at).total_seconds() / 3600.0
        if elapsed_since_refresh_hours > float(policy["max_hours_since_full_refresh"]):
            alerts.append(
                f"Stale full refresh: {elapsed_since_refresh_hours:.1f}h since last full refresh "
                f"(threshold {policy['max_hours_since_full_refresh']}h)."
            )
    else:
        alerts.append("Missing full refresh heartbeat (phase1_5/reports/full_refresh_status.json).")

    smoke_rows = load_csv_rows(smoke_path)
    recent_refresh_failures = 0
    for row in smoke_rows:
        if (row.get("status") or "").strip().lower() in {"fail", "failed", "error"}:
            recent_refresh_failures += 1
    if recent_refresh_failures > int(policy["max_consecutive_refresh_failures"]):
        alerts.append(
            f"Refresh QA failures exceed threshold: {recent_refresh_failures} > {policy['max_consecutive_refresh_failures']}."
        )

    manual_failure_count, manual_failure_samples = extract_recent_ingestion_failures(manual_log_path)
    if manual_failure_count > 0:
        alerts.append(f"Manual ingestion log has {manual_failure_count} failure-like lines.")

    phase5_rows = load_csv_rows(phase5_report_path)
    phase5_metrics = compute_phase5_metrics(phase5_rows)
    if phase5_metrics["no_answer_rate"] > float(policy["max_no_answer_rate"]):
        alerts.append(
            f"No-answer rate spike: {phase5_metrics['no_answer_rate']:.2%} > {float(policy['max_no_answer_rate']):.2%}."
        )

    allowlist_violations = sum(1 for r in phase5_rows if (r.get("citations_allowlisted") or "yes") != "yes")
    if allowlist_violations > int(policy["max_allowlist_violations"]):
        alerts.append(
            f"Source-link allowlist violations: {allowlist_violations} > {policy['max_allowlist_violations']}."
        )

    baseline = {}
    if baseline_path.exists():
        baseline = load_json(baseline_path)
    baseline_metrics = baseline.get("metrics", {})

    def maybe_alert_drop(metric_name: str, threshold_key: str) -> None:
        current = safe_float(phase5_metrics.get(metric_name), 0.0)
        if metric_name not in baseline_metrics:
            return
        previous = safe_float(baseline_metrics.get(metric_name), 0.0)
        drop = previous - current
        if drop > safe_float(policy.get(threshold_key), 0.0):
            alerts.append(
                f"Drift detected for {metric_name}: dropped by {drop:.2%} "
                f"(from {previous:.2%} to {current:.2%})."
            )

    maybe_alert_drop("refusal_precision", "max_refusal_precision_drop")
    maybe_alert_drop("refusal_recall", "max_refusal_recall_drop")
    maybe_alert_drop("factual_rate", "max_factual_correctness_drop")

    if args.update_baseline or not baseline_path.exists():
        baseline_payload = {
            "updated_at": now.isoformat(),
            "metrics": phase5_metrics,
        }
        baseline_path.parent.mkdir(parents=True, exist_ok=True)
        baseline_path.write_text(json.dumps(baseline_payload, ensure_ascii=True, indent=2), encoding="utf-8")

    current_urls = read_registry_urls(registry_path)
    changes = build_change_log(current_urls, source_snapshot_path)

    status_payload = {
        "generated_at": now.isoformat(),
        "policy": policy,
        "refresh_schedule_utc_cron": policy["refresh_schedule_utc_cron"],
        "last_full_refresh_at": last_full_refresh_at.isoformat() if last_full_refresh_at else None,
        "elapsed_since_refresh_hours": round(elapsed_since_refresh_hours, 2) if elapsed_since_refresh_hours is not None else None,
        "recent_refresh_failures": recent_refresh_failures,
        "manual_ingestion_failure_lines": manual_failure_count,
        "phase5_metrics": phase5_metrics,
        "allowlist_violations": allowlist_violations,
        "source_registry_url_count": len(current_urls),
        "source_registry_changes": changes,
        "alerts": alerts,
        "status": "alert" if alerts else "ok",
    }

    status_out = repo_root / args.status_out
    status_out.parent.mkdir(parents=True, exist_ok=True)
    status_out.write_text(json.dumps(status_payload, ensure_ascii=True, indent=2), encoding="utf-8")

    summary_lines = [
        "# Phase 6 Operations Summary",
        "",
        f"- Generated at (UTC): {now.strftime('%Y-%m-%dT%H:%M:%SZ')}",
        f"- Scheduler cron (UTC): `{policy['refresh_schedule_utc_cron']}`",
        f"- Last full refresh at: `{status_payload['last_full_refresh_at']}`",
        f"- Hours since full refresh: `{status_payload['elapsed_since_refresh_hours']}`",
        f"- Refresh QA failures observed: `{recent_refresh_failures}`",
        f"- Manual ingestion failure-like lines: `{manual_failure_count}`",
        f"- Source registry count: `{len(current_urls)}`",
        f"- Source changes this run: `+{len(changes['added'])} / -{len(changes['removed'])}`",
        f"- Ops status: `{'ALERT' if alerts else 'OK'}`",
        "",
        "## Drift Metrics",
        f"- Contract compliance: `{phase5_metrics['contract_rate']:.2%}`",
        f"- Citation correctness: `{phase5_metrics['citation_rate']:.2%}`",
        f"- Factual correctness: `{phase5_metrics['factual_rate']:.2%}`",
        f"- Refusal precision: `{phase5_metrics['refusal_precision']:.2%}`",
        f"- Refusal recall: `{phase5_metrics['refusal_recall']:.2%}`",
        f"- No-answer rate: `{phase5_metrics['no_answer_rate']:.2%}`",
        "",
        "## Alerts",
    ]
    if alerts:
        summary_lines.extend([f"- {a}" for a in alerts])
    else:
        summary_lines.append("- None.")

    if manual_failure_samples:
        summary_lines.extend(["", "## Recent Manual Ingestion Failure Samples"])
        summary_lines.extend([f"- `{line}`" for line in manual_failure_samples[:5]])

    summary_out = repo_root / args.summary_out
    summary_out.parent.mkdir(parents=True, exist_ok=True)
    summary_out.write_text("\n".join(summary_lines) + "\n", encoding="utf-8")

    change_lines = [
        "# Phase 6 Source Change Log",
        "",
        f"- Captured at (UTC): {now.strftime('%Y-%m-%dT%H:%M:%SZ')}",
        f"- Total registry URLs: {len(current_urls)}",
        "",
        "## Added URLs",
    ]
    if changes["added"]:
        change_lines.extend([f"- {url}" for url in changes["added"]])
    else:
        change_lines.append("- None.")
    change_lines.extend(["", "## Removed URLs"])
    if changes["removed"]:
        change_lines.extend([f"- {url}" for url in changes["removed"]])
    else:
        change_lines.append("- None.")

    change_out = repo_root / args.change_log_out
    change_out.parent.mkdir(parents=True, exist_ok=True)
    change_out.write_text("\n".join(change_lines) + "\n", encoding="utf-8")

    print(f"Phase 6 operations complete. status={status_payload['status']} alerts={len(alerts)}")


if __name__ == "__main__":
    main()
