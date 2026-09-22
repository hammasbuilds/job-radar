"""What level is this role, and is it one worth applying to?

The role filter answers *what* the job is. This answers *how senior*, and the
two are independent: "Senior Machine Learning Engineer" and "Junior Machine
Learning Engineer" are the same role at opposite ends of a career.

Without this the list filled with Senior, Staff and Lead titles, because that
is most of what gets advertised — a company posts one junior role for every
four senior ones, and the senior ones score identically on every other filter.

**A title with no level word is accepted.** "AI Engineer" and "Machine Learning
Engineer" are the common case and they are exactly what is wanted; treating an
absent word as a missing qualification would throw away most of the good
postings. Absence is not seniority.

The accepted levels live in `profile.py` so the whole policy is one edit.
"""

from __future__ import annotations

import re

INTERN = "intern"
ASSISTANT = "assistant"
JUNIOR = "junior"
ASSOCIATE = "associate"
MID = "mid"            # no level word at all — "AI Engineer"
SENIOR = "senior"
STAFF = "staff"
LEAD = "lead"
PRINCIPAL = "principal"
EXECUTIVE = "executive"

# Ordered from most junior to most senior. The first pattern that matches a
# title wins, and the order matters: "Senior Staff Engineer" is staff, and
# "Junior to Mid Engineer" is junior, because the more specific and the more
# junior reading is the useful one when a title straddles two levels.
_LEVELS = (
    (EXECUTIVE, (
        r"\b(?:vp|vice president|head of|director|chief|cto|cio|c-level)\b",
        r"\bdirector\b",
    )),
    (PRINCIPAL, (r"\bprincipal\b", r"\bdistinguished\b", r"\bfellow engineer\b")),
    (STAFF, (r"\bstaff\b",)),
    (LEAD, (r"\blead\b", r"\bleader\b", r"\bmanager\b", r"\bhead\b")),
    (SENIOR, (r"\bsenior\b", r"\bsr\.?\b", r"\bsnr\b", r"\bexperienced\b",
              r"\bexpert\b", r"\bm[üu]nchen senior\b")),
    (ASSOCIATE, (r"\bassociate\b",)),
    (JUNIOR, (r"\bjunior\b", r"\bjr\.?\b", r"\bentry[- ]level\b",
              r"\bgraduate\b", r"\bnew grad\b", r"\bearly career\b",
              r"\btrainee\b", r"\blevel 1\b", r"\bl1\b", r"\bi{1}\b(?<!\bii\b)")),
    (ASSISTANT, (r"\bassistant\b",)),
    (INTERN, (r"\bintern(?:ship)?\b", r"\bworking student\b", r"\bwerkstudent\b",
              r"\bapprentice\b", r"\bplacement\b", r"\bco[- ]op\b")),
)

# A level word inside a product name is not a seniority. "Senior Care
# Platform", "Lead Generation Engineer" and "Principal Component Analysis" all
# used to read as ranks, and "Lead Generation" is common enough in job titles
# to matter on its own.
_NOT_A_RANK = (
    r"lead generation", r"senior care", r"senior living", r"senior housing",
    r"principal component", r"head of terms", r"lead qualification",
)


# --- years demanded ---------------------------------------------------------
#
# A title is only half the answer. "AI Engineer" reads as mid-level and then
# asks for eight years in paragraph three, which is a senior role that forgot
# to say so in its title.
#
# Written to catch the ways a requirement is actually phrased, including the
# ranges: "3-5 years", "5+ years", "at least four years", "minimum of 2 years".
_WORD_NUM = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10,
}

_YEARS = re.compile(
    r"(?:(?:at least|minimum(?: of)?|min\.?|over|more than|\+)\s*)?"
    r"(\d{1,2}|one|two|three|four|five|six|seven|eight|nine|ten)"
    r"\s*(?:\+|plus)?\s*"
    r"(?:\s*(?:-|–|to)\s*\d{1,2}\s*)?"
    r"(?:\+\s*)?year",
    re.I,
)

# "10 years of building X" in a company blurb is not a requirement, and
# neither is "founded 5 years ago". Only count a number that sits near a word
# about the candidate's experience.
_EXPERIENCE_NEAR = re.compile(
    r"experience|background|track record|working with|practice|industry", re.I
)


def years_required(text: str) -> int | None:
    """The lowest number of years the posting actually demands, or None.

    The **minimum** across all mentions is deliberate and it is the generous
    reading. A description often says "3+ years required" in one place and
    "8 years would be ideal" in another; the first is the bar and the second
    is a wish, and rejecting on the wish would throw away a job the candidate
    is qualified for.
    """
    found: list[int] = []
    for match in _YEARS.finditer(text):
        # Only count it if experience is being discussed within a short window
        # either side, so company-history numbers do not read as requirements.
        start, end = match.span()
        window = text[max(0, start - 90):min(len(text), end + 90)]
        if not _EXPERIENCE_NEAR.search(window):
            continue
        raw = match.group(1).lower()
        value = _WORD_NUM.get(raw) or (int(raw) if raw.isdigit() else None)
        if value is not None and 0 < value <= 25:
            found.append(value)
    return min(found) if found else None


def classify(title: str) -> tuple[str, str]:
    """(level, the word that decided it). MID when no level word appears."""
    low = f" {title.lower()} "
    for pattern in _NOT_A_RANK:
        low = re.sub(pattern, " ", low)

    for level, patterns in _LEVELS:
        for pattern in patterns:
            found = re.search(pattern, low)
            if found:
                return level, found.group(0).strip()
    return MID, "no level stated"
