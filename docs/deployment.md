# Deployment Runbook

## Backend (Render Web Service)

- Service name: `rag-bot-backend`
- Runtime: Python
- Build command:

```bash
pip install -r requirements.txt
```

- Start command:

```bash
uvicorn backend.server:app --host 0.0.0.0 --port $PORT
```

- Required environment variables:
  - `GROQ_API_KEY` (secret)
  - `TZ=Asia/Kolkata`

## Scheduled Refresh (Render Cron)

- Service name: `rag-bot-refresh-weekdays`
- Schedule (UTC): `15 4 * * 1-5` (Mon-Fri 09:45 IST)
- Build command:

```bash
pip install -r requirements.txt
```

- Start command:

```bash
python phase6/scripts/run_phase6_scheduled_refresh.py
```

- Required environment variables:
  - `GROQ_API_KEY` (secret)
  - `TZ=Asia/Kolkata`

## Frontend

Set:

- `VITE_API_BASE_URL=<your-render-backend-url>`

Then build/deploy frontend as usual.

## Pre-Go-Live Verification

Run from project root:

```bash
python phase5/scripts/run_phase5_evaluation.py --cases phase5/policy/evaluation_cases.json --report phase5/reports/evaluation_report.csv --summary phase5/reports/evaluation_summary.md --exit-check phase5/reports/phase5_exit_check.md --api-base-url http://127.0.0.1:8001
python phase5/scripts/run_phase5_regression.py --report phase5/reports/evaluation_report.csv --thresholds phase5/policy/regression_thresholds.json --gate-report phase5/reports/regression_gate.md
python phase6/scripts/run_phase6_operations.py --policy phase6/policy/operations_policy.json --status-out phase6/reports/ops_status.json --summary-out phase6/reports/ops_summary.md --change-log-out phase6/reports/source_change_log.md
```

Expected:

- Phase 5 gate: `PASS`
- Phase 6 status: `ok` with `alerts=0`
