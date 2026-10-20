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
import shutil
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from . import config
from .filters.fit import role_match
from .posting import key_for

# Application states a human can set. Anything else is refused, so a stray
# request cannot write arbitrary text into the pipeline.
STATES = ("applied", "replied", "rejected", "closed")

# Bumped whenever stored ids or columns change meaning; see `_migrate`.
SCHEMA_VERSION = 1

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
-- The by-country lens: every posting that is the right role at the right level, with its
-- route as a value to filter on rather than a reason it was hidden. Rebuilt by every run.
CREATE TABLE IF NOT EXISTS lens (
    id         TEXT PRIMARY KEY,
    source     TEXT NOT NULL,
    company    TEXT NOT NULL,
    title      TEXT NOT NULL,
    location   TEXT,
    url        TEXT NOT NULL,
    posted     TEXT,
    family     TEXT NOT NULL,
    track      TEXT NOT NULL,
    countries  TEXT NOT NULL,          -- JSON list of display names
    regions    TEXT NOT NULL,          -- JSON list
    workplace  TEXT NOT NULL,
    terms      TEXT NOT NULL,
    years      INTEGER,
    level      TEXT,
    route      TEXT NOT NULL,          -- sections it reached, or why it reached none
    auth       TEXT,
    score      REAL NOT NULL,
    excerpt    TEXT,
    at         TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS lens_family ON lens(family);

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

-- Every YC company of the last three years of batches, hiring or not. Kept apart from
-- yc_company (the hiring directory with its boards) because the question differs: "who went
-- through YC recently and how do I reach them", not "who is advertising".
CREATE TABLE IF NOT EXISTS yc_recent (
    slug            TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    batch           TEXT,
    batch_year      INTEGER,
    website         TEXT,
    yc_url          TEXT,
    jobs_url        TEXT,
    hiring          INTEGER NOT NULL DEFAULT 0,
    status          TEXT,
    one_liner       TEXT,
    industry        TEXT,
    location        TEXT,
    team_size       INTEGER,
    tags            TEXT,
    is_ai           INTEGER NOT NULL DEFAULT 0,
    linkedin        TEXT,
    linkedin_source TEXT,
    at              TEXT NOT NULL
);

-- Programmes, platforms, accelerators and grants: the directory written by every crawl,
-- with the live posting count each one has in the lens right now.
CREATE TABLE IF NOT EXISTS directory (
    kind       TEXT NOT NULL,
    name       TEXT NOT NULL,
    url        TEXT NOT NULL,
    jobs_url   TEXT,
    region     TEXT,
    what       TEXT,
    pay        TEXT,
    pay_source TEXT,
    who        TEXT,
    match      TEXT,
    live       INTEGER NOT NULL DEFAULT 0,
    at         TEXT NOT NULL,
    PRIMARY KEY (kind, name)
);

-- Accelerator and investor portfolios, from their job-board sitemaps.
CREATE TABLE IF NOT EXISTS portfolio_company (
    programme  TEXT NOT NULL,
    slug       TEXT NOT NULL,
    name       TEXT NOT NULL,
    url        TEXT NOT NULL,
    roles      INTEGER NOT NULL DEFAULT 0,
    ai_roles   INTEGER NOT NULL DEFAULT 0,
    junior_ai  INTEGER NOT NULL DEFAULT 0,
    at         TEXT NOT NULL,
    PRIMARY KEY (programme, slug)
);
CREATE TABLE IF NOT EXISTS portfolio_job (
    programme  TEXT NOT NULL,
    company    TEXT NOT NULL,
    title      TEXT NOT NULL,
    url        TEXT NOT NULL,
    ai         INTEGER NOT NULL DEFAULT 0,
    junior     INTEGER NOT NULL DEFAULT 0,
    family     TEXT,
    track      TEXT,
    level      TEXT,
    at         TEXT NOT NULL,
    PRIMARY KEY (programme, url)
);
CREATE TABLE IF NOT EXISTS portfolio_programme (
    name       TEXT PRIMARY KEY,
    kind       TEXT NOT NULL,
    board      TEXT NOT NULL,
    companies  INTEGER NOT NULL,
    roles      INTEGER NOT NULL,
    ai_roles   INTEGER NOT NULL,
    junior_ai  INTEGER NOT NULL,
    failed     TEXT NOT NULL DEFAULT '',
    at         TEXT NOT NULL
);

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


def db_path(path: Path | None = None) -> Path:
    """The database in use: an explicit path, else `$JOBRADAR_DB`, else data/."""
    return path or config.db_path()


def connect(path: Path | None = None) -> sqlite3.Connection:
    target = db_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    existed = target.exists() and target.stat().st_size > 0
    conn = sqlite3.connect(target)
    conn.row_factory = sqlite3.Row
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    conn.executescript(SCHEMA)
    if existed and version < SCHEMA_VERSION:
        _migrate(conn, target, version)
    conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
    return conn


def _migrate(conn: sqlite3.Connection, target: Path, version: int) -> None:
    """Bring an older database up to `SCHEMA_VERSION`, after backing it up.

    **v0 -> v1: posting ids.** v0 hashed the URL with its query string cut
    off, so every posting whose job id lived in the query (Databricks and
    Stripe `?gh_jid=`, Hacker News `item?id=`) shared one id per employer.
    Each stored row is re-keyed from the URL it kept, and applications follow
    their posting. Rows that v0 had already merged cannot be split again —
    the other postings' URLs were never stored — so the verdicts on those
    rows are cleared and the next run writes them afresh. The Killed table is
    rebuilt by every run and is simply emptied.

    The database is personal and cannot be regenerated (applications are
    typed by hand), so a copy is taken first and never removed.
    """
    if version >= 1:
        return
    backup = target.with_name(f"{target.name}.pre-v1.bak")
    if not backup.exists():
        conn.commit()
        shutil.copy2(target, backup)
    with conn:
        rows = conn.execute("SELECT id, url, source, company, title, location "
                            "FROM posting").fetchall()
        for row in rows:
            new = key_for(row["url"], f"{row['source']}|{row['company']}|"
                                      f"{row['title']}|{row['location']}")
            if new == row["id"]:
                continue
            clash = conn.execute("SELECT 1 FROM posting WHERE id = ?", (new,)).fetchone()
            if clash:
                continue
            conn.execute("UPDATE posting SET id = ? WHERE id = ?", (new, row["id"]))
            conn.execute("UPDATE application SET posting_id = ? WHERE posting_id = ?",
                         (new, row["id"]))
        # Every row may carry a verdict grafted from another posting, and
        # none is known to be current: clear the sections until a run says.
        conn.execute("UPDATE posting SET section = ''")
        conn.execute("DELETE FROM killed")


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def save(postings: list, funnel, path: Path | None = None) -> int:
    """Record one run. Returns how many kept postings were never seen before.

    The run is the whole truth about what is on screen. Every posting's
    section is cleared first and only this run's survivors get theirs back,
    so a posting kept yesterday and killed today — or one that has simply
    disappeared from its board — leaves every tab instead of lingering in
    both the Remote tab and the Killed tab at once. Rows are never deleted:
    the Pipeline tab still reaches a posting you applied to after it closes.
    """
    conn = connect(path)
    now = _now()
    new = 0
    try:
        with conn:
            conn.execute("UPDATE posting SET section = ''")
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
                        source=excluded.source, company=excluded.company,
                        title=excluded.title, location=excluded.location,
                        url=excluded.url, posted=excluded.posted, text=excluded.text,
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
            conn.execute("DELETE FROM lens")
            for posting in getattr(funnel, "lens", []):
                v = posting.verdict
                conn.execute(
                    """INSERT OR REPLACE INTO lens
                       (id, source, company, title, location, url, posted, family, track,
                        countries, regions, workplace, terms, years, level, route, auth,
                        score, excerpt, at)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (posting.key, posting.source, posting.company, posting.title,
                     posting.location, posting.url,
                     posting.posted.isoformat() if posting.posted else None,
                     v.get("family", ""), v.get("track", ""),
                     json.dumps(v.get("lens_countries", v.get("countries", []))),
                     json.dumps([r for r in v.get("regions", []) if r not in ("other", "excluded")]),
                     v.get("workplace", ""), v.get("terms", ""), v.get("years"),
                     v.get("level", ""), v.get("route", ""), v.get("auth", ""),
                     posting.score, (posting.text or "")[:600], now),
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
                             "after_dedup": funnel.after_dedup,
                             # Rendered once, in pipeline order, so the
                             # dashboard shows the same funnel as the console.
                             "lines": funnel.as_lines()})),
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


def section_total(name: str, path: Path | None = None) -> int:
    """How many postings a section holds before the per-company cap."""
    conn = connect(path)
    try:
        return conn.execute(
            "SELECT COUNT(*) FROM posting WHERE ',' || section || ',' LIKE '%,' || ? || ',%'",
            (name,),
        ).fetchone()[0]
    finally:
        conn.close()


def newest(limit: int = 40, path: Path | None = None) -> list[dict]:
    """The Today screen: kept postings first seen in the most recent run.

    "The most recent run", not "the newest first_seen". A run that found
    nothing new must show nothing new; reading MAX(first_seen) instead showed
    the previous run's postings again, so Today was not "new since last run".
    """
    conn = connect(path)
    try:
        last = conn.execute("SELECT MAX(at) AS t FROM run").fetchone()["t"]
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
                WHERE p.first_seen = ? AND p.section != ''
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


def posting(posting_id: str, path: Path | None = None) -> dict | None:
    """One posting, **with** its description.

    Every other reader here strips `text` — it is up to 20 KB and no list
    needs it. The gap report is the exception: comparing a job against a CV
    means reading the job, so this is the one accessor that keeps the body.
    """
    conn = connect(path)
    try:
        row = conn.execute("SELECT * FROM posting WHERE id = ?", (posting_id,)).fetchone()
        if not row:
            return None
        out = dict(row)
        out["verdict"] = json.loads(out["verdict"])
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


def yc_age_hours(path: Path | None = None) -> float | None:
    """How old the stored YC directory is, or None when there is none.

    Used by the launcher so a one-click run does not spend two minutes
    re-resolving 326 company boards that were resolved this morning.
    """
    conn = connect(path)
    try:
        row = conn.execute("SELECT MAX(at) AS at FROM yc_company").fetchone()
        if not row or not row["at"]:
            return None
        stored = datetime.fromisoformat(row["at"])
        if stored.tzinfo is None:
            stored = stored.replace(tzinfo=UTC)
        return (datetime.now(UTC) - stored).total_seconds() / 3600
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


def save_yc_recent(companies: list, path: Path | None = None) -> None:
    conn = connect(path)
    now = _now()
    try:
        with conn:
            for c in companies:
                r = c.row()
                conn.execute(
                    """INSERT OR REPLACE INTO yc_recent (slug, name, batch, batch_year, website,
                       yc_url, jobs_url, hiring, status, one_liner, industry, location,
                       team_size, tags, is_ai, linkedin, linkedin_source, at)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (r["slug"], r["name"], r["batch"], r["batch_year"], r["website"],
                     r["yc_url"], r["jobs_url"], int(r["hiring"]), r["status"], r["one_liner"],
                     r["industry"], r["location"], r["team_size"], r["tags"], int(r["is_ai"]),
                     r["linkedin"], r["linkedin_source"], now),
                )
    finally:
        conn.close()


def yc_recent_linkedin(path: Path | None = None) -> dict[str, tuple[str, str]]:
    """slug -> (linkedin, source) already read, so a re-run does not ask YC again."""
    conn = connect(path)
    try:
        rows = conn.execute("SELECT slug, linkedin, linkedin_source FROM yc_recent "
                            "WHERE linkedin_source = 'yc page'").fetchall()
        return {r["slug"]: (r["linkedin"], r["linkedin_source"]) for r in rows}
    finally:
        conn.close()


def yc_recent_age_hours(path: Path | None = None) -> float | None:
    conn = connect(path)
    try:
        row = conn.execute("SELECT MAX(at) FROM yc_recent").fetchone()
    finally:
        conn.close()
    if not row or not row[0]:
        return None
    return (datetime.now(UTC) - datetime.fromisoformat(row[0])).total_seconds() / 3600


def save_portfolio(p, jobs: list[dict], path: Path | None = None) -> None:
    """Replace one programme's companies and roles with what its sitemaps say now."""
    conn = connect(path)
    now = _now()
    per: dict[str, list[int]] = {}
    for j in jobs:
        c = per.setdefault(j["company_slug"], [0, 0, 0])
        c[0] += 1
        c[1] += int(j["ai"])
        c[2] += int(j["junior"])
    try:
        with conn:
            # A sitemap that could not be read leaves the last good copy in place rather than
            # replacing a whole portfolio with nothing.
            if not p.read:
                return
            conn.execute("DELETE FROM portfolio_company WHERE programme = ?", (p.name,))
            conn.execute("DELETE FROM portfolio_job WHERE programme = ?", (p.name,))
            from .sources.portfolios import name_from_slug

            for slug, url in p.companies.items():
                roles, ai, junior = per.get(slug, [0, 0, 0])
                conn.execute("INSERT OR REPLACE INTO portfolio_company VALUES (?,?,?,?,?,?,?,?)",
                             (p.name, slug, name_from_slug(slug), url, roles, ai, junior, now))
            for j in jobs:
                conn.execute(
                    "INSERT OR REPLACE INTO portfolio_job VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (p.name, j["company"], j["title"], j["url"], int(j["ai"]), int(j["junior"]),
                     j["family"], j["track"], j["level"], now))
            conn.execute("INSERT OR REPLACE INTO portfolio_programme VALUES (?,?,?,?,?,?,?,?,?)",
                         (p.name, p.kind, p.board, len(p.companies), len(jobs),
                          sum(j["ai"] for j in jobs), sum(j["junior"] for j in jobs),
                          "; ".join(p.failed), now))
    finally:
        conn.close()


