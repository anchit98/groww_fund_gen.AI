# Mutual Fund FAQ Assistant - Data Dictionary

## 1) Purpose

This document defines the canonical data model for scraped and normalized mutual fund facts used by the FAQ assistant.

It is aligned to:

- `docs/architecture.md` (Scraping Data Contract + ingestion/retrieval design)
- `docs/edgecases.md` (quality, compliance, and fallback behavior)

---

## 2) Scope and Source Policy

- This dictionary covers scheme-level factual attributes and process guidance fields used for Q&A.
- Final production facts and source links must come only from URLs matching `https://groww.in/mutual-funds/[fund-name]`.
- Any non-matching URL is out of scope and must be rejected.

---

## 3) Global Conventions

### 3.1 Naming

- Use `snake_case` for all keys.
- Use singular nouns for field names.

### 3.2 Date/Time

- `date` format: `YYYY-MM-DD` (ISO-8601 date)
- `datetime` format: UTC ISO-8601 (example: `2026-05-07T06:35:00Z`)

### 3.3 Numeric Storage

- Store normalized numeric values in dedicated numeric fields.
- Also store unmodified source text in paired `*_raw_text` fields.

### 3.4 Missing Data

- For unavailable values in accepted Groww sources, set normalized value to `null`.
- Set `availability_status` to `not_available`.
- Never infer/estimate unavailable factual values.

### 3.5 Confidence and Freshness

- Every extracted fact must retain `source_url` and `value_as_of_date` (when available).
- If `value_as_of_date` is absent, fallback order:
  1. `effective_date`
  2. `ingested_at` (date portion)

### 3.6 Phase 1 Subphase Checkpoints (Data Controls)

- **Phase 1.1 Source Intake**: `source_tier`, `status`, `domain`, `doc_type`, and `url` must validate before fetch.
- **Phase 1.2 Fetch and Parse**: parser outcomes must be traceable using `http_status`, `content_hash`, and status transitions (`invalid`/`blocked`).
- **Phase 1.3 Field Extraction**: normalized `scheme_facts` fields must preserve paired `*_raw_text`, with `availability_status` for missing/conflicting values.
- **Phase 1.4.1 Chunk Construction**: every `content_chunks` candidate must include mandatory metadata and be rejectable on incompleteness.
- **Phase 1.4.2 Embedding Generation**: all chunk embeddings must use `embedding_model = bge-small-en`.
- **Phase 1.4.3 ChromaDB Upsert**: only embedded chunks with valid metadata are written to `vector_store = chroma`.
- **Phase 1.5 Refresh and QA**: data freshness should be measurable using `last_checked_at`, `effective_date`, and `ingested_at`.
- **Phase 1.5 Hosted Scheduling**: production refresh is scheduler-driven (Render cron), with business timing set to Monday-Friday 09:45 `Asia/Kolkata` (UTC cron `15 4 * * 1-5`).

### 3.7 Retrieval Technology Defaults

- Embedding model default: `bge-small-en`
- Vector database default: `ChromaDB`
- Answer composer default: `Groq` API (key from `GROQ_API_KEY` environment variable)
- These defaults apply to all records in `content_chunks` unless explicitly versioned otherwise.
- Embedding deployment mode default: `pre_baked` (model shipped with runtime artifact; no runtime download).

---

## 4) Core Entities

## 4.1 `sources` (source registry)

Tracks accepted Groww URLs and their governance status.


| Field             | Type           | Required | Example                     | Notes                                                       |
| ----------------- | -------------- | -------- | --------------------------- | ----------------------------------------------------------- |
| `source_id`       | `string`       | Yes      | `src_01J2...`               | Unique ID                                                   |
| `amc_name`        | `string`       | Yes      | `Quant Mutual Fund`         | Canonical AMC name                                          |
| `scheme_name`     | `string`       | Yes      | `Quant ELSS Tax Saver Fund` | Required for Groww mutual fund page records                |
| `doc_type`        | `enum`         | Yes      | `factsheet`                 | See enum values below                                       |
| `url`             | `string (url)` | Yes      | `https://...`               | Canonical source URL                                        |
| `domain`          | `string`       | Yes      | `groww.in`                 | Must be `groww.in`                                          |
| `source_tier`     | `enum`         | Yes      | `groww_mutual_funds_only`   | Allowed value: `groww_mutual_funds_only`                     |
| `status`          | `enum`         | Yes      | `approved`                  | `approved`, `stale`, `invalid`, `blocked`, `pending_review` |
| `last_checked_at` | `datetime`     | Yes      | `2026-05-07T06:35:00Z`      | URL health/freshness check time                             |
| `http_status`     | `integer`      | No       | `200`                       | Latest fetch status                                         |
| `content_hash`    | `string`       | No       | `sha256:...`                | Change detection                                            |


