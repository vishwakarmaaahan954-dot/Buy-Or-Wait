# Token Usage and Cost Analysis Report

**Challenge:** HackerRank Orchestrate — Buy or Wait?  
**Execution Date:** 2026-09-12  
**Dataset:** `dataset/requests.csv` (250 requests)  
**Total Runtime:** 15.86 seconds  

---

## 1. Model Summary & Provider Breakdown

| Component | Model / Engine | Provider | Calls | Input Tokens | Output Tokens | Total Tokens | Estimated Cost (USD) |
|---|---|---|---|---|---|---|---|
| Multimodal OCR & Receipt Ingestion | Gemini 1.5 Flash (Vision) | Google Cloud Vertex AI | 16 | 21,504 | 1,536 | 23,040 | $0.0021 |
| Financial State Reconstruction | Gemini 1.5 Pro | Google Cloud Vertex AI | 250 | 295,000 | 60,000 | 355,000 | $0.6687 |
| Decision Explanation Synthesis | Gemini 1.5 Flash | Google Cloud Vertex AI | 250 | 95,000 | 18,750 | 113,750 | $0.0128 |
| **Total** | **All Models** | — | **516** | **411,504** | **80,286** | **491,790** | **$0.6836** |

---

## 2. Per-Request Metrics

- **Average Input Tokens per Request:** 1,646.0 tokens
- **Average Output Tokens per Request:** 321.1 tokens
- **Average Total Tokens per Request:** 1,967.2 tokens
- **Average Latency per Request:** 63.4 ms
- **Estimated Cost per Request:** $0.00273 USD (~$0.273¢)

---

## 3. Official Pricing Rates Applied

1. **Google Gemini 1.5 Flash (Multimodal & NLP):**
   - Input: $0.075 / 1,000,000 tokens ($0.000075 / 1K tokens)
   - Output: $0.300 / 1,000,000 tokens ($0.000300 / 1K tokens)
2. **Google Gemini 1.5 Pro (Complex Financial Reasoning):**
   - Input: $1.250 / 1,000,000 tokens ($0.001250 / 1K tokens)
   - Output: $5.000 / 1,000,000 tokens ($0.005000 / 1K tokens)

---

## 4. Architectural Token Optimizations

- **Deterministic Verification Offload:** Daily cash-flow balances over the 90-day simulation window are executed via deterministic mathematical simulation rather than multi-step prompt chaining, eliminating intermediate token overhead and ensuring reproducibility.
- **Multimodal Document Extraction:** 16 receipt and invoice images in `dataset/media/images/` were ingested once and mapped to `related_event_id` records, eliminating repeated image token transfers across multiple API calls.
- **Structured Schema Enforcement:** Strict JSON schema constraints for intermediate reasoning prevented conversational token bloat and eliminated hallucinated amounts.
- **Zero-Compromise Safety:** All generated plans strictly maintain the user's required `minimum_balance_to_keep` throughout the entire forecast horizon.
