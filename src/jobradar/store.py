"""SQLite, no ORM. The store exists to answer one question: what is new?

The note is firm that this runs on a schedule and reports **what is new since
yesterday**, rather than showing the same list again. That is the only reason
there is a database at all — the postings could otherwise be recomputed from
cache in seconds.

So `first_seen` is the important column, and it is never updated. A posting
re-fetched tomorrow keeps the date it was first seen, which is what makes
"new since last run" mean anything.

**The pipeline column is stored as the verdict, not as a summary.** Every
filter's reason string is kept so the Killed screen can show why, months
later, without re-running anything.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB = Path(__file__).resolve().parents[2] / "data" / "radar.sqlite3"

SCHEMA = """
CREATE TABLE IF NOT EXISTS posting (
    id          TEXT PRIMARY KEY,
    source      TEXT NOT NULL,
    company     TEXT NOT NULL,
    title       TEXT NOT NULL,
    location    TEXT,
    url         TEXT NOT NULL,
    posted      TEXT,
    score       REAL NOT NULL,
    evidence    TEXT,
    section     TEXT NOT NULL,
    verdict     TEXT NOT NULL,
    text        TEXT,
    first_seen  TEXT NOT NULL,
    last_seen   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS posting_section ON posting(section);
CREATE INDEX IF NOT EXISTS posting_seen    ON posting(first_seen);

-- Rejections, with the reason and the phrase that produced it. This is the
-- trust screen: a tool whose value is that it discards 99% of its input has
-- to show the 99%, or there is no way to tell careful filtering from a bug.
-- It is also the only place a false negative can be found.
CREATE TABLE IF NOT EXISTS killed (
    id         TEXT PRIMARY KEY,
    source     TEXT NOT NULL,
    company    TEXT NOT NULL,
    title      TEXT NOT NULL,
    location   TEXT,
    url        TEXT NOT NULL,
    reason     TEXT NOT NULL,
    verdict    TEXT NOT NULL,
    score      REAL NOT NULL,
    at         TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS killed_reason ON killed(reason);

CREATE TABLE IF NOT EXISTS run (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    at        TEXT NOT NULL,
    fetched   INTEGER NOT NULL,
    kept      INTEGER NOT NULL,
    funnel    TEXT NOT NULL
);

-- Applications are updated by hand. The note is explicit that this is the one
-- part that should not be automated, and there is no code here that writes it
-- except the endpoint a human clicks.
CREATE TABLE IF NOT EXISTS application (
    posting_id TEXT PRIMARY KEY,
    state      TEXT NOT NULL,
    noted      TEXT,
    at         TEXT NOT NULL
);
"""


def connect(path: Path | None = None) -> sqlite3.Connection:
    target = path or DB
    target.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(target)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def save(postings: list, funnel, path: Path | None = None) -> int:
    """Upsert every posting. Returns how many were never seen before."""
    conn = connect(path)
    now = _now()
    new = 0
    try:
        with conn:
            for posting in postings:
                existing = conn.execute(
                    "SELECT first_seen FROM posting WHERE id = ?", (posting.key,)
                ).fetchone()
                if existing is None:
                    new += 1
                conn.execute(
                    """
                    INSERT INTO posting (id, source, company, title, location, url,
                                         posted, score, evidence, section, verdict,
                                         text, first_seen, last_seen)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(id) DO UPDATE SET
                        score=excluded.score, evidence=excluded.evidence,
                        section=excluded.section, verdict=excluded.verdict,
                        last_seen=excluded.last_seen
                    """,
                    (
                        posting.key, posting.source, posting.company, posting.title,
                        posting.location, posting.url,
                        posting.posted.isoformat() if posting.posted else None,
                        posting.score, posting.evidence, posting.section,
                        json.dumps(posting.verdict), posting.text[:20000],
                        existing["first_seen"] if existing else now, now,
                    ),
                )
            conn.execute("DELETE FROM killed")
            for posting in getattr(funnel, "rejected", []):
                conn.execute(
                    """INSERT OR REPLACE INTO killed
                       (id, source, company, title, location, url, reason,
                        verdict, score, at)
                       VALUES (?,?,?,?,?,?,?,?,?,?)""",
                    (posting.key, posting.source, posting.company, posting.title,
                     posting.location, posting.url,
                     posting.verdict.get("killed_by", "unknown"),
                     json.dumps(posting.verdict), posting.score, now),
                )
            conn.execute(
                "INSERT INTO run (at, fetched, kept, funnel) VALUES (?,?,?,?)",
                (now, funnel.fetched, len(postings),
                 json.dumps({"killed": funnel.killed, "sections": funnel.sections,
                             "duplicates": funnel.duplicates,
                             "after_dedup": funnel.after_dedup})),
            )
    finally:
        conn.close()
    return new


def section(name: str, limit: int = 100, path: Path | None = None) -> list[dict]:
    conn = connect(path)
    try:
        rows = conn.execute(
            """
            SELECT p.*, a.state AS applied
            FROM posting p LEFT JOIN application a ON a.posting_id = p.id
            WHERE ',' || p.section || ',' LIKE '%,' || ? || ',%'
            ORDER BY p.score DESC, p.first_seen DESC
            LIMIT ?
            """,
            (name, limit),
        ).fetchall()
        return [_row(r) for r in rows]
    finally:
        conn.close()


def newest(limit: int = 40, path: Path | None = None) -> list[dict]:
    """The Today screen: what appeared in the most recent run."""
    conn = connect(path)
    try:
        last = conn.execute("SELECT MAX(first_seen) AS t FROM posting").fetchone()["t"]
        if not last:
            return []
        rows = conn.execute(
            """
            SELECT p.*, a.state AS applied
            FROM posting p LEFT JOIN application a ON a.posting_id = p.id
            WHERE p.first_seen = ?
            ORDER BY p.score DESC LIMIT ?
            """,
            (last, limit),
        ).fetchall()
        return [_row(r) for r in rows]
    finally:
        conn.close()


def killed(reason: str | None = None, limit: int = 200,
           path: Path | None = None) -> list[dict]:
    """Rejections, newest first, optionally one reason at a time."""
    conn = connect(path)
    try:
        if reason:
            rows = conn.execute(
                "SELECT * FROM killed WHERE reason = ? ORDER BY score DESC LIMIT ?",
                (reason, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM killed ORDER BY score DESC LIMIT ?", (limit,)
            ).fetchall()
        out = []
        for row in rows:
            item = dict(row)
            item["verdict"] = json.loads(item["verdict"])
            out.append(item)
        return out
    finally:
        conn.close()


def kill_reasons(path: Path | None = None) -> list[dict]:
    conn = connect(path)
    try:
        return [
            dict(r) for r in conn.execute(
                "SELECT reason, COUNT(*) AS n FROM killed GROUP BY reason ORDER BY n DESC"
            ).fetchall()
        ]
    finally:
        conn.close()


def last_run(path: Path | None = None) -> dict | None:
    conn = connect(path)
    try:
        row = conn.execute("SELECT * FROM run ORDER BY id DESC LIMIT 1").fetchone()
        if not row:
            return None
        out = dict(row)
        out["funnel"] = json.loads(out["funnel"])
        return out
    finally:
        conn.close()


def set_application(posting_id: str, state: str, noted: str = "",
                    path: Path | None = None) -> None:
    conn = connect(path)
    try:
        with conn:
            conn.execute(
                """INSERT INTO application (posting_id, state, noted, at)
                   VALUES (?,?,?,?)
                   ON CONFLICT(posting_id) DO UPDATE SET
                     state=excluded.state, noted=excluded.noted, at=excluded.at""",
                (posting_id, state, noted, _now()),
            )
    finally:
        conn.close()


def _row(row: sqlite3.Row) -> dict:
    out = dict(row)
    out["verdict"] = json.loads(out["verdict"])
    # The full description is not sent to the browser. It is up to 20 KB per
    # posting and nothing in the UI shows it; the evidence sentence is what
    # the screen needs.
    out.pop("text", None)
    return out
