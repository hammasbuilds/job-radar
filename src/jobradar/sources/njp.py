"""Pakistan's National Job Portal (njp.gov.pk): government and public-sector jobs.

robots.txt allows every path (`User-agent: * / Disallow:`), checked 2026-10-20. There is no
public JSON feed - `/api/jobs` answers an empty list to an anonymous request - so this reads the
public listing (`/jobs/live?page=N`, 21 a page) and each job page, at the HTTP layer's pace.
Job pages change rarely, so they are cached for a day rather than six hours.
"""

from __future__ import annotations

import html
import re
from datetime import UTC, datetime

from ..posting import Posting, clean
from .http import get_text

LISTING = "https://njp.gov.pk/jobs/live?page={page}"
JOB = "https://njp.gov.pk/jobs/{id}"
_JOB_LINK = re.compile(r"https://njp\.gov\.pk/jobs/(\d+)")
_TITLE = re.compile(r'const jobTitle = "((?:[^"\\]|\\.)*)"')
_EMPLOYER = re.compile(r'<p class="text-\[18px\] text-\[#FFFFFFE5\]">\s*([^<]+?)\s*</p>')
_CARD = r'<p class="text-\[12px\][^"]*">{label}</p>\s*(?:</div>\s*)?<p[^>]*>\s*([^<]+?)\s*</p>'
_DESCRIPTION = re.compile(r'<p class="text-white/90[^"]*leading-relaxed[^"]*">(.*?)</p>', re.S)
_DATED = r'{label}:</span>\s*<span[^>]*>\s*([^<]+?)\s*</span>'
_LOCATION = re.compile(r"Job Location:\s*([^<\n]+)", re.I)
DAY = 24 * 3600


def _card(page: str, label: str) -> str:
    m = re.search(_CARD.format(label=re.escape(label)), page)
    return html.unescape(m.group(1)).strip() if m else ""


def _date(page: str, label: str) -> datetime | None:
    m = re.search(_DATED.format(label=re.escape(label)), page)
    if not m:
        return None
    raw = m.group(1).strip()
    for fmt in ("%d %b %Y", "%d %B %Y", "%Y-%m-%d", "%b %d, %Y", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(raw, fmt).replace(tzinfo=UTC)
        except ValueError:
            continue
    return None


def parse(page: str, url: str) -> Posting | None:
    title = _TITLE.search(page)
    if not title:
        return None
    employer = _EMPLOYER.search(page)
    body = _DESCRIPTION.search(page)
    text = clean(body.group(1)) if body else ""
    where = _LOCATION.search(text)
    grade, kind = _card(page, "Grade"), _card(page, "Job Type")
    deadline = _date(page, "Deadline")
    extra = [f"Grade: {grade}" if grade else "", f"Job type: {kind}" if kind else "",
             f"Apply by: {deadline:%d %b %Y}" if deadline else ""]
    return Posting(
        source="njp",
        company=html.unescape(employer.group(1)).strip() if employer else "Government of Pakistan",
        title=html.unescape(title.group(1).encode().decode("unicode_escape", "ignore")).strip(),
        location=f"{where.group(1).strip().rstrip('.')}, Pakistan" if where else "Pakistan",
        url=url,
        text="\n".join(x for x in [text, *extra] if x),
        posted=_date(page, "Posted"),
        remote_hint=False,
        tags=tuple(filter(None, ("public sector", kind, grade))),
    )


def fetch(pages: int = 30, limit: int = 600, **kw) -> list[Posting]:
    ids: list[str] = []
    for page in range(1, pages + 1):
        listing = get_text(LISTING.format(page=page), **kw)
        if not listing:
            break
        new = [i for i in dict.fromkeys(_JOB_LINK.findall(listing)) if i not in ids]
        if not new:
            break
        ids += new
        if len(ids) >= limit:
            break
    out = []
    for jid in ids[:limit]:
        url = JOB.format(id=jid)
        page = get_text(url, max_age=kw.get("max_age", DAY))
        posting = parse(page or "", url)
        if posting:
            out.append(posting)
    return out
