# Phase 1 Quality Dashboard

## Source Freshness
- Total sources: 8
- Broken URLs: 0
- Invalid URL pattern count: 0
- Latest check (UTC): 2026-05-07T12:25:26+00:00
- Source age (days): 0 (SLA <= 7)
- Freshness status: pass

## Pipeline Success Rates
- Parse success rate: 8/8 (100.00%)
- Extraction success rate: 8/8 (100.00%)
- Chunk readiness rate: 339/339 (100.00%)
- Embedding success rate: 339/339 (100.00%)
- Upsert success rate: 339/339 (100.00%)
- Atomic ingestion status: pass
- Atomic ingestion failures: none

## Extraction Completeness
- nav_status: 8/8 (100.00%)
- aum_status: 8/8 (100.00%)
- rating_status: 8/8 (100.00%)
- expense_ratio_status: 8/8 (100.00%)
- exit_load_status: 8/8 (100.00%)
- minimum_sip_status: 8/8 (100.00%)
- riskometer_status: 8/8 (100.00%)
- benchmark_status: 8/8 (100.00%)

## Retrieval Smoke Tests
- expense_ratio: pass | matched: expense ratio | urls: https://groww.in/mutual-funds/quant-small-cap-fund-direct-plan-growth | https://groww.in/mutual-funds/quant-flexi-cap-fund-direct-growth | https://groww.in/mutual-funds/quant-multi-cap-fund-direct-growth
- exit_load: pass | matched: exit load | urls: https://groww.in/mutual-funds/quant-flexi-cap-fund-direct-growth | https://groww.in/mutual-funds/quant-mid-cap-fund-direct-growth | https://groww.in/mutual-funds/quant-aggressive-hybrid-fund-direct-growth
- minimum_sip: pass | matched: min. for sip | urls: https://groww.in/mutual-funds/quant-large-and-mid-cap-fund-direct-growth | https://groww.in/mutual-funds/quant-large-cap-fund-direct-growth | https://groww.in/mutual-funds/quant-small-cap-fund-direct-plan-growth
- riskometer: pass | matched: risk; riskometer | urls: https://groww.in/mutual-funds/quant-multi-cap-fund-direct-growth | https://groww.in/mutual-funds/quant-elss-tax-saver-fund-direct-growth | https://groww.in/mutual-funds/quant-mid-cap-fund-direct-growth
- benchmark: pass | matched: benchmark; fund benchmark | urls: https://groww.in/mutual-funds/quant-elss-tax-saver-fund-direct-growth | https://groww.in/mutual-funds/quant-large-cap-fund-direct-growth | https://groww.in/mutual-funds/quant-large-and-mid-cap-fund-direct-growth

## Phase 1.5 Gate
- Exit gate: pass
- Gate rules: no broken URLs, freshness SLA pass, atomic ingestion, smoke tests pass.
