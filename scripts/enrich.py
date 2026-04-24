"""`make enrich DOMAIN=<domain>` — run the enrichment pipeline on one prospect."""
from __future__ import annotations

import argparse
import sys

from agent.enrichment.pipeline import enrich


def main() -> int:
    p = argparse.ArgumentParser(description="Run enrichment on one prospect domain.")
    p.add_argument("--domain", required=True)
    p.add_argument("--out", default=None, help="write briefs to this dir (default: eval/briefs/<domain>/)")
    args = p.parse_args()

    out = args.out or f"eval/briefs/{args.domain}"
    try:
        hiring, gap = enrich(args.domain, write_to=out)
    except Exception as e:  # noqa: BLE001
        print(f"ERROR: {e}", file=sys.stderr)
        return 2

    print(f"✓ enrichment complete for {args.domain}")
    print(f"  segment={hiring.primary_segment_match} confidence={hiring.segment_confidence:.2f}")
    print(f"  ai_maturity={hiring.ai_maturity.score}/3 conf={hiring.ai_maturity.confidence:.2f}")
    print(f"  velocity={hiring.hiring_velocity.velocity_label}")
    print(f"  honesty_flags={hiring.honesty_flags}")
    print(f"  bench_available={hiring.bench_to_brief_match.bench_available} gaps={hiring.bench_to_brief_match.gaps}")
    print(f"  competitor_gap_brief={'yes' if gap else 'no'}")
    print(f"  briefs written to: {out}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
