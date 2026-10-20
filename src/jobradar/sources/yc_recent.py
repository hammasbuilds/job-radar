"""Every Y Combinator company from the last three years of batches, hiring or not.

The YC tab elsewhere is the hiring companies; this is the whole recent cohort, because a funded
company that is not advertising yet is reachable by email and may be the better lead. Rows come
from the yc-oss mirror's per-batch lists (`api/batches/<batch>.json`), which carry the hiring
flag, status, website and YC page for each company.

**LinkedIn comes from the company's own YC page**, not from LinkedIn. ycombinator.com's
robots.txt allows `/companies/<slug>` (it disallows only the search URLs with a query string),
and every company page links its LinkedIn profile. Where a page has none, the row carries a
LinkedIn *search* link, labelled as a search. LinkedIn itself is never requested.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from datetime import UTC, datetime

from .http import get_json, get_text

META = "https://yc-oss.github.io/api/meta.json"
YC_PAGE = "https://www.ycombinator.com/companies/{slug}"
_YEAR = re.compile(r"(\d{4})")
_LINKEDIN = re.compile(r"https://(?:[a-z]{2,3}\.)?linkedin\.com/company/[A-Za-z0-9_\-%.]+/?")
WEEK = 7 * 24 * 3600


@dataclass
class RecentCompany:
    slug: str
    name: str
    batch: str
    batch_year: int
    website: str
    yc_url: str
    jobs_url: str
    hiring: bool
    status: str
    one_liner: str
    industry: str
    location: str
    team_size: int | None
    tags: str
    is_ai: bool
    linkedin: str = ""
    linkedin_source: str = ""      # "yc page" when read there, "search" otherwise

    def row(self) -> dict:
        return asdict(self)


def batches_since(year: int, **kw) -> list[tuple[str, str]]:
    meta = get_json(META, **kw) or {}
    out = []
    for key, info in (meta.get("batches") or {}).items():
        found = _YEAR.search(key)
        if found and int(found.group(1)) >= year:
            out.append((info.get("name", key), info.get("api", "")))
    return out


_AI = re.compile(r"\b(?:ai|artificial intelligence|machine learning|ml|llm|generative|"
                 r"computer vision|deep learning|nlp|agents?|robotics)\b", re.I)


def recent(years: int = 3, **kw) -> list[RecentCompany]:
    since = datetime.now(UTC).year - years
    seen: set[str] = set()
    out: list[RecentCompany] = []
    for name, api in batches_since(since, **kw):
        for row in get_json(api, **kw) or []:
            slug = row.get("slug") or ""
            if not slug or slug in seen:
                continue
            seen.add(slug)
            tags = row.get("tags") or []
            blob = " ".join([row.get("one_liner") or "", " ".join(tags),
                             row.get("industry") or "", row.get("subindustry") or ""])
            year = _YEAR.search(name)
            out.append(RecentCompany(
                slug=slug, name=(row.get("name") or slug).strip(), batch=name,
                batch_year=int(year.group(1)) if year else 0,
                website=row.get("website") or "",
                yc_url=YC_PAGE.format(slug=slug),
                jobs_url=YC_PAGE.format(slug=slug) + "/jobs",
                hiring=bool(row.get("isHiring")), status=row.get("status") or "",
                one_liner=(row.get("one_liner") or "").strip(),
                industry=row.get("industry") or "", location=row.get("all_locations") or "",
                team_size=row.get("team_size"), tags=", ".join(tags),
                is_ai=bool(_AI.search(blob)),
            ))
    return out


def linkedin_from_page(slug: str, **kw) -> str:
    """The LinkedIn company URL the YC page links, or ''."""
    page = get_text(YC_PAGE.format(slug=slug), max_age=kw.get("max_age", WEEK))
    if not page:
        return ""
    for url in _LINKEDIN.findall(page):
        if "/company/ycombinator" not in url and "/company/y-combinator" not in url:
            return url
    return ""


def search_link(name: str) -> str:
    from urllib.parse import quote

    return f"https://www.linkedin.com/search/results/companies/?keywords={quote(name)}"
