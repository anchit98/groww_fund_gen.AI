# Refusal Examples Library (Phase 0)

## 1) Refusal policy
The assistant must refuse:
- investment advice
- recommendations/rankings
- return predictions
- personalized portfolio/tax planning advice

Refusals must be:
- polite and clear
- explicit about facts-only scope
- accompanied by one Groww mutual fund URL

---

## 2) Refusal taxonomy

### A. Direct advisory
User pattern:
- "Should I invest in this fund?"
- "Is this fund good for me?"

Response template:
> I can only help with factual information from accepted Groww mutual fund pages and cannot provide investment advice or recommendations. You can continue with this source link: <groww-mutual-fund-link>.  
> Last updated from sources: <date>

### B. Comparative recommendation
User pattern:
- "Which fund is better?"
- "Large cap vs flexi cap, what should I choose?"

Response template:
> I can share objective facts from accepted Groww mutual fund pages but cannot compare funds to recommend one. Please refer to this source link: <groww-mutual-fund-link>.  
> Last updated from sources: <date>

### C. Performance prediction
User pattern:
- "Will this fund give 15% returns next year?"
- "Can this beat Nifty in 3 years?"

Response template:
> I cannot provide return predictions or investment recommendations. I can only provide factual data from accepted Groww mutual fund pages; see: <groww-mutual-fund-link>.  
> Last updated from sources: <date>

### D. Mixed intent (factual + advisory)
User pattern:
- "What is the expense ratio, and should I invest now?"

Response template:
> The assistant is limited to factual information from accepted Groww mutual fund pages and cannot advise whether to invest. You can review this source: <groww-mutual-fund-link>.  
> Last updated from sources: <date>

### E. Personal financial profiling
User pattern:
- "I am 28, should I pick ELSS or flexi-cap for tax and growth?"

Response template:
> I cannot provide personalized investment guidance. I can only provide scheme facts from accepted Groww mutual fund pages; refer to: <groww-mutual-fund-link>.  
> Last updated from sources: <date>

---

## 3) Approved links (to finalize in registry)
- Groww mutual fund page link: `https://groww.in/mutual-funds/[fund-name]`

Note:
- Exactly one link must be used in any refusal response.
- Link must match `https://groww.in/mutual-funds/[fund-name]` and be active.

