"""Lever public postings API. No key, full text, and two useful structured fields.

    https://api.lever.co/v0/postings/<slug>?mode=json

Unlike Greenhouse, Lever states two of the five filters outright:

  categories.commitment   "Permanent" | "Contract" | "Full-time" | ...
  workplaceType           "remote" | "hybrid" | "onsite"

Those are recorded as *hints*, not verdicts. A posting tagged `remote` whose
body says "you must be located in Germany" is not remote in the sense this
tool cares about, and taking the structured field as final would let exactly
the postings this project exists to kill through the net.
"""

from __future__ import annotations

from datetime import UTC, datetime

from ..posting import Posting, clean
from .http import get_json

BOARD = "https://api.lever.co/v0/postings/{slug}?mode=json"
NAME = "lever"

_WORKPLACE = {"remote": True, "hybrid": False, "onsite": False, "on-site": False}


def _when(ms: int | None) -> datetime | None:
    if not ms:
        return None
    try:
        return datetime.fromtimestamp(ms / 1000, tz=UTC)
    except (ValueError, OSError, TypeError):
        return None


def fetch(slug: str, company: str | None = None, **kw) -> list[Posting]:
    payload = get_json(BOARD.format(slug=slug), **kw)
    # A wrong slug returns {"ok": false}, not a 404. Seed lists are full of
    # wrong slugs, so this must be a quiet empty rather than an exception.
    if not isinstance(payload, list):
        return []

    out = []
    for job in payload:
        cats = job.get("categories") or {}
        locations = cats.get("allLocations") or ([cats["location"]] if cats.get("location") else [])
        # `lists` holds the requirements/benefits blocks, which is often where
        # the visa and contract lines actually are.
        extra = " ".join(
            f"{block.get('text', '')} {clean(block.get('content'))}"
            for block in (job.get("lists") or [])
        )
        body = "\n".join(
            part for part in (
                job.get("descriptionPlain") or clean(job.get("description")),
                extra,
                job.get("additionalPlain") or clean(job.get("additional")),
            ) if part
        )
        out.append(
            Posting(
                source=NAME,
                company=company or slug,
                title=job.get("text", "").strip(),
                location=", ".join(locations),
                url=job.get("hostedUrl") or job.get("applyUrl", ""),
                text=body,
                posted=_when(job.get("createdAt")),
                remote_hint=_WORKPLACE.get((job.get("workplaceType") or "").lower()),
                tags=tuple(
                    t for t in (cats.get("commitment"), cats.get("department"),
                                cats.get("team")) if t
                ),
            )
        )
    return out
