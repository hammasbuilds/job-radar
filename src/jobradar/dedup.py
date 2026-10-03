"""The problem the note said would actually bite.

One role appears on the company's Greenhouse board, on Arbeitnow, on Remotive
and on four other aggregators. Ten thousand fetched rows are perhaps six
hundred real jobs, and a dashboard showing one job seven times is worse than
no dashboard at all.

**The rule comes from comms-desk, which measured it.** From the design note:

    Company is a hard barrier, never a similarity feature. Two companies
    posting identically worded "AI Engineer" roles are two jobs. Same
    company, same title, two boards, within a week — one job. Dropping the
    barrier and merging on text similarity alone was wrong 87% of the time
    on real data.

So company equality is a precondition for merging, not a signal that raises a
similarity score. Two different companies are never merged however identical
their postings, because identical postings across companies are *normal* — the
same recruiter template, the same JD bought from the same agency.

**Seniority and place are part of what a job is.** An earlier version
stripped "senior", "junior", "lead" and every place name from the title
before comparing, so a Senior and a Junior ML Engineer at one company became
one row - and the one that survived was the Senior, which was then killed,
silently taking the junior role with it. "Research Scientist (Zurich)" and
"Research Scientist (Remote, Worldwide)" became one row too, and it was the
Zurich one. Only words that carry no identity at all (gender markers,
full-time/part-time) are dropped now, and two postings must name the same
places to merge.

Which copy survives matters: the ATS copy wins. It carries the full
description, and every filter in this project reads prose.
"""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import UTC, datetime, timedelta

from .filters import places

_EPOCH = datetime.min.replace(tzinfo=UTC)

# "Same company, same title, two boards, within a week - one job."
WINDOW = timedelta(days=7)

# The ATS boards originate postings; the aggregators mirror them, sometimes
# with the description truncated. Higher wins.
PRIORITY = {
    "greenhouse": 3, "lever": 3, "ashby": 3, "smartrecruiters": 3, "workable": 3,
    "recruitee": 3, "personio": 3,
    "arbeitnow": 2, "remotive": 2, "himalayas": 2, "jobicy": 2, "remoteok": 2,
    "themuse": 2, "mustakbil": 2,
}

# Words that never distinguish one job from another.
_NOISE = re.compile(
    r"\b(?:m/f/d|m/w/d|f/m/d|w/m/d|m/f/x|all genders|f/m/x|"
    r"full[- ]time|part[- ]time|permanent)\b"
)
_PUNCT = re.compile(r"[^a-z0-9 ]+")
_WS = re.compile(r"\s+")


def company_key(name: str) -> str:
    """Normalised company name.

    Legal suffixes and spacing differ between sources for the same firm -
    "Vivid Money GmbH" on one board, "Vivid" on another. Without this the hard
    barrier stops working precisely where it is needed, and the same company's
    duplicate postings survive into the dashboard.
    """
    name = _PUNCT.sub(" ", (name or "").lower())
    name = re.sub(
        r"\b(?:gmbh|ag|sa|sas|bv|nv|ltd|limited|llc|inc|corp|co|plc|oy|ab|as|"
        r"aps|srl|spa|sp z o o|s a|group|holdings?|technologies|technology|"
        r"labs?|software|solutions)\b",
        " ",
        name,
    )
    return _WS.sub(" ", name).strip()


def title_key(title: str) -> str:
    """Title with only identity-free words removed. Seniority and place stay."""
    title = _NOISE.sub(" ", (title or "").lower())
    title = _PUNCT.sub(" ", title)
    return _WS.sub(" ", title).strip()


def place_key(location: str) -> str:
    """The countries and regions a location names, order-free.

    "Berlin" and "Berlin, Germany" are the same place on two boards; "Zurich"
    and "Remote, Worldwide" are not. An unreadable location keys as itself.
    """
    tokens = []
    for token in places.tokens(location):
        if token in places.GLOBAL_WORDS:
            tokens.append("global")
        elif token in places.COUNTRIES or token in places.REGIONS:
            tokens.append(token)
        elif token in places.CITY_COUNTRY:
            tokens.append(places.CITY_COUNTRY[token])
    return ",".join(sorted(set(tokens))) or _WS.sub(" ", (location or "").lower()).strip()


def _within_a_week(members: list) -> list[list]:
    """Split one (company, title, place) group wherever postings are more than
    a week apart. Postings without a date join the cluster they sort next to."""
    ordered = sorted(members, key=lambda p: p.posted or _EPOCH)
    clusters: list[list] = []
    last = None
    for posting in ordered:
        when = posting.posted
        if clusters and (when is None or last is None or when - last <= WINDOW):
            clusters[-1].append(posting)
        else:
            clusters.append([posting])
        if when is not None:
            last = when
    return clusters


def deduplicate(postings: list) -> tuple[list, int]:
    """Collapse duplicates. Returns (kept, number removed).

    Grouping is by (company, title, places) and a one-week window - no text
    similarity anywhere. The 87% error rate that comms-desk measured came
    from letting text similarity decide, and nothing here gives it the chance.
    """
    groups: dict[tuple[str, str, str], list] = defaultdict(list)
    kept = []

    for posting in postings:
        company = company_key(posting.company)
        title = title_key(posting.title)
        if not company or not title:
            # Without both halves the barrier cannot be applied, and merging
            # on a missing key would merge unrelated jobs. Keep it whole.
            kept.append(posting)
            continue
        groups[(company, title, place_key(posting.location))].append(posting)

    removed = 0
    for members in groups.values():
        for cluster in _within_a_week(members):
            # Prefer the originating board; among equals prefer the longest
            # description, because a truncated copy loses the filters' evidence.
            best = max(
                cluster,
                key=lambda p: (PRIORITY.get(p.source, 0), len(p.text), p.posted or _EPOCH),
            )
            kept.append(best)
            removed += len(cluster) - 1
    return kept, removed
