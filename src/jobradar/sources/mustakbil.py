"""Mustakbil — a Pakistani board that turns out to be readable after all.

The Pakistan section of this tool has been the thin one: sixteen employers
probed, one readable board, and everything else either HTML-only or behind a
bot wall. `registry.py` recorded Mustakbil as "HTML only, no feed". That was
wrong, and this module is the correction.

Two things make it fetchable without scraping anything:

  an RSS feed           `rss.mustakbil.com/jobs-rss?c=0` returns the 500 most
                        recent postings in ONE request, each with title,
                        company, city, country, category, pubdate and the full
                        description. This is the default path.
  a published sitemap   `sitemaps.mustakbil.com/sitemaps` lists all 1,403 live
                        postings, and every job page carries JobPosting
                        JSON-LD. That is the deep path, used only when the
                        feed's 500 are not enough - it is one request per
                        posting and takes hours, because their pages are 235 KB
                        and answer in about nine seconds.

The feed was found by reading a job page's own links, after the sitemap sweep
had been running for eight minutes to fetch fifty jobs. Worth remembering: the
slow way worked, which is exactly why it did not get questioned sooner.

**Why not the board everyone would name first.** Rozee.pk is bigger and it is
behind a Cloudflare managed challenge — the "enable JavaScript and cookies"
interstitial. Getting past that means pretending to be a browser, which is
where reading a public record turns into evading a control. It stays NO_API.

**Why not LinkedIn, where the jobs are visible.** It is in `registry.py` as
PROHIBITED and it stays there. Their terms forbid automated collection, they
have no open jobs API, and the account at risk is the one this whole tool
exists to get a job with.

`fetch_feed()` is the default and costs one request. `fetch()` walks the
sitemap and is opt-in: at nine seconds a page it is hours, not the twenty
minutes first estimated here, and the HTTP cache is what makes a second pass
bearable.
"""

from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone

from ..posting import Posting, clean
from .http import get_text

# The feed's title and company come through with raw entities - "Marketing
# &amp; Growth" - and a title is not HTML, so it never went through the tag
# stripper that decodes them. `clean` handles both.

SITEMAP_INDEX = "https://sitemaps.mustakbil.com/sitemaps"
JOBS_SITEMAP = "https://sitemaps.mustakbil.com/sitemaps/jobs/1"

