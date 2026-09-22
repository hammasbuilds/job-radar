"""Build the YC directory: companies, their links, and every job they have open.

    python scripts/fetch_yc.py              # AI-tagged companies that are hiring
    python scripts/fetch_yc.py --all        # all 1,483 hiring companies
    python scripts/fetch_yc.py --new-only   # only those launched within a year

This is the company-first half of the tool and it deliberately does **no job
filtering at all**. Everywhere else the description is the product; here the
signal is that a company is YC-backed, funded and hiring, so every open role is
listed whatever it says.

Resolving a board is the slow part: each company's slug is tried against
Greenhouse and then Lever, so a run is up to two requests per company. The HTTP
cache makes a second run within six hours nearly free.
"""

from __future__ import annotations

import argparse
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from jobradar import store  # noqa: E402
from jobradar.sources import yc  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--all", action="store_true",
                        help="every hiring company, not just AI-tagged ones")
    parser.add_argument("--new-only", action="store_true",
                        help="only companies launched within the last year")
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--fresh", action="store_true")
    parser.add_argument(
        "--if-older-than", type=float, default=None, metavar="HOURS",
        help="skip entirely when the stored directory is newer than this",
    )
    args = parser.parse_args()

    # The launcher passes this so a one-click run does not spend two minutes
    # re-resolving 326 company boards that were resolved this morning. YC
    # batches move on a scale of weeks; a day-old directory is current.
    if args.if_older_than is not None:
        age = store.yc_age_hours()
        if age is not None and age < args.if_older_than:
            print(f"YC directory is {age:.1f}h old — still current, skipping.")
            print("Force a refresh with: python scripts/fetch_yc.py --fresh")
            return

    kw = {"max_age": 0.0} if args.fresh else {}
    companies = yc.hiring(ai_only=not args.all, **kw)
    if not companies:
        raise SystemExit("YC API returned nothing — check the network")

    if args.new_only:
        companies = [c for c in companies if c.age_bucket]

    print(f"{len(companies)} YC companies listed as hiring"
          f"{' (AI-tagged)' if not args.all else ''}"
          f"{' launched within a year' if args.new_only else ''}")
    print("resolving boards — up to two requests each…\n")

    started = time.time()

    def resolve(company):
        company.jobs = yc.jobs_for(company, **kw)
        return company

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        companies = list(pool.map(resolve, companies))

    with_board = [c for c in companies if c.jobs]
    jobs = sum(len(c.jobs) for c in companies)

    print(f"{len(with_board)} of {len(companies)} have a readable board "
          f"({jobs:,} open roles) in {time.time() - started:.0f}s")
    print("The rest hire through a form or an email and are kept anyway —")
    print("funded, hiring and reachable is worth knowing without a board.\n")

    for name, _, label in yc.BUCKETS:
        part = [c for c in companies if c.age_bucket == name]
        roles = sum(len(c.jobs) for c in part)
        print(f"  {name:<7} {len(part):>4} companies, {roles:>5} roles   {label}")
    established = [c for c in companies if not c.age_bucket]
    print(f"  {'older':<7} {len(established):>4} companies, "
          f"{sum(len(c.jobs) for c in established):>5} roles")

    store.save_yc(companies)
    print(f"\nstored in {store.DB}")
    print("open the YC tab in the dashboard")


if __name__ == "__main__":
    main()
