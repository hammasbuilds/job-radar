"""Where the data lives, and the few values that belong to one person.

Two kinds of setting, kept apart on purpose:

**Paths** come from environment variables so a test, a replay or a second
copy of the tool can point at its own database and cache without touching
the owner's. Every path is resolved when it is used, never at import time,
so setting the variable in a test fixture is enough.

    JOBRADAR_DATA     directory holding the database and the HTTP cache
    JOBRADAR_DB       the SQLite file (default: $JOBRADAR_DATA/radar.sqlite3)
    JOBRADAR_CACHE    the HTTP cache (default: $JOBRADAR_DATA/cache)
    JOBRADAR_OFFLINE  "1" = read the cache whatever its age, never the network
    JOBRADAR_CONFIG   the personal config file (default: ./config.toml)

**Personal values** (the contact address sent to job boards, where the CV and
the portfolio index are) live in `config.toml`, which is gitignored.
`config.example.toml` is the template. Without a config the tool still runs:
it sends no address, and the gap report works from whatever it is given.
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def data_dir() -> Path:
    return Path(os.environ.get("JOBRADAR_DATA") or ROOT / "data")


def db_path() -> Path:
    return Path(os.environ.get("JOBRADAR_DB") or data_dir() / "radar.sqlite3")


def cache_dir() -> Path:
    return Path(os.environ.get("JOBRADAR_CACHE") or data_dir() / "cache")


def offline() -> bool:
    return os.environ.get("JOBRADAR_OFFLINE", "") == "1"


def config_path() -> Path:
    return Path(os.environ.get("JOBRADAR_CONFIG") or ROOT / "config.toml")


@dataclass(frozen=True)
class Settings:
    """The personal half. Every field has a safe empty default."""

    # Sent in the User-Agent so a board operator can reach whoever is polling
    # them. Empty means no address is sent.
    contact_email: str = ""
    # The portfolio index whose `**Stack:**` lines prove skills.
    projects_md: Path | None = None
    # One CV file (.docx or .pdf). Nothing is searched for: a tool that globs
    # a stranger's Downloads folder for "*CV*" has no business doing so.
    cv_path: Path | None = None


def load(path: Path | None = None) -> Settings:
    """Read the config file, or return the defaults when there is none.

    A malformed file is an error rather than a silent default, because a
    typo that quietly drops the CV from the gap report looks exactly like a
    CV with nothing in it.
    """
    target = path or config_path()
    if not target.exists():
        return Settings()
    with target.open("rb") as handle:
        raw = tomllib.load(handle)
    unknown = set(raw) - {"contact_email", "projects_md", "cv_path"}
    if unknown:
        raise ValueError(f"{target}: unknown setting(s) {sorted(unknown)}")

    def _path(key: str) -> Path | None:
        value = raw.get(key)
        return Path(value).expanduser() if value else None

    return Settings(
        contact_email=str(raw.get("contact_email", "")).strip(),
        projects_md=_path("projects_md"),
        cv_path=_path("cv_path"),
    )