_LOC = re.compile(r"<loc>([^<]+)</loc>")
_LD = re.compile(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', re.S)

# Pace between uncached requests. Their sitemap invites a crawl; it does not
# invite a flood, and this tool has no deadline.
DELAY = 0.7


def _iso(value) -> datetime | None:
    if not value:
        return None
    text = str(value).replace("Z", "+00:00")
    # Their validThrough carries seven-digit fractional seconds, which
    # fromisoformat rejects before 3.11 and accepts inconsistently after.
    text = re.sub(r"\.(\d{6})\d+", r".\1", text)
    try:
        stamp = datetime.fromisoformat(text)
    except ValueError:
        return None
    return stamp if stamp.tzinfo else stamp.replace(tzinfo=timezone.utc)


def job_urls(limit: int | None = None) -> list[str]:
    """Every live posting, from the sitemap rather than from a search page."""
    xml = get_text(JOBS_SITEMAP, max_age=6 * 3600)
    if not xml:
        return []
    urls = [u for u in _LOC.findall(xml) if "/jobs/job/" in u]
    return urls[:limit] if limit else urls


def _posting_from(html: str, url: str) -> Posting | None:
    for block in _LD.findall(html):
        try:
            data = json.loads(block)
        except json.JSONDecodeError:
            continue
        if not isinstance(data, dict) or data.get("@type") != "JobPosting":
            continue

        org = data.get("hiringOrganization") or {}
        company = str(org.get("name") or "").strip()

        # jobLocation is often absent on this board, and an empty location
        # would be read downstream as "location unknown" rather than as what
        # it is: a job in Pakistan. jobLocationType REMOTE is kept as a hint
        # instead of being flattened into the string.
        loc = data.get("jobLocation") or {}
        if isinstance(loc, list):
            loc = loc[0] if loc else {}
        addr = (loc or {}).get("address") or {}
        parts = [addr.get("addressLocality"), addr.get("addressRegion")]
        where = ", ".join(p for p in parts if p) or "Pakistan"
        remote = str(data.get("jobLocationType") or "").upper() == "TELECOMMUTE"

        types = data.get("employmentType") or ()
        if isinstance(types, str):
            types = (types,)

        return Posting(
            source="mustakbil",
            company=company or "unknown",
            title=str(data.get("title") or "").strip(),
            location=where,
            url=url,
            text=clean(str(data.get("description") or "")),
            posted=_iso(data.get("datePosted")),
            remote_hint=remote or None,
            tags=tuple(str(t) for t in types),
        )
    return None


def fetch(limit: int | None = None, *, delay: float = DELAY,
          progress=None) -> list[Posting]:
    """Fetch postings, one page per job, paced.

    A job whose page is gone or carries no JSON-LD is skipped rather than
    raised on: a sitemap generated an hour ago will always contain a few
    postings that have since been taken down.
    """
    out: list[Posting] = []
    urls = job_urls(limit)
    for i, url in enumerate(urls, 1):
        html = get_text(url, max_age=7 * 24 * 3600)
        if html:
            posting = _posting_from(html, url)
            if posting and posting.title:
                out.append(posting)
        if progress and i % 50 == 0:
            progress(i, len(urls), len(out))
        if delay and html is not None:
            time.sleep(delay)
    return out

# --------------------------------------------------------------- the feed
# c=0 is every category. The others are per-category and mostly tiny: of
# fifteen ids probed, eleven returned fewer than five postings.
RSS = "https://rss.mustakbil.com/jobs-rss?c={category}"

_ITEM = re.compile(r"<item>(.*?)</item>", re.S)


def _field(item: str, tag: str) -> str:
    m = re.search(rf"<{tag}>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</{tag}>", item, re.S)
    return m.group(1).strip() if m else ""


def _rss_date(value: str) -> datetime | None:
    """RFC-822, with the timezone sometimes HTML-escaped as &#x2B;0000."""
    if not value:
        return None
    from email.utils import parsedate_to_datetime
    cleaned = value.replace("&#x2B;", "+").replace("&#43;", "+")
    try:
        stamp = parsedate_to_datetime(cleaned)
    except (TypeError, ValueError):
        return None
    return stamp if stamp.tzinfo else stamp.replace(tzinfo=timezone.utc)


def fetch_feed(category: int = 0, **kw) -> list[Posting]:
    """The 500 most recent postings, in one request.

    The board is Pakistani but the feed is not Pakistan-only: employers post
    roles in Dubai, Kabul, Delhi and further. `location` keeps what the feed
    said rather than assuming, and the places filter decides.
    """
    xml = get_text(RSS.format(category=category), **kw)
    if not xml:
        return []
    out: list[Posting] = []
    for item in _ITEM.findall(xml):
        title = _field(item, "title")
        link = _field(item, "link")
        if not title or not link:
            continue
        city = _field(item, "city")
        country = _field(item, "country")
        where = ", ".join(p for p in (city, country) if p) or "Pakistan"
        # Every title ends "... Jobs in <city>, <country>", which is the
        # location repeated inside the job title. Left in, it reaches the
        # title-matching in the fit score and every posting looks like a
        # partial match on its own city.
        clean_title = re.sub(r"\s+Jobs in .*$", "", clean(title)).strip()
        category_tag = _field(item, "category")
        out.append(Posting(
            source="mustakbil",
            company=clean(_field(item, "company")) or "unknown",
            title=clean_title or title,
            location=where,
            url=link,
            text=clean(_field(item, "description")),
            posted=_rss_date(_field(item, "pubdate")),
            tags=(category_tag,) if category_tag else (),
        ))
    return out
