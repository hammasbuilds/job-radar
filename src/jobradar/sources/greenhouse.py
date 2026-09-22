"""Greenhouse public board API. No key, full job text.

    https://boards-api.greenhouse.io/v1/boards/<slug>/jobs?content=true

`content=true` is the whole reason to prefer this over any aggregator: it
returns the complete description, which is where the sponsorship and
contract lines live. Without it you get a title and a location, and every
filter in this project has nothing to read.
"""

from __future__ import annotations

from datetime import datetime, timezone

from ..posting import Posting, clean
from .http import get_json

BOARD = "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true"
NAME = "greenhouse"


def _when(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def fetch(slug: str, company: str | None = None, **kw) -> list[Posting]:
    payload = get_json(BOARD.format(slug=slug), **kw)
    if not payload or "jobs" not in payload:
        return []

    out = []
    for job in payload["jobs"]:
        # Greenhouse double-escapes the content field.
        body = clean(job.get("content", ""))
        out.append(
            Posting(
                source=NAME,
                company=company or slug,
                title=job.get("title", "").strip(),
                location=(job.get("location") or {}).get("name", "").strip(),
                url=job.get("absolute_url", ""),
                text=body,
                posted=_when(job.get("updated_at") or job.get("first_published")),
            )
        )
    return out
