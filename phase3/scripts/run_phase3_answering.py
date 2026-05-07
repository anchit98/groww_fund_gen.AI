import argparse
import csv
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple

import chromadb
import requests
from sentence_transformers import SentenceTransformer


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Phase 3 answer generation and output contract checks")
    parser.add_argument("--policy", required=True, help="Path to Phase 3 answer policy JSON")
    parser.add_argument("--report", required=True, help="Output answer contract report CSV")
    parser.add_argument("--summary", required=True, help="Output answer summary markdown")
    parser.add_argument("--exit-check", required=True, help="Output phase3 exit check markdown")
    return parser.parse_args()


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def load_jsonl(path: Path) -> List[Dict]:
    rows: List[Dict] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as fp:
        for line in fp:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def simple_sentence_count(text: str) -> int:
    chunks = [x.strip() for x in re.split(r"(?<=[.!?])\s+", text) if x.strip()]
    return len(chunks)


def extract_urls(text: str) -> List[str]:
    return re.findall(r"https?://[^\s)]+", text)


def classify_advisory(query: str, markers: List[str]) -> bool:
    q = query.lower()
    return any(m in q for m in markers)


def normalize_scheme_text(text: str) -> str:
    t = text.lower()
    t = t.replace("&", " and ")
    t = re.sub(r"[^a-z0-9\s]", " ", t)
    t = re.sub(r"\bdirect\b|\bgrowth\b|\bplan\b", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def category_tokens(text: str) -> set[str]:
    tokens = set(normalize_scheme_text(text).split())
    categories = {
        "large",
        "mid",
        "small",
        "flexi",
        "multi",
        "hybrid",
        "aggressive",
        "elss",
        "tax",
        "saver",
    }
    return tokens & categories


def extract_scheme_name(query: str, schemes: List[str]) -> str:
    q = normalize_scheme_text(query)
    q_categories = category_tokens(query)
    for scheme in sorted(schemes, key=len, reverse=True):
        s_norm = normalize_scheme_text(scheme)
        if s_norm in q:
            if q_categories and not q_categories.issubset(category_tokens(scheme)):
                continue
            return scheme
    # Fallback: token-overlap strict match for phrasing variants.
    q_tokens = set(q.split())
    best_scheme = ""
    best_overlap = 0.0
    for scheme in schemes:
        s_tokens = set(normalize_scheme_text(scheme).split())
        if not s_tokens:
            continue
        if q_categories and not q_categories.issubset(category_tokens(scheme)):
            continue
        overlap = len(q_tokens & s_tokens) / len(s_tokens)
        if overlap > best_overlap:
            best_overlap = overlap
            best_scheme = scheme
    if best_overlap >= 0.8:
        return best_scheme
    return ""


def detect_requested_field(query: str) -> str:
    q = query.lower()
    field_map = [
        ("expense_ratio", ["expense ratio"]),
        ("exit_load", ["exit load"]),
        ("minimum_sip", ["minimum sip", "min sip", "sip amount"]),
        ("benchmark", ["benchmark"]),
        ("riskometer", ["riskometer", "risk"]),
        ("nav", ["nav"]),
        ("aum", ["aum", "fund size"]),
        ("rating", ["rating"]),
        ("elss_lock_in", ["lock-in", "lock in"]),
    ]
    for field, markers in field_map:
        if any(m in q for m in markers):
            return field
    return ""


def build_fact_answer(field: str, fact_row: Dict) -> str:
    scheme = fact_row.get("scheme_name", "This scheme")
    as_of = fact_row.get("effective_date", "")
    if field == "expense_ratio" and fact_row.get("expense_ratio_percent") is not None:
        return f"The expense ratio for {scheme} is {fact_row['expense_ratio_percent']}%."
    if field == "exit_load" and fact_row.get("exit_load_text"):
        return f"The exit load for {scheme} is {fact_row['exit_load_text']}."
    if field == "minimum_sip" and fact_row.get("min_sip_amount_inr") is not None:
        return f"The minimum SIP amount for {scheme} is INR {fact_row['min_sip_amount_inr']}."
    if field == "benchmark" and fact_row.get("benchmark_full_name"):
        return f"The benchmark index for {scheme} is {fact_row['benchmark_full_name']}."
    if field == "riskometer" and fact_row.get("riskometer_label"):
        return f"The riskometer classification for {scheme} is {fact_row['riskometer_label']}."
    if field == "nav" and fact_row.get("nav_value") is not None:
        suffix = f" as of {as_of}" if as_of else ""
        return f"The NAV for {scheme} is INR {fact_row['nav_value']}{suffix}."
    if field == "aum" and fact_row.get("aum_value_cr") is not None:
        return f"The fund size (AUM) for {scheme} is INR {fact_row['aum_value_cr']} Cr."
    if field == "rating" and fact_row.get("rating_value"):
        return f"The rating for {scheme} is {fact_row['rating_value']}."
    if field == "elss_lock_in" and fact_row.get("elss_lock_in_years") is not None:
        return f"The ELSS lock-in period for {scheme} is {fact_row['elss_lock_in_years']} years."
    return ""


def choose_citation(chunks: List[Dict], allowed_re: re.Pattern[str]) -> str:
    for c in chunks:
        url = c.get("source_url", "")
        if allowed_re.match(url):
            return url
    return ""


def grounding_check(answer: str, contexts: List[Dict]) -> bool:
    answer_tokens = set(re.findall(r"[a-z0-9.%-]+", answer.lower()))
    context_tokens: set[str] = set()
    for c in contexts:
        context_tokens |= set(re.findall(r"[a-z0-9.%-]+", c.get("chunk_text", "").lower()))
    if not answer_tokens:
        return False
    overlap = len(answer_tokens & context_tokens) / max(1, len(answer_tokens))
    return overlap >= 0.2


def policy_leak_check(answer: str, interpretation_markers: List[str]) -> bool:
    a = answer.lower()
    return any(m in a for m in interpretation_markers)


def retrieve_context(
    query: str,
    collection,
    model: SentenceTransformer,
    top_k: int,
    allowed_re: re.Pattern[str],
    scheme_name: str,
) -> List[Dict]:
    q_emb = model.encode([query], normalize_embeddings=True).tolist()
    result = collection.query(query_embeddings=q_emb, n_results=top_k, include=["documents", "metadatas", "distances"])
    docs = result.get("documents", [[]])[0]
    metas = result.get("metadatas", [[]])[0]
    distances = result.get("distances", [[]])[0]

    rows: List[Dict] = []
    for i, m in enumerate(metas):
        meta = m or {}
        source_url = str(meta.get("source_url", "") or meta.get("citation_url", ""))
        if not allowed_re.match(source_url):
            continue
        rows.append(
            {
                "chunk_text": docs[i] if i < len(docs) else "",
                "source_url": source_url,
                "scheme_name": str(meta.get("scheme_name", "")),
                "distance": float(distances[i]) if i < len(distances) else 999.0,
            }
        )
    rows.sort(key=lambda x: x["distance"])
    if scheme_name:
        strict = [r for r in rows if r["scheme_name"].lower() == scheme_name.lower()]
        if strict:
            return strict
    return rows


def call_groq(groq_cfg: Dict, api_key: str, question: str, contexts: List[Dict], citation_url: str) -> str:
    context_text = "\n\n".join([f"[{i+1}] {c['chunk_text'][:800]}" for i, c in enumerate(contexts[:3])])
    prompt = (
        "You are a strict facts-only mutual fund assistant.\n"
        "Rules:\n"
        "1) Answer only from context.\n"
        "2) Do not give recommendations, opinions, or performance interpretation.\n"
        "3) Keep the answer to max 2 factual sentences.\n"
        "4) Add exactly one citation URL line as: Citation: <url>\n"
        "5) Add footer line as: As of YYYY-MM-DD.\n"
        "If context is insufficient, say: information unavailable.\n\n"
        f"Question: {question}\n"
        f"Context:\n{context_text}\n"
        f"Required citation url: {citation_url}\n"
    )
    payload = {
        "model": groq_cfg["model"],
        "temperature": groq_cfg.get("temperature", 0),
        "max_tokens": groq_cfg.get("max_tokens", 220),
        "messages": [{"role": "user", "content": prompt}],
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    response = requests.post(groq_cfg["base_url"], headers=headers, json=payload, timeout=60)
    response.raise_for_status()
    data = response.json()
    return data["choices"][0]["message"]["content"].strip()


def build_refusal(query: str, fallback_url: str, date_str: str) -> str:
    return (
        "I can only provide factual information from Groww mutual fund pages and cannot provide investment advice. "
        f"You can review the official fund details here.\nCitation: {fallback_url}\nAs of {date_str}."
    )


def enforce_contract(answer: str, citation_url: str, date_str: str, max_sentences: int, one_citation: bool) -> Tuple[str, Dict[str, bool]]:
    lines = [l.strip() for l in answer.splitlines() if l.strip()]
    body_lines = [l for l in lines if not l.lower().startswith("citation:") and not l.lower().startswith("as of ")]
    body = " ".join(body_lines).strip()
    if not body:
        body = "information unavailable."

    sentences = [x.strip() for x in re.split(r"(?<=[.!?])\s+", body) if x.strip()]
    body = " ".join(sentences[:max_sentences])

    if not body.endswith((".", "!", "?")):
        body = body + "."

    citation_line = f"Citation: {citation_url}"
    footer_line = f"As of {date_str}."
    final_answer = f"{body}\n{citation_line}\n{footer_line}"

    urls = extract_urls(final_answer)
    checks = {
        "sentence_limit_ok": simple_sentence_count(body) <= max_sentences,
        "one_citation_ok": (len(urls) == 1) if one_citation else True,
        "footer_ok": bool(re.search(r"^As of \d{4}-\d{2}-\d{2}\.$", footer_line)),
    }
    return final_answer, checks


def main() -> None:
    args = parse_args()
    project_root = Path(__file__).resolve().parents[2]
    policy = json.loads((project_root / args.policy).read_text(encoding="utf-8"))
    load_env_file(project_root / ".env")
    facts_rows = load_jsonl(project_root / "phase1_3/reports/extracted/scheme_facts.jsonl")
    facts_by_scheme = {r.get("scheme_name", ""): r for r in facts_rows if r.get("scheme_name")}
    scheme_names = list(facts_by_scheme.keys())

    api_key = os.getenv("GROQ_API_KEY", "").strip()
    allowed_re = re.compile(policy["accepted_url_regex"])
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    chroma_cfg = policy["chroma"]
    client = chromadb.PersistentClient(path=str(project_root / chroma_cfg["persist_directory"]))
    collection = client.get_collection(chroma_cfg["collection_name"])
    model = SentenceTransformer(str(project_root / policy["embedding"]["model_path"]))

    rows: List[Dict] = []
    contract_pass = 0
    advisory_leaks = 0

    for test in policy["phase3_tests"]:
        query = test["query"]
        test_id = test["id"]
        is_advisory = classify_advisory(query, policy["advisory_markers"])
        requested_field = detect_requested_field(query)
        detected_scheme = extract_scheme_name(query, scheme_names)
        likely_scheme_query = ("quant" in query.lower()) and ("fund" in query.lower()) and bool(requested_field)

        contexts = retrieve_context(
            query,
            collection,
            model,
            int(policy["retrieval"]["top_k"]),
            allowed_re,
            detected_scheme,
        )
        citation_url = choose_citation(contexts, allowed_re)
        if not citation_url:
            citation_url = "https://groww.in/mutual-funds/quant-large-and-mid-cap-fund-direct-growth"

        raw_answer = ""
        used_structured_fact = False
        mode = "refusal" if is_advisory else "factual"
        if is_advisory:
            raw_answer = build_refusal(query, citation_url, now)
        else:
            fact_based_answer = ""
            if detected_scheme and requested_field:
                fact_row = facts_by_scheme.get(detected_scheme, {})
                availability = (fact_row.get("field_statuses", {}) or {}).get(requested_field, "")
                if availability == "available":
                    fact_based_answer = build_fact_answer(requested_field, fact_row)
                    if fact_row.get("source_url"):
                        citation_url = fact_row["source_url"]

            if fact_based_answer:
                raw_answer = fact_based_answer
                used_structured_fact = True
            elif likely_scheme_query and not detected_scheme:
                # Strict scheme guard: avoid answering with an adjacent scheme when the requested
                # scheme is not confidently recognized in the canonical extracted-facts set.
                raw_answer = "information unavailable."
            elif api_key:
                try:
                    raw_answer = call_groq(policy["groq"], api_key, query, contexts, citation_url)
                except Exception:
                    raw_answer = "information unavailable."
            else:
                raw_answer = "information unavailable."

            if policy_leak_check(raw_answer, policy["interpretation_markers"]):
                mode = "refusal"
                raw_answer = build_refusal(query, citation_url, now)
                advisory_leaks += 1

            if (not used_structured_fact) and raw_answer != "information unavailable." and not grounding_check(raw_answer, contexts):
                raw_answer = "information unavailable."

        final_answer, checks = enforce_contract(
            raw_answer,
            citation_url,
            now,
            max_sentences=int(policy["contract"]["max_sentences"]),
            one_citation=bool(policy["contract"]["exactly_one_citation"]),
        )
        pass_flag = all(checks.values()) and (("cannot provide investment advice" in final_answer.lower()) if is_advisory else True)
        contract_pass += 1 if pass_flag else 0

        rows.append(
            {
                "test_id": test_id,
                "query": query,
                "route_mode": mode,
                "retrieved_chunks": len(contexts),
                "detected_scheme": detected_scheme,
                "requested_field": requested_field,
                "answer_source": "structured_fact" if used_structured_fact else "llm_or_fallback",
                "citation_url": citation_url,
                "sentence_limit_ok": "yes" if checks["sentence_limit_ok"] else "no",
                "one_citation_ok": "yes" if checks["one_citation_ok"] else "no",
                "footer_ok": "yes" if checks["footer_ok"] else "no",
                "pass": "yes" if pass_flag else "no",
                "final_answer": final_answer.replace("\n", " || "),
            }
        )

    report_path = project_root / args.report
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with report_path.open("w", encoding="utf-8", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    total = len(rows)
    pass_rate = (contract_pass / total) if total else 0.0
    no_advisory_leak = advisory_leaks == 0

    summary = [
        "# Phase 3 Answer Contract Summary",
        "",
        f"- Generated at (UTC): {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}",
        f"- Total tests: {total}",
        f"- Contract pass rate: {pass_rate:.2%}",
        f"- Advisory leak count (factual flow): {advisory_leaks}",
        f"- Groq API key detected: {'yes' if bool(api_key) else 'no'}",
        "",
        "## Controls covered",
        "- Grounding check blocks unsupported claims.",
        "- Interpretation/recommendation markers trigger refusal reroute.",
        "- Exactly one citation URL enforced.",
        "- Footer date standardized as ISO date.",
        "",
    ]
    summary_path = project_root / args.summary
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text("\n".join(summary) + "\n", encoding="utf-8")

    exit_lines = [
        "# Phase 3 Exit Check",
        "",
        "## Exit criteria status",
        "",
        "1. **Contract pass rate near 100% on test suite**",
        f"   - Status: `{'PASS' if pass_rate >= 0.95 else 'FAIL'}`",
        f"   - Value: `{pass_rate:.2%}`",
        "",
        "2. **No advisory content leaks in factual answers**",
        f"   - Status: `{'PASS' if no_advisory_leak else 'FAIL'}`",
        f"   - Value: `{'0 leaks' if no_advisory_leak else str(advisory_leaks) + ' leaks'}`",
        "",
        "## Phase gate decision",
        f"- `{'READY' if (pass_rate >= 0.95 and no_advisory_leak) else 'CONDITIONAL'}` for Phase 4 progression.",
    ]
    exit_path = project_root / args.exit_check
    exit_path.parent.mkdir(parents=True, exist_ok=True)
    exit_path.write_text("\n".join(exit_lines) + "\n", encoding="utf-8")

    print(f"Phase 3 complete. tests={total} pass_rate={pass_rate:.2%} advisory_leaks={advisory_leaks}")


if __name__ == "__main__":
    main()
