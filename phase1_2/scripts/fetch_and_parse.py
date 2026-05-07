import argparse
import csv
import json
import re
import ssl
from dataclasses import dataclass
from datetime import datetime, timezone
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._skip_depth = 0
        self.parts: List[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:  # noqa: ANN001
        if tag.lower() in {"script", "style", "noscript"}:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style", "noscript"} and self._skip_depth > 0:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0:
            cleaned = data.strip()
            if cleaned:
                self.parts.append(cleaned)

    def as_text(self) -> str:
        return "\n".join(self.parts)


@dataclass
class RecordOutcome:
    source_id: str
    url: str
    parse_status: str
    fetch_status: str
    http_status: str
    final_url: str
    content_type: str
    raw_chars: int
    normalized_chars: int
    error_reason: str
    notes: str
    normalized_text: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Phase 1.2 fetch + parse pipeline")
    parser.add_argument("--input", required=True, help="Phase 1.1 source registry CSV")
    parser.add_argument("--policy", required=True, help="Fetch/parse policy JSON")
    parser.add_argument("--report", required=True, help="Output parse report CSV")
    parser.add_argument("--summary", required=True, help="Output parse summary markdown")
    parser.add_argument("--parsed", required=True, help="Output parsed documents JSONL")
    return parser.parse_args()


def load_policy(policy_path: Path) -> Dict:
    with policy_path.open("r", encoding="utf-8") as fp:
        return json.load(fp)


def bool_from_text(value: str) -> bool:
    return str(value).strip().lower() in {"yes", "true", "1"}


def accepted_url(url: str, regex: re.Pattern[str]) -> bool:
    return bool(regex.match(url.strip()))


def fetch_url(url: str, timeout_s: int) -> Tuple[str, str, str, bytes, str]:
    req = Request(url=url, method="GET", headers={"User-Agent": "phase1.2-fetch-parse/1.0"})
    context = ssl.create_default_context()
    try:
        with urlopen(req, timeout=timeout_s, context=context) as resp:
            code = str(resp.getcode())
            final_url = resp.geturl()
            content_type = resp.headers.get("Content-Type", "")
            body = resp.read()
            return code, final_url, content_type, body, ""
    except HTTPError as e:
        return str(e.code), e.geturl() or url, "", b"", f"http_error:{e.code}"
    except URLError as e:
        return "", url, "", b"", f"url_error:{e.reason}"
    except Exception as e:  # noqa: BLE001
        return "", url, "", b"", f"exception:{type(e).__name__}"


def parse_html(raw_bytes: bytes) -> str:
    try:
        html = raw_bytes.decode("utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        return ""
    parser = _TextExtractor()
    parser.feed(html)
    direct_text = parser.as_text()
    if len(direct_text) >= 200:
        return direct_text

    # Fallback: extract text from embedded JSON script blocks when HTML body is thin/JS-heavy.
    fallback_chunks: List[str] = []
    for pattern in [
        r"<script[^>]*id=\"__NEXT_DATA__\"[^>]*>(.*?)</script>",
        r"<script[^>]*type=\"application/ld\+json\"[^>]*>(.*?)</script>",
    ]:
        for match in re.findall(pattern, html, flags=re.IGNORECASE | re.DOTALL):
            snippet = re.sub(r"\s+", " ", unescape(match)).strip()
            if snippet:
                fallback_chunks.append(snippet)
    if fallback_chunks:
        return "\n".join(fallback_chunks)
    return direct_text


def parse_pdf(raw_bytes: bytes) -> Tuple[str, str]:
    try:
        from pypdf import PdfReader  # type: ignore
    except Exception:  # noqa: BLE001
        return "", "pdf_parser_unavailable"

    try:
        import io

        reader = PdfReader(io.BytesIO(raw_bytes))
        all_text: List[str] = []
        for page in reader.pages:
            text = page.extract_text() or ""
            if text.strip():
                all_text.append(text.strip())
        merged = "\n".join(all_text).strip()
        if not merged:
            return "", "pdf_no_extractable_text"
        return merged, ""
    except Exception as e:  # noqa: BLE001
        return "", f"pdf_parse_error:{type(e).__name__}"


def normalize_lines(text: str, strip_patterns: List[re.Pattern[str]], max_lines: int) -> str:
    lines = text.replace("\r", "\n").split("\n")
    normalized: List[str] = []
    for line in lines:
        candidate = re.sub(r"\s+", " ", line).strip()
        if not candidate:
            continue
        if any(p.match(candidate) for p in strip_patterns):
            continue
        normalized.append(candidate)
        if len(normalized) >= max_lines:
            break
    return "\n".join(normalized).strip()


def evaluate_parse_status(
    normalized_chars: int, min_valid: int, min_low_conf: int, parser_note: str
) -> Tuple[str, str]:
    if normalized_chars >= min_valid:
        return "parsed", parser_note
    if normalized_chars >= min_low_conf:
        note = parser_note or "content_too_short_for_confident_parse"
        return "low_confidence_extract", note
    note = parser_note or "insufficient_extractable_content"
    return "invalid", note


def read_input_rows(input_path: Path, url_re: re.Pattern[str]) -> List[Dict[str, str]]:
    with input_path.open("r", encoding="utf-8", newline="") as fp:
        reader = csv.DictReader(fp)
        rows = []
        for row in reader:
            if not bool_from_text(row.get("retrieval_eligible", "")):
                continue
            url = row.get("url", "").strip()
            if not accepted_url(url, url_re):
                continue
            rows.append(row)
        return rows


def process_rows(rows: List[Dict[str, str]], policy: Dict) -> List[RecordOutcome]:
    timeout_s = int(policy.get("request_timeout_seconds", 10))
    min_valid = int(policy.get("min_text_chars_for_valid_parse", 700))
    min_low_conf = int(policy.get("min_text_chars_for_low_confidence", 250))
    blocked_codes = {str(v) for v in policy.get("blocked_http_statuses", [401, 403, 429])}
    retries = int(policy.get("retry_attempts", 1))
    url_re = re.compile(policy["accepted_url_regex"])

    strip_patterns = [re.compile(x, flags=re.IGNORECASE) for x in policy.get("strip_line_patterns", [])]
    max_lines = int(policy.get("max_lines_to_keep", 1200))

    outcomes: List[RecordOutcome] = []
    for row in rows:
        source_id = row["source_id"]
        url = row["url"].strip()

        code = ""
        final_url = url
        content_type = ""
        body = b""
        err = ""
        attempts = 0
        while attempts <= retries:
            code, final_url, content_type, body, err = fetch_url(url, timeout_s)
            attempts += 1
            if not err:
                break
            if code in blocked_codes:
                break

        if err:
            status = "blocked" if code in blocked_codes else "invalid"
            outcomes.append(
                RecordOutcome(
                    source_id=source_id,
                    url=url,
                    parse_status=status,
                    fetch_status="failed",
                    http_status=code,
                    final_url=final_url,
                    content_type=content_type,
                    raw_chars=0,
                    normalized_chars=0,
                    error_reason=err,
                    notes="",
                    normalized_text="",
                )
            )
            continue

        if not accepted_url(final_url, url_re):
            outcomes.append(
                RecordOutcome(
                    source_id=source_id,
                    url=url,
                    parse_status="blocked",
                    fetch_status="ok",
                    http_status=code,
                    final_url=final_url,
                    content_type=content_type,
                    raw_chars=0,
                    normalized_chars=0,
                    error_reason="redirect_outside_allowed_groww_pattern",
                    notes="",
                    normalized_text="",
                )
            )
            continue

        lower_ctype = content_type.lower()
        parser_note = ""
        parsed_text = ""
        if "pdf" in lower_ctype or final_url.lower().endswith(".pdf"):
            parsed_text, parser_note = parse_pdf(body)
        else:
            parsed_text = parse_html(body)

        raw_chars = len(parsed_text)
        normalized = normalize_lines(parsed_text, strip_patterns, max_lines=max_lines)
        normalized_chars = len(normalized)
        parse_status, status_note = evaluate_parse_status(normalized_chars, min_valid, min_low_conf, parser_note)

        outcomes.append(
            RecordOutcome(
                source_id=source_id,
                url=url,
                parse_status=parse_status,
                fetch_status="ok",
                http_status=code,
                final_url=final_url,
                content_type=content_type,
                raw_chars=raw_chars,
                normalized_chars=normalized_chars,
                error_reason="" if parse_status == "parsed" else status_note,
                notes=status_note if parse_status == "parsed" else "",
                normalized_text=normalized if parse_status in {"parsed", "low_confidence_extract"} else "",
            )
        )
    return outcomes


def write_report(path: Path, rows: List[Dict[str, str]], outcomes: List[RecordOutcome]) -> None:
    by_source = {o.source_id: o for o in outcomes}
    fieldnames = list(rows[0].keys()) + [
        "parse_status",
        "fetch_status",
        "http_status",
        "final_url",
        "content_type",
        "raw_chars",
        "normalized_chars",
        "error_reason",
        "parse_notes",
        "processed_at",
    ]
    processed_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            outcome = by_source[row["source_id"]]
            out = dict(row)
            out["parse_status"] = outcome.parse_status
            out["fetch_status"] = outcome.fetch_status
            out["http_status"] = outcome.http_status
            out["final_url"] = outcome.final_url
            out["content_type"] = outcome.content_type
            out["raw_chars"] = str(outcome.raw_chars)
            out["normalized_chars"] = str(outcome.normalized_chars)
            out["error_reason"] = outcome.error_reason
            out["parse_notes"] = outcome.notes
            out["processed_at"] = processed_at
            writer.writerow(out)


def write_parsed_jsonl(path: Path, outcomes: List[RecordOutcome], rows: List[Dict[str, str]]) -> None:
    by_source = {r["source_id"]: r for r in rows}
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fp:
        for outcome in outcomes:
            if outcome.parse_status not in {"parsed", "low_confidence_extract"}:
                continue
            src = by_source[outcome.source_id]
            payload = {
                "source_id": outcome.source_id,
                "scheme_name": src.get("scheme_name", ""),
                "doc_type": src.get("doc_type", ""),
                "source_url": outcome.final_url,
                "parse_status": outcome.parse_status,
                "normalized_chars": outcome.normalized_chars,
                "parsed_text": outcome.normalized_text,
            }
            fp.write(json.dumps(payload, ensure_ascii=True) + "\n")


def write_summary(path: Path, outcomes: List[RecordOutcome]) -> None:
    total = len(outcomes)
    parsed = sum(1 for o in outcomes if o.parse_status == "parsed")
    blocked = sum(1 for o in outcomes if o.parse_status == "blocked")
    invalid = sum(1 for o in outcomes if o.parse_status == "invalid")
    low_conf = sum(1 for o in outcomes if o.parse_status == "low_confidence_extract")
    success_rate = (parsed / total * 100.0) if total else 0.0

    lines = [
        "# Phase 1.2 Parse Summary",
        "",
        f"- Generated at (UTC): {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}",
        f"- Total records: {total}",
        f"- Parsed: {parsed}",
        f"- Low confidence: {low_conf}",
        f"- Invalid: {invalid}",
        f"- Blocked: {blocked}",
        f"- Parse success rate: {success_rate:.2f}%",
        "",
        "## Records requiring action",
        "",
        "| source_id | parse_status | error_reason |",
        "|---|---|---|",
    ]
    needs_action = False
    for o in outcomes:
        if o.parse_status != "parsed":
            needs_action = True
            lines.append(f"| {o.source_id} | {o.parse_status} | {o.error_reason or '-'} |")
    if not needs_action:
        lines.append("| - | - | No action required |")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_exit_check(path: Path, outcomes: List[RecordOutcome]) -> None:
    total = len(outcomes)
    parsed = sum(1 for o in outcomes if o.parse_status == "parsed")
    non_silent = all(o.parse_status in {"parsed", "invalid", "blocked", "low_confidence_extract"} for o in outcomes)
    success_rate = (parsed / total * 100.0) if total else 0.0
    threshold_met = success_rate >= 80.0
    failed_labeled = all(
        o.parse_status == "parsed" or (o.parse_status in {"invalid", "blocked", "low_confidence_extract"} and o.error_reason)
        for o in outcomes
    )

    status_success = "PASS" if threshold_met else "CONDITIONAL"
    status_failed = "PASS" if failed_labeled else "FAIL"
    status_silent = "PASS" if non_silent else "FAIL"

    lines = [
        "# Phase 1.2 Exit Check",
        "",
        "## Exit criteria status",
        "",
        "1. **Parse success rate meets threshold for accepted Groww source set**",
        f"   - Status: `{status_success}` ({success_rate:.2f}% parsed)",
        "",
        "2. **Failed parses are explicitly labeled (`invalid`, `blocked`, or `low_confidence_extract`)**",
        f"   - Status: `{status_failed}`",
        "",
        "3. **No silent parser failures**",
        f"   - Status: `{status_silent}`",
        "",
        "## Phase gate decision",
    ]
    if threshold_met and failed_labeled and non_silent:
        lines.append("- `READY` for Phase 1.3 progression.")
    else:
        lines.append("- `CONDITIONAL` readiness; resolve non-parsed records first.")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    policy = load_policy(Path(args.policy))
    url_re = re.compile(policy["accepted_url_regex"])

    input_rows = read_input_rows(Path(args.input), url_re=url_re)
    if not input_rows:
        raise ValueError("No eligible Groww URLs found in input registry.")

    outcomes = process_rows(input_rows, policy=policy)
    write_report(Path(args.report), input_rows, outcomes)
    write_summary(Path(args.summary), outcomes)
    write_parsed_jsonl(Path(args.parsed), outcomes, input_rows)
    write_exit_check(Path(args.summary).parent / "phase1_2_exit_check.md", outcomes)

    parsed = sum(1 for o in outcomes if o.parse_status == "parsed")
    low_conf = sum(1 for o in outcomes if o.parse_status == "low_confidence_extract")
    invalid = sum(1 for o in outcomes if o.parse_status == "invalid")
    blocked = sum(1 for o in outcomes if o.parse_status == "blocked")
    print(
        "Phase 1.2 complete. "
        f"total={len(outcomes)} parsed={parsed} low_confidence={low_conf} invalid={invalid} blocked={blocked}"
    )


if __name__ == "__main__":
    main()
