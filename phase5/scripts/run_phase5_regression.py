import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Dict


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Phase 5 regression gate")
    parser.add_argument("--report", required=True, help="Phase 5 detailed report CSV")
    parser.add_argument("--thresholds", required=True, help="Threshold config JSON")
    parser.add_argument("--gate-report", required=True, help="Output markdown gate report")
    return parser.parse_args()


def load_thresholds(path: Path) -> Dict[str, float]:
    return json.loads(path.read_text(encoding="utf-8"))


def as_bool(value: str) -> bool:
    return str(value).strip().lower() == "yes"


def safe_div(n: int, d: int) -> float:
    return (n / d) if d else 0.0


def main() -> None:
    args = parse_args()
    project_root = Path(__file__).resolve().parents[2]
    thresholds = load_thresholds(project_root / args.thresholds)

    rows = []
    with (project_root / args.report).open("r", encoding="utf-8", newline="") as fp:
        reader = csv.DictReader(fp)
        for row in reader:
            rows.append(row)

    total = len(rows)
    contract_ok = sum(1 for r in rows if as_bool(r.get("contract_ok", "no")))
    citation_ok = sum(1 for r in rows if as_bool(r.get("citation_ok", "no")))
    allowlist_violations = sum(1 for r in rows if not as_bool(r.get("citations_allowlisted", "yes")))

    factual_rows = [r for r in rows if r.get("expected_refusal", "no").lower() == "no"]
    factual_ok = sum(1 for r in factual_rows if as_bool(r.get("factual_ok", "no")))

    tp = sum(1 for r in rows if r.get("expected_refusal") == "yes" and r.get("predicted_refusal") == "yes")
    fp = sum(1 for r in rows if r.get("expected_refusal") == "no" and r.get("predicted_refusal") == "yes")
    fn = sum(1 for r in rows if r.get("expected_refusal") == "yes" and r.get("predicted_refusal") == "no")
    refusal_precision = safe_div(tp, tp + fp)
    refusal_recall = safe_div(tp, tp + fn)

    adversarial_rows = [r for r in rows if r.get("category", "") == "adversarial"]
    adversarial_failures = sum(1 for r in adversarial_rows if r.get("predicted_refusal", "no") != "yes")

    contract_rate = safe_div(contract_ok, total)
    citation_rate = safe_div(citation_ok, total)
    factual_rate = safe_div(factual_ok, len(factual_rows))

    checks = {
        "contract_compliance": contract_rate >= float(thresholds["min_contract_compliance"]),
        "citation_correctness": citation_rate >= float(thresholds["min_citation_correctness"]),
        "factual_correctness": factual_rate >= float(thresholds["min_factual_correctness"]),
        "refusal_precision": refusal_precision >= float(thresholds["min_refusal_precision"]),
        "refusal_recall": refusal_recall >= float(thresholds["min_refusal_recall"]),
        "allowlist_violations": allowlist_violations <= int(thresholds["max_allowlist_violations"]),
        "adversarial_failures": adversarial_failures <= int(thresholds["max_adversarial_failures"]),
    }
    overall_pass = all(checks.values())

    lines = [
        "# Phase 5 Regression Gate",
        "",
        "## Metrics",
        f"- Contract compliance: `{contract_rate:.2%}` (min `{float(thresholds['min_contract_compliance']):.0%}`)",
        f"- Citation correctness: `{citation_rate:.2%}` (min `{float(thresholds['min_citation_correctness']):.0%}`)",
        f"- Factual correctness: `{factual_rate:.2%}` (min `{float(thresholds['min_factual_correctness']):.0%}`)",
        f"- Refusal precision: `{refusal_precision:.2%}` (min `{float(thresholds['min_refusal_precision']):.0%}`)",
        f"- Refusal recall: `{refusal_recall:.2%}` (min `{float(thresholds['min_refusal_recall']):.0%}`)",
        f"- Allowlist violations: `{allowlist_violations}` (max `{int(thresholds['max_allowlist_violations'])}`)",
        f"- Adversarial failures: `{adversarial_failures}` (max `{int(thresholds['max_adversarial_failures'])}`)",
        "",
        "## Check status",
    ]
    for name, passed in checks.items():
        lines.append(f"- {name}: `{'PASS' if passed else 'FAIL'}`")
    lines.extend(["", f"## Overall gate: `{'PASS' if overall_pass else 'FAIL'}`", ""])

    gate_report = project_root / args.gate_report
    gate_report.parent.mkdir(parents=True, exist_ok=True)
    gate_report.write_text("\n".join(lines), encoding="utf-8")

    print(f"Phase 5 regression gate: {'PASS' if overall_pass else 'FAIL'}")
    if not overall_pass:
        sys.exit(1)


if __name__ == "__main__":
    main()
