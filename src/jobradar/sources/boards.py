"""Public job-board APIs that answer without a key.

Every endpoint here was probed before it was written. Of twenty candidates
from the master list, five answer key-free with usable JSON; the rest need a
key, return HTML, or are gone. They are recorded in `registry.py` with the
reason rather than left as names in a list, because a source list full of
plausible URLs that 404 is worse than a short one that works.

  himalayas    `locationRestrictions` — the geo restriction as data
  jobicy       `jobGeo`, `jobLevel` — supports a geo query parameter
  remoteok     one flat array, `position`/`company`/`location`
  themuse      20,639 pages, so it MUST be category-filtered or it returns
               nursing and retail jobs forever
  hn           the monthly "Ask HN: Who is hiring" thread via Algolia

**Not here, deliberately: LinkedIn, Glassdoor, Indeed.** Their terms prohibit
unauthorised scraping, and getting blocked costs the profile this tool exists
to build a career on. The ATS endpoints in `ats.py` carry the same jobs at
the source.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

from ..posting import Posting, clean
from .http import get_json

HIMALAYAS = "https://himalayas.app/jobs/api?limit={limit}"
JOBICY = "https://jobicy.com/api/v2/remote-jobs?count={limit}"
REMOTEOK = "https://remoteok.com/api"
MUSE = ("https://www.themuse.com/api/public/jobs?page={page}"
        "&category=Data%20and%20Analytics&category=Engineering"
        "&category=Science%20and%20Engineering")
# Filtered by author, not by query text. Searching the words "Ask HN Who is
# hiring" returns every thread that ever discussed one; the monthly threads
# are all posted by the `whoishiring` account, which identifies them exactly.
# `search_by_date` matters too — plain `search` ranks by relevance and handed
# back the November 2016 thread.
HN = ("https://hn.algolia.com/api/v1/search_by_date"
      "?tags=story,author_whoishiring&hitsPerPage=6")
HN_ITEM = "https://hn.algolia.com/api/v1/items/{id}"


def _epoch(value) -> datetime | None:
    try:
        return datetime.fromtimestamp(int(value), tz=timezone.utc)
    except (TypeError, ValueError, OSError):
        return None


def _iso(value) -> datetime | None:
    if not value:
        return None
    try:
        stamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return stamp if stamp.tzinfo else stamp.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def himalayas(limit: int = 200, **kw) -> list[Posting]:
    payload = get_json(HIMALAYAS.format(limit=limit), **kw)
    if not payload or "jobs" not in payload:
        return []
    out = []
    for job in payload["jobs"]:
        where = job.get("locationRestrictions") or []
        out.append(
            Posting(
                source="himalayas",
                company=(job.get("companyName") or "").strip(),
                title=(job.get("title") or "").strip(),
                # The restriction list is the geographic answer stated as
                # data, which is the most valuable field any source gives.
                location=", ".join(where) if isinstance(where, list) else str(where),
                url=job.get("applicationLink") or job.get("guid", ""),
                text=clean(job.get("description") or job.get("excerpt")),
                posted=_epoch(job.get("pubDate")),
                remote_hint=True,
                tags=tuple(filter(None, [job.get("employmentType"), job.get("seniority")])),
            )
        )
    return out


def jobicy(limit: int = 100, geo: str | None = None, **kw) -> list[Posting]:
    url = JOBICY.format(limit=limit)
    if geo:
        url += f"&geo={geo}"
    payload = get_json(url, **kw)
    if not payload or "jobs" not in payload:
        return []
    return [
        Posting(
            source="jobicy",
            company=(job.get("companyName") or "").strip(),
            title=(job.get("jobTitle") or "").strip(),
            location=job.get("jobGeo", "") or "",
            url=job.get("url", ""),
            text=clean(job.get("jobDescription") or job.get("jobExcerpt")),
            posted=_iso(job.get("pubDate")),
            remote_hint=True,
            tags=tuple(job.get("jobType") or []) + tuple(job.get("jobLevel") or []),
        )
        for job in payload["jobs"]
    ]


def remoteok(**kw) -> list[Posting]:
    """One flat array whose first element is a legal notice, not a job."""
    payload = get_json(REMOTEOK, **kw)
    if not isinstance(payload, list):
        return []
    out = []
    for job in payload:
        if not job.get("position"):
            continue          # the legal-notice row
        out.append(
            Posting(
                source="remoteok",
                company=(job.get("company") or "").strip(),
                title=job["position"].strip(),
                location=(job.get("location") or "").strip(),
                url=job.get("url") or job.get("apply_url", ""),
                text=clean(job.get("description")),
                posted=_iso(job.get("date")),
                remote_hint=True,
                tags=tuple(job.get("tags") or []),
            )
        )
    return out


def themuse(pages: int = 3, **kw) -> list[Posting]:
    """The Muse, category-filtered.

    Unfiltered this endpoint reports 20,639 pages and the first one is
    nursing and retail. The category parameters are not an optimisation:
    without them the source contributes noise at a rate that would swamp
    everything else in the corpus.
    """
    out = []
    for page in range(1, pages + 1):
        payload = get_json(MUSE.format(page=page), **kw)
        if not payload or "results" not in payload:
            break
        for job in payload["results"]:
            places = [p.get("name", "") for p in (job.get("locations") or [])]
            out.append(
                Posting(
                    source="themuse",
                    company=(job.get("company") or {}).get("name", ""),
                    title=(job.get("name") or "").strip(),
                    location=", ".join(places),
                    url=(job.get("refs") or {}).get("landing_page", ""),
                    text=clean(job.get("contents")),
                    posted=_iso(job.get("publication_date")),
                    tags=tuple(lv.get("name", "") for lv in (job.get("levels") or [])),
                )
            )
    return out


_HN_COMPANY = re.compile(r"^\s*([^|\n]{2,60}?)\s*[|•·—-]", re.M)


def hacker_news(**kw) -> list[Posting]:
    """The monthly "Ask HN: Who is hiring" thread.

    Each top-level comment is one company's posting, conventionally written
    as `Company | Role | Location | Remote`. The convention is loose enough
    that only the first field is reliable, so the company is parsed and the
    whole comment is kept as the text for the filters to read.

    Worth having because YC founders post here and many of those roles appear
    nowhere else.
    """
    threads = get_json(HN, **kw)
    if not threads or not threads.get("hits"):
        return []

    # The account posts three threads a month — hiring, wants to be hired and
    # freelancer — so the newest story is not necessarily the hiring one.
    hiring = [h for h in threads["hits"]
              if "who is hiring" in (h.get("title") or "").lower()
              and "wants to be hired" not in (h.get("title") or "").lower()]

    out = []
    for hit in hiring[:1]:                   # the most recent month only
        item = get_json(HN_ITEM.format(id=hit["objectID"]), **kw)
        if not item:
            continue
        for comment in item.get("children") or []:
            body = clean(comment.get("text"))
            if not body or len(body) < 60:
                continue
            found = _HN_COMPANY.search(body)
            company = found.group(1).strip() if found else "(unnamed, HN thread)"
            head = body.split("\n")[0][:160]
            out.append(
                Posting(
                    source="hn",
                    company=company,
                    title=head,
                    location="",
                    url=f"https://news.ycombinator.com/item?id={comment.get('id')}",
                    text=body,
                    posted=_iso(comment.get("created_at")),
                )
            )
    return out
