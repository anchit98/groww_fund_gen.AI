import argparse
import csv
import json
import ssl
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


@dataclass
class ValidationResult:
    status: str = "pass"  # pass | quarantine | reject
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    http_status: str = ""
    final_url: str = ""

    def reject(self, reason: str) -> None:
        self.status = "reject"
        self.errors.append(reason)

    def quarantine(self, reason: str) -> None:
        if self.status != "reject":
            self.status = "quarantine"
        self.errors.append(reason)

    def warn(self, reason: str) -> None:
        self.warnings.append(reason)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate Phase 1.1 source intake registry")
    parser.add_argument("--input", required=True, help="Path to source registry CSV")
    parser.add_argument("--policy", required=True, help="Path to source intake policy JSON")
    parser.add_argument("--report", required=True, help="Path to output validation report CSV")
    parser.add_argument("--summary", required=True, help="Path to output summary markdown")
    parser.add_argument(
        "--skip-http",
        action="store_true",
        help="Skip URL health checks (policy-only validation mode)",
    )
    return parser.parse_args()


def load_policy(policy_path: Path) -> Dict:
    with policy_path.open("r", encoding="utf-8") as fp:
        return json.load(fp)


def bool_from_text(value: str) -> bool:
    return str(value).strip().lower() in {"yes", "true", "1"}


def canonical_domain(netloc: str) -> str:
    domain = netloc.lower().strip()
    if domain.startswith("www."):
        domain = domain[4:]
    return domain


def is_domain_allowed(domain: str, allowed_domains: List[str]) -> bool:
    domain = canonical_domain(domain)
    allowed = [canonical_domain(d) for d in allowed_domains]
    return any(domain == item or domain.endswith("." + item) for item in allowed)


def validate_url_shape(url: str) -> Tuple[Optional[str], Optional[str]]:
    try:
        parsed = urlparse(url)
    except Exception:
        return None, None
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None, None
    return parsed.scheme, parsed.netloc


def check_health(url: str, timeout_s: int) -> Tuple[str, str, str]:
    req = Request(url=url, method="GET", headers={"User-Agent": "phase1.1-validator/1.0"})
    context = ssl.create_default_context()
    try:
        with urlopen(req, timeout=timeout_s, context=context) as resp:
            code = str(resp.getcode())
            final_url = resp.geturl()
            return code, final_url, ""
    except HTTPError as e:
        return str(e.code), e.geturl() or url, f"http_error:{e.code}"
    except URLError as e:
        return "", url, f"url_error:{e.reason}"
    except Exception as e:  # noqa: BLE001
        return "", url, f"exception:{type(e).__name__}"


def validate_row(row: Dict[str, str], policy: Dict, skip_http: bool) -> ValidationResult:
    result = ValidationResult()

    source_tier = row.get("source_tier", "").strip()
    doc_type = row.get("doc_type", "").strip()
    url = row.get("url", "").strip()
    retrieval_eligible = bool_from_text(row.get("retrieval_eligible", ""))
    citation_eligible = bool_from_text(row.get("citation_eligible", ""))

    allowed_tiers = set(policy.get("allowed_source_tiers", []))
    allowed_doc_types = set(policy.get("allowed_doc_types", []))
    domain_allowlist = policy.get("domain_allowlist", {})
    blocked_keywords = policy.get("blocked_path_keywords", [])
    doc_type_hints = policy.get("doc_type_path_hints", {})
    timeout_s = int(policy.get("max_timeout_seconds", 8))

    # Tier and doc type validation
    if source_tier not in allowed_tiers:
        result.reject(f"invalid_source_tier:{source_tier}")
    if doc_type not in allowed_doc_types:
        result.reject(f"invalid_doc_type:{doc_type}")

    # URL parse validation
    scheme, netloc = validate_url_shape(url)
    if not scheme or not netloc:
        result.reject("invalid_url")
        return result
    source_domain = canonical_domain(netloc)

    # Domain allowlist by tier
    tier_domains = domain_allowlist.get(source_tier, [])
    if not is_domain_allowed(source_domain, tier_domains):
        result.reject(f"domain_not_allowlisted_for_tier:{source_domain}:{source_tier}")

    # Groww-only hard policy
    parsed_url = urlparse(url)
    if source_tier == "groww_mutual_funds_only":
        if not parsed_url.path.startswith("/mutual-funds/"):
            result.reject("groww_path_mismatch")
        if not retrieval_eligible:
            result.reject("groww_source_must_be_retrieval_eligible")
        if not citation_eligible:
            result.reject("groww_source_must_be_citation_eligible")

    # Suspicious mirror/content path blocking
    path_plus_query = f"{urlparse(url).path}?{urlparse(url).query}".lower()
    for keyword in blocked_keywords:
        if keyword in path_plus_query:
            result.reject(f"suspicious_path_keyword:{keyword}")
            break

    # Doc type hint check (warning/quarantine)
    hints = doc_type_hints.get(doc_type, [])
    if hints:
        if not any(h in path_plus_query for h in hints):
            result.quarantine(f"doc_type_path_mismatch:{doc_type}")

    # HTTP health check
    if not skip_http:
        code, final_url, err = check_health(url, timeout_s=timeout_s)
        result.http_status = code
        result.final_url = final_url
        if err:
            result.quarantine(f"health_check_failed:{err}")
        if code and not code.startswith("2"):
            result.quarantine(f"non_2xx_status:{code}")

        # Redirect domain validation
        _, final_netloc = validate_url_shape(final_url)
        if final_netloc:
            final_domain = canonical_domain(final_netloc)
            if not is_domain_allowed(final_domain, tier_domains):
                result.reject(f"redirect_to_non_allowlisted_domain:{final_domain}")
    else:
        result.http_status = "skipped"
        result.final_url = url

    return result


