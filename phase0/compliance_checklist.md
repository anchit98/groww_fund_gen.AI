# Phase 0 Compliance Checklist

Use this checklist before moving from Phase 0 to Phase 1.

## A) Scope baseline
- [x] Single AMC selected.
- [x] 3-5 schemes marked as in-scope.
- [x] Category diversity present in selected schemes.
- [x] Reserve schemes (if any) explicitly marked out-of-scope.

## B) URL governance
- [x] Only URLs matching `https://groww.in/mutual-funds/[fund-name]` are accepted.
- [x] Non-matching URLs are blocked for retrieval and citation.
- [ ] All in-scope schemes have at least one approved Groww mutual fund URL.
- [ ] URL health checks completed for approved Groww URLs.

## C) Data contract baseline
- [x] Mandatory scraping field list finalized.
- [x] Missing-value behavior defined (`not_available`, no inference).
- [x] Conflict resolution policy documented.
- [x] Date/freshness fallback policy documented.

## D) Policy and output contract
- [x] Facts-only policy defined.
- [x] Refusal taxonomy defined for advisory/comparative queries.
- [x] Output contract defined:
  - [x] max 3 sentences
  - [x] exactly 1 citation link
  - [x] footer with source date

## E) Edge-case coverage (from `docs/edgecases.md`)
- [x] Advisory requests are routed to refusal templates.
- [x] URL pattern mismatch handling documented.
- [x] Non-Groww URL misuse prevention documented.
- [x] Missing rating in Groww source content handled as `not_available`.
- [x] NAV date ambiguity handling documented.

## Sign-off
- Phase 0 owner: `TBD`
- Compliance reviewer: `TBD`
- Date: `TBD`
- Status:
  - `PARTIALLY COMPLETE` (Groww URL approvals still pending)

