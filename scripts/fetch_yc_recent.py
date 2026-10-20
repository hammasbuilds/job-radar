"""Every YC company from the last three years of batches, with real LinkedIn and career links.

    python scripts/fetch_yc_recent.py               # list + LinkedIn from each YC page (slow)
    python scripts/fetch_yc_recent.py --no-pages    # list only, minutes; LinkedIn as a search
    python scripts/fetch_yc_recent.py --years 2

Reading each company's YC page is one request per company at the HTTP layer's pace (about
2,500 for three years), so the first full run is about an hour. Pages are cached for a week and
every company is saved as it is read, so a stopped run loses nothing.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from jobradar import store  # noqa: E402
from jobradar.sources import yc_recent  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--years", type=int, default=3)
    parser.add_argument("--no-pages", action="store_true",
                        help="skip reading YC pages; LinkedIn becomes a search link")
    parser.add_argument("--if-older-than", type=float, default=None, metavar="HOURS",
                        help="skip when the stored list is newer than this")
    args = parser.parse_args()
    if args.if_older_than is not None:
        age = store.yc_recent_age_hours()
        if age is not None and age < args.if_older_than:
            print(f"Recent-YC list is {age:.0f}h old - still current, skipping.")
            return
    started = time.time()
    companies = yc_recent.recent(args.years)
    print(f"{len(companies):,} companies from the last {args.years} years of batches; "
          f"{sum(c.hiring for c in companies):,} say they are hiring", flush=True)
    known = store.yc_recent_linkedin()
    batch: list = []
    for i, company in enumerate(companies, 1):
        if company.slug in known and known[company.slug][0]:
            company.linkedin, company.linkedin_source = known[company.slug]
        elif not args.no_pages:
            try:
                company.linkedin = yc_recent.linkedin_from_page(company.slug)
            except Exception:  # one unreadable page must not end the run
                company.linkedin = ""
            company.linkedin_source = "yc page" if company.linkedin else ""
        if not company.linkedin:
            company.linkedin = yc_recent.search_link(company.name)
            company.linkedin_source = "search"
        batch.append(company)
        if len(batch) >= 50:
            store.save_yc_recent(batch)
            batch = []
            print(f"  {i:,}/{len(companies):,} saved", flush=True)
    if batch:
        store.save_yc_recent(batch)
    real = sum(1 for c in companies if c.linkedin_source == "yc page")
    print(f"done in {(time.time() - started) / 60:.0f} min: {real:,} LinkedIn profiles read "
          f"from YC pages, {len(companies) - real:,} shown as a search")


if __name__ == "__main__":
    for _stream in (sys.stdout, sys.stderr):
        _stream.reconfigure(encoding="utf-8", errors="replace")
    main()