def write_report(rows: List[Dict[str, str]], results: Dict[str, ValidationResult], report_path: Path) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    checked_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    fieldnames = list(rows[0].keys()) + [
        "validation_status",
        "errors",
        "warnings",
        "http_status",
        "final_url",
        "checked_at",
    ]
    with report_path.open("w", encoding="utf-8", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            source_id = row["source_id"]
            res = results[source_id]
            out = dict(row)
            out["validation_status"] = res.status
            out["errors"] = ";".join(res.errors)
            out["warnings"] = ";".join(res.warnings)
            out["http_status"] = res.http_status
            out["final_url"] = res.final_url
            out["checked_at"] = checked_at
            writer.writerow(out)


def write_summary(rows: List[Dict[str, str]], results: Dict[str, ValidationResult], summary_path: Path) -> None:
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    total = len(rows)
    passed = sum(1 for r in results.values() if r.status == "pass")
    quarantined = sum(1 for r in results.values() if r.status == "quarantine")
    rejected = sum(1 for r in results.values() if r.status == "reject")

    lines = [
        "# Source Intake Validation Summary",
        "",
        f"- Generated at (UTC): {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}",
        f"- Total records: {total}",
        f"- Pass: {passed}",
        f"- Quarantine: {quarantined}",
        f"- Reject: {rejected}",
        "",
        "## Records requiring action",
        "",
        "| source_id | status | errors |",
        "|---|---|---|",
    ]

    for row in rows:
        source_id = row["source_id"]
        res = results[source_id]
        if res.status != "pass":
            errors = ", ".join(res.errors) if res.errors else "-"
            lines.append(f"| {source_id} | {res.status} | {errors} |")

    if all(res.status == "pass" for res in results.values()):
        lines.append("| - | - | No action required |")

    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    input_path = Path(args.input)
    policy_path = Path(args.policy)
    report_path = Path(args.report)
    summary_path = Path(args.summary)

    policy = load_policy(policy_path)

    rows: List[Dict[str, str]] = []
    with input_path.open("r", encoding="utf-8", newline="") as fp:
        reader = csv.DictReader(fp)
        rows = list(reader)
    if not rows:
        raise ValueError("Input source registry is empty.")

    results: Dict[str, ValidationResult] = {}
    for row in rows:
        source_id = row.get("source_id", "").strip()
        if not source_id:
            raise ValueError("Every row must include source_id.")
        results[source_id] = validate_row(row, policy, skip_http=args.skip_http)

    write_report(rows, results, report_path)
    write_summary(rows, results, summary_path)

    rejected = sum(1 for r in results.values() if r.status == "reject")
    quarantined = sum(1 for r in results.values() if r.status == "quarantine")
    print(
        f"Validation complete. total={len(rows)} pass={len(rows)-rejected-quarantined} "
        f"quarantine={quarantined} reject={rejected}"
    )


if __name__ == "__main__":
    main()
