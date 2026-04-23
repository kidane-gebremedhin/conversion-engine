"""D0 artifact — fetch one public job listing via Playwright, save as JSON.

Proves the Playwright stack is installed and working. Target defaults to
Stripe's public Greenhouse board because the DOM is stable and
unauthenticated; override with --company or --url for anywhere else.

Output shape matches agent.enrichment.jobposts.JobPost so the sample can
feed the existing snapshot reader.

Run:
    pip install -e '.[live]' && playwright install chromium
    python -m scripts.fetch_job_sample
    python -m scripts.fetch_job_sample --company vercel --domain vercel.com
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
from datetime import date, datetime

_OUT = pathlib.Path("data/jobposts_samples")


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def fetch_one(url: str, company_domain: str) -> dict:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            anchor = page.locator("a[href*='/jobs/']").first
            anchor.wait_for(timeout=15000)
            title = anchor.inner_text().strip()
            href = anchor.get_attribute("href") or ""
        finally:
            browser.close()

    if href.startswith("/"):
        href = f"https://boards.greenhouse.io{href}"

    return {
        "company_domain": company_domain,
        "title": title,
        "posted_at": date.today().isoformat(),
        "location": None,
        "department": None,
        "role_category": "other",
        "url": href,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser("fetch_job_sample")
    p.add_argument("--company", default="stripe", help="Greenhouse board slug")
    p.add_argument("--url", default=None, help="Override full URL (ignores --company)")
    p.add_argument("--domain", default=None, help="Company domain tag for JobPost record")
    args = p.parse_args(argv)

    url = args.url or f"https://boards.greenhouse.io/{args.company}"
    domain = args.domain or f"{args.company}.com"

    try:
        job = fetch_one(url, domain)
    except Exception as exc:
        print(f"fetch failed: {exc}", file=sys.stderr)
        return 1

    _OUT.mkdir(parents=True, exist_ok=True)
    out = _OUT / f"{_slug(domain)}_{datetime.utcnow().strftime('%Y%m%dT%H%M%S')}.json"
    out.write_text(json.dumps(job, indent=2))
    print(f"ok — {out}")
    print(json.dumps(job, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
