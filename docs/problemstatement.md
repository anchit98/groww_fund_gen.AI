# Problem Statement: Mutual Fund FAQ Assistant (Facts-Only Q&A)

## Source Policy Override
All system stages (ingestion, retrieval, and citation) must accept only URLs matching:
`https://groww.in/mutual-funds/[fund-name]`

Any non-matching URL must be rejected.

## Overview
The objective of this project is to build a facts-only FAQ assistant for mutual fund schemes, using Groww as the source context. The assistant will answer objective, verifiable queries related to mutual funds by retrieving information exclusively from URLs matching `https://groww.in/mutual-funds/[fund-name]`.

The system must strictly avoid providing investment advice, opinions, or recommendations. Every response must adhere to defined constraints around clarity, accuracy, and compliance, while source links are exposed separately by the UI.

---

## Objective
Design and implement a lightweight Retrieval-Augmented Generation (RAG)-based assistant that:
- Answers factual queries about mutual fund schemes  
- Uses a curated corpus of Groww mutual fund pages  
- Provides concise, source-backed responses  

---

## Target Users
- Retail investors comparing mutual fund schemes  
- Customer support and content teams handling repetitive mutual fund queries  

---

## Scope of Work

### 1. Corpus Definition
- Select one Asset Management Company (AMC)  
- Choose 3–5 mutual fund schemes, ensuring category diversity (e.g., large-cap, flexi-cap, ELSS)  
- Collect 7-25 Groww mutual fund URLs that match `https://groww.in/mutual-funds/[fund-name]` and cover selected schemes.

---

### 2. FAQ Assistant Requirements

The assistant must:

**Answer facts-only queries, such as:**
- Expense ratio of a scheme  
- Exit load details  
- Minimum SIP amount  
- ELSS lock-in period  
- Riskometer classification  
- Benchmark index  
- Process to download statements or capital gains reports  

**Ensure:**
- Each response is exactly 3 concise sentences  
- Response text contains no inline citation label/URL  
- Response text contains no inline footer/date line  
- Source links are provided separately in structured response metadata for UI rendering

---

### 3. Refusal Handling

The assistant must refuse non-factual or advisory queries, such as:
- “Should I invest in this fund?”  
- “Which fund is better?”  

**Refusal responses should:**
- Be polite and clearly worded  
- Reinforce the facts-only limitation  
- Avoid inline source links in refusal text.  

---

### 4. User Interface (Minimal)

The solution should include a simple interface with:
- A welcome message  
- Two fixed example questions  
- Header-level chat tabs  
- A visible disclaimer:  
  > “Facts-only. No investment advice.”  

---

## Constraints

### Data and Sources
- Use only URLs matching `https://groww.in/mutual-funds/[fund-name]`  
- Do not use any other websites, blogs, or aggregator pages  

### Privacy and Security
Do not collect, store, or process:
- PAN or Aadhaar numbers  
- Account numbers  
- OTPs  
- Email addresses or phone numbers  

### Content Restrictions
- No investment advice or recommendations  
- No performance comparisons or return calculations  
- For performance-related queries, refuse politely without adding inline links in answer text  

### Transparency
- Responses must be short, factual, and verifiable  
- Source links and freshness metadata should be exposed via structured fields and status endpoints (not inline answer text)  

---

## Expected Deliverables

### README Document
- Setup instructions  
- Selected AMC and schemes  
- Architecture overview (RAG approach)  
- Known limitations  

### Disclaimer Snippet
> “Facts-only. No investment advice.”  

---

## Success Criteria
- Accurate retrieval of factual mutual fund information  
- Strict adherence to facts-only responses  
- Consistent structured source-link metadata for factual responses  
- Proper refusal of advisory queries  
- Clean, minimal, and user-friendly interface  

---

## Summary
The goal is to build a trustworthy, transparent, and compliant mutual fund FAQ assistant that prioritizes accuracy over intelligence. The system should ensure that users receive only verified, source-backed financial information, without any advisory bias or speculative content.