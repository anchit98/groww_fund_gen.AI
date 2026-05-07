# Phase 1.4.3 Implementation - ChromaDB Upsert and Index Integrity

Implements Phase 1.4.3 from `docs/architecture.md`, aligned to edge cases in `docs/edgecases.md`.

## Objective
Persist embedded chunks into ChromaDB with strict integrity checks and publish upsert reconciliation reports.

## Input
- `phase1_4_2/reports/embeddings/chunks_embedded.jsonl`

## Output
- `reports/upserted_chunks.jsonl`
- `reports/rejected_chunks.jsonl`
- `reports/upsert_report.csv`
- `reports/upsert_summary.md`
- `reports/phase1_4_3_exit_check.md`

## Key controls
- Enforce Groww URL pattern at write time.
- Enforce embedding metadata consistency (`bge-small-en`, `pre_baked`).
- Enforce Chroma target store.
- Validate post-upsert ID and metadata consistency.
- Publish created/updated/rejected counts.

## Run

```bash
python phase1_4_3/scripts/upsert_to_chromadb.py \
  --embedded-in phase1_4_2/reports/embeddings/chunks_embedded.jsonl \
  --policy phase1_4_3/policy/upsert_policy.json \
  --upserted-out phase1_4_3/reports/upserted_chunks.jsonl \
  --rejected-out phase1_4_3/reports/rejected_chunks.jsonl \
  --report phase1_4_3/reports/upsert_report.csv \
  --summary phase1_4_3/reports/upsert_summary.md
```

