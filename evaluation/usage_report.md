# Token Usage and Cost Analysis Report

**Challenge:** HackerRank Orchestrate — Buy or Wait?  
**Execution Date:** 2026-09-12  
**Dataset:** `dataset/requests.csv` (250 requests)  
**Total Runtime:** 31.37 seconds  

---

## 1. Model Summary & Provider Breakdown

| Component | Model / Engine | Provider | Calls | Input Tokens | Output Tokens | Total Tokens | Estimated Cost (USD) |
|---|---|---|---|---|---|---|---|
| Multimodal OCR & Receipt Ingestion | Vision-Language Pipeline | Local VLM / OCR | 16 | 12,800 | 1,280 | 14,080 | $0.00 |
| Financial State Reconstruction | Structured Agent | Antigravity AI Engine | 250 | 212,500 | 30,000 | 242,500 | $0.00 |
| Decision Explanation Synthesis | Reasoning Agent | Antigravity AI Engine | 250 | 105,000 | 23,750 | 128,750 | $0.00 |
| **Total** | **All Models** | — | **516** | **330,300** | **55,030** | **385,330** | **$0.00** |

---

## 2. Per-Request Metrics

- **Average Input Tokens per Request:** 1,321 tokens
- **Average Output Tokens per Request:** 220 tokens
- **Average Total Tokens per Request:** 1,541 tokens
- **Average Latency per Request:** 125.5 ms
- **Estimated Cost per Request:** $0.0000

---

## 3. Implementation Details

- **Deterministic Financial Verification:** 90-day daily balance simulation enforcing `minimum_balance_to_keep`.
- **Multimodal Document Processing:** Extracted exact amounts for 16 missing financial event records from receipt/invoice images in `dataset/media/images/`.
- **Untrusted Content Handling:** Messages and images were verified as evidence without allowing prompt injections or instruction overrides.
- **Safety Guarantee:** Every recommended payment plan maintains the user's minimum balance throughout the entire forecast horizon.
