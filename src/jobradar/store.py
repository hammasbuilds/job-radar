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

-- YC companies. This section is company-first rather than posting-first: the
-- signal is "YC-backed, funded, hiring", so every open role is listed and the
-- job description is not filtered at all. A company with no readable board is
-- still kept, because "funded, hiring, reachable by email" is worth knowing.
CREATE TABLE IF NOT EXISTS yc_company (
    slug        TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    batch       TEXT,
    website     TEXT,
    yc_url      TEXT,
    linkedin    TEXT,
    linkedin_search TEXT,
    one_liner   TEXT,
    industry    TEXT,
    team_size   INTEGER,
    location    TEXT,
    tags        TEXT,
    is_ai       INTEGER NOT NULL DEFAULT 0,
    launched_at INTEGER,
    age_days    INTEGER,
    age_bucket  TEXT,
    age_label   TEXT,
    job_count   INTEGER NOT NULL DEFAULT 0,
    at          TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS yc_bucket ON yc_company(age_bucket);

CREATE TABLE IF NOT EXISTS yc_job (
    id         TEXT PRIMARY KEY,
    slug       TEXT NOT NULL,
    title      TEXT NOT NULL,
    location   TEXT,
    url        TEXT NOT NULL,
    posted     TEXT,
    role_match TEXT,
    at         TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS yc_job_slug ON yc_job(slug);

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


# One employer must not fill the screen. Anthropic repeats "we do sponsor
# visas" in every posting, which is true and which put 161 of 170 sponsorship
# rows under one name — a correct filter producing a useless list. The note is
# specific that this is ten to thirty rows, never three hundred, so the view
# shows the best few per company and says how many were folded away.
PER_COMPANY = 3


def section(name: str, limit: int = 100, per_company: int = PER_COMPANY,
            path: Path | None = None) -> list[dict]:
    """Best rows in a section, at most `per_company` from any one employer.

    Nothing is deleted: the folded rows stay in the table and the count of
    them rides along on the first row from that company, so the screen can
    say "and 158 more at Anthropic" rather than silently hiding them.
    """
    conn = connect(path)
    try:
        rows = conn.execute(
            """
            WITH ranked AS (
                SELECT p.*, a.state AS applied,
                       ROW_NUMBER() OVER (
                           PARTITION BY p.company ORDER BY p.score DESC, p.first_seen DESC
                       ) AS rank_in_company,
                       COUNT(*) OVER (PARTITION BY p.company) AS at_company
                FROM posting p LEFT JOIN application a ON a.posting_id = p.id
                WHERE ',' || p.section || ',' LIKE '%,' || ? || ',%'
            )
            SELECT * FROM ranked
            WHERE rank_in_company <= ?
            ORDER BY score DESC, first_seen DESC
            LIMIT ?
            """,
            (name, per_company, limit),
        ).fetchall()
        out = []
        for row in rows:
            item = _row(row)
            item["more_at_company"] = (
                item["at_company"] - per_company
                if item["rank_in_company"] == 1 and item["at_company"] > per_company
                else 0
            )
            out.append(item)
        return out
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
            WITH ranked AS (
                SELECT p.*, a.state AS applied,
                       ROW_NUMBER() OVER (
                           PARTITION BY p.company ORDER BY p.score DESC
                       ) AS rank_in_company,
                       COUNT(*) OVER (PARTITION BY p.company) AS at_company
                FROM posting p LEFT JOIN application a ON a.posting_id = p.id
                WHERE p.first_seen = ?
            )
            SELECT * FROM ranked WHERE rank_in_company <= ?
            ORDER BY score DESC LIMIT ?
            """,
            (last, PER_COMPANY, limit),
        ).fetchall()
        out = []
        for row in rows:
            item = _row(row)
            item["more_at_company"] = (
                item["at_company"] - PER_COMPANY
                if item["rank_in_company"] == 1 and item["at_company"] > PER_COMPANY
                else 0
            )
            out.append(item)
        return out
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


def pipeline(path: Path | None = None) -> list[dict]:
    """What has been applied to, newest first.

    Updated only by a human clicking. The design note is explicit that this is
    the one part that should not be automated, so nothing in the crawl ever
    writes here.
    """
    conn = connect(path)
    try:
        rows = conn.execute(
            """
            SELECT p.*, a.state AS applied, a.noted, a.at AS applied_at
            FROM application a JOIN posting p ON p.id = a.posting_id
            ORDER BY a.at DESC
            """
        ).fetchall()
        return [_row(r) for r in rows]
    finally:
        conn.close()


def save_yc(companies: list, path: Path | None = None) -> int:
    """Replace the YC directory. Returns how many companies were written."""
    conn = connect(path)
    now = _now()
    try:
        with conn:
            conn.execute("DELETE FROM yc_company")
            conn.execute("DELETE FROM yc_job")
            for c in companies:
                conn.execute(
                    """INSERT OR REPLACE INTO yc_company
                       (slug,name,batch,website,yc_url,linkedin,linkedin_search,
                        one_liner,industry,team_size,location,tags,is_ai,
                        launched_at,age_days,age_bucket,age_label,job_count,at)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (c.slug, c.name, c.batch, c.website, c.yc_url,
                     c.linkedin_guess, c.linkedin_search, c.one_liner,
                     c.industry, c.team_size, c.location, json.dumps(list(c.tags)),
                     int(c.is_ai), c.launched_at, c.age_days, c.age_bucket,
                     c.age_label, len(c.jobs), now),
                )
                for job in c.jobs:
                    from .filters.fit import role_match

                    conn.execute(
                        """INSERT OR REPLACE INTO yc_job
                           (id,slug,title,location,url,posted,role_match,at)
                           VALUES (?,?,?,?,?,?,?,?)""",
                        (job.key, c.slug, job.title, job.location, job.url,
                         job.posted.isoformat() if job.posted else None,
                         role_match(job.title) or "", now),
                    )
    finally:
        conn.close()
    return len(companies)


def yc_companies(bucket: str | None = None, ai_only: bool = False,
                 hiring_only: bool = False, limit: int = 400,
                 path: Path | None = None) -> list[dict]:
    """YC companies with their jobs attached.

    `bucket` selects a new-startup section ("0-3m", "3-6m", "6-12m"); omitted,
    it returns everything, newest first.
    """
    conn = connect(path)
    try:
        where, args = [], []
        if bucket:
            where.append("age_bucket = ?")
            args.append(bucket)
        if ai_only:
            where.append("is_ai = 1")
        if hiring_only:
            where.append("job_count > 0")
        clause = ("WHERE " + " AND ".join(where)) if where else ""
        rows = conn.execute(
            f"""SELECT * FROM yc_company {clause}
                ORDER BY (age_days IS NULL), age_days ASC, job_count DESC
                LIMIT ?""",
            (*args, limit),
        ).fetchall()

        out = []
        for row in rows:
            item = dict(row)
            item["tags"] = json.loads(item["tags"] or "[]")
            item["jobs"] = [
                dict(j) for j in conn.execute(
                    """SELECT title, location, url, posted, role_match
                       FROM yc_job WHERE slug = ?
                       ORDER BY (role_match = '') ASC, posted DESC""",
                    (item["slug"],),
                ).fetchall()
            ]
            out.append(item)
        return out
    finally:
        conn.close()


def yc_counts(path: Path | None = None) -> dict:
    conn = connect(path)
    try:
        row = conn.execute(
            """SELECT COUNT(*) AS companies,
                      SUM(job_count) AS jobs,
                      SUM(is_ai) AS ai,
                      SUM(job_count > 0) AS with_board
               FROM yc_company"""
        ).fetchone()
        buckets = {
            r["age_bucket"]: r["n"] for r in conn.execute(
                """SELECT age_bucket, COUNT(*) AS n FROM yc_company
                   WHERE age_bucket != '' GROUP BY age_bucket"""
            ).fetchall()
        }
        out = dict(row)
        out["buckets"] = buckets
        return out
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
