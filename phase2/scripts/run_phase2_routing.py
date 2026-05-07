import argparse
import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple

import chromadb
from sentence_transformers import SentenceTransformer


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Phase 2 retrieval and policy routing checks")
    parser.add_argument("--policy", required=True, help="Path to routing policy JSON")
    parser.add_argument("--source-registry", required=True, help="Phase 1.1 source registry CSV")
    parser.add_argument("--report", required=True, help="Output routing report CSV")
    parser.add_argument("--summary", required=True, help="Output routing summary markdown")
    parser.add_argument("--exit-check", required=True, help="Output phase2 exit check markdown")
    return parser.parse_args()


def load_registry(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as fp:
        return list(csv.DictReader(fp))


def tokenize(text: str) -> List[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def extract_scheme(query: str, scheme_names: List[str]) -> str:
    q = query.lower()
    for scheme in sorted(scheme_names, key=len, reverse=True):
        if scheme.lower() in q:
            return scheme
    return ""


def classify_query(query: str, cfg: Dict) -> Tuple[str, str]:
    q = query.lower()
    advisory_terms = [kw for kw in cfg["advisory_keywords"] if kw in q]
    factual_terms = [kw for kw in cfg["factual_markers"] if kw in q]
    comparative_terms = [kw for kw in cfg["comparative_markers"] if kw in q]

    if comparative_terms:
        return "refusal", "comparative_or_advisory_intent"
    if advisory_terms and factual_terms:
        return "refusal", "mixed_intent_advisory_dominant"
    if advisory_terms:
        return "refusal", "advisory_intent"
    if factual_terms:
        return "factual", "factual_intent"
    return "factual", "default_factual_route"


def keyword_overlap(query: str, doc_text: str) -> float:
    q_tokens = set(tokenize(query))
    d_tokens = set(tokenize(doc_text))
    if not q_tokens:
        return 0.0
    return len(q_tokens & d_tokens) / len(q_tokens)


def retrieve(
    query: str,
    collection,
    model: SentenceTransformer,
    top_k: int,
    accepted_url_re: re.Pattern[str],
    scheme_name: str,
    distance_threshold: float,
    min_keyword_overlap: float,
) -> Tuple[List[Dict], str]:
    q_emb = model.encode([query], normalize_embeddings=True).tolist()
    result = collection.query(
        query_embeddings=q_emb,
        n_results=top_k,
        include=["metadatas", "documents", "distances"],
    )

    docs = result.get("documents", [[]])[0]
    metas = result.get("metadatas", [[]])[0]
    distances = result.get("distances", [[]])[0]

    filtered: List[Dict] = []
    dropped_non_allowlist = 0
    for i, meta in enumerate(metas):
        m = meta or {}
        url = str(m.get("source_url", "") or m.get("citation_url", ""))
        if not accepted_url_re.match(url):
            dropped_non_allowlist += 1
            continue
        row = {
            "chunk_text": docs[i] if i < len(docs) else "",
            "distance": float(distances[i]) if i < len(distances) else 999.0,
            "source_url": url,
            "scheme_name": str(m.get("scheme_name", "")),
            "source_id": str(m.get("source_id", "")),
        }
        filtered.append(row)

    reason = "retrieval_ok"
    if dropped_non_allowlist > 0:
        reason = "dropped_non_allowlisted_chunks"

    if scheme_name:
        strict = [r for r in filtered if r["scheme_name"].lower() == scheme_name.lower()]
        if strict:
            filtered = strict
            reason = "scheme_filtered"

    good = []
    for row in filtered:
        overlap = keyword_overlap(query, row["chunk_text"])
        row["keyword_overlap"] = overlap
        if row["distance"] <= distance_threshold and overlap >= min_keyword_overlap:
            good.append(row)

    if not good:
        return [], "weak_or_missing_evidence"
    return good, reason


def write_csv(path: Path, rows: List[Dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    args = parse_args()
    project_root = Path(__file__).resolve().parents[2]
    policy = json.loads((project_root / args.policy).read_text(encoding="utf-8"))
    registry = load_registry(project_root / args.source_registry)
    scheme_names = [r.get("scheme_name", "") for r in registry if r.get("scheme_name")]

    chroma_cfg = policy["chroma"]
    client = chromadb.PersistentClient(path=str(project_root / chroma_cfg["persist_directory"]))
    collection = client.get_collection(chroma_cfg["collection_name"])
    model = SentenceTransformer(str(project_root / policy["embedding"]["model_path"]))
    accepted_url_re = re.compile(policy["accepted_url_regex"])

    retrieval_cfg = policy["retrieval"]
    class_cfg = policy["classification"]
    rows: List[Dict] = []

    factual_total = 0
    factual_with_evidence = 0
    advisory_total = 0
    advisory_refused = 0

    for t in policy["gold_tests"]:
        qid = t["id"]
        query = t["query"]
        expected_route = t["expected_route"]
        predicted_route, route_reason = classify_query(query, class_cfg)
        scheme = extract_scheme(query, scheme_names)

        retrieved = []
        retrieval_reason = ""
        top_url = ""
        top_scheme = ""
        if predicted_route == "factual":
            retrieved, retrieval_reason = retrieve(
                query=query,
                collection=collection,
                model=model,
                top_k=int(retrieval_cfg["top_k"]),
                accepted_url_re=accepted_url_re,
                scheme_name=scheme,
                distance_threshold=float(retrieval_cfg["distance_threshold"]),
                min_keyword_overlap=float(retrieval_cfg["min_keyword_overlap"]),
            )
            if not retrieved:
                predicted_route = "no_answer"
            else:
                top_url = retrieved[0]["source_url"]
                top_scheme = retrieved[0]["scheme_name"]

        if expected_route == "factual":
            factual_total += 1
            if predicted_route == "factual" and len(retrieved) > 0:
                factual_with_evidence += 1
        else:
            advisory_total += 1
            if predicted_route == "refusal":
                advisory_refused += 1

        pass_flag = (
            (expected_route == "factual" and predicted_route == "factual" and len(retrieved) > 0)
            or (expected_route == "refusal" and predicted_route == "refusal")
        )
        rows.append(
            {
                "query_id": qid,
                "query": query,
                "expected_route": expected_route,
                "predicted_route": predicted_route,
                "pass": "yes" if pass_flag else "no",
                "route_reason": route_reason,
                "retrieval_reason": retrieval_reason,
                "detected_scheme": scheme,
                "retrieved_chunk_count": len(retrieved),
                "top_source_url": top_url,
                "top_scheme_name": top_scheme,
                "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            }
        )

    write_csv(project_root / args.report, rows)

    advisory_refusal_rate = (advisory_refused / advisory_total) if advisory_total else 0.0
    factual_retrieval_rate = (factual_with_evidence / factual_total) if factual_total else 0.0

    advisory_target = float(policy["thresholds"]["min_advisory_refusal_rate"])
    factual_target = float(policy["thresholds"]["min_factual_retrieval_rate"])

    exit_ready = advisory_refusal_rate >= advisory_target and factual_retrieval_rate >= factual_target

    summary_lines = [
        "# Phase 2 Routing Summary",
        "",
        f"- Generated at (UTC): {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}",
        f"- Total tests: {len(rows)}",
        f"- Passed tests: {sum(1 for r in rows if r['pass'] == 'yes')}",
        f"- Advisory refusal rate: {advisory_refusal_rate:.2%} (target >= {advisory_target:.2%})",
        f"- Factual retrieval rate: {factual_retrieval_rate:.2%} (target >= {factual_target:.2%})",
        "",
        "## Edge-case controls exercised",
        "- Mixed-intent and comparative questions route to refusal.",
        "- Retrieval enforces hard Groww URL post-filter.",
        "- Scheme-aware strict filtering is applied when scheme entity is present.",
        "- Weak evidence routes to safe no-answer path.",
        "",
    ]
    summary_path = project_root / args.summary
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text("\n".join(summary_lines) + "\n", encoding="utf-8")

    exit_lines = [
        "# Phase 2 Exit Check",
        "",
        "## Exit criteria status",
        "",
        "1. **Advisory prompts route to refusal >= target threshold**",
        f"   - Status: `{'PASS' if advisory_refusal_rate >= advisory_target else 'FAIL'}`",
        f"   - Value: `{advisory_refusal_rate:.2%}` (target `{advisory_target:.2%}`)",
        "",
        "2. **Factual prompts retrieve at least one relevant chunk for gold test set**",
        f"   - Status: `{'PASS' if factual_retrieval_rate >= factual_target else 'FAIL'}`",
        f"   - Value: `{factual_retrieval_rate:.2%}` (target `{factual_target:.2%}`)",
        "",
        "## Phase gate decision",
        f"- `{'READY' if exit_ready else 'CONDITIONAL'}` for Phase 3 progression.",
    ]
    exit_path = project_root / args.exit_check
    exit_path.parent.mkdir(parents=True, exist_ok=True)
    exit_path.write_text("\n".join(exit_lines) + "\n", encoding="utf-8")

    print(
        "Phase 2 complete. "
        f"tests={len(rows)} pass={sum(1 for r in rows if r['pass'] == 'yes')} "
        f"advisory_refusal={advisory_refusal_rate:.2%} factual_retrieval={factual_retrieval_rate:.2%}"
    )


if __name__ == "__main__":
    main()
