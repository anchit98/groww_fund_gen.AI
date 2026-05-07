# Phase 1.3 Implementation - Normalization and Field Extraction

This package implements Phase 1.3 from `docs/architecture.md` and aligns with Phase 1.3 edge cases in `docs/edgecases.md`.

## Objective
Extract mandatory scheme facts from parsed Groww content, normalize values, preserve raw evidence, and explicitly label missing/conflicting outcomes.

## Input
- `phase1_2/reports/parsed/parsed_documents.jsonl`
- `phase1_1/data/source_registry_phase1_1.csv`

## Output
- `reports/extracted/scheme_facts.jsonl`
- `reports/extracted/scheme_process_guides.jsonl`
- `reports/extraction_report.csv`
- `reports/extraction_summary.md`
- `reports/phase1_3_exit_check.md`

## Mandatory fields covered
- NAV
- Fund Size (AUM)
- Rating
- Expense ratio
- Exit load
- Minimum SIP amount
- ELSS lock-in period (if applicable)
- Riskometer classification
- Benchmark index (full name)
- Process to download statements or capital gains reports

## Key controls
- Missing values are marked as `not_available` (no inference).
- Multiple contradictory candidates are marked as `conflicting`.
- Numeric normalization includes unit handling and validation.
- Raw snippets are retained for auditability.

## Run

```bash
python phase1_3/scripts/extract_fields.py \
  --parsed phase1_2/reports/parsed/parsed_documents.jsonl \
  --registry phase1_1/data/source_registry_phase1_1.csv \
  --policy phase1_3/policy/extraction_policy.json \
  --facts-out phase1_3/reports/extracted/scheme_facts.jsonl \
  --process-out phase1_3/reports/extracted/scheme_process_guides.jsonl \
  --report phase1_3/reports/extraction_report.csv \
  --summary phase1_3/reports/extraction_summary.md
```

