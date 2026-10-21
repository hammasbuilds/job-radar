"""Read the job page of every AI portfolio role shown as open to a junior, and keep what the
page says about itself: the real title (with its level word), where it is, the salary, the
posting date, the years asked - and whether the job is gone.

The sitemaps give a title made from the address, which loses "Staff" and "Senior" and every
location. One request per job, at each board's own pace (robots.txt asks named crawlers for
10 seconds and this honours that for everyone), one board per thread, pages cached for a day.

    python scripts/fetch_portfolio_details.py              # roles not read in the last 7 days
    python scripts/fetch_portfolio_details.py --limit 50   # a sample
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from jobradar import store  # noqa: E402
from jobradar.filters import places, seniority  # noqa: E402
from jobradar.profile import ACCEPT_LEVELS, MAX_YEARS  # noqa: E402
from jobradar.sources import portfolios  # noqa: E402
from jobradar.sources.http import SourceError, get_text  # noqa: E402

DAY = 24 * 3600
PACE = 10.0
_write = threading.Lock()


def judge(page: dict) -> dict:
    """The junior verdict from the page's own title and text, as the crawl judges any job."""
    level, _ = seniority.classify(page["title"])
    found = [y for y in (seniority.years_required(page["text"]),
                         seniority.years_in_title(page["title"])) if y is not None]
    years = max(found) if found else None
    return {"level": level, "years": years,
            "junior": int(level in ACCEPT_LEVELS and (years is None or years <= MAX_YEARS))}


def read_one(url: str) -> dict:
    try:
        raw = get_text(url, max_age=DAY)
    except SourceError as exc:
        return {"error": str(exc)}
    if raw is None:  # 404 or 410: the job is gone
        return {"gone": 1}
    page = portfolios.parse_job_page(raw)
    if not page:
        return {"error": "no JobPosting data on the page"}
    return {**page, **judge(page), "countries": places.countries_of("; ".join(page["locations"]))}


def save(db: Path, url: str, d: dict) -> None:
    with _write:
        conn = sqlite3.connect(db)
        try:
            with conn:
                conn.execute(
                    "INSERT OR REPLACE INTO portfolio_detail VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    (url, d.get("title"), json.dumps(d.get("locations") or []),
                     json.dumps(d.get("countries") or []), int(bool(d.get("remote"))),
                     d.get("posted"), d.get("salary"), d.get("years"), d.get("level"),
                     d.get("junior"), int(d.get("gone", 0)), datetime.now(UTC).isoformat()))
        finally:
            conn.close()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--limit", type=int, default=0, help="at most this many roles in all")
    ap.add_argument("--days", type=float, default=7, help="re-read a role older than this")
    args = ap.parse_args()
    db = store.db_path()
    store.connect(db).close()  # creates portfolio_detail on an older database
    conn = sqlite3.connect(db)
    since = (datetime.now(UTC) - timedelta(days=args.days)).isoformat()
    rows = conn.execute(
        "SELECT j.programme, j.url FROM portfolio_job j LEFT JOIN portfolio_detail d "
        "ON d.url = j.url WHERE j.ai = 1 AND j.junior = 1 AND (d.url IS NULL OR d.at < ?) "
        "ORDER BY j.programme, j.company", (since,)).fetchall()
    conn.close()
    if args.limit:
        rows = rows[:args.limit]
    by_programme: dict[str, list[str]] = {}
    for programme, url in rows:
        by_programme.setdefault(programme, []).append(url)
    print(f"{len(rows)} roles to read across {len(by_programme)} boards", flush=True)
    started = time.time()
    tally = {"read": 0, "gone": 0, "error": 0, "now senior": 0}

    def board(programme: str, urls: list[str]) -> None:
        for i, url in enumerate(urls, 1):
            t0 = time.monotonic()
            d = read_one(url)
            # robots.txt asks its named crawlers for 10 s between requests; every crawler
            # gets the same courtesy here, whatever the http layer's own minimum is.
            time.sleep(max(0.0, PACE - (time.monotonic() - t0)))
            if "error" in d:
                tally["error"] += 1
                continue
            save(db, url, d)
            tally["gone" if d.get("gone") else "read"] += 1
            if not d.get("gone") and not d.get("junior"):
                tally["now senior"] += 1
            if i % 50 == 0:
                print(f"  {programme}: {i}/{len(urls)}", flush=True)

    with ThreadPoolExecutor(max(1, len(by_programme))) as pool:
        for f in [pool.submit(board, p, u) for p, u in by_programme.items()]:
            f.result()
    print(f"done in {time.time() - started:.0f}s: {tally}", flush=True)


if __name__ == "__main__":
    for _stream in (sys.stdout, sys.stderr):
        _stream.reconfigure(encoding="utf-8", errors="replace")
    main()
