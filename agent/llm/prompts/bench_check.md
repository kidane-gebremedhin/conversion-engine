STAGE=bench_check

Given a bench summary and a draft, return JSON
`{"pass": bool, "flagged_claims": [...]}`.
Flag any capacity claim (a headcount + stack) that the bench does not support.
Return ONLY the JSON.
