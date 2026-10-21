"""Accelerator and investor portfolios: which companies they back, and which AI roles those
companies have open - read from the sitemaps of their job boards.

Most of these boards run on Getro. Its API (api.getro.com) disallows every agent in robots.txt,
so it is not used. The boards' own sitemaps are allowed - robots.txt names only three crawlers
for a 10-second delay, which this tool honours for everyone - and they list every portfolio
company page and every job page, with the job's title written into its address
(`/companies/<company>/jobs/<id>-<title-words>`). That is enough to say who is backed and which
roles are open, without the page bodies, which are large enough that this connection cuts them
off mid-download.

A title read from an address loses its punctuation and capitals ("ai ml engineer"), so the
dashboard links every role to its real page, where the location and full title are.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass, field

from .http import get_text

DAY = 24 * 3600

# (name, kind, board). Each board's robots.txt names <board>/sitemap.xml, an index that points to
# the company list and to the jobs, split over sitemap_jobs1..N.xml on the larger boards - so the
# index is always the starting point, never a guessed child name. Probed 2026-10-20.
PROGRAMMES = (
    ("Techstars", "accelerator", "https://jobs.techstars.com"),
    ("Antler", "accelerator", "https://careers.antler.co"),
    ("a16z", "investor", "https://jobs.a16z.com"),
    ("General Catalyst", "investor", "https://jobs.generalcatalyst.com"),
    ("Accel", "investor", "https://jobs.accel.com"),
    ("Thrive Capital", "investor", "https://jobs.thrivecap.com"),
    ("Insight Partners", "investor", "https://jobs.insightpartners.com"),
)

_LOC = re.compile(r"<loc>\s*([^<\s]+)\s*</loc>")
_COMPANY = re.compile(r"/compan(?:y|ies)/([a-z0-9][a-z0-9-]*)/?$", re.I)
# a16z's board lists each company's job page as /jobs/<company>, with no job pages under it.
_JOBS_PAGE = re.compile(r"^https?://[^/]+/jobs/([a-z][a-z0-9-]*)/?$", re.I)
_JOB = re.compile(r"/compan(?:y|ies)/([a-z0-9][a-z0-9-]*)/jobs/(\d+)-([a-z0-9-]+)", re.I)
_UUID = re.compile(r"-(?:\d+-)?[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
_SMALL_WORDS = {"and", "of", "the", "for", "to", "in", "at", "on", "a", "an", "with", "or"}
_KEEP_UPPER = {"ai", "ml", "dl", "cv", "llm", "nlp", "ui", "ux", "qa", "sre", "api", "gpu",
               "ios", "aws", "gcp", "hr", "cto", "vp", "sr", "jr", "ii", "iii", "iv", "3d"}


def name_from_slug(slug: str) -> str:
    """'xairos-2-ca2f9510-...' -> 'Xairos'; 'helgen-technologies' -> 'Helgen Technologies'."""
    core = _UUID.sub("", slug)
    core = re.sub(r"-\d+$", "", core)
    words = [w for w in core.split("-") if w]
    half = len(words) // 2
    if half >= 2 and len(words) % 2 == 0 and words[:half] == words[half:]:
        words = words[:half]          # 'spindle-ai-spindle-ai' -> 'Spindle Ai'
    return " ".join(w.capitalize() for w in words)


def title_from_slug(slug: str) -> str:
    words = slug.split("-")
    out = []
    for i, w in enumerate(words):
        if w in _KEEP_UPPER:
            out.append(w.upper())
        elif i and w in _SMALL_WORDS:
            out.append(w)
        else:
            out.append(w.capitalize())
    return " ".join(out)


@dataclass
class Portfolio:
    name: str
    kind: str
    board: str
    companies: dict[str, str] = field(default_factory=dict)   # slug -> company page URL
    jobs: list[dict] = field(default_factory=list)            # {company, title, url}
    read: int = 0
    failed: list[str] = field(default_factory=list)


# Attributes come in any order: Getro writes data-testid="job-ldjson" before the type.
_LD = re.compile(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', re.S | re.I)
_TAGS = re.compile(r"<[^>]+>")


def parse_job_page(page: str) -> dict | None:
    """The JobPosting a portfolio job page publishes about itself, or None when it has none.

    The address gave the title in lower-case slug words ("ai-research-engineer-computer-vision")
    and lost what the board's own title says - "Staff AI Research Engineer - Computer Vision" -
    and the page is the only place the location, the salary and the posting date are.
    """
    import json as _json

    for raw in _LD.findall(page or ""):
        try:
            data = _json.loads(raw)
        except ValueError:
            continue
        for obj in data if isinstance(data, list) else [data]:
            if not isinstance(obj, dict) or obj.get("@type") != "JobPosting":
                continue
            places = obj.get("jobLocation") or []
            places = places if isinstance(places, list) else [places]
            locations = []
            for pl in places:
                addr = (pl or {}).get("address") or {}
                if isinstance(addr, dict):
                    text = addr.get("addressLocality") or ", ".join(
                        str(addr[k]) for k in ("addressRegion", "addressCountry") if addr.get(k))
                    if text:
                        locations.append(str(text))
            salary = ""
            base = obj.get("baseSalary") or {}
            value = base.get("value") if isinstance(base, dict) else None
            if isinstance(value, dict) and (value.get("minValue") or value.get("maxValue")):
                lo, hi = value.get("minValue"), value.get("maxValue")
                unit = str(value.get("unitText") or "").lower()
                salary = f"{base.get('currency', '')} {lo:,}-{hi:,}" if lo and hi else \
                    f"{base.get('currency', '')} {lo or hi:,}"
                salary += f" / {unit}" if unit else ""
            return {
                "title": html.unescape(str(obj.get("title") or "")).strip(),
                "locations": locations,
                "remote": obj.get("jobLocationType") == "TELECOMMUTE",
                "posted": str(obj.get("datePosted") or "")[:10],
                "salary": salary.strip(),
                "text": html.unescape(_TAGS.sub(" ", str(obj.get("description") or ""))),
            }
    return None


def asks_for_api(programme: tuple) -> str:
    """The board's own request not to be crawled, or "" when there is none.

    On 2026-10-21 the Getro boards replaced their robots.txt rules with "We'd be happy to
    provide all job data to you through our API services ... contact api@getro.com". A file
    with no rules technically permits everything; the operator's request is plain all the same,
    so this reads it and the portfolio refresh stops, keeping the last stored copy.
    """
    board = programme[2]
    try:
        text = get_text(f"{board}/robots.txt", max_age=DAY) or ""
    except Exception:  # an unreadable robots.txt is not a request; the fetch decides
        return ""
    low = text.lower()
    if "through our api" in low or ("api@" in low and "disallow" not in low and "allow" not in low):
        return "robots.txt asks crawlers to use the board's API instead"
    return ""


def _locs(url: str, p: Portfolio, kw: dict, seen: set[str], depth: int = 0) -> list[str]:
    """Every page address under one sitemap, following an index down to its children.

    A child that cannot be read, or reads as something other than a sitemap (a 404 page, an
    empty body), is recorded in `p.failed` and the rest are still read: a portfolio with
    a missing jobs file must say so, not show "0 roles" as if that were the answer.
    """
    if url in seen or depth > 2:
        return []
    seen.add(url)
    try:
        body = get_text(url, max_age=kw.get("max_age", DAY)) or ""
    except Exception as exc:  # one unreadable sitemap must not lose the others
        p.failed.append(f"{url}: {exc}")
        return []
    if "<urlset" not in body and "<sitemapindex" not in body:
        p.failed.append(f"{url}: not a sitemap ({len(body)} bytes)")
        return []
    p.read += 1
    locs = _LOC.findall(body)
    if "<sitemapindex" in body:
        out: list[str] = []
        for child in locs:
            out += _locs(child, p, kw, seen, depth + 1)
        return out
    return locs


def fetch(programme: tuple, **kw) -> Portfolio:
    name, kind, board = programme[:3]
    p = Portfolio(name, kind, board)
    for loc in _locs(kw.get("sitemap") or f"{board}/sitemap.xml", p, kw, set()):
        job = _JOB.search(loc)
        if job:
            slug = job.group(1)
            p.jobs.append({"company_slug": slug, "company": name_from_slug(slug),
                           "title": title_from_slug(job.group(3)), "url": loc})
            p.companies.setdefault(slug, f"{board}/companies/{slug}")
            continue
        company = _COMPANY.search(loc) or _JOBS_PAGE.search(loc)
        if company:
            p.companies.setdefault(company.group(1), loc)
    return p
