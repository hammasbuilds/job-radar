"""Fetch every source, run the pipeline, store the result, print the funnel.

    python scripts/fetch.py            # cached where fresh
    python scripts/fetch.py --fresh    # ignore the cache

This is the whole tool in one command. It is safe to run repeatedly: the HTTP
cache means a second run within six hours is offline, and the store records
what was already seen so "new since last run" is real rather than a re-listing
of the same jobs.
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from jobradar import companies, pipeline, store  # noqa: E402
from jobradar.sources import (  # noqa: E402
    aggregators, ats, boards, greenhouse, lever, mustakbil,
)
from jobradar.sources.http import SourceError  # noqa: E402

# Six providers, not two. companies.py can seed a slug on any of them, and
# for a while it could not: the Pakistan section looked empty because the only
# two providers asked were the two Pakistani employers least often use.
FETCHERS = {
    "greenhouse": greenhouse.fetch,
    "lever": lever.fetch,
    "workable": ats.workable,
    "ashby": ats.ashby,
    "smartrecruiters": ats.smartrecruiters,
    "recruitee": ats.recruitee,
}


def collect(fresh: bool, quiet: bool = False,
            pakistan: bool = False) -> tuple[list, dict]:
    kw = {"max_age": 0.0} if fresh else {}
    postings = []
    per_source = {}
    dead = []

    for provider, slug in companies.all_slugs():
        try:
            got = FETCHERS[provider](slug, **kw)
        except (SourceError, ValueError, OSError) as exc:
            # One bad board must never end the run. A 67-board crawl that dies
            # on entry 11 has fetched nothing, and the seed list is hand-made,
            # so bad entries are the expected case rather than the surprise.
            if not quiet:
                print(f"  ! {provider}/{slug}: {exc}")
            continue
        if not got:
            dead.append(f"{provider}/{slug}")
            continue
        postings += got
        per_source[provider] = per_source.get(provider, 0) + len(got)

    for name, call in (("arbeitnow", aggregators.fetch_arbeitnow),
                       ("remotive", aggregators.fetch_remotive),
                       ("himalayas", boards.himalayas),
                       ("jobicy", boards.jobicy),
                       ("remoteok", boards.remoteok),
                       ("themuse", boards.themuse),
                       ("hn", boards.hacker_news)):
        try:
            got = call(**kw)
            postings += got
            per_source[name] = len(got)
        except (SourceError, ValueError, OSError) as exc:
            # One board being down must not cost the whole run.
            if not quiet:
                print(f"  ! {name}: {exc}")

    # Mustakbil is one HTTP request per posting - 1,403 of them, paced - so it
    # is opt-in rather than part of every run. Everything else here answers in
    # one call and the whole default crawl is about five minutes; adding
    # twenty to it by default would make the launcher's one-click run useless.
    try:
        got = mustakbil.fetch_feed(**kw)
        postings += got
        per_source["mustakbil"] = len(got)
    except (SourceError, ValueError, OSError) as exc:
        if not quiet:
            print(f"  ! mustakbil: {exc}")

    # The deep sweep: all 1,403 live postings instead of the feed's freshest
    # 500, at one request each. Opt-in because their pages answer in about
    # nine seconds, so a full pass is hours rather than minutes.
    if pakistan:
        try:
            def tick(i, n, kept):
                if not quiet:
                    print(f"  mustakbil {i}/{n} fetched, {kept} parsed")

            seen = {p.url for p in postings}
            got = [p for p in mustakbil.fetch(progress=tick) if p.url not in seen]
            postings += got
            per_source["mustakbil"] = per_source.get("mustakbil", 0) + len(got)
        except (SourceError, ValueError, OSError) as exc:
            if not quiet:
                print(f"  ! mustakbil deep sweep: {exc}")

    if dead and not quiet:
        print(f"  {len(dead)} board(s) returned nothing: {', '.join(dead[:8])}"
              f"{' …' if len(dead) > 8 else ''}")
    return postings, per_source


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fresh", action="store_true", help="ignore the HTTP cache")
    parser.add_argument("--min-score", type=float, default=pipeline.MIN_SCORE)
    parser.add_argument(
        "--pakistan", action="store_true",
        help="Mustakbil deep sweep: all 1,403 postings, one request each. "
             "The feed's freshest 500 are fetched on every run regardless.",
    )
    parser.add_argument(
        "--if-older-than", type=float, default=None, metavar="HOURS",
        help="skip entirely when the last run is newer than this",
    )
    args = parser.parse_args()

    # The launcher passes this. Twelve sources take about five minutes, and a
    # one-click shortcut that sits on a console for five minutes before
    # showing anything is a shortcut nobody clicks twice. Postings do not turn
    # over in an hour.
    if args.if_older_than is not None:
        last = store.last_run()
        if last:
            age = (datetime.now(timezone.utc)
                   - datetime.fromisoformat(last["at"])).total_seconds() / 3600
            if age < args.if_older_than:
                print(f"Last run was {age:.1f}h ago — still current, skipping the crawl.")
                print("Force one with: python scripts/fetch.py")
                return

    started = time.time()
    extra = " plus a Mustakbil deep sweep" if args.pakistan else ""
    print(f"asking {companies.count()} company boards plus 8 job-board APIs{extra}…")
    postings, per_source = collect(args.fresh, pakistan=args.pakistan)
    if not postings:
        raise SystemExit("nothing fetched — check the network, then --fresh")

    print(f"\nfetched {len(postings):,} postings in {time.time() - started:.0f}s")
    for name, n in sorted(per_source.items(), key=lambda kv: -kv[1]):
        print(f"  {name:<12} {n:>6,}")

    kept, funnel = pipeline.run(postings, args.min_score)

    print("\nthe funnel")
    for line in funnel.as_lines():
        print("  " + line)

    new = store.save(kept, funnel)
    print(f"\n{len(kept):,} kept, {new:,} new since the last run")
    print(f"stored in {store.DB}")
    print("\nnext: python -m jobradar.api   (then open http://127.0.0.1:8000)")


if __name__ == "__main__":
    main()