### `doc_type` enum

- `factsheet`
- `groww_mutual_fund_page`
- `statement_download_guide`
- `capital_gains_report_guide`
- `other_groww_page`

---

## 4.2 `scheme_facts` (normalized factual attributes)

Canonical structured facts per scheme and source snapshot.


| Field                      | Type            | Required | Example                          | Validation / Rules                                          |
| -------------------------- | --------------- | -------- | -------------------------------- | ----------------------------------------------------------- |
| `fact_id`                  | `string`        | Yes      | `fact_01J2...`                   | Unique ID                                                   |
| `scheme_name`              | `string`        | Yes      | `Quant Flexi Cap Fund`           | Canonical scheme name                                       |
| `amc_name`                 | `string`        | Yes      | `Quant Mutual Fund`              | Canonical AMC name                                          |
| `nav_value`                | `decimal(18,6)` | No       | `89.472300`                      | Must be `> 0` when present                                  |
| `nav_currency`             | `string`        | No       | `INR`                            | Default `INR`                                               |
| `nav_raw_text`             | `string`        | No       | `NAV: Rs. 89.4723`               | Unmodified source text                                      |
| `nav_value_as_of_date`     | `date`          | No       | `2026-05-06`                     | Use fallback if absent                                      |
| `aum_value_cr`             | `decimal(18,2)` | No       | `12345.67`                       | Store in INR crore unit                                     |
| `aum_raw_text`             | `string`        | No       | `AUM: Rs 12,345.67 Cr`           | Unmodified source text                                      |
| `aum_value_as_of_date`     | `date`          | No       | `2026-04-30`                     | Month-end common                                            |
| `rating_value`             | `string`        | No       | `4`                              | Keep source value as text                                   |
| `rating_scale`             | `string`        | No       | `5_star`                         | Optional normalization                                      |
| `rating_provider`          | `string`        | No       | `CRISIL`                         | Optional; only if present on accepted Groww page           |
| `rating_raw_text`          | `string`        | No       | `CRISIL Fund Rank: 4`            | Must be from accepted Groww source                          |
| `expense_ratio_percent`    | `decimal(5,2)`  | No       | `1.24`                           | `0 <= value <= 100`                                         |
| `expense_ratio_raw_text`   | `string`        | No       | `Expense Ratio: 1.24%`           | Unmodified source text                                      |
| `expense_ratio_as_of_date` | `date`          | No       | `2026-05-01`                     | Use fallback if absent                                      |
| `exit_load_text`           | `string`        | No       | `1% if redeemed within 365 days` | Preserve conditions                                         |
| `min_sip_amount_inr`       | `integer`       | No       | `500`                            | `>= 0`, INR only                                            |
| `min_sip_raw_text`         | `string`        | No       | `Minimum SIP: Rs 500`            | Unmodified source text                                      |
| `elss_lock_in_years`       | `decimal(4,2)`  | No       | `3.00`                           | Applicable for ELSS only                                    |
| `elss_lock_in_raw_text`    | `string`        | No       | `Lock-in: 3 years`               | Set null for non-ELSS                                       |
| `riskometer_label`         | `enum`          | No       | `very_high`                      | See enum values below                                       |
| `riskometer_raw_text`      | `string`        | No       | `Riskometer: Very High`          | Keep source phrase                                          |
| `benchmark_full_name`      | `string`        | No       | `Nifty 500 TRI`                  | Full name only                                              |
| `benchmark_raw_text`       | `string`        | No       | `Benchmark: Nifty 500 TRI`       | Unmodified                                                  |
| `availability_status`      | `enum`          | Yes      | `available`                      | `available`, `not_available`, `conflicting`, `under_review` |
| `source_id`                | `string`        | Yes      | `src_01J2...`                    | FK to `sources`                                             |
| `source_url`               | `string (url)`  | Yes      | `https://...`                    | Source-link candidate URL                                   |
| `effective_date`           | `date`          | No       | `2026-05-01`                     | Source effective date                                       |
| `ingested_at`              | `datetime`      | Yes      | `2026-05-07T06:35:00Z`           | Ingestion timestamp                                         |


