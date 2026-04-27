"""Ensure required local data sources exist before enrichment.

Idempotent: if a file already exists it is left alone. If missing, we
either rebuild it from its public URL (crunchbase ODM) or restore the
seed from git HEAD (jobposts snapshot, layoffs, synthetic prospects).

Used by `make enrich` (and friends) so a fresh checkout — or one where
`data/` has been wiped — can run end-to-end without manual setup.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Callable

from agent.config import REPO_ROOT, settings


def _restore_from_git(path: Path) -> bool:
    """Restore `path` from git HEAD. Return True on success."""
    rel = path.relative_to(REPO_ROOT)
    res = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "checkout", "HEAD", "--", str(rel)],
        capture_output=True,
        text=True,
    )
    if res.returncode != 0:
        sys.stderr.write(f"  git checkout failed for {rel}: {res.stderr.strip()}\n")
        return False
    return path.exists()


def _build_crunchbase(path: Path) -> bool:
    """Fetch the Crunchbase ODM CSV and project it into the local schema."""
    from scripts.build_crunchbase_odm import main as build_main
    rc = build_main()
    return rc == 0 and path.exists()


def _build_synthetic_prospects(path: Path) -> bool:
    """Derive synthetic prospects from the Crunchbase ODM sample."""
    cb_path = REPO_ROOT / settings.CRUNCHBASE_ODM_LOCAL_PATH
    if not cb_path.exists():
        # Crunchbase must be present first; ensure_all() processes sources in
        # order so this only happens if a caller invoked the builder directly.
        if not _build_crunchbase(cb_path):
            return False
    from scripts.build_synthetic_prospects import main as build_main
    rc = build_main()
    return rc == 0 and path.exists()


def _build_jobposts_snapshot(path: Path) -> bool:
    """Synthesise the job-posts snapshot from the Crunchbase ODM sample."""
    cb_path = REPO_ROOT / settings.CRUNCHBASE_ODM_LOCAL_PATH
    if not cb_path.exists():
        if not _build_crunchbase(cb_path):
            return False
    from scripts.build_jobposts_snapshot import main as build_main
    rc = build_main()
    return rc == 0 and path.exists()


# Each source: (label, absolute path, builder).
# Builder receives the absolute path and returns True iff the file now exists.
_Source = tuple[str, Path, Callable[[Path], bool]]


def _sources() -> list[_Source]:
    return [
        (
            "crunchbase_odm",
            REPO_ROOT / settings.CRUNCHBASE_ODM_LOCAL_PATH,
            _build_crunchbase,
        ),
        (
            "job_posts_snapshot",
            REPO_ROOT / settings.JOB_POSTS_SNAPSHOT_PATH,
            _build_jobposts_snapshot,
        ),
        (
            "layoffs",
            # The challenge ships a hand-curated layoffs.csv at data/layoffs.csv.
            # settings.LAYOFFS_FYI_LOCAL_PATH points to a quarter-stamped name
            # we do not commit; restore the canonical seed instead.
            REPO_ROOT / "data" / "layoffs.csv",
            _restore_from_git,
        ),
        (
            "synthetic_prospects",
            REPO_ROOT / "data" / "synthetic_prospects.json",
            _build_synthetic_prospects,
        ),
    ]


def ensure_all() -> int:
    """Ensure every data source exists. Return the number of files (re)built."""
    rebuilt = 0
    failed: list[str] = []
    for label, path, builder in _sources():
        if path.exists():
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        sys.stderr.write(f"→ {label}: missing at {path.relative_to(REPO_ROOT)}, rebuilding ...\n")
        if builder(path):
            sys.stderr.write(f"  ✓ {label} ready\n")
            rebuilt += 1
        else:
            sys.stderr.write(f"  ✗ {label} could not be built\n")
            failed.append(label)
    if failed:
        sys.stderr.write(f"\nERROR: failed to materialise: {', '.join(failed)}\n")
        return 2
    if rebuilt == 0:
        sys.stderr.write("All data sources already present.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(ensure_all())
