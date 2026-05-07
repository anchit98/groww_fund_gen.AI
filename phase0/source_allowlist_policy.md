# Source Allowlist Policy (Phase 0 Baseline)

## 1) Purpose
Define which URLs are eligible for ingestion, retrieval, and citation.

This policy enforces:
- strict Groww URL pattern requirement
- third-party exclusion

## 2) Accepted source rule
- Only URLs matching `https://groww.in/mutual-funds/[fund-name]` are accepted.
- Domain must be exactly `groww.in`.
- Path must begin with `/mutual-funds/`.

## 3) Hard block rules
- Block all third-party blogs, aggregators, forums, social media, and mirrors.
- Block any URL that does not match `https://groww.in/mutual-funds/[fund-name]`.
- Block citation selection from non-matching URLs.

## 4) URL approval workflow
1. Add candidate URL to registry as `pending_review`.
2. Validate exact URL pattern, domain, and path.
3. Confirm page is public and crawlable.
4. Mark as `approved` only after reviewer sign-off.

## 5) Edge-case controls implemented
- Prevent non-Groww ingestion and citation.
- Prevent accidental acceptance of `groww.in` URLs outside `/mutual-funds/`.

## 6) Phase 0 go/no-go rule
Phase 1 ingestion must not begin until all selected schemes have at least one approved Groww mutual fund URL.

