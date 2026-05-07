import argparse
import csv
import json
import re
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Phase 5 evaluation, QA, and hardening runner")
    parser.add_argument("--cases", required=True, help="Path to evaluation cases JSON")
    parser.add_argument("--report", required=True, help="Output detailed CSV report")
    parser.add_argument("--summary", required=True, help="Output markdown summary")
    parser.add_argument("--exit-check", required=True, help="Output markdown exit check")
    parser.add_argument("--api-base-url", default="http://127.0.0.1:8001", help="Backend base URL")
    return parser.parse_args()


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    rows: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fp:
        for line in fp:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def post_query(api_base_url: str, query: str) -> Tuple[Dict[str, Any], str]:
    payload = json.dumps({"query": query}).encode("utf-8")
    req = urllib.request.Request(
        f"{api_base_url.rstrip('/')}/query",
        data=payload,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as response:
            data = json.loads(response.read().decode("utf-8"))
            return data, ""
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        return {}, f"http_error:{e.code}:{body}"
    except Exception as e:  # noqa: BLE001
        return {}, f"request_error:{e}"


def sentence_count(text: str) -> int:
    parts = [p.strip() for p in re.split(r"(?<=[.!?])\s+", text.strip()) if p.strip()]
    return len(parts)


def has_inline_citation_or_footer(text: str) -> bool:
    t = text.lower()
    if "citation:" in t:
        return True
    if "last updated from sources:" in t:
        return True
    if re.search(r"\bas of\s+\d{4}-\d{2}-\d{2}\b", t):
        return True
    if re.search(r"https?://", t):
        return True
    return False


def normalize_text(text: str) -> str:
    t = text.lower().replace("&", " and ")
    t = re.sub(r"[^a-z0-9.%\s]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def expected_field_signals(field: str, fact_row: Dict[str, Any]) -> List[str]:
    if field == "expense_ratio" and fact_row.get("expense_ratio_percent") is not None:
        return [str(fact_row["expense_ratio_percent"]).lower(), "expense ratio"]
    if field == "exit_load" and fact_row.get("exit_load_text"):
        text = str(fact_row["exit_load_text"]).lower()
        tokens = [x for x in re.findall(r"[a-z0-9.%]+", text) if len(x) >= 3]
        return (tokens[:4] or ["exit load"]) + ["exit load"]
    if field == "minimum_sip" and fact_row.get("min_sip_amount_inr") is not None:
        return [str(fact_row["min_sip_amount_inr"]), "sip"]
    if field == "benchmark" and fact_row.get("benchmark_full_name"):
        bench = str(fact_row["benchmark_full_name"]).lower()
        tokens = [x for x in re.findall(r"[a-z0-9]+", bench) if len(x) >= 3]
        return (tokens[:4] or ["benchmark"]) + ["benchmark"]
    if field == "riskometer" and fact_row.get("riskometer_label"):
        return [str(fact_row["riskometer_label"]).lower(), "risk"]
    if field == "nav" and fact_row.get("nav_value") is not None:
        return [str(fact_row["nav_value"]).lower(), "nav"]
    if field == "aum" and fact_row.get("aum_value_cr") is not None:
        return [str(fact_row["aum_value_cr"]).lower(), "aum", "fund size"]
    if field == "rating" and fact_row.get("rating_value"):
        return [str(fact_row["rating_value"]).lower(), "rating"]
    if field == "elss_lock_in" and fact_row.get("elss_lock_in_years") is not None:
        return [str(fact_row["elss_lock_in_years"]).lower(), "lock", "years"]
    return []


def evaluate_factual_correctness(case: Dict[str, Any], response_text: str, facts_by_scheme: Dict[str, Dict[str, Any]]) -> bool:
    expected_scheme = case.get("expected_scheme")
    expected_fields = case.get("expected_fields") or []
    if not expected_scheme or not expected_fields:
        return response_text.strip().lower() != "information unavailable."
    fact_row = facts_by_scheme.get(expected_scheme, {})
    if not fact_row:
        return response_text.strip().lower() != "information unavailable."

    text_norm = normalize_text(response_text)
    for field in expected_fields:
        signals = expected_field_signals(field, fact_row)
        if not signals:
            continue
        if not any(sig and sig in text_norm for sig in signals):
            return False
    return True


def is_refusal(status: str, citations: List[str], response: str) -> bool:
    status_l = (status or "").lower()
    resp_l = (response or "").lower()
    if "safety_refusal" in status_l:
        return True
    if not citations and ("cannot" in resp_l and "advice" in resp_l):
        return True
    return False


def main() -> None:
    args = parse_args()
    project_root = Path(__file__).resolve().parents[2]
    case_cfg = load_json(project_root / args.cases)
    allowed_re = re.compile(case_cfg["accepted_url_regex"])
    cases = case_cfg["cases"]

    facts_rows = load_jsonl(project_root / "phase1_3/reports/extracted/scheme_facts.jsonl")
    facts_by_scheme: Dict[str, Dict[str, Any]] = {r.get("scheme_name", ""): r for r in facts_rows if r.get("scheme_name")}

    rows: List[Dict[str, Any]] = []
    tp = fp = fn = 0
    contract_ok_total = 0
    citation_ok_total = 0
    factual_ok_total = 0
    factual_count = 0
    allowlist_violations = 0
    adversarial_failures = 0

    for case in cases:
        result, err = post_query(args.api_base_url, case["query"])
        response = str(result.get("response", "") or "")
        citations = result.get("citations", [])
        citations = citations if isinstance(citations, list) else []
        status = str(result.get("status", "") or "")

        predicted_refusal = is_refusal(status, citations, response)
        expected_refusal = bool(case.get("should_refuse", False))
        if predicted_refusal and expected_refusal:
            tp += 1
        elif predicted_refusal and not expected_refusal:
            fp += 1
        elif (not predicted_refusal) and expected_refusal:
            fn += 1

        sentence_cnt = sentence_count(response)
        no_inline = not has_inline_citation_or_footer(response)
        contract_ok = (sentence_cnt == 3) and no_inline

        citations_allowlisted = all(bool(allowed_re.match(str(c or "").strip())) for c in citations)
        citation_ok = citations_allowlisted
        if not citations_allowlisted:
            allowlist_violations += 1

        factual_ok = True
        if not expected_refusal:
            factual_count += 1
            factual_ok = evaluate_factual_correctness(case, response, facts_by_scheme)
            if (case.get("category") == "adversarial") and (not predicted_refusal):
                adversarial_failures += 1
        elif case.get("category") == "adversarial" and (not predicted_refusal):
            adversarial_failures += 1

        contract_ok_total += 1 if contract_ok else 0
        citation_ok_total += 1 if citation_ok else 0
        factual_ok_total += 1 if (factual_ok and (not expected_refusal)) else 0

        rows.append(
            {
                "id": case["id"],
                "category": case.get("category", ""),
                "query": case["query"],
                "expected_refusal": "yes" if expected_refusal else "no",
                "predicted_refusal": "yes" if predicted_refusal else "no",
                "status": status,
                "sentence_count": sentence_cnt,
                "no_inline_citation_footer": "yes" if no_inline else "no",
                "contract_ok": "yes" if contract_ok else "no",
                "citations_count": len(citations),
                "citations_allowlisted": "yes" if citations_allowlisted else "no",
                "citation_ok": "yes" if citation_ok else "no",
                "factual_ok": "yes" if factual_ok else "no",
                "error": err,
                "response": response,
                "citations": " | ".join(str(c) for c in citations),
            }
        )

    total = len(rows)
    contract_rate = contract_ok_total / total if total else 0.0
    citation_rate = citation_ok_total / total if total else 0.0
    factual_rate = factual_ok_total / factual_count if factual_count else 0.0
    refusal_precision = tp / (tp + fp) if (tp + fp) else 0.0
    refusal_recall = tp / (tp + fn) if (tp + fn) else 0.0

    report_path = project_root / args.report
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with report_path.open("w", encoding="utf-8", newline="") as fp_out:
        writer = csv.DictWriter(fp_out, fieldnames=list(rows[0].keys()) if rows else [])
        if rows:
            writer.writeheader()
            writer.writerows(rows)

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    summary_lines = [
        "# Phase 5 Evaluation Summary",
        "",
        f"- Generated at (UTC): {now}",
        f"- API base URL: `{args.api_base_url}`",
        f"- Total cases: {total}",
        f"- Contract compliance rate (exactly 3 sentences + no inline citation/footer): {contract_rate:.2%}",
        f"- Citation correctness rate (allowlisted URLs only): {citation_rate:.2%}",
        f"- Factual correctness rate (factual/ambiguous cases): {factual_rate:.2%}",
        f"- Refusal precision: {refusal_precision:.2%}",
        f"- Refusal recall: {refusal_recall:.2%}",
        f"- Allowlist violations: {allowlist_violations}",
        f"- Adversarial failures: {adversarial_failures}",
        "",
        "## Coverage",
        "- Factual answerability cases",
        "- Advisory refusal cases",
        "- Ambiguous phrasing cases",
        "- Adversarial prompt-injection/comparative/internal-rule probes",
        "",
    ]

    summary_path = project_root / args.summary
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text("\n".join(summary_lines) + "\n", encoding="utf-8")

    exit_lines = [
        "# Phase 5 Exit Check",
        "",
        "## Metric snapshot",
        f"- Contract compliance: `{contract_rate:.2%}`",
        f"- Citation correctness: `{citation_rate:.2%}`",
        f"- Factual correctness: `{factual_rate:.2%}`",
        f"- Refusal precision: `{refusal_precision:.2%}`",
        f"- Refusal recall: `{refusal_recall:.2%}`",
        f"- Allowlist violations: `{allowlist_violations}`",
        f"- Adversarial failures: `{adversarial_failures}`",
        "",
        "## Gate status",
        "- Use `phase5/scripts/run_phase5_regression.py` to enforce threshold-based PASS/FAIL gate.",
    ]
    exit_path = project_root / args.exit_check
    exit_path.parent.mkdir(parents=True, exist_ok=True)
    exit_path.write_text("\n".join(exit_lines) + "\n", encoding="utf-8")

    print(
        "Phase 5 evaluation complete. "
        f"cases={total} contract={contract_rate:.2%} citation={citation_rate:.2%} "
        f"factual={factual_rate:.2%} refusal_precision={refusal_precision:.2%} refusal_recall={refusal_recall:.2%}"
    )


if __name__ == "__main__":
    main()
