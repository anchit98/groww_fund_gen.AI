# Phase 1.1 Implementation - Source Intake and Validation Gate

This package implements Phase 1.1 from `docs/architecture.md` with edge-case safeguards from `docs/edgecases.md`.

## Objective
Ensure only approved, healthy, and policy-compliant URLs enter ingestion.

## What is implemented
- Source intake registry: `data/source_registry_phase1_1.csv`
- Allowlist and validation policy: `policy/source_intake_policy.json`
- Executable validator: `scripts/validate_source_intake.py`
- Validation outputs:
  - `reports/source_validation_report.csv`
  - `reports/source_validation_summary.md`

## Controls covered (Phase 1.1)
- Groww URL pattern allowlist and source tier eligibility
- Only `https://groww.in/mutual-funds/[fund-name]` acceptance
- Doc type validity checks and path-hint mismatch warnings
- URL-level non-matching path blocking
- URL health checks (HTTP status, final URL, redirect domain check)
- Quarantine/reject workflow with explicit reasons

## Run
From repo root:

```bash
python phase1_1/scripts/validate_source_intake.py \
  --input phase1_1/data/source_registry_phase1_1.csv \
  --policy phase1_1/policy/source_intake_policy.json \
  --report phase1_1/reports/source_validation_report.csv \
  --summary phase1_1/reports/source_validation_summary.md
```

Optional (offline/policy-only checks):

```bash
python phase1_1/scripts/validate_source_intake.py \
  --input phase1_1/data/source_registry_phase1_1.csv \
  --policy phase1_1/policy/source_intake_policy.json \
  --report phase1_1/reports/source_validation_report.csv \
  --summary phase1_1/reports/source_validation_summary.md \
  --skip-http
```

## Output status meanings
- `pass`: Eligible for Phase 1.2 fetch stage.
- `quarantine`: Requires manual review/fix before ingestion.
- `reject`: Violates hard policy controls (must not proceed).

