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
import urllib.parse
from datetime import UTC, datetime

from ..posting import Posting, clean
from .http import get_json

# The API caps `limit` at 20 whatever is asked for, so more than twenty jobs
# means following `nextCursor`. Asking for limit=200 in one call returned 20.
HIMALAYAS = "https://himalayas.app/jobs/api?limit=20"
HIMALAYAS_PAGE = 20
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
        return datetime.fromtimestamp(int(value), tz=UTC)
    except (TypeError, ValueError, OSError):
        return None


def _iso(value) -> datetime | None:
    if not value:
        return None
    try:
        stamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return stamp if stamp.tzinfo else stamp.replace(tzinfo=UTC)
    except ValueError:
        return None


def himalayas(limit: int = 200, **kw) -> list[Posting]:
    jobs: list[dict] = []
    url = HIMALAYAS
    while len(jobs) < limit:
        payload = get_json(url, **kw)
        if not payload or not payload.get("jobs"):
            break
        jobs += payload["jobs"]
        cursor = payload.get("nextCursor")
        if not cursor:
            break
        url = f"{HIMALAYAS}&cursor={urllib.parse.quote(str(cursor), safe='')}"
    out = []
    for job in jobs[:limit]:
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

# A word that makes a phrase a job title. Deliberately wider than the target
# roles: every role in a post must become its own posting so the ones that
# are not wanted are killed *as themselves*, not mixed into the one that is.
_ROLE_WORD = re.compile(
    r"\b(?:engineers?|scientists?|researchers?|developers?|designers?|managers?|"
    r"architects?|analysts?|leads?|directors?|head of|interns?|recruiters?|"
    r"specialists?|sre|devops|mlops|cto|vp|consultants?|writers?|technicians?|"
    r"operators?|founding|fellows?|associates?|administrators?|representatives?|"
    r"executives?|advocates?|strategists?|coordinators?|programmers?|swes?)\b",
    re.I,
)
_PROSE = re.compile(
    r"\b(?:we|we're|we've|our|you|you'll|your|i'm|i've|my|me|looking|"
    r"hiring|join|build|help|is|are|was|will)\b", re.I)
_URL = re.compile(r"https?://\S+|\b[\w-]+\.(?:com|io|ai|co|org|dev|app|net)\b\S*", re.I)
_BULLET = re.compile(r"^\s*(?:[-*•·◦▪>]|\d{1,2}[.)])\s*")
_MONEY = re.compile(r"[$€£]|\b\d+\s*k\b|\bequity\b|\bsalary\b", re.I)
# "Full-time", "Contract / Part-time (10-40 hrs/wk)": the employment field of
# the header, which sits beside the location and is not one.
_EMPLOYMENT_FIELD = re.compile(
    r"^\W*(?:(?:full|part)[- ]?time|contract\w*|freelanc\w*|intern\w*|permanent|"
    r"temporary|temp\b)", re.I)
MAX_ROLES = 12


_SEPARATOR = re.compile(r"\s*(?:,|;|&|\+|\band\b|\bor\b)\s*", re.I)


def _split_outside_parens(field: str) -> list[tuple[str, str]]:
    """Split on separators that sit outside parentheses. Returns (part, the
    separator that followed it), so a part can be glued back as written."""
    parts: list[tuple[str, str]] = []
    depth, start, i = 0, 0, 0
    while i < len(field):
        ch = field[i]
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
        elif depth == 0:
            sep = _SEPARATOR.match(field, i)
            if sep and sep.end() > i and (field[i] in ",;&+" or field[i].isspace()):
                parts.append((field[start:i], sep.group(0)))
                start = i = sep.end()
                continue
        i += 1
    parts.append((field[start:], ""))
    return parts


def _role_parts(field: str) -> list[str]:
    """One header field to its roles.

    "ML Engineer, Backend Engineer" is two; "Research Engineer, Pre-training"
    is one, because the part after the comma names no role and is glued back
    onto the one before it; "Backend & Cloud Platform Engineer" is one, because
    a leading part with no role word is glued onto the next. Separators inside
    parentheses never split: "Software Engineer (Autonomy, Perception)".
    """
    roles: list[str] = []
    prefix = ""
    for part, sep in _split_outside_parens(field):
        part = part.strip(" -–—:")
        if not part:
            continue
        if _ROLE_WORD.search(part):
            roles.append(prefix + part)
            prefix = ""
        elif roles and not prefix:
            roles[-1] = f"{roles[-1]}, {part}"
        else:
            prefix += part + (sep if sep.strip() else " ")
    return roles


