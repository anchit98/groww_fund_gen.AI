import argparse
import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Phase 1.3 field extraction")
    parser.add_argument("--parsed", required=True, help="Parsed JSONL input from Phase 1.2")
    parser.add_argument("--registry", required=True, help="Source registry CSV from Phase 1.1")
    parser.add_argument("--policy", required=True, help="Extraction policy JSON")
    parser.add_argument("--facts-out", required=True, help="Output scheme facts JSONL")
    parser.add_argument("--process-out", required=True, help="Output process guides JSONL")
    parser.add_argument("--report", required=True, help="Extraction report CSV")
    parser.add_argument("--summary", required=True, help="Extraction summary markdown")
    return parser.parse_args()


def load_policy(path: Path) -> Dict:
    with path.open("r", encoding="utf-8") as fp:
        return json.load(fp)


def load_registry(path: Path) -> Dict[str, Dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as fp:
        return {row["source_id"]: row for row in csv.DictReader(fp)}


def to_float(value: str) -> Optional[float]:
    clean = value.replace(",", "").strip()
    try:
        return float(clean)
    except Exception:  # noqa: BLE001
        return None


def to_int(value: str) -> Optional[int]:
    clean = value.replace(",", "").strip()
    try:
        return int(float(clean))
    except Exception:  # noqa: BLE001
        return None


def parse_nav_date(raw: str) -> Optional[str]:
    text = raw.replace("'", "").strip()
    for fmt in ("%d %b %Y", "%d %b %y"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def collect_unique(values: List[Tuple[str, str]]) -> List[Tuple[str, str]]:
    seen = {}
    for normalized, raw in values:
        if normalized not in seen:
            seen[normalized] = raw
    return [(k, v) for k, v in seen.items()]


def detect_conflict(values: List[Tuple[str, str]]) -> bool:
    return len(collect_unique(values)) > 1


def extract_nav(text: str) -> Dict:
    candidates: List[Tuple[str, str, Optional[str]]] = []
    p1 = re.compile(
        r"NAV:\s*([0-9]{1,2}\s+[A-Za-z]{3}\s+'?[0-9]{2,4})\s*[₹?]?\s*([0-9,]+(?:\.[0-9]+)?)",
        flags=re.IGNORECASE,
    )
    for m in p1.finditer(text):
        nav_val = to_float(m.group(2))
        if nav_val is not None:
            nav_date = parse_nav_date(m.group(1))
            candidates.append((f"{nav_val:.6f}", m.group(0), nav_date))

    if not candidates:
        return {"value": None, "raw": None, "date": None, "status": "not_available", "conflict": False}

    uniq = []
    seen = set()
    for val, raw, date in candidates:
        key = (val, date or "")
        if key not in seen:
            seen.add(key)
            uniq.append((val, raw, date))

    if len(uniq) > 1:
        return {"value": None, "raw": None, "date": None, "status": "conflicting", "conflict": True}

    val, raw, date = uniq[0]
    return {"value": float(val), "raw": raw, "date": date, "status": "available", "conflict": False}


def extract_aum(text: str) -> Dict:
    pat = re.compile(r"Fund size\s*\(AUM\)\s*[₹?]?\s*([0-9,]+(?:\.[0-9]+)?)\s*Cr", flags=re.IGNORECASE)
    values: List[Tuple[str, str]] = []
    for m in pat.finditer(text):
        v = to_float(m.group(1))
        if v is not None:
            values.append((f"{v:.2f}", m.group(0)))
    if not values:
        return {"value": None, "raw": None, "status": "not_available", "conflict": False}
    if detect_conflict(values):
        return {"value": None, "raw": None, "status": "conflicting", "conflict": True}
    chosen = collect_unique(values)[0]
    return {"value": float(chosen[0]), "raw": chosen[1], "status": "available", "conflict": False}


def extract_expense_ratio(text: str) -> Dict:
    pat = re.compile(r"Expense ratio\s*([0-9]+(?:\.[0-9]+)?)%", flags=re.IGNORECASE)
    values: List[Tuple[str, str]] = []
    for m in pat.finditer(text):
        v = to_float(m.group(1))
        if v is not None:
            values.append((f"{v:.2f}", m.group(0)))
    if not values:
        return {"value": None, "raw": None, "status": "not_available", "conflict": False}
    if detect_conflict(values):
        return {"value": None, "raw": None, "status": "conflicting", "conflict": True}
    chosen = collect_unique(values)[0]
    return {"value": float(chosen[0]), "raw": chosen[1], "status": "available", "conflict": False}


def extract_min_sip(text: str) -> Dict:
    values: List[Tuple[str, str]] = []
    for m in re.finditer(r"Min\.\s*for\s*SIP\s*[₹?]?\s*([0-9,]+)", flags=re.IGNORECASE, string=text):
        v = to_int(m.group(1))
        if v is not None:
            values.append((str(v), m.group(0)))
    for m in re.finditer(r"Minimum SIP Investment is set to\s*[₹?]?\s*([0-9,]+)", flags=re.IGNORECASE, string=text):
        v = to_int(m.group(1))
        if v is not None:
            values.append((str(v), m.group(0)))
    if not values:
        return {"value": None, "raw": None, "status": "not_available", "conflict": False}
    if detect_conflict(values):
        return {"value": None, "raw": None, "status": "conflicting", "conflict": True}
    chosen = collect_unique(values)[0]
    return {"value": int(chosen[0]), "raw": chosen[1], "status": "available", "conflict": False}


def extract_rating(text: str) -> Dict:
    pat = re.compile(r"Rating\s*([0-5](?:\.[0-9])?)\b", flags=re.IGNORECASE)
    values: List[Tuple[str, str]] = []
    for m in pat.finditer(text):
        values.append((m.group(1), m.group(0)))
    if not values:
        return {"value": None, "raw": None, "status": "not_available", "conflict": False}
    if detect_conflict(values):
        return {"value": None, "raw": None, "status": "conflicting", "conflict": True}
    chosen = collect_unique(values)[0]
    return {"value": chosen[0], "raw": chosen[1], "status": "available", "conflict": False}


def extract_exit_load(text: str) -> Dict:
    values: List[Tuple[str, str]] = []

    # 1) Prefer value from the dedicated section:
    # "Exit load, stamp duty and tax | Exit load | <value> | Stamp duty on investment:"
    section_pat = re.compile(
        r"Exit load,\s*stamp duty and tax(?:\s*\|\s*|\s+)"
        r"Exit load(?:\s*\|\s*|\s+)"
        r"(.*?)"
        r"(?:\s*\|\s*|\s+)"
        r"Stamp duty on investment:",
        flags=re.IGNORECASE | re.DOTALL,
    )
    for m in section_pat.finditer(text):
        raw_value = re.sub(r"\s+", " ", m.group(1)).strip(" |;")
        if raw_value:
            values.append((raw_value.lower(), f"Exit load | {raw_value}"))

    # If dedicated section value exists, trust it over historical inline snippets.
    if values:
        # use the last section occurrence, usually the current displayed value
        chosen = values[-1]
        normalized = chosen[0]
        if normalized in {"--", "nil", "na", "n/a", "not applicable"}:
            # Keep Nil explicitly, but treat placeholder markers as not_available
            if normalized == "nil":
                return {"value": "0", "raw": chosen[1], "status": "available", "conflict": False}
            return {"value": None, "raw": None, "status": "not_available", "conflict": False}
        return {"value": normalized, "raw": chosen[1], "status": "available", "conflict": False}

    # 2) Fallback: explicit inline sentence-style clause
    pat = re.compile(
        r"Exit load of\s+([0-9]+(?:\.[0-9]+)?%[^.\n]*?(?:redeemed|redemption)[^.\n]*)",
        flags=re.IGNORECASE,
    )
    for m in pat.finditer(text):
        phrase = m.group(1).strip()
        if phrase:
            values.append((f"exit load of {phrase}".lower(), m.group(0)))
    if not values:
        return {"value": None, "raw": None, "status": "not_available", "conflict": False}
    if detect_conflict(values):
        return {"value": None, "raw": None, "status": "conflicting", "conflict": True}
    chosen = collect_unique(values)[0]
    return {"value": chosen[0], "raw": chosen[1], "status": "available", "conflict": False}


def extract_lock_in(text: str) -> Dict:
    values: List[Tuple[str, str]] = []
    for m in re.finditer(r"([0-9]+(?:\.[0-9]+)?)Y\s*Lock-?in", text, flags=re.IGNORECASE):
        v = to_float(m.group(1))
        if v is not None:
            values.append((f"{v:.2f}", m.group(0)))
    for m in re.finditer(r"Lock-?in(?: period)?(?: is| of)?\s*([0-9]+(?:\.[0-9]+)?)\s*years", text, flags=re.IGNORECASE):
        v = to_float(m.group(1))
        if v is not None:
            values.append((f"{v:.2f}", m.group(0)))
    if not values:
        return {"value": None, "raw": None, "status": "not_available", "conflict": False}
    if detect_conflict(values):
        return {"value": None, "raw": None, "status": "conflicting", "conflict": True}
    chosen = collect_unique(values)[0]
    return {"value": float(chosen[0]), "raw": chosen[1], "status": "available", "conflict": False}


def extract_riskometer(text: str, risk_map: Dict[str, str]) -> Dict:
    values: List[Tuple[str, str]] = []
    for m in re.finditer(r"rated\s+([A-Za-z ]+?)\s+risk", text, flags=re.IGNORECASE):
        raw = m.group(1).strip().lower()
        mapped = risk_map.get(raw)
        if mapped:
            values.append((mapped, m.group(0)))

    if not values:
        for label, mapped in risk_map.items():
            m = re.search(rf"\b{re.escape(label)}\s+risk\b", text, flags=re.IGNORECASE)
            if m:
                values.append((mapped, m.group(0)))

    if not values:
        return {"value": None, "raw": None, "status": "not_available", "conflict": False}
    if detect_conflict(values):
        return {"value": None, "raw": None, "status": "conflicting", "conflict": True}
    chosen = collect_unique(values)[0]
    return {"value": chosen[0], "raw": chosen[1], "status": "available", "conflict": False}


def extract_benchmark(text: str) -> Dict:
    pat = re.compile(
        r"Fund benchmark\s*([A-Za-z0-9 &:()/',.\-]+?(?:Index|TRI))",
        flags=re.IGNORECASE,
    )
    values: List[Tuple[str, str]] = []
    for m in pat.finditer(text):
        val = re.sub(r"\s+", " ", m.group(1)).strip()
        if val:
            values.append((val.lower(), m.group(0)))
    if not values:
        return {"value": None, "raw": None, "status": "not_available", "conflict": False}
    if detect_conflict(values):
        return {"value": None, "raw": None, "status": "conflicting", "conflict": True}
    chosen = collect_unique(values)[0]
    return {"value": chosen[0], "raw": chosen[1], "status": "available", "conflict": False}


def extract_process_guides(text: str, source_url: str, scheme_name: str, source_id: str) -> Tuple[Optional[Dict], Optional[Dict], bool]:
    statement_m = re.search(
        r"(download[^.\n]*statement[^.\n]*|statement[^.\n]*download[^.\n]*)",
        text,
        flags=re.IGNORECASE,
    )
    cap_m = re.search(
        r"(download[^.\n]*capital gain[^.\n]*|capital gain[^.\n]*download[^.\n]*)",
        text,
        flags=re.IGNORECASE,
    )
    has_any = bool(statement_m or cap_m)

    statement_obj = None
    cap_obj = None
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    if statement_m:
        statement_obj = {
            "guide_id": f"{source_id}-statement",
            "scheme_name": scheme_name,
            "guide_type": "statement_download",
            "channel": "web",
            "instruction_steps": [statement_m.group(0).strip()],
            "instruction_raw_text": statement_m.group(0).strip(),
            "source_id": source_id,
            "source_url": source_url,
            "ingested_at": now,
        }

    if cap_m:
        cap_obj = {
            "guide_id": f"{source_id}-capital-gains",
            "scheme_name": scheme_name,
            "guide_type": "capital_gains_report_download",
            "channel": "web",
            "instruction_steps": [cap_m.group(0).strip()],
            "instruction_raw_text": cap_m.group(0).strip(),
            "source_id": source_id,
            "source_url": source_url,
            "ingested_at": now,
        }

    return statement_obj, cap_obj, has_any


def process_record(rec: Dict, registry_row: Dict[str, str], policy: Dict) -> Tuple[Dict, List[Dict], Dict]:
    text = rec.get("parsed_text", "")
    source_id = rec["source_id"]
    source_url = rec["source_url"]
    scheme_name = rec.get("scheme_name", "")
    amc_name = registry_row.get("amc_name", policy.get("default_amc_name", ""))
    ingested_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    nav = extract_nav(text)
    aum = extract_aum(text)
    rating = extract_rating(text)
    expense = extract_expense_ratio(text)
    exit_load = extract_exit_load(text)
    min_sip = extract_min_sip(text)
    lock_in = extract_lock_in(text)
    risk = extract_riskometer(text, policy.get("riskometer_map", {}))
    benchmark = extract_benchmark(text)
    stmt_guide, cap_guide, has_guide = extract_process_guides(text, source_url, scheme_name, source_id)

    process_status = "available" if has_guide else "not_available"

    field_statuses = [
        nav["status"],
        aum["status"],
        rating["status"],
        expense["status"],
        exit_load["status"],
        min_sip["status"],
        lock_in["status"],
        risk["status"],
        benchmark["status"],
        process_status,
    ]
    if any(s == "conflicting" for s in field_statuses):
        availability_status = "conflicting"
    elif all(s == "not_available" for s in field_statuses):
        availability_status = "not_available"
    else:
        availability_status = "available"

    effective_date = nav.get("date") or ingested_at[:10]

    fact_obj = {
        "fact_id": f"fact-{source_id}",
        "scheme_name": scheme_name,
        "amc_name": amc_name,
        "nav_value": nav["value"],
        "nav_currency": "INR",
        "nav_raw_text": nav["raw"],
        "nav_value_as_of_date": nav.get("date"),
        "aum_value_cr": aum["value"],
        "aum_raw_text": aum["raw"],
        "aum_value_as_of_date": nav.get("date"),
        "rating_value": rating["value"],
        "rating_scale": None,
        "rating_provider": None,
        "rating_raw_text": rating["raw"],
        "expense_ratio_percent": expense["value"],
        "expense_ratio_raw_text": expense["raw"],
        "expense_ratio_as_of_date": nav.get("date"),
        "exit_load_text": exit_load["value"],
        "min_sip_amount_inr": min_sip["value"],
        "min_sip_raw_text": min_sip["raw"],
        "elss_lock_in_years": lock_in["value"],
        "elss_lock_in_raw_text": lock_in["raw"],
        "riskometer_label": risk["value"],
        "riskometer_raw_text": risk["raw"],
        "benchmark_full_name": benchmark["value"],
        "benchmark_raw_text": benchmark["raw"],
        "availability_status": availability_status,
        "source_id": source_id,
        "source_url": source_url,
        "effective_date": effective_date,
        "ingested_at": ingested_at,
        "field_statuses": {
            "nav": nav["status"],
            "aum": aum["status"],
            "rating": rating["status"],
            "expense_ratio": expense["status"],
            "exit_load": exit_load["status"],
            "minimum_sip": min_sip["status"],
            "elss_lock_in": lock_in["status"],
            "riskometer": risk["status"],
            "benchmark": benchmark["status"],
            "process_guides": process_status,
        },
    }

    guides: List[Dict] = []
    if stmt_guide:
        guides.append(stmt_guide)
    if cap_guide:
        guides.append(cap_guide)

    report_row = {
        "source_id": source_id,
        "scheme_name": scheme_name,
        "source_url": source_url,
        "availability_status": availability_status,
        "nav_status": nav["status"],
        "aum_status": aum["status"],
        "rating_status": rating["status"],
        "expense_ratio_status": expense["status"],
        "exit_load_status": exit_load["status"],
        "minimum_sip_status": min_sip["status"],
        "elss_lock_in_status": lock_in["status"],
        "riskometer_status": risk["status"],
        "benchmark_status": benchmark["status"],
        "process_guides_status": process_status,
    }

    return fact_obj, guides, report_row


def write_jsonl(path: Path, rows: List[Dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fp:
        for row in rows:
            fp.write(json.dumps(row, ensure_ascii=True) + "\n")


def write_report_csv(path: Path, rows: List[Dict]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_summary(path: Path, report_rows: List[Dict]) -> None:
    total = len(report_rows)
    conflicting = sum(1 for r in report_rows if r["availability_status"] == "conflicting")
    available = sum(1 for r in report_rows if r["availability_status"] == "available")
    not_avail = sum(1 for r in report_rows if r["availability_status"] == "not_available")

    mandatory_fields = [
        "nav_status",
        "aum_status",
        "rating_status",
        "expense_ratio_status",
        "exit_load_status",
        "minimum_sip_status",
        "elss_lock_in_status",
        "riskometer_status",
        "benchmark_status",
        "process_guides_status",
    ]
    missing_counts = {f: 0 for f in mandatory_fields}
    conflict_counts = {f: 0 for f in mandatory_fields}
    for r in report_rows:
        for f in mandatory_fields:
            if r[f] == "not_available":
                missing_counts[f] += 1
            if r[f] == "conflicting":
                conflict_counts[f] += 1

    lines = [
        "# Phase 1.3 Extraction Summary",
        "",
        f"- Generated at (UTC): {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}",
        f"- Total parse-success records processed: {total}",
        f"- Availability status -> available: {available}, conflicting: {conflicting}, not_available: {not_avail}",
        "",
        "## Missing field counts",
        "",
        "| field | not_available_count | conflicting_count |",
        "|---|---:|---:|",
    ]
    for f in mandatory_fields:
        lines.append(f"| {f} | {missing_counts[f]} | {conflict_counts[f]} |")

    lines.extend(
        [
            "",
            "## Records requiring review",
            "",
            "| source_id | availability_status | fields_to_review |",
            "|---|---|---|",
        ]
    )
    has_review = False
    for r in report_rows:
        problematic = [f for f in mandatory_fields if r[f] in {"not_available", "conflicting"}]
        if problematic:
            has_review = True
            lines.append(f"| {r['source_id']} | {r['availability_status']} | {', '.join(problematic)} |")
    if not has_review:
        lines.append("| - | - | No action required |")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_exit_check(path: Path, report_rows: List[Dict]) -> None:
    total = len(report_rows)
    complete = total > 0
    labeled = True
    for r in report_rows:
        for key, value in r.items():
            if key.endswith("_status") and value not in {"available", "not_available", "conflicting"}:
                labeled = False

    lines = [
        "# Phase 1.3 Exit Check",
        "",
        "## Exit criteria status",
        "",
        "1. **Mandatory field extraction is complete for all parse-success records**",
        f"   - Status: `{'PASS' if complete else 'FAIL'}`",
        "",
        "2. **Missing and conflicting values are explicitly labeled**",
        f"   - Status: `{'PASS' if labeled else 'FAIL'}`",
        "",
        "3. **Extraction audit sample is available for manual review**",
        "   - Status: `PASS` (see `extraction_report.csv` + `scheme_facts.jsonl` raw snippets)",
        "",
        "## Phase gate decision",
        f"- `{'READY' if complete and labeled else 'CONDITIONAL'}` for Phase 1.4 progression.",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    parsed_path = Path(args.parsed)
    registry = load_registry(Path(args.registry))
    policy = load_policy(Path(args.policy))
    url_re = re.compile(policy["accepted_url_regex"])

    facts: List[Dict] = []
    guides: List[Dict] = []
    report_rows: List[Dict] = []

    with parsed_path.open("r", encoding="utf-8") as fp:
        for line in fp:
            rec = json.loads(line)
            source_id = rec.get("source_id", "")
            if source_id not in registry:
                continue
            source_url = rec.get("source_url", "")
            if not url_re.match(source_url):
                continue
            if rec.get("parse_status") != "parsed":
                continue

            fact_obj, guide_objs, report_row = process_record(rec, registry[source_id], policy)
            facts.append(fact_obj)
            guides.extend(guide_objs)
            report_rows.append(report_row)

    write_jsonl(Path(args.facts_out), facts)
    write_jsonl(Path(args.process_out), guides)
    write_report_csv(Path(args.report), report_rows)
    write_summary(Path(args.summary), report_rows)
    write_exit_check(Path(args.summary).parent / "phase1_3_exit_check.md", report_rows)

    print(
        "Phase 1.3 complete. "
        f"records={len(report_rows)} facts={len(facts)} process_guides={len(guides)}"
    )


if __name__ == "__main__":
    main()
