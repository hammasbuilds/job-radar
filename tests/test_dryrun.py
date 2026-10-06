"""The offline dry run, the crawl loop's error handling, and the dashboard host check."""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path

import pytest

from jobradar import config

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def fetch_script():
    spec = importlib.util.spec_from_file_location("fetch_script", ROOT / "scripts" / "fetch.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_dry_run_reaches_every_section_and_kill_reason(fetch_script, isolated_data):
    payload = fetch_script.dry_run(quiet=True)

    assert payload["dry_run"] and payload["offline_replay"]
    assert payload["fetched"] == 20 and payload["duplicates"] == 1
    assert set(payload["sections"]) == {"sponsorship", "remote", "europe", "pakistan"}
    assert set(payload["killed"]) == {
        "not one of the target roles", "senior level", "refuses sponsorship",
        "remote, country-locked", "relocation offered, sponsorship unstated",
        "remote, region-locked, no contractor route",
    }
    kept = {(p["company"], p["title"]): p["section"] for p in payload["kept_postings"]}
    # The audit's fixes, end to end through the adapters.
    assert ("acme-ai", "Data Scientist, Marketing") in kept
    assert kept[("Fjordtech", "ML Engineer")] == "sponsorship,europe"
    assert ("Spektrum GmbH", "Founding ML Engineer") in kept
    assert ("acme-ai", "AI Engineer") not in kept
    assert ("nordlicht", "NLP Engineer") not in kept


def test_the_dry_run_touches_none_of_the_owners_files(fetch_script, isolated_data):
    before = {name: os.environ.get(name) for name in
              ("JOBRADAR_DATA", "JOBRADAR_DB", "JOBRADAR_CACHE", "JOBRADAR_OFFLINE")}
    fetch_script.dry_run(quiet=True)
    after = {name: os.environ.get(name) for name in before}
    assert before == after
    # The conftest's scratch data directory stands in for the owner's: the dry
    # run used its own temporary one and left this one untouched.
    assert not config.db_path().exists()
    assert not config.cache_dir().exists()


def test_one_broken_adapter_does_not_end_the_crawl(fetch_script, monkeypatch):
    """A board that changes its JSON shape raises KeyError or TypeError; the
    loop caught only network errors, so one such board ended the run."""
    from jobradar.posting import Posting

    def broken(slug, **kw):
        raise KeyError("jobs")

    def fine(slug, **kw):
        return [Posting(source="greenhouse", company="Acme", title="ML Engineer",
                        location="Berlin", url="https://example.com/1", text="")]

    monkeypatch.setitem(fetch_script.FETCHERS, "greenhouse", fine)
    monkeypatch.setitem(fetch_script.FETCHERS, "lever", broken)
    postings, per_source = fetch_script.collect(
        False, quiet=True, slugs=[("lever", "x"), ("greenhouse", "y")], boards=())
    assert len(postings) == 1 and per_source == {"greenhouse": 1}


def _status(app, host: str, path: str = "/api/pipeline") -> int:
    """One GET through the ASGI app, without a test client dependency."""
    import asyncio

    sent: list[dict] = []

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        sent.append(message)

    scope = {
        "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
        "method": "GET", "scheme": "http", "path": path, "raw_path": path.encode(),
        "root_path": "", "query_string": b"", "headers": [(b"host", host.encode())],
        "client": ("127.0.0.1", 5000), "server": ("127.0.0.1", 8000),
    }
    asyncio.run(app(scope, receive, send))
    return next(m["status"] for m in sent if m["type"] == "http.response.start")


def test_the_dashboard_refuses_a_foreign_host_header():
    """DNS rebinding: a page on another domain pointed at 127.0.0.1 must not
    be able to read the search history."""
    from jobradar import api

    assert _status(api.app, "127.0.0.1:8000") == 200
    assert _status(api.app, "localhost:8000") == 200
    assert _status(api.app, "attacker.example") == 400
