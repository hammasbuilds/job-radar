"""Y Combinator companies, from the community API that mirrors their directory.

    https://yc-oss.github.io/api/

No key, no scraping, and it is rebuilt daily. 6,245 launched companies, of
which **1,483 are currently hiring** and 894 carry the `ai` tag.

This section works differently from the rest of the tool on purpose. Everywhere
else the job description is the product: five filters read it and most postings
die. Here the *company* is the signal — YC-backed, funded, and hiring — so
**every open role is listed and the description is not filtered at all**. A
small funded company that will talk to you matters more than whether this
particular posting was worded for your stack.

**LinkedIn is derived, never fetched.** The YC API carries no LinkedIn field —
checked, including the per-company detail endpoint. So the URL here is
constructed from the company slug and labelled as a guess, with a search link
beside it that always lands somewhere. Requesting LinkedIn programmatically is
the one thing this project will not do: it is the only source where getting
caught costs the profile you are building.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from ..posting import Posting
from .http import get_json

# Age buckets, exclusive, so a company appears in exactly one. Measured from
# `launched_at`, which is when the company launched on YC's directory rather
# than when it was incorporated — close enough to "how new is this" to be
# useful, and different enough to be worth saying out loud.
#
# On the 1,483 currently-hiring companies: 32 under three months, 47 at three
# to six, 136 at six to twelve.
BUCKETS = (
    ("0-3m", 92, "launched in the last 3 months"),
    ("3-6m", 183, "launched 3 to 6 months ago"),
    ("6-12m", 366, "launched 6 to 12 months ago"),
)

META = "https://yc-oss.github.io/api/meta.json"
HIRING = "https://yc-oss.github.io/api/companies/hiring.json"
TAG = "https://yc-oss.github.io/api/tags/{tag}.json"

# Tags worth crossing with "is hiring" when the full list is too broad.
AI_TAGS = ("ai", "machine-learning", "generative-ai", "computer-vision", "nlp",
           "ai-assistant", "aiops", "deep-learning", "llm")


@dataclass
class YCCompany:
    """One YC company, with the links a person actually wants to open."""

    slug: str
    name: str
    batch: str
    website: str
    yc_url: str
    one_liner: str
    industry: str
    team_size: int | None
    location: str
    tags: tuple[str, ...] = ()
    stage: str = ""
    status: str = ""
    launched_at: int | None = None
    jobs: list = field(default_factory=list)

    @property
    def age_days(self) -> int | None:
        if not self.launched_at:
            return None
        launched = datetime.fromtimestamp(self.launched_at, tz=timezone.utc)
        return (datetime.now(timezone.utc) - launched).days

    @property
    def age_bucket(self) -> str:
        """Which new-startup section this belongs in, or "" for established."""
        age = self.age_days
        if age is None:
            return ""
        for name, limit, _ in BUCKETS:
            if age <= limit:
                return name
        return ""

    @property
    def age_label(self) -> str:
        age = self.age_days
        if age is None:
            return "launch date unknown"
        if age < 60:
            return f"launched {age} days ago"
        if age < 720:
            return f"launched {age // 30} months ago"
        return f"launched {age // 365} years ago"

    @property
    def linkedin_guess(self) -> str:
        """Almost always right, occasionally wrong, never verified.

        Presented as a guess in the UI rather than as a fact, because a
        confident wrong link to another company's page is worse than an
        obvious search."""
        return f"https://www.linkedin.com/company/{self.slug}"

    @property
    def linkedin_search(self) -> str:
        name = self.name.replace(" ", "%20")
        return f"https://www.linkedin.com/search/results/companies/?keywords={name}"

    @property
    def is_ai(self) -> bool:
        low = {t.lower() for t in self.tags}
        return any(t in low for t in AI_TAGS)


def _one(row: dict) -> YCCompany:
    return YCCompany(
        slug=row.get("slug", ""),
        name=row.get("name", ""),
        batch=row.get("batch", ""),
        website=row.get("website", "") or "",
        yc_url=row.get("url", "") or "",
        one_liner=row.get("one_liner", "") or "",
        industry=row.get("industry", "") or "",
        team_size=row.get("team_size"),
        location=row.get("all_locations", "") or "",
        tags=tuple(row.get("tags") or []),
        stage=row.get("stage", "") or "",
        status=row.get("status", "") or "",
        launched_at=row.get("launched_at"),
    )


def hiring(ai_only: bool = False, **kw) -> list[YCCompany]:
    """Companies YC lists as currently hiring.

    `isHiring` is the company's own flag in the directory. It is not a
    guarantee that a board exists — plenty hire through a form or an email —
    which is why `resolve_boards` reports how many actually resolved rather
    than assuming.
    """
    payload = get_json(HIRING, **kw)
    if not payload:
        return []
    rows = payload if isinstance(payload, list) else payload.get("companies", [])
    companies = [_one(r) for r in rows]
    if ai_only:
        companies = [c for c in companies if c.is_ai]
    return companies


def jobs_for(company: YCCompany, **kw) -> list[Posting]:
    """Every open role at this company, unfiltered.

    The YC slug is tried against Greenhouse and Lever. Most YC companies use
    one of the two; those that do not simply return nothing, and the company
    still appears in the directory with its website and YC profile, because
    "funded, hiring, no board I can read" is still worth an email.
    """
    from . import greenhouse, lever

    for fetch in (greenhouse.fetch, lever.fetch):
        try:
            got = fetch(company.slug, company=company.name, **kw)
        except Exception:
            continue
        if got:
            return got
    return []