def hn_roles(body: str) -> tuple[str, list[str], str]:
    """(company, role titles, location) from one "Who is hiring" comment.

    The convention is `Company | Role | Location | Remote | VISA`, loosely
    kept: several roles in one field, roles listed as bullets further down,
    or no header at all. The first version took the first 160 characters as
    the title, so the level and role filters read *other* roles and prose -
    Sourcegraph's "Agent Engineer" was killed as "lead" because "Tech Lead"
    was also listed, and Whistle Robotics as "executive" from "I'm Gio, CTO".
    """
    lines = [ln.strip() for ln in body.split("\n") if ln.strip()]
    header = lines[0] if lines else ""
    fields = [f.strip() for f in header.split("|")] if "|" in header else [header]

    found = _HN_COMPANY.search(body)
    if len(fields) > 1:
        company = fields[0]
    elif found and not _PROSE.search(found.group(1)):
        company = found.group(1)
    else:
        company = ""
    company = _URL.sub("", company.strip()).strip(" -–—,:")
    # A first field that is a role is not the company: "DevOps Engineer (QVAC):" is QVAC's
    # role list, and "Founding Engineer (Security / AI ...) — Stealth" names no company.
    if _ROLE_WORD.search(company) or len(company) > 60:
        inner = re.search(r"\(([A-Z][A-Za-z0-9&.\- ]{1,30})\)", company)
        company = inner.group(1) if inner and not _ROLE_WORD.search(inner.group(1)) else ""
    company = company or "(unnamed, HN thread)"

    roles: list[str] = []
    places: list[str] = []
    for field in fields[1:]:
        text = _URL.sub("", field).strip()
        if not text:
            continue
        parts = _role_parts(text) if not _PROSE.search(text) else []
        if parts:
            roles += parts
        elif (len(text) <= 60 and not _MONEY.search(text) and not _PROSE.search(text)
              and not _EMPLOYMENT_FIELD.match(text)):
            places.append(text)

    for line in lines[1:]:
        text = _URL.sub("", line).strip(" -–—:")
        bulleted = bool(_BULLET.match(line))
        text = _BULLET.sub("", text).strip()
        if not text or not _ROLE_WORD.search(text) or _PROSE.search(text):
            continue
        short = len(text) <= 60 and len(text.split()) <= 8 and not text.endswith(".")
        if (bulleted and len(text) <= 100) or short:
            roles.append(text.split(" - ")[0].strip())

    seen: set[str] = set()
    unique = []
    for role in roles:
        key = role.lower()
        if key not in seen:
            seen.add(key)
            unique.append(role[:120])
    return company[:80], unique[:MAX_ROLES], ", ".join(places)[:200]


def hacker_news(**kw) -> list[Posting]:
    """The monthly "Ask HN: Who is hiring" thread, one posting per role.

    Each top-level comment is one company's post and often several roles.
    Each role becomes its own posting sharing the comment's text, so the
    level and role filters judge the role's own title. A comment naming no
    recognisable role still becomes one posting, titled with its header, and
    is judged (and usually killed) on that.

    Worth having because YC founders post here and many of those roles appear
    nowhere else.
    """
    threads = get_json(HN, **kw)
    if not threads or not threads.get("hits"):
        return []

    # The account posts three threads a month - hiring, wants to be hired and
    # freelancer - so the newest story is not necessarily the hiring one.
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
            company, roles, where = hn_roles(body)
            url = f"https://news.ycombinator.com/item?id={comment.get('id')}"
            header = body.split("\n")[0]
            titles = roles or [header.split("|", 1)[-1].strip()[:120] or header[:120]]
            for title in titles:
                slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:60]
                out.append(
                    Posting(
                        source="hn",
                        company=company,
                        title=title,
                        location=where,
                        # One comment, several roles: the fragment keeps each
                        # role's identity apart in the store.
                        url=url if len(titles) == 1 else f"{url}#{slug}",
                        text=body,
                        posted=_iso(comment.get("created_at")),
                    )
                )
    return out
