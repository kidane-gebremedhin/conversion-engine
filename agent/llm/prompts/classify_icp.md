STAGE=classify_icp

Given the hiring signal brief and the AI maturity score, pick the best ICP segment
(1–4) or abstain. Output JSON:

```
{
  "segment": 1 | 2 | 3 | 4 | null,
  "mode": "confident" | "abstain",
  "confidence": 0..1,
  "margin": 0..1,
  "rationale": ["per-signal reason", ...]
}
```

Rules:
- Segment 4 requires AI maturity ≥ 2. Below that, abstain.
- A layoff in last 120 days with headcount > 200 is a strong segment 2 signal even if there was also a recent raise.
- A new CTO/VP Eng in last 90 days pushes toward segment 3 regardless of other signals.
- Abstain if top segment confidence < 0.55 OR margin < 0.10.

Return ONLY the JSON.