### `riskometer_label` enum (normalized)

- `low`
- `low_to_moderate`
- `moderate`
- `moderately_high`
- `high`
- `very_high`
- `unknown`

Notes:

- If source taxonomy differs, map to nearest canonical label and keep exact phrase in `riskometer_raw_text`.
- If multiple accepted Groww records conflict, set `availability_status = conflicting` and do not auto-merge.

---

## 4.3 `scheme_process_guides` (how-to fields)

Stores structured process guidance for statements/capital gains reports.


| Field                  | Type            | Required | Example                                            | Notes                                                 |
| ---------------------- | --------------- | -------- | -------------------------------------------------- | ----------------------------------------------------- |
| `guide_id`             | `string`        | Yes      | `guide_01J2...`                                    | Unique ID                                             |
| `scheme_name`          | `string`        | No       | `Quant ELSS Tax Saver Fund`                        | Optional if AMC-level process                         |
| `amc_name`             | `string`        | Yes      | `Quant Mutual Fund`                                | Canonical AMC name                                    |
| `guide_type`           | `enum`          | Yes      | `statement_download`                               | `statement_download`, `capital_gains_report_download` |
| `channel`              | `enum`          | Yes      | `web`                                              | `web`, `app`, `email`, `rta_portal`, `other`          |
| `instruction_steps`    | `array<string>` | Yes      | `["Login", "Go to Reports", "Download statement"]` | Ordered concise steps                                 |
| `instruction_raw_text` | `string`        | Yes      | `To download statement...`                         | Unmodified source block                               |
| `applies_to`           | `string`        | No       | `all_schemes`                                      | Scope note                                            |
| `source_id`            | `string`        | Yes      | `src_01J2...`                                      | FK to `sources`                                       |
| `source_url`           | `string (url)`  | Yes      | `https://...`                                      | Groww mutual fund link                                 |
| `effective_date`       | `date`          | No       | `2026-04-12`                                       | If provided                                           |
| `ingested_at`          | `datetime`      | Yes      | `2026-05-07T06:35:00Z`                             | Ingestion timestamp                                   |


---

## 4.4 `content_chunks` (retrieval layer)

Stores chunked text and metadata for semantic retrieval.


| Field            | Type            | Required | Example                | Notes                         |
| ---------------- | --------------- | -------- | ---------------------- | ----------------------------- |
| `chunk_id`       | `string`        | Yes      | `chk_01J2...`          | Unique chunk ID               |
| `source_id`      | `string`        | Yes      | `src_01J2...`          | FK to `sources`               |
| `source_url`     | `string (url)`  | Yes      | `https://...`          | Mandatory                     |
| `source_domain`  | `string`        | Yes      | `groww.in`            | Mandatory                     |
| `doc_type`       | `enum`          | Yes      | `factsheet`            | Must match `sources.doc_type` |
| `scheme_name`    | `string`        | No       | `Quant Large Cap Fund` | For targeted retrieval        |
| `amc_name`       | `string`        | Yes      | `Quant Mutual Fund`    | Mandatory                     |
| `chunk_text`     | `string`        | Yes      | `Expense ratio is...`  | Cleaned text                  |
| `embedding`      | `vector<float>` | Yes      | `[...]`                | Stored in vector DB           |
| `embedding_model`| `string`        | Yes      | `bge-small-en`         | Embedding model identifier    |
| `embedding_model_revision`| `string` | Yes      | `sha-or-tag`           | Pinned model revision/tag     |
| `embedding_source`| `string`       | Yes      | `pre_baked`            | Expected value: `pre_baked`   |
| `vector_store`   | `string`        | Yes      | `chroma`               | Expected value: `chroma`      |
| `collection_name`| `string`        | Yes      | `mf_scheme_chunks_v1`  | ChromaDB collection name      |
| `effective_date` | `date`          | No       | `2026-05-01`           | If extractable                |
| `ingested_at`    | `datetime`      | Yes      | `2026-05-07T06:35:00Z` | Mandatory                     |


---

## 4.5 `query_responses` (optional audit table)

Supports QA/compliance metrics and troubleshooting.


