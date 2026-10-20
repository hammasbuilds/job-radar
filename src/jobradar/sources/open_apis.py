"""Three open job APIs that search across employers, probed 2026-10-20.

  workable_search   jobs.workable.com/api/v1/jobs - every company hiring on Workable,
                    worldwide, searched by title. Its robots.txt disallows only the
                    /search pages, not the API. 660 computer-vision roles on one query.
  mycareersfuture   Singapore's government job portal API (api.mycareersfuture.gov.sg),
                    no key, no robots rules. States minimum years and position level as
                    data, which the junior filter uses directly.
  jobtech           Sweden's public employment service (jobsearch.api.jobtechdev.se),
                    no key, no robots rules.

Each is queried with the six title families rather than one broad word, because a search for
"AI" returns sales roles by the hundred and the title filter would kill them after paying for
the requests. The queries are a net; the title filter in fit.py is still the judge.

Tried and not wired: the German Bundesagentur jobsuche API answers 403 to every request,
robots.txt included, so it stays out.
"""

from __future__ import annotations

import urllib.parse
from datetime import UTC, datetime

from ..posting import Posting, clean
from .http import SourceError, get_json

QUERIES = (
    "machine learning engineer", "ml engineer", "deep learning", "computer vision",
    "generative ai", "llm engineer", "agentic ai", "ai agent engineer",
    "machine learning researcher", "research scientist machine learning",
)

WORKABLE = "https://jobs.workable.com/api/v1/jobs?query={q}"
MCF = "https://api.mycareersfuture.gov.sg/v2/jobs?search={q}&limit=100&page={page}"
# 50 a page: at 100 a page is over a megabyte, and on a throttled line it arrived cut off on
# every retry. Smaller pages finish; a page that still fails costs that page, not the source.
JOBTECH = "https://jobsearch.api.jobtechdev.se/search?q={q}&limit=50&offset={offset}"


def _iso(value) -> datetime | None:
    if not value:
        return None
    try:
        stamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return stamp if stamp.tzinfo else stamp.replace(tzinfo=UTC)
    except ValueError:
        return None


def _q(text: str) -> str:
    return urllib.parse.quote(text)


def workable_search(pages: int = 6, queries=QUERIES, _base: str = "", **kw) -> list[Posting]:
    seen: set[str] = set()
    out: list[Posting] = []
    for query in queries:
        first = _base or WORKABLE.format(q=_q(query))
        url = first
        for _ in range(pages):
            payload = get_json(url, **kw)
            if not payload or not payload.get("jobs"):
                break
            for job in payload["jobs"]:
                jid = str(job.get("id", ""))
                if not jid or jid in seen:
                    continue
                seen.add(jid)
                where = job.get("location") or {}
                places = job.get("locations") or []
                location = "; ".join(places) if places else ", ".join(
                    x for x in (where.get("city"), where.get("countryName")) if x)
                workplace = str(job.get("workplace") or "")
                out.append(Posting(
                    source="workable-search",
                    company=((job.get("company") or {}).get("title") or "").strip(),
                    title=(job.get("title") or "").strip(),
                    location=location + (" (remote)" if workplace == "remote" else ""),
                    url=job.get("url", ""),
                    text=clean(" ".join(filter(None, (job.get("description"),
                                                      job.get("requirementsSection"),
                                                      job.get("benefitsSection"))))),
                    posted=_iso(job.get("created")),
                    remote_hint=workplace == "remote",
                    tags=tuple(filter(None, (job.get("employmentType"), workplace))),
                ))
            token = payload.get("nextPageToken")
            if not token:
                break
            url = first + f"&pageToken={_q(str(token))}"
    return out


