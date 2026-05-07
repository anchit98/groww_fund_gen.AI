# Phase 3 Implementation - Answer Generation and Output Contract

Implements Phase 3 from `docs/architecture.md` with controls aligned to `docs/edgecases.md`.

## Objective
Produce deterministic, compliant, source-grounded answers with strict output contract checks.

## What is implemented
- Groq LLM-based factual answer composer.
- Advisory/refusal routing with one Groww citation.
- Grounding check to prevent unsupported claims.
- Policy leak check to block recommendation language.
- Contract enforcement:
  - max 3 sentences
  - exactly 1 citation URL
  - mandatory footer date (`As of YYYY-MM-DD.`)
- Phase 3 test harness and exit check reports.

## Inputs
- `phase3/policy/answer_policy.json`
- `phase1_4_3/chroma_store` collection
- `models/bge-small-en`
- `.env` with `GROQ_API_KEY`

## Outputs
- `phase3/reports/answer_contract_report.csv`
- `phase3/reports/answer_summary.md`
- `phase3/reports/phase3_exit_check.md`

## Run
```bash
python phase3/scripts/run_phase3_answering.py \
  --policy phase3/policy/answer_policy.json \
  --report phase3/reports/answer_contract_report.csv \
  --summary phase3/reports/answer_summary.md \
  --exit-check phase3/reports/phase3_exit_check.md
```
