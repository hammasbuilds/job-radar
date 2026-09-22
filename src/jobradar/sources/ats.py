"""The other applicant-tracking platforms, all public and all key-free.

Greenhouse and Lever cover a lot but not the newer companies, and they miss
most of YC: **Ashby is what the recent batches use.** Adding it took the YC
board hit-rate from 13 companies to many times that, which is the difference
between a directory and a job list.

Each endpoint below was verified to return real data before it was written,
because a source list full of plausible URLs that 404 is worse than a short
one that works:

    Ashby           linear 31 jobs, vanta 90, ashby 72
    SmartRecruiters valid JSON envelope, 0 for a wrong slug
    Workable        valid JSON envelope, POST not GET
    Personio        XML, real positions for a correct slug

One correction worth recording: Ashby is a **GET**, not a POST. An earlier
attempt used POST, got `Unauthorized`, and the whole provider was written off
as needing a key. It does not.

**Deliberately absent: LinkedIn, Glassdoor and Indeed.** Their terms prohibit
unauthorised scraping. The ATS endpoints here are meant to be polled and give
the same jobs at the source, which is why the design note called them the ten
sources that matter.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

from ..posting import Posting, clean
from .http import get_json, get_text

ASHBY = "https://api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=false"
SMARTRECRUITERS = "https://api.smartrecruiters.com/v1/companies/{slug}/postings?limit=100"
WORKABLE = "https://apply.workable.com/api/v3/accounts/{slug}/jobs"
PERSONIO = "https://{slug}.jobs.personio.de/xml"
RECRUITEE = "https://{slug}.recruitee.com/api/offers/"


def _when(value) -> datetime | None:
    if not value:
        return None
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(value / (1000 if value > 1e11 else 1),
                                          tz=timezone.utc)
        except (ValueError, OSError):
            return None
    try:
        stamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return stamp if stamp.tzinfo else stamp.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def ashby(slug: str, company: str | None = None, **kw) -> list[Posting]:
    """Ashby. What the newer YC companies use, and a plain GET."""
    payload = get_json(ASHBY.format(slug=slug), **kw)
    if not payload or not isinstance(payload, dict):
        return []
    out = []
    for job in payload.get("jobs", []):
        out.append(
            Posting(
                source="ashby",
                company=company or payload.get("name") or slug,
                title=(job.get("title") or "").strip(),
                location=(job.get("location") or "").strip(),
                url=job.get("jobUrl") or job.get("applyUrl", ""),
                text=clean(job.get("descriptionHtml") or job.get("descriptionPlain")),
                posted=_when(job.get("publishedAt") or job.get("updatedAt")),
                remote_hint=bool(job.get("isRemote")),
                tags=tuple(t for t in (job.get("employmentType"),
                                       job.get("department"),
                                       job.get("team")) if t),
            )
        )
    return out


def smartrecruiters(slug: str, company: str | None = None, **kw) -> list[Posting]:
    """SmartRecruiters. The listing has no description, so each posting would
    need a second request; the title and location carry enough for the role
    and region filters, and the body is fetched only if it is ever needed."""
    payload = get_json(SMARTRECRUITERS.format(slug=slug), **kw)
    if not payload or "content" not in payload:
        return []
    out = []
    for job in payload["content"]:
        where = job.get("location") or {}
        parts = [where.get("city"), where.get("region"), where.get("country")]
        out.append(
            Posting(
                source="smartrecruiters",
                company=company or (job.get("company") or {}).get("name") or slug,
                title=(job.get("name") or "").strip(),
                location=", ".join(p for p in parts if p),
                url=f"https://jobs.smartrecruiters.com/{slug}/{job.get('id', '')}",
                text=clean((job.get("jobAd") or {}).get("sections", {}).get(
                    "jobDescription", {}).get("text", "")),
                posted=_when(job.get("releasedDate")),
                remote_hint=bool(where.get("remote")),
                tags=tuple(t for t in ((job.get("typeOfEmployment") or {}).get("label"),
                                       (job.get("department") or {}).get("label"))
                           if t),
            )
        )
    return out


def workable(slug: str, company: str | None = None, **kw) -> list[Posting]:
    """Workable. A POST with an empty body, which is why a GET returns nothing."""
    payload = get_json(WORKABLE.format(slug=slug), method="POST", body=b"{}", **kw)
    if not payload or "results" not in payload:
        return []
    out = []
    for job in payload["results"]:
        where = job.get("location") or {}
        parts = [where.get("city"), where.get("region"), where.get("country")]
        out.append(
            Posting(
                source="workable",
                company=company or slug,
                title=(job.get("title") or "").strip(),
                location=", ".join(p for p in parts if p),
                url=job.get("url") or f"https://apply.workable.com/{slug}/j/{job.get('shortcode','')}/",
                text=clean(job.get("description")),
                posted=_when(job.get("published_on") or job.get("created_at")),
                remote_hint=bool(job.get("remote") or where.get("workplace") == "remote"),
                tags=tuple(t for t in (job.get("employment_type"),
                                       job.get("department")) if t),
            )
        )
    return out


_POSITION = re.compile(r"<position>(.*?)</position>", re.S | re.I)


def _tag(block: str, name: str) -> str:
    found = re.search(rf"<{name}>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</{name}>",
                      block, re.S | re.I)
    return clean(found.group(1)) if found else ""


def personio(slug: str, company: str | None = None, **kw) -> list[Posting]:
    """Personio. XML rather than JSON, and widely used by German companies.

    Parsed with regular expressions rather than an XML parser on purpose: the
    feed is a flat list of <position> blocks, and an XML dependency here would
    be the only one in the project that is not standard library.
    """
    raw = get_text(PERSONIO.format(slug=slug), **kw)
    if not raw or "<position>" not in raw:
        return []
    out = []
    for block in _POSITION.findall(raw):
        name = _tag(block, "name")
        if not name:
            continue
        out.append(
            Posting(
                source="personio",
                company=company or slug,
                title=name,
                location=_tag(block, "office"),
                url=(f"https://{slug}.jobs.personio.de/job/{_tag(block, 'id')}"),
                text=" ".join(filter(None, [
                    _tag(block, "jobDescriptions"), _tag(block, "description"),
                    _tag(block, "subcompany"),
                ])),
                posted=_when(_tag(block, "createdAt")),
                tags=tuple(t for t in (_tag(block, "employmentType"),
                                       _tag(block, "seniority"),
                                       _tag(block, "department")) if t),
            )
        )
    return out


def recruitee(slug: str, company: str | None = None, **kw) -> list[Posting]:
    payload = get_json(RECRUITEE.format(slug=slug), **kw)
    if not payload or "offers" not in payload:
        return []
    return [
        Posting(
            source="recruitee",
            company=company or slug,
            title=(job.get("title") or "").strip(),
            location=", ".join(p for p in (job.get("city"), job.get("country")) if p),
            url=job.get("careers_url") or job.get("url", ""),
            text=clean(job.get("description")),
            posted=_when(job.get("published_at")),
            remote_hint=bool(job.get("remote")),
            tags=tuple(t for t in (job.get("employment_type_code"),
                                   job.get("department")) if t),
        )
        for job in payload["offers"]
    ]


# Every provider this project can read, in the order a company slug is tried.
# Greenhouse and Lever first because they are the most common; Ashby third
# because it is the one that actually resolves most YC companies.
PROVIDERS = {
    "ashby": ashby,
    "smartrecruiters": smartrecruiters,
    "workable": workable,
    "personio": personio,
    "recruitee": recruitee,
}