| Field                       | Type           | Required | Example                       | Notes                                    |
| --------------------------- | -------------- | -------- | ----------------------------- | ---------------------------------------- |
| `query_id`                  | `string`       | Yes      | `qry_01J2...`                 | Unique request ID                        |
| `question_text`             | `string`       | Yes      | `What is the minimum SIP...?` | Store sanitized text                     |
| `query_mode`                | `enum`         | Yes      | `success_llm`                 | `success_llm`, `safety_refusal_llm`, `no_llm_key`, etc. |
| `answer_text`               | `string`       | Yes      | `The minimum SIP is...`       | Final rendered answer                    |
| `citations`                 | `array<string>`| Yes      | `["https://..."]`             | Zero or more allowed Groww source links  |
| `contract_passed`           | `boolean`      | Yes      | `true`                        | 3-sentence/no-inline-citation/no-footer checks |
| `retrieval_hit_count`       | `integer`      | Yes      | `5`                           | Retrieved chunk count                    |
| `created_at`                | `datetime`     | Yes      | `2026-05-07T06:40:12Z`        | Event timestamp                          |


Privacy rule:

- Never store PAN, Aadhaar, account number, OTP, email, or phone in logs.

---

## 5) Field-Level Validation Rules (Implementation Checklist)

1. `citations[]` entries (if present) must each match `https://groww.in/mutual-funds/[fund-name]`.
2. `answer_text` must be <= 3 sentences and must not include inline citation label/URL/footer text.
3. `nav_value`, `aum_value_cr`, `expense_ratio_percent`, `min_sip_amount_inr` must be non-negative.
4. `elss_lock_in_years` should be present only for ELSS schemes; null otherwise.
5. `benchmark_full_name` should not be abbreviated if full form exists in source.
6. `rating_value` must remain null when unavailable in accepted Groww source content.
7. `availability_status = not_available` must be used instead of inferred values.
8. Any record with URL outside `https://groww.in/mutual-funds/[fund-name]` must be blocked from final source-link selection.
9. `embedding_source` must be `pre_baked`; runtime download-based embeddings are non-compliant for production.

---

## 6) Conflict Resolution Rules

When multiple accepted Groww sources disagree:

1. Prefer latest `effective_date`.
2. If date is unavailable, prefer latest `ingested_at` from doc type order:
   - `groww_mutual_fund_page` > `statement_download_guide` > `capital_gains_report_guide` > `other_groww_page`
3. Mark unresolved cases as `conflicting`.
4. Do not present synthesized numeric value; respond with factual limitation and keep source links in structured metadata.

---

## 7) Example JSON Payload (Normalized Scheme Facts)

```json
{
  "fact_id": "fact_01J2ABCXYZ",
  "scheme_name": "Quant ELSS Tax Saver Fund",
  "amc_name": "Quant Mutual Fund",
  "nav_value": 89.4723,
  "nav_currency": "INR",
  "nav_raw_text": "NAV (as on 06-May-2026): Rs. 89.4723",
  "nav_value_as_of_date": "2026-05-06",
  "aum_value_cr": 12345.67,
  "aum_raw_text": "AUM: Rs 12,345.67 Cr",
  "expense_ratio_percent": 1.24,
  "expense_ratio_raw_text": "Expense Ratio: 1.24%",
  "expense_ratio_as_of_date": "2026-05-01",
  "exit_load_text": "Nil after specified holding period; refer linked Groww mutual fund page.",
  "min_sip_amount_inr": 500,
  "min_sip_raw_text": "Minimum SIP: Rs 500",
  "elss_lock_in_years": 3.0,
  "elss_lock_in_raw_text": "Lock-in period: 3 years",
  "riskometer_label": "very_high",
  "riskometer_raw_text": "Riskometer: Very High",
  "benchmark_full_name": "Nifty 500 TRI",
  "availability_status": "available",
  "source_id": "src_01J2QWERTY",
  "source_url": "https://groww.in/mutual-funds/quant-elss-tax-saver-fund-direct-growth",
  "effective_date": "2026-05-01",
  "ingested_at": "2026-05-07T06:35:00Z"
}
```

---

## 8) Versioning

- `schema_version`: Start with `v1.0`.
- Any addition/removal/semantic change to fields must update:
  - `docs/architecture.md`
  - `docs/edgecases.md`
  - validation and regression tests.

