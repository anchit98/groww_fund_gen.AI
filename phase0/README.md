# Phase 0 Implementation Package

This folder contains the Phase 0 outputs defined in `docs/architecture.md`, implemented as standalone artifacts and aligned with controls from `docs/edgecases.md`.

## Included deliverables
- `corpus_registry.csv` - selected AMC, scheme set, category coverage, and intake status.
- `discovery_url_register.csv` - accepted Groww mutual fund URLs.
- `source_allowlist_policy.md` - strict Groww URL-pattern policy.
- `scraping_field_contract.md` - finalized extraction fields and normalization rules.
- `compliance_checklist.md` - Phase 0 go/no-go checklist and sign-off criteria.
- `refusal_examples_library.md` - refusal taxonomy and approved response patterns.

## Phase 0 status
- Scope and compliance baselines are documented.
- Groww mutual fund URLs are registered.
- URL acceptance is restricted to one pattern.

## Important guardrail
Only URLs matching `https://groww.in/mutual-funds/[fund-name]` are accepted for ingestion, retrieval, and citation.

