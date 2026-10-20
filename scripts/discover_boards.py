"""Find which candidate employers have a readable job board, on which provider.

    python scripts/discover_boards.py              # every candidate, every provider
    python scripts/discover_boards.py --region gulf
    python scripts/discover_boards.py --report     # what the last pass found, no network

Each name in `candidates.py` is tried in its usual slug spellings on Greenhouse, Lever, Ashby,
Workable, Recruitee and Personio - every provider this tool reads (SmartRecruiters forbids it in
robots.txt). A board counts only if it answers with at least one posting, because an empty board
and a wrong slug look the same and only the first is a source.

Results go to `src/jobradar/boards_found.json`, which `companies.all_slugs()` merges into every
crawl. Progress is saved after each answer, so an interrupted pass resumes where it stopped.
One thread per provider: every host is paced by the HTTP layer, so providers run side by side
and no single host is asked faster than its robots.txt allows.
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from jobradar import candidates, companies  # noqa: E402
from jobradar.sources import ats, greenhouse, lever  # noqa: E402

PROVIDERS = {
    "greenhouse": greenhouse.fetch,
    "lever": lever.fetch,
    "ashby": ats.ashby,
    "workable": ats.workable,
    "recruitee": ats.recruitee,
    "personio": ats.personio,
}
FOUND = ROOT / "src" / "jobradar" / "boards_found.json"
PROGRESS = ROOT / "data" / "discover_progress.json"
_lock = threading.Lock()


def _load(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _save(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=1, ensure_ascii=False, sort_keys=True) + "\n",
                   encoding="utf-8")
    tmp.replace(path)


def probe(provider: str, todo: list[tuple[str, str]], found: dict, progress: dict,
          seeded: set[tuple[str, str]], say) -> None:
    fetch = PROVIDERS[provider]
    hits = 0
    for i, (region, name) in enumerate(todo, 1):
        for slug in candidates.slugs_for(name):
            key = f"{provider}|{slug}"
            if (provider, slug) in seeded:
                break
            if key in progress:
                if progress[key] > 0:
                    break
                continue
            try:
                n = len(fetch(slug))
            except Exception:  # a wrong slug is the expected case, in many shapes
                n = 0
            with _lock:
                progress[key] = n
                if n > 0:
                    hits += 1
                    found.setdefault(provider, {})[slug] = {
                        "company": name, "region": region, "postings": n,
                        "found": time.strftime("%Y-%m-%d"),
                    }
                    _save(FOUND, found)
                if len(progress) % 25 == 0:
                    _save(PROGRESS, progress)
            if n > 0:
                say(f"  + {provider}/{slug} ({name}, {region}): {n}")
                break
        if i % 100 == 0:
            say(f"  {provider}: {i}/{len(todo)} names asked, {hits} boards so far")
    with _lock:
        _save(PROGRESS, progress)
    say(f"  {provider}: done, {hits} new boards")


def report(found: dict) -> None:
    total = sum(len(v) for v in found.values())
    postings = sum(b["postings"] for v in found.values() for b in v.values())
    print(f"{total} boards found, {postings:,} postings at discovery time")
    by_region: dict[str, int] = {}
    for boards in found.values():
        for b in boards.values():
            by_region[b["region"]] = by_region.get(b["region"], 0) + 1
    for provider, boards in sorted(found.items()):
        print(f"  {provider:<11} {len(boards):>4}")
    for region, n in sorted(by_region.items(), key=lambda kv: -kv[1]):
        print(f"  region {region:<10} {n:>4}")
    print(f"  plus {companies.count()} hand-seeded boards in companies.py")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--region", choices=sorted(candidates.REGIONS), default=None)
    parser.add_argument("--report", action="store_true")
    args = parser.parse_args()
    found = _load(FOUND, {})
    if args.report:
        report(found)
        return
    progress = _load(PROGRESS, {})
    seeded = set(companies.SEEDS_ONLY())
    todo = candidates.names(args.region)

    def say(*a):
        with _lock:
            print(*a, flush=True)

    say(f"asking {len(todo)} employers on {len(PROVIDERS)} providers "
        f"({len(progress)} answers already saved)")
    started = time.time()
    with ThreadPoolExecutor(len(PROVIDERS)) as pool:
        for provider in PROVIDERS:
            pool.submit(probe, provider, todo, found, progress, seeded, say)
    say(f"finished in {(time.time() - started) / 60:.0f} min")
    report(found)


if __name__ == "__main__":
    for _stream in (sys.stdout, sys.stderr):
        _stream.reconfigure(encoding="utf-8", errors="replace")
    main()
