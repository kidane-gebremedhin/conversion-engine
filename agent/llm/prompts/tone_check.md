STAGE=tone_check

Given a style guide excerpt and a draft, return JSON
`{"pass": bool, "violations": [...], "suggestions": [...]}`.
Be strict about marketing superlatives, first-person plural overuse, vagueness.
Return ONLY the JSON.
