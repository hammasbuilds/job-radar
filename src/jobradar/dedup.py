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

Which copy survives matters: the ATS copy wins. It carries the full
description, and every filter in this project reads prose.
"""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime, timezone

_EPOCH = datetime.min.replace(tzinfo=timezone.utc)

# The ATS boards originate postings; the aggregators mirror them, sometimes
# with the description truncated. Higher wins.
PRIORITY = {"greenhouse": 3, "lever": 3, "arbeitnow": 2, "remotive": 2}

_NOISE = re.compile(
    r"\b(?:senior|sr|junior|jr|lead|staff|principal|mid|m/f/d|m/w/d|f/m/d|"
    r"all genders|remote|hybrid|onsite|full[- ]time|part[- ]time|contract|"
    r"permanent|freelance|b2b|eu|emea|europe)\b"
)

# A role advertised in three countries carries the country in its title:
#   "Machine Learning Fellow - Human Frontier Collective (Canada)"
#   "Machine Learning Fellow - Human Frontier Collective (UK)"
# Those are one job with three apply links, and leaving the country in the
# identity key put all three on the dashboard as separate rows. The location
# is not part of what the job *is*, which is the same reason seniority is
# stripped above.
_PLACE = re.compile(
    r"\b(?:usa?|united states|uk|united kingdom|canada|ireland|germany|france|"
    r"spain|portugal|poland|netherlands|belgium|sweden|denmark|norway|finland|"
    r"italy|austria|switzerland|romania|india|apac|latam|amer|north america|"
    r"london|berlin|paris|madrid|lisbon|amsterdam|dublin|munich|warsaw|"
    r"stockholm|copenhagen|zurich|milan|barcelona|remote)\b"
)
_PUNCT = re.compile(r"[^a-z0-9 ]+")
_WS = re.compile(r"\s+")


def company_key(name: str) -> str:
    """Normalised company name.

    Legal suffixes and spacing differ between sources for the same firm —
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
    """Title with seniority and arrangement words removed.

    'Senior ML Engineer (Remote, m/f/d)' and 'ML Engineer' at the same company
    in the same week are one job advertised twice, and the words that differ
    are exactly the ones that carry no identity.
    """
    title = (title or "").lower()
    # Drop a trailing parenthetical before punctuation is flattened, so
    # "Engineer (Canada)" and "Engineer (UK)" reduce to the same thing.
    title = re.sub(r"\([^)]*\)", " ", title)
    title = _PUNCT.sub(" ", title)
    title = _NOISE.sub(" ", title)
    title = _PLACE.sub(" ", title)
    return _WS.sub(" ", title).strip()


def deduplicate(postings: list) -> tuple[list, int]:
    """Collapse duplicates. Returns (kept, number removed).

    Grouping is by (company, title) only — no text similarity anywhere. The
    87% error rate that comms-desk measured came from letting text similarity
    decide, and nothing here gives it the chance.
    """
    groups: dict[tuple[str, str], list] = defaultdict(list)
    singles = []

    for posting in postings:
        company = company_key(posting.company)
        title = title_key(posting.title)
        if not company or not title:
            # Without both halves the barrier cannot be applied, and merging
            # on a missing key would merge unrelated jobs. Keep it whole.
            singles.append(posting)
            continue
        groups[(company, title)].append(posting)

    kept = list(singles)
    removed = 0
    for members in groups.values():
        if len(members) == 1:
            kept.append(members[0])
            continue
        # Prefer the originating board; among equals prefer the longest
        # description, because a truncated copy loses the filters' evidence.
        best = max(
            members,
            key=lambda p: (PRIORITY.get(p.source, 0), len(p.text), p.posted or _EPOCH),
        )
        kept.append(best)
        removed += len(members) - 1
    return kept, removed
