"""An offline run of the whole tool on bundled fixtures.

    python scripts/fetch.py --dry-run

The fixtures in `tests/fixtures/dryrun/` are small, invented API responses -
fictional companies, written in each source's real shape - that between them
reach every kill reason the pipeline has and every adapter quirk that has bitten
before: Greenhouse's entity-escaped HTML and null fields, Lever's structured
`workplaceType`, RemoteOK's legal-notice row, Himalayas' cursor pages, the
Hacker News header convention, Mustakbil's escaped RSS timezone.

They are not real postings on purpose. The real corpus is other people's job
ads and a personal search history, and neither belongs in a repository.

The fixtures are loaded into a scratch HTTP cache with `http.prime` and read
back in offline mode, so they travel the exact code path a cached live
response does. `isolated` points every path at a temporary directory first:
a dry run never reads or writes the owner's database, cache or config.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from . import config
from .sources import aggregators, boards, greenhouse, http, lever, mustakbil

FIXTURES = config.ROOT / "tests" / "fixtures" / "dryrun"

# (provider, slug) for the company boards the fixtures stand in for.
SEEDS = [("greenhouse", "acme-ai"), ("lever", "nordlicht")]

# Names from scripts/fetch.py BOARDS that have fixtures.
BOARDS = {"arbeitnow", "remoteok", "himalayas", "hn", "mustakbil"}


def responses() -> list[tuple[str, str]]:
    """(URL exactly as the adapter asks for it, fixture file)."""
    return [
        (greenhouse.BOARD.format(slug="acme-ai"), "greenhouse-acme-ai.json"),
        (lever.BOARD.format(slug="nordlicht"), "lever-nordlicht.json"),
        (aggregators.ARBEITNOW, "arbeitnow.json"),
        (boards.REMOTEOK, "remoteok.json"),
        (boards.HIMALAYAS, "himalayas-1.json"),
        (f"{boards.HIMALAYAS}&cursor=page-two", "himalayas-2.json"),
        (boards.HN, "hn-search.json"),
        (boards.HN_ITEM.format(id="1"), "hn-item.json"),
        (mustakbil.RSS.format(category=0), "mustakbil.xml"),
    ]


_ENV = ("JOBRADAR_DATA", "JOBRADAR_DB", "JOBRADAR_CACHE", "JOBRADAR_CONFIG",
        "JOBRADAR_OFFLINE")


def _reset_process_state() -> None:
    http.user_agent.cache_clear()
    http._robots.clear()
    http._last_request.clear()


@contextmanager
def isolated(scratch: Path) -> Iterator[Path]:
    """Point the database, cache and config at `scratch`, offline, then restore."""
    saved = {name: os.environ.get(name) for name in _ENV}
    os.environ["JOBRADAR_DATA"] = str(scratch)
    os.environ["JOBRADAR_DB"] = str(scratch / "radar.sqlite3")
    os.environ["JOBRADAR_CACHE"] = str(scratch / "cache")
    os.environ["JOBRADAR_CONFIG"] = str(scratch / "no-config.toml")
    os.environ["JOBRADAR_OFFLINE"] = "1"
    _reset_process_state()
    try:
        yield scratch
    finally:
        for name, value in saved.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        _reset_process_state()


def install(fixtures: Path = FIXTURES) -> dict:
    """Copy every fixture into the (scratch) cache. Returns what to crawl."""
    if not config.offline() or "JOBRADAR_CACHE" not in os.environ:
        raise RuntimeError("dryrun.install() runs only inside dryrun.isolated()")
    for url, name in responses():
        http.prime(url, (fixtures / name).read_text(encoding="utf-8"))
    return {"seeds": list(SEEDS), "boards": set(BOARDS)}


def evidence(verdict: dict) -> str:
    """The phrase behind a kill, from whichever filter made it."""
    reason = verdict.get("killed_by", "")
    if reason.startswith(("refuses", "citizens", "relocation")):
        return verdict.get("auth_why", "")
    if reason.endswith(" level"):
        return verdict.get("level_why", "")
    if reason.startswith("wants "):
        return verdict.get("years_why", "")
    if reason == "not one of the target roles":
        return verdict.get("fit_why", "")
    return verdict.get("scope_why", "")
