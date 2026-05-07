# Phase 1.2 Implementation - Content Fetch and Parse

This package implements Phase 1.2 from `docs/architecture.md` with edge-case handling from `docs/edgecases.md`.

## Objective
Fetch and parse accepted Groww mutual fund pages reliably, normalize extracted text, and publish explicit parse outcomes.

## Inputs
- Source registry from Phase 1.1:
  - `phase1_1/data/source_registry_phase1_1.csv`

## Outputs
- `reports/parse_report.csv` - per-URL fetch and parse status.
- `reports/parse_summary.md` - aggregate metrics and action list.
- `reports/parsed/parsed_documents.jsonl` - normalized parse payloads for successful records.
- `reports/phase1_2_exit_check.md` - exit criteria check.

## Edge-case controls included
- `200` but empty/near-empty body -> parser fallback, then mark `invalid` if still empty.
- PDF with low/no extractable text -> mark `low_confidence_extract`.
- Robots/access failure (`401/403/429`) -> mark `blocked`.
- Redirect target validation -> accept only if final URL still matches `https://groww.in/mutual-funds/[fund-name]`.
- No silent failures -> every record gets explicit `parse_status`.

## Run

```bash
python phase1_2/scripts/fetch_and_parse.py \
  --input phase1_1/data/source_registry_phase1_1.csv \
  --policy phase1_2/policy/fetch_parse_policy.json \
  --report phase1_2/reports/parse_report.csv \
  --summary phase1_2/reports/parse_summary.md \
  --parsed phase1_2/reports/parsed/parsed_documents.jsonl
```

## Status values
- `parsed`: fetch and parse successful.
- `invalid`: response readable but text extraction insufficient/invalid.
- `blocked`: fetch blocked by server/policy.
- `low_confidence_extract`: extracted text exists but too weak for reliable downstream use.

