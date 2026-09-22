"""Arbeitnow and Remotive. Broad, shallow, and worth exactly one thing each.

The ATS boards in this package are deep but narrow: they only return jobs at
companies already in the seed list. These two are the opposite — they carry
companies nobody thought to seed, which is how the list grows.

They are also where the duplicates come from. A job on a company's own
Greenhouse board frequently appears here too, and `dedup.py` exists because of
that. The ATS copy wins, because it has the full description and these
sometimes truncate.

**Remotive's `candidate_required_location` is the single most valuable field
any source in this project provides.** It is the geographic restriction stated
as data rather than buried in paragraph six — "USA, Canada, Argentina" says
plainly that a Pakistan-based applicant is out, and it costs nothing to read.
"""

from __future__ import annotations

from datetime import datetime, timezone

from ..posting import Posting, clean
from .http import get_json

ARBEITNOW = "https://www.arbeitnow.com/api/job-board-api"
REMOTIVE = "https://remotive.com/api/remote-jobs"


def _epoch(value) -> datetime | None:
    try:
        return datetime.fromtimestamp(int(value), tz=timezone.utc)
    except (TypeError, ValueError, OSError):
        return None


def _iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return stamp if stamp.tzinfo else stamp.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def fetch_arbeitnow(**kw) -> list[Posting]:
    """Mostly Germany and the wider EU, which is the target market."""
    payload = get_json(ARBEITNOW, **kw)
    if not payload or "data" not in payload:
        return []
    return [
        Posting(
            source="arbeitnow",
            company=(job.get("company_name") or "").strip(),
            title=(job.get("title") or "").strip(),
            location=(job.get("location") or "").strip(),
            url=job.get("url", ""),
            text=clean(job.get("description")),
            posted=_epoch(job.get("created_at")),
            remote_hint=bool(job.get("remote")),
            tags=tuple(job.get("job_types") or []) + tuple(job.get("tags") or []),
        )
        for job in payload["data"]
    ]


def fetch_remotive(limit: int = 500, **kw) -> list[Posting]:
    payload = get_json(f"{REMOTIVE}?limit={limit}", **kw)
    if not payload or "jobs" not in payload:
        return []
    out = []
    for job in payload["jobs"]:
        # The restriction is data here, so it goes into `location` where the
        # remote-scope filter reads it, rather than being lost.
        where = (job.get("candidate_required_location") or "").strip()
        out.append(
            Posting(
                source="remotive",
                company=(job.get("company_name") or "").strip(),
                title=(job.get("title") or "").strip(),
                location=where,
                url=job.get("url", ""),
                text=clean(job.get("description")),
                posted=_iso(job.get("publication_date")),
                remote_hint=True,          # the whole board is remote
                tags=tuple(job.get("tags") or []) + ((job.get("job_type"),) if job.get("job_type") else ()),
            )
        )
    return out
