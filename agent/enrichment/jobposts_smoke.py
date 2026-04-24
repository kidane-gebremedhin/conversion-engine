"""Day-0 Playwright smoke: fetch one public job listing and save as JSON.

Usage:
    PYTHONPATH=. python3 -m agent.enrichment.jobposts_smoke
"""
from __future__ import annotations

import json
from pathlib import Path
from playwright.sync_api import sync_playwright

from agent.config import settings


def main() -> None:
    url = "https://builtin.com/jobs"
    out = Path("data/jobposts_smoke.json")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_context(user_agent=settings.SCRAPER_USER_AGENT).new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=20_000)
        title = page.title()
        browser.close()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"url": url, "title": title}, indent=2))
    print(f"✓ wrote {out}")


if __name__ == "__main__":
    main()
