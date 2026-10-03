"""Fetch every source, run the pipeline, store the result, print the funnel.

    python scripts/fetch.py                    # live crawl, cached where fresh
    python scripts/fetch.py --fresh            # ignore the cache
    python scripts/fetch.py --offline          # replay the cache, no network
    python scripts/fetch.py --offline --results results/replay.json
    python scripts/fetch.py --list-sources     # every source considered, and why

This is the whole tool in one command. It is safe to run repeatedly: the HTTP
cache means a second run within six hours is offline, and the store records
what was already seen so "new since last run" is real rather than a re-listing
of the same jobs.

--offline replays whatever the cache holds, however old, and never touches the
network. Same bytes in, same funnel out: it is how every number in the README
is reproduced. Point JOBRADAR_CACHE at a frozen copy of a cache and
JOBRADAR_DB (or --db) at a scratch database to replay without touching yours.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from jobradar import companies, config, pipeline, store  # noqa: E402
from jobradar.sources import (  # noqa: E402
    aggregators,
    ats,
    boards,
    greenhouse,
    lever,
    mustakbil,
    registry,
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

BOARDS = (
    ("arbeitnow", aggregators.fetch_arbeitnow),
    ("remotive", aggregators.fetch_remotive),
    ("himalayas", boards.himalayas),
    ("jobicy", boards.jobicy),
    ("remoteok", boards.remoteok),
    ("themuse", boards.themuse),
    ("hn", boards.hacker_news),
    # Mustakbil's RSS feed: the 500 freshest Pakistani postings in one
    # request, so it runs every time. The deep sweep below is the slow part.
    ("mustakbil", mustakbil.fetch_feed),
)


def collect(fresh: bool, quiet: bool = False,
            pakistan: bool = False) -> tuple[list, dict]:
    """Every source, one line of progress each. One bad board never ends a run."""
    kw = {"max_age": 0.0} if fresh else {}
    postings: list = []
    per_source: dict[str, int] = {}
    dead: list[str] = []
    failed: list[str] = []
    say = (lambda *a: None) if quiet else (lambda *a: print(*a, flush=True))

    slugs = companies.all_slugs()
    total = len(slugs) + len(BOARDS)
    for i, (provider, slug) in enumerate(slugs, 1):
        try:
            got = FETCHERS[provider](slug, **kw)
        except (SourceError, ValueError, OSError) as exc:
            # The seed list is hand-made, so bad entries are the expected case
            # rather than the surprise; a 67-board crawl that dies on entry 11
            # has fetched nothing.
            failed.append(f"{provider}/{slug}")
            say(f"  [{i:>2}/{total}] {provider}/{slug}: failed ({exc})")
            continue
        if not got:
            dead.append(f"{provider}/{slug}")
        postings += got
        per_source[provider] = per_source.get(provider, 0) + len(got)
        say(f"  [{i:>2}/{total}] {provider}/{slug}: {len(got):,}")

    for j, (name, call) in enumerate(BOARDS, len(slugs) + 1):
        try:
            got = call(**kw)
        except (SourceError, ValueError, OSError) as exc:
            failed.append(name)
            say(f"  [{j:>2}/{total}] {name}: failed ({exc})")
            continue
        postings += got
        per_source[name] = per_source.get(name, 0) + len(got)
        say(f"  [{j:>2}/{total}] {name}: {len(got):,}")

    # The deep sweep: all ~1,400 live postings instead of the feed's freshest
    # 500, at one request each. Opt-in because their pages answer in about
    # nine seconds, so a full pass is hours rather than minutes.
    if pakistan:
        try:
            def tick(i, n, kept):
                say(f"  mustakbil {i}/{n} fetched, {kept} parsed")

            seen = {p.url for p in postings}
            got = [p for p in mustakbil.fetch(progress=tick) if p.url not in seen]
            postings += got
            per_source["mustakbil"] = per_source.get("mustakbil", 0) + len(got)
        except (SourceError, ValueError, OSError) as exc:
            say(f"  ! mustakbil deep sweep: {exc}")

    if dead:
        say(f"  {len(dead)} board(s) returned nothing: {', '.join(dead[:8])}"
            f"{' …' if len(dead) > 8 else ''}")
    if failed:
        say(f"  {len(failed)} source(s) failed: {', '.join(failed[:8])}"
            f"{' …' if len(failed) > 8 else ''}")
    return postings, per_source


def list_sources() -> None:
    """Print every source ever considered, grouped by what happened to it."""
    for status in (registry.WIRED, registry.NEEDS_KEY, registry.NO_API,
                   registry.PROHIBITED, registry.OUT_OF_SCOPE):
        rows = registry.by_status(status)
        print(f"\n{status} ({len(rows)})")
        for source in rows:
            note = f"  - {source.note}" if source.note else ""
            print(f"  {source.name:<38} {source.group:<14}{note}")


def results_payload(postings: list, per_source: dict, kept: list, funnel) -> dict:
    """Everything the README quotes, in one file, so each number has a source."""
    return {
        "generated": datetime.now(UTC).isoformat(timespec="seconds"),
        "offline_replay": config.offline(),
        "fetched": funnel.fetched,
        "per_source": dict(sorted(per_source.items(), key=lambda kv: -kv[1])),
        "after_dedup": funnel.after_dedup,
        "duplicates": funnel.duplicates,
        "killed": funnel.killed,
        "kill_order": list(funnel.order),
        "kept": len(kept),
        "sections": funnel.sections,
        "distinct_keys": len({p.key for p in postings}),
        "kept_postings": [
            {"company": p.company, "title": p.title, "location": p.location,
             "section": p.section, "url": p.url,
             "auth": p.verdict.get("auth"), "auth_why": p.verdict.get("auth_why"),
             "scope": p.verdict.get("scope"), "scope_why": p.verdict.get("scope_why")}
            for p in kept
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--fresh", action="store_true",
                        help="ignore the HTTP cache and ask every board again")
    parser.add_argument("--offline", action="store_true",
                        help="replay the HTTP cache whatever its age; never use the network")
    parser.add_argument("--db", type=Path, default=None, metavar="PATH",
                        help="SQLite file to write (default: $JOBRADAR_DB or data/radar.sqlite3)")
    parser.add_argument("--results", type=Path, default=None, metavar="FILE",
                        help="also write the funnel and every kept posting to this JSON file")
    parser.add_argument(
        "--pakistan", action="store_true",
        help="Mustakbil deep sweep: every live posting, one request each (hours). "
             "The feed's freshest 500 are fetched on every run regardless.",
    )
    parser.add_argument(
        "--if-older-than", type=float, default=None, metavar="HOURS",
        help="skip entirely when the last run is newer than this",
    )
    parser.add_argument("--list-sources", action="store_true",
                        help="print every source considered and why it is or is not wired")
    args = parser.parse_args()

    if args.list_sources:
        list_sources()
        return
    if args.fresh and args.offline:
        parser.error("--fresh and --offline contradict each other")
    if args.offline:
        os.environ["JOBRADAR_OFFLINE"] = "1"
    if args.db:
        os.environ["JOBRADAR_DB"] = str(args.db.resolve())

    # The launcher passes this. Twenty sources take minutes, and a one-click
    # shortcut that sits on a console before showing anything is a shortcut
    # nobody clicks twice. Postings do not turn over in an hour.
    if args.if_older_than is not None:
        last = store.last_run()
        if last:
            age = (datetime.now(UTC)
                   - datetime.fromisoformat(last["at"])).total_seconds() / 3600
            if age < args.if_older_than:
                print(f"Last run was {age:.1f}h ago - still current, skipping the crawl.")
                print("Force one with: python scripts/fetch.py")
                return

    started = time.time()
    extra = " plus a Mustakbil deep sweep" if args.pakistan else ""
    mode = " (offline replay of the cache)" if args.offline else ""
    print(f"asking {companies.count()} company boards and {len(BOARDS)} job-board APIs"
          f"{extra}{mode}...", flush=True)
    postings, per_source = collect(args.fresh, pakistan=args.pakistan)
    if not postings:
        raise SystemExit("nothing fetched - check the network, then --fresh"
                         if not args.offline else "nothing in the cache to replay")

    print(f"\nfetched {len(postings):,} postings in {time.time() - started:.0f}s")
    for name, n in sorted(per_source.items(), key=lambda kv: -kv[1]):
        print(f"  {name:<16} {n:>6,}")

    kept, funnel = pipeline.run(postings)

    print("\nthe funnel, in pipeline order")
    for line in funnel.as_lines():
        print("  " + line)

    new = store.save(kept, funnel)
    print(f"\n{len(kept):,} kept, {new:,} new since the last run")
    print(f"stored in {store.db_path()}")

    if args.results:
        args.results.parent.mkdir(parents=True, exist_ok=True)
        payload = results_payload(postings, per_source, kept, funnel)
        args.results.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                                encoding="utf-8")
        print(f"results written to {args.results}")

    print("\nnext: python -m jobradar.api   (then open http://127.0.0.1:8000)")


if __name__ == "__main__":
    # A Windows console defaults to the ANSI code page; the output has arrows and ellipses.
    for _stream in (sys.stdout, sys.stderr):
        _stream.reconfigure(encoding="utf-8", errors="replace")
    main()
