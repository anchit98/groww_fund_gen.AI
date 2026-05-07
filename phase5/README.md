# Phase 5 - Evaluation, QA, and Hardening

This phase validates quality, safety, and reliability using an executable evaluation suite aligned with:

- `docs/architecture.md` (Phase 5 tasks)
- `docs/edgecases.md` (test-set gaps, adversarial coverage, contract regression)

## What is implemented

- Evaluation set covering:
  - factual answerability
  - advisory refusal
  - ambiguous phrasing
  - adversarial prompt injection/comparative/internal-rule probes
- Metrics:
  - factual correctness
  - citation/source-link correctness (Groww allowlist only)
  - response contract compliance (exactly 3 sentences, no inline citation/footer text)
  - refusal precision/recall
- Regression gate script with explicit thresholds for CI-style pass/fail checks.

## Files

- `phase5/policy/evaluation_cases.json`
- `phase5/policy/regression_thresholds.json`
- `phase5/scripts/run_phase5_evaluation.py`
- `phase5/scripts/run_phase5_regression.py`
- `phase5/reports/` (generated at runtime)

## Run locally

1. Start backend:

```bash
python backend/server.py
```

2. Run evaluation:

```bash
python phase5/scripts/run_phase5_evaluation.py \
  --cases phase5/policy/evaluation_cases.json \
  --report phase5/reports/evaluation_report.csv \
  --summary phase5/reports/evaluation_summary.md \
  --exit-check phase5/reports/phase5_exit_check.md \
  --api-base-url http://127.0.0.1:8001
```

3. Run regression gate:

```bash
python phase5/scripts/run_phase5_regression.py \
  --report phase5/reports/evaluation_report.csv \
  --thresholds phase5/policy/regression_thresholds.json \
  --gate-report phase5/reports/regression_gate.md
```

## Suggested CI command

Use the same two commands above in sequence. The regression script exits non-zero when thresholds fail.