def portfolio_age_hours(path: Path | None = None) -> float | None:
    conn = connect(path)
    try:
        row = conn.execute("SELECT MIN(at) FROM portfolio_programme").fetchone()
    finally:
        conn.close()
    if not row or not row[0]:
        return None
    return (datetime.now(UTC) - datetime.fromisoformat(row[0])).total_seconds() / 3600


def save_directory(entries: list[dict], path: Path | None = None) -> None:
    conn = connect(path)
    now = _now()
    try:
        with conn:
            conn.execute("DELETE FROM directory")
            for e in entries:
                pattern = (e.get("match") or "").lower()
                live = 0
                if pattern:
                    # For a fellowship only its programme postings count: Anthropic's other
                    # three hundred roles are not the Fellows Program.
                    only = " AND family = 'Fellowship / programme'" \
                        if e["kind"] == "Fellowship / paid programme" else ""
                    live = conn.execute(
                        "SELECT COUNT(*) FROM lens WHERE lower(company) LIKE ?" + only,
                        (f"%{pattern}%",)).fetchone()[0]
                conn.execute(
                    """INSERT OR REPLACE INTO directory (kind, name, url, jobs_url, region,
                       what, pay, pay_source, who, match, live, at)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (e["kind"], e["name"], e["url"], e.get("jobs_url", ""), e.get("region", ""),
                     e.get("what", ""), e.get("pay", ""), e.get("pay_source", ""),
                     e.get("who", ""), e.get("match", ""), live, now),
                )
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
    """Record a human's decision. Raises ValueError for an unknown state and
    KeyError for a posting that was never stored."""
    if state not in STATES:
        raise ValueError(f"state must be one of {', '.join(STATES)}")
    conn = connect(path)
    try:
        if not conn.execute("SELECT 1 FROM posting WHERE id = ?", (posting_id,)).fetchone():
            raise KeyError(posting_id)
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
