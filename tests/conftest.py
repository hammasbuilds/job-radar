"""Every test runs against a scratch data directory, never the owner's.

The database is a personal record (applications are typed by hand) and the
cache is a frozen corpus; a test must not create, read or write either. Every
path in the package is resolved from these variables at the moment it is
used, so pointing them at a temporary directory is enough. Offline mode is on
as well: a test that reaches for the network fails instead of hanging.
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def isolated_data(tmp_path, monkeypatch):
    data = tmp_path / "data"
    monkeypatch.setenv("JOBRADAR_DATA", str(data))
    monkeypatch.setenv("JOBRADAR_DB", str(data / "radar.sqlite3"))
    monkeypatch.setenv("JOBRADAR_CACHE", str(data / "cache"))
    monkeypatch.setenv("JOBRADAR_CONFIG", str(tmp_path / "no-config.toml"))
    monkeypatch.setenv("JOBRADAR_OFFLINE", "1")
    from jobradar.sources import http

    http.user_agent.cache_clear()
    yield data
    http.user_agent.cache_clear()
