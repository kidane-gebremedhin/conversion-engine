"""Copy `data/local_traces.jsonl` into `eval/trace_log.jsonl` (deduped).

In live mode this would be a Langfuse export. In local mode it's a file copy.
"""
from __future__ import annotations

import json
import pathlib


def main() -> int:
    src = pathlib.Path("data/local_traces.jsonl")
    dst = pathlib.Path("eval/trace_log.jsonl")
    dst.parent.mkdir(exist_ok=True)
    if not src.exists():
        dst.touch()
        print("[export] no local traces to export")
        return 0
    seen: set[str] = set()
    n = 0
    with dst.open("w") as out:
        for line in src.read_text().splitlines():
            if not line.strip():
                continue
            try:
                t = json.loads(line)
            except json.JSONDecodeError:
                continue
            tid = t.get("trace_id", "")
            if tid in seen:
                continue
            seen.add(tid)
            out.write(line + "\n")
            n += 1
    print(f"[export] wrote {n} traces → {dst}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
