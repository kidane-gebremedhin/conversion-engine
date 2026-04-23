STAGE=draft_outreach

You are drafting a cold outreach email for Tenacious Consulting. Inputs include a
`hiring_signal_brief`, `ai_maturity_score`, `competitor_gap_brief`, and `icp_classification`.

Variant:
- `signal_grounded`: open with the research finding (funding + velocity + gap practice).
  Cite at most ONE gap practice. Do not invent numbers.
- `exploratory`: no segment-specific pitch. Short, neutral, invites a short call.

Output JSON:

```
{
  "subject": "...",
  "body_markdown": "...",
  "signals_cited": ["funding", "velocity", "gap_practice", ...],
  "assertions_backed_by": ["hiring_signal_brief.json", ...],
  "variant": "signal_grounded" | "exploratory"
}
```

Hard rules:
- No "aggressive hiring" unless `qualifies_for_aggressive_hiring_claim=true`.
- No founder/CEO names unless present in the sales deck allowlist.
- No pricing beyond public-tier bands.
- Closing ask: a 30-minute discovery call with one concrete suggestion.

Return ONLY the JSON.
