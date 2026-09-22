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
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from jobradar import companies, pipeline, store  # noqa: E402
from jobradar.sources import aggregators, boards, greenhouse, lever  # noqa: E402
from jobradar.sources.http import SourceError  # noqa: E402

FETCHERS = {"greenhouse": greenhouse.fetch, "lever": lever.fetch}


def collect(fresh: bool, quiet: bool = False) -> tuple[list, dict]:
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

    if dead and not quiet:
        print(f"  {len(dead)} board(s) returned nothing: {', '.join(dead[:8])}"
              f"{' …' if len(dead) > 8 else ''}")
    return postings, per_source


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fresh", action="store_true", help="ignore the HTTP cache")
    parser.add_argument("--min-score", type=float, default=pipeline.MIN_SCORE)
    args = parser.parse_args()

    started = time.time()
    print(f"asking {companies.count()} boards plus 2 aggregators…")
    postings, per_source = collect(args.fresh)
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
