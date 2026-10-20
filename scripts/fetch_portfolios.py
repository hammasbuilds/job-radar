"""Accelerator and investor portfolios: companies backed, and their AI roles, from job-board
sitemaps (see sources/portfolios.py for why sitemaps and not the board API).

    python scripts/fetch_portfolios.py
    python scripts/fetch_portfolios.py --if-older-than 24
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from jobradar import families, store  # noqa: E402
from jobradar.filters import fit, seniority  # noqa: E402
from jobradar.profile import ACCEPT_LEVELS  # noqa: E402
from jobradar.sources import portfolios  # noqa: E402


def judge(job: dict) -> dict:
    title = job["title"]
    role = fit.role_match(title) or ""
    program = families.is_program(title)
    data_work = not role and families.is_data_work(title)
    ai = bool(role or program or data_work)
    family, track = families.classify(title, data_work=data_work) if ai else ("", "")
    level, _ = seniority.classify(title)
    return {**job, "ai": ai, "family": family, "track": track,
            "level": level, "junior": ai and level in ACCEPT_LEVELS}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--if-older-than", type=float, default=None, metavar="HOURS")
    args = parser.parse_args()
    if args.if_older_than is not None:
        age = store.portfolio_age_hours()
        if age is not None and age < args.if_older_than:
            print(f"Portfolios are {age:.0f}h old - still current, skipping.")
            return
    started = time.time()
    for programme in portfolios.PROGRAMMES:
        p = portfolios.fetch(programme)
        jobs = [judge(j) for j in p.jobs]
        store.save_portfolio(p, jobs)
        ai = sum(j["ai"] for j in jobs)
        junior = sum(j["junior"] for j in jobs)
        note = f" ({len(p.failed)} sitemap(s) unreadable)" if p.failed else ""
        print(f"  {p.name:<18} {len(p.companies):>5,} companies  {len(jobs):>6,} roles  "
              f"{ai:>4} AI  {junior:>4} junior AI{note}", flush=True)
    print(f"done in {time.time() - started:.0f}s")


if __name__ == "__main__":
    for _stream in (sys.stdout, sys.stderr):
        _stream.reconfigure(encoding="utf-8", errors="replace")
    main()
