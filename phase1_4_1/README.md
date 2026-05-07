# Phase 1.4.1 Implementation - Chunk Construction and Metadata Binding

Implements Phase 1.4.1 from `docs/architecture.md` with safeguards from `docs/edgecases.md`.

## Objective
Create stable retrieval chunks from parsed Groww source text and attach complete mandatory metadata.

## Inputs
- `phase1_2/reports/parsed/parsed_documents.jsonl`
- `phase1_3/reports/extracted/scheme_facts.jsonl`

## Outputs
- `reports/chunks/chunks_valid.jsonl`
- `reports/chunks/chunks_quarantined.jsonl`
- `reports/chunks/chunks_rejected.jsonl`
- `reports/metadata_validation_report.csv`
- `reports/metadata_validation_summary.md`
- `reports/phase1_4_1_exit_check.md`

## Mandatory metadata bound per chunk
- `source_url`
- `source_domain`
- `doc_type`
- `scheme_name`
- `amc_name`
- `effective_date`
- `ingested_at`

## Run

```bash
python phase1_4_1/scripts/build_chunks_and_metadata.py \
  --parsed phase1_2/reports/parsed/parsed_documents.jsonl \
  --facts phase1_3/reports/extracted/scheme_facts.jsonl \
  --policy phase1_4_1/policy/chunking_policy.json \
  --valid-out phase1_4_1/reports/chunks/chunks_valid.jsonl \
  --quarantine-out phase1_4_1/reports/chunks/chunks_quarantined.jsonl \
  --rejected-out phase1_4_1/reports/chunks/chunks_rejected.jsonl \
  --report phase1_4_1/reports/metadata_validation_report.csv \
  --summary phase1_4_1/reports/metadata_validation_summary.md
```

