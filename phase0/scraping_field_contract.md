# Scraping Field Contract (Phase 0 Finalized)

## 1) Mandatory extraction fields
The ingestion layer must extract these fields wherever available in accepted Groww mutual fund URLs:

1. NAV
2. Fund Size (AUM)
3. Rating
4. Expense ratio
5. Exit load
6. Minimum SIP amount
7. ELSS lock-in period (if applicable)
8. Riskometer classification
9. Benchmark index (full name)
10. Process to download statements or capital gains reports

## 2) Normalization rules
- Numeric fields (NAV, AUM, expense ratio, minimum SIP):
  - store normalized numeric value
  - store original `raw_text`
- Date-sensitive fields (NAV, AUM, expense ratio):
  - capture `value_as_of_date` when present
  - fallback to source `effective_date`, else `ingested_at`
- Categorical fields (riskometer, benchmark, lock-in applicability):
  - map to canonical normalized values
  - preserve original text
- Process field:
  - store stepwise instructions in ordered steps
  - include source URL and channel scope where present (web/app/email/rta)

## 3) Missing and conflicting data rules
- If unavailable in accepted Groww source content: mark as `not_available`.
- Do not infer, estimate, or synthesize values.
- If conflicting across approved sources:
  - prefer latest effective date
  - else mark as `conflicting` and avoid merged numeric output

## 4) Compliance constraints
- Only URLs matching `https://groww.in/mutual-funds/[fund-name]` are valid citation sources for extracted facts.
- Output must remain facts-only with no recommendation language.

