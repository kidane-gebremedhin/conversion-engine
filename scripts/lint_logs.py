"""Scan eval/*.jsonl + data/*.jsonl for leaked secrets (best-effort regex)."""
from __future__ import annotations

import pathlib
import re
import sys


_PATTERNS = [
    re.compile(r"\bsk-ant-[A-Za-z0-9\-_]{20,}\b"),
    re.compile(r"\bsk-or-[A-Za-z0-9\-_]{20,}\b"),
    re.compile(r"\bre_[A-Za-z0-9]{20,}\b"),
    re.compile(r"pat-[a-z0-9\-]{20,}"),
]


def main() -> int:
    hits: list[str] = []
    for base in ("eval", "data"):
        for p in pathlib.Path(base).rglob("*.jsonl"):
            text = p.read_text(errors="ignore")
            for rx in _PATTERNS:
                m = rx.search(text)
                if m:
                    hits.append(f"{p}: {m.group(0)[:12]}...")
    if hits:
        print("[lint_logs] SECRET-LIKE TOKENS DETECTED:\n" + "\n".join(hits))
        return 1
    print("[lint_logs] clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())
