# Phase 1.5 Implementation - Refresh Scheduling and Data Foundation QA

Implements Phase 1.5 from `docs/architecture.md` with checks mapped to `docs/edgecases.md`.

## Objective
Operationalize refresh and quality checks before Phase 2 by validating:
- source freshness and broken URLs
- ingestion failure signals
- retrieval smoke tests
- dashboard metrics

## Inputs
- `phase1_1/reports/source_validation_report.csv`
- `phase1_2/reports/parse_report.csv`
- `phase1_3/reports/extraction_report.csv`
- `phase1_4_1/reports/metadata_validation_report.csv`
- `phase1_4_2/reports/embedding_report.csv`
- `phase1_4_3/reports/upsert_report.csv`
- Chroma collection from `phase1_4_3/chroma_store`

## Outputs
- `reports/smoke_test_report.csv`
- `reports/phase1_quality_dashboard.md`
- `reports/phase1_5_exit_check.md`

## Scheduled Refresh (Production)
- Cron: `45 9 * * 1-5` (Monday to Friday at 09:45)
- Timezone: `Asia/Kolkata`
- Hosting note: run this via your server scheduler/platform cron (not tied to an active local system/session).

## Render Deployment
- Render cron uses UTC schedule; for `09:45 Asia/Kolkata` use `15 4 * * 1-5`.
- Config file: `render.yaml`
- Scheduled command: `python phase1_5/scripts/run_refresh_pipeline.py`
- The pipeline runs Phase `1.1 -> 1.5` in sequence and refreshes reports/index automatically.

## Run
```bash
python phase1_5/scripts/run_phase1_5_checks.py \
  --policy phase1_5/policy/phase1_5_policy.json \
  --source-report phase1_1/reports/source_validation_report.csv \
  --parse-report phase1_2/reports/parse_report.csv \
  --extraction-report phase1_3/reports/extraction_report.csv \
  --chunk-report phase1_4_1/reports/metadata_validation_report.csv \
  --embedding-report phase1_4_2/reports/embedding_report.csv \
  --upsert-report phase1_4_3/reports/upsert_report.csv \
  --smoke-out phase1_5/reports/smoke_test_report.csv \
  --dashboard-out phase1_5/reports/phase1_quality_dashboard.md
```

