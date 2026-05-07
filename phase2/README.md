# Phase 2 Implementation - Retrieval and Policy Routing

Implements Phase 2 from `docs/architecture.md` with controls aligned to `docs/edgecases.md`.

## Objective
Route advisory vs factual queries safely and retrieve only policy-eligible evidence.

## What is implemented
- Rule-based factual vs advisory classifier (including mixed intent handling).
- Scheme/entity extraction from known scheme names for stricter retrieval.
- Metadata-aware retrieval over Chroma with hard allowlist URL filtering.
- Weak evidence fallback to safe `no_answer`.
- Gold test harness and Phase 2 gate reports.

## Inputs
- `phase1_1/data/source_registry_phase1_1.csv`
- `phase1_4_3/chroma_store` collection
- `models/bge-small-en`
- `phase2/policy/routing_policy.json`

## Outputs
- `phase2/reports/routing_report.csv`
- `phase2/reports/routing_summary.md`
- `phase2/reports/phase2_exit_check.md`

## Run
```bash
python phase2/scripts/run_phase2_routing.py \
  --policy phase2/policy/routing_policy.json \
  --source-registry phase1_1/data/source_registry_phase1_1.csv \
  --report phase2/reports/routing_report.csv \
  --summary phase2/reports/routing_summary.md \
  --exit-check phase2/reports/phase2_exit_check.md
```