# The countries a worldwide query under-serves. Asked "machine learning" globally, Workable's
# first pages are mostly American; asked per country it returned Saudi Arabia 43, Pakistan 34,
# UAE 21, Malaysia 16, Japan 16, Hong Kong 9 and China 6 (2026-10-20).
THIN_COUNTRIES = (
    "United Arab Emirates", "Saudi Arabia", "Qatar", "Kuwait", "Bahrain", "Oman", "Pakistan",
    "Malaysia", "China", "Hong Kong", "Taiwan", "Japan", "South Korea", "Indonesia", "Vietnam",
    "Thailand", "Philippines", "Turkey",
)
COUNTRY_QUERIES = ("machine learning", "artificial intelligence", "data scientist")


def workable_by_country(pages: int = 3, countries=THIN_COUNTRIES, queries=COUNTRY_QUERIES,
                        **kw) -> list[Posting]:
    """Workable search asked per country, for the places a worldwide query buries."""
    out: list[Posting] = []
    seen: set[str] = set()
    for country in countries:
        for query in queries:
            base = WORKABLE.format(q=_q(query)) + f"&location={_q(country)}"
            for posting in workable_search(pages=pages, queries=(query,), _base=base, **kw):
                if posting.url not in seen:
                    seen.add(posting.url)
                    out.append(posting)
    return out


def mycareersfuture(pages: int = 3, queries=QUERIES, **kw) -> list[Posting]:
    seen: set[str] = set()
    out: list[Posting] = []
    for query in queries:
        for page in range(pages):
            payload = get_json(MCF.format(q=_q(query), page=page), **kw)
            results = (payload or {}).get("results") or []
            for job in results:
                uid = str(job.get("uuid", ""))
                if not uid or uid in seen:
                    continue
                seen.add(uid)
                meta = job.get("metadata") or {}
                years = job.get("minimumYearsExperience")
                levels = [lv.get("position", "") for lv in job.get("positionLevels") or []]
                kinds = [k.get("employmentType", "") for k in job.get("employmentTypes") or []]
                # The structured minimum becomes a sentence the years filter already reads,
                # so one rule decides juniority whatever the source.
                stated = (f"\nRequires at least {years} years of experience."
                          if isinstance(years, int) and years > 0 else "")
                company = (job.get("hiringCompany") or job.get("postedCompany") or {})
                out.append(Posting(
                    source="mycareersfuture",
                    company=(company.get("name") or "").strip().title(),
                    title=(job.get("title") or "").strip(),
                    location="Singapore",
                    url=meta.get("jobDetailsUrl", ""),
                    text=clean(job.get("description")) + stated,
                    posted=_iso(meta.get("newPostingDate")),
                    remote_hint=False,
                    tags=tuple(filter(None, [*levels, *kinds])),
                ))
            if len(results) < 100:
                break
    return out


def jobtech(pages: int = 4, queries=QUERIES, **kw) -> list[Posting]:
    seen: set[str] = set()
    out: list[Posting] = []
    for query in queries:
        for page in range(pages):
            try:
                payload = get_json(JOBTECH.format(q=_q(query), offset=page * 50), **kw)
            except SourceError:
                break
            hits = (payload or {}).get("hits") or []
            for job in hits:
                jid = str(job.get("id", ""))
                if not jid or jid in seen:
                    continue
                seen.add(jid)
                addr = job.get("workplace_address") or {}
                town = addr.get("municipality") or addr.get("city") or ""
                hours = (job.get("working_hours_type") or {}).get("label", "")
                kind = (job.get("employment_type") or {}).get("label", "")
                out.append(Posting(
                    source="jobtech",
                    company=((job.get("employer") or {}).get("name") or "").strip(),
                    title=(job.get("headline") or "").strip(),
                    location=", ".join(x for x in (town.title() if town.isupper() else town,
                                                   "Sweden") if x),
                    url=job.get("webpage_url", ""),
                    text=clean((job.get("description") or {}).get("text")),
                    posted=_iso(job.get("publication_date")),
                    remote_hint=False,
                    tags=tuple(filter(None, (hours, kind))),
                ))
            if len(hits) < 50:
                break
    return out
