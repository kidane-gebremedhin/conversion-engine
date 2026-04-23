STAGE=classify_reply

Given the prospect's reply body, classify intent and extract useful structure.

Output JSON:

```
{
  "intent": "interested" | "objection" | "off_topic" | "unsubscribe" | "scheduling_question" | "bench_question" | "pricing_question",
  "confidence": 0..1,
  "extracted": {
    "preferred_channel": "email" | "sms" | null,
    "asked_time": "ISO8601 | null",
    "objection_class": "offshore_perception" | "cost" | "timing" | "capability" | null
  }
}
```

Return ONLY the JSON.
