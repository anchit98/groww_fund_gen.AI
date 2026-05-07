# Phase 6 - Operations and Continuous Refresh

Phase 6 operationalizes monitoring for freshness, ingestion reliability, drift, and source-change traceability.

It implements architecture tasks from `docs/architecture.md` and checks from `docs/edgecases.md`:

- automate scheduled refresh execution
- alert on stale sources or failed ingestion
- track drift in refusal/retrieval quality proxies
- maintain source update change logs

## Files

- `phase6/policy/operations_policy.json`
- `phase6/scripts/run_phase6_operations.py`
- `phase6/scripts/run_phase6_scheduled_refresh.py`
- `phase6/reports/` (generated)

## Run operations checks only

```bash
python phase6/scripts/run_phase6_operations.py \
  --policy phase6/policy/operations_policy.json \
  --status-out phase6/reports/ops_status.json \
  --summary-out phase6/reports/ops_summary.md \
  --change-log-out phase6/reports/source_change_log.md
```

Optional: update drift baseline from latest Phase 5 metrics:

```bash
python phase6/scripts/run_phase6_operations.py \
  --policy phase6/policy/operations_policy.json \
  --status-out phase6/reports/ops_status.json \
  --summary-out phase6/reports/ops_summary.md \
  --change-log-out phase6/reports/source_change_log.md \
  --update-baseline
```

## Run scheduled refresh + checks

```bash
python phase6/scripts/run_phase6_scheduled_refresh.py
```

This script runs:

1. `phase1_5/scripts/run_refresh_pipeline.py`
2. `phase6/scripts/run_phase6_operations.py`

## Outputs

- `phase6/reports/ops_status.json`: machine-readable operations health + alert state
- `phase6/reports/ops_summary.md`: human-readable operations report
- `phase6/reports/source_change_log.md`: added/removed source URLs vs last snapshot
- `phase6/reports/source_registry_snapshot.json`: current source snapshot for diffing
- `phase6/reports/drift_baseline.json`: stored baseline for drift comparisons
