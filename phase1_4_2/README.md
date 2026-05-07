# Phase 1.4.2 Implementation - Embedding Generation

Implements Phase 1.4.2 from `docs/architecture.md` with edge-case safeguards from `docs/edgecases.md`.

## Objective
Generate consistent embeddings for valid chunks using pre-baked `bge-small-en`, and explicitly quarantine failures.

## Inputs
- `phase1_4_1/reports/chunks/chunks_valid.jsonl`

## Outputs
- `reports/embeddings/chunks_embedded.jsonl`
- `reports/embeddings/chunks_embedding_failed.jsonl`
- `reports/embedding_report.csv`
- `reports/embedding_summary.md`
- `reports/phase1_4_2_exit_check.md`

## Key controls
- Pre-baked model enforcement:
  - no runtime model download
  - fail precheck if local model path is missing
- Single model consistency:
  - `embedding_model = bge-small-en`
  - `embedding_source = pre_baked`
  - pinned `embedding_model_revision`
- Explicit failure labeling for each non-embedded chunk

## Run

```bash
python phase1_4_2/scripts/generate_embeddings.py \
  --chunks-in phase1_4_1/reports/chunks/chunks_valid.jsonl \
  --policy phase1_4_2/policy/embedding_policy.json \
  --embedded-out phase1_4_2/reports/embeddings/chunks_embedded.jsonl \
  --failed-out phase1_4_2/reports/embeddings/chunks_embedding_failed.jsonl \
  --report phase1_4_2/reports/embedding_report.csv \
  --summary phase1_4_2/reports/embedding_summary.md
```

