"""How much overlap with their working day do they demand?

The note is firm that this is **not a kill filter**:

    PKT is UTC+5, CET is +1/+2. A 3-4h overlap is good — surface it as a
    plus, not a filter.

That is right and it is easy to get wrong. Pakistan is UTC+5, so a 09:00-18:00
PKT day overlaps 06:00-13:00 CET — the entire European morning. Against UK time
it is 05:00-12:00. For most European roles the overlap is genuinely good, and a
filter that killed on "must overlap core hours" would throw away the best
matches in the corpus for no reason.

What is worth flagging is the opposite end: a US-Pacific role wanting core
hours is a 12-hour gap and means working nights indefinitely.
"""

from __future__ import annotations

import re

from ..profile import TZ_OFFSET
from . import rx

GOOD = "good"          # substantial overlap with a PKT working day
PARTIAL = "partial"    # some overlap, awkward
POOR = "poor"          # nights
ASYNC = "async"        # explicitly does not care
UNSTATED = "unstated"

# UTC offsets of the zones a posting is likely to name.
#
# Spelled-out names match in any case. **Abbreviations match only in capitals,
# as written**, and the two-letter ones only beside a time: the first version
# matched lower-cased text, so German "Unsere Firma ist in Berlin" read as
# India Standard Time and "Part-time (PT)" as Pacific, on a board (Arbeitnow)
# that is mostly German.
_NAMED = {
    r"\b(?:central european|cet|cest)\b": 1,
    r"\b(?:eastern european|eet|eest)\b": 2,
    r"\b(?:uk time|london time|greenwich)\b": 0,
    r"\bindia standard\b": 5.5,
    r"\beastern time\b": -5,
    r"\bcentral time\b": -6,
    r"\bpacific time\b": -8,
}
_ABBREV = {
    r"\b(?:CET|CEST)\b": 1,
    r"\b(?:EET|EEST)\b": 2,
    r"\b(?:GMT|BST|UTC)\b": 0,
    r"\bIST\b": 5.5,
    r"\b(?:EST|EDT)\b": -5,
    r"\b(?:CST|CDT)\b": -6,
    r"\b(?:PST|PDT)\b": -8,
}
# ET / CT / PT only when a clock time or "hours"/"timezone" sits right next to it.
_SHORT = {"ET": -5, "CT": -6, "PT": -8}
_NEAR_TIME = re.compile(
    r"(?:\d\s*(?:am|pm)?\s*[-–/]?\s*$|(?:hours|time\s?zone|overlap|core)\W*$)", re.I)
_AFTER_TIME = re.compile(r"^\W{0,3}(?:hours|time|timezone|overlap|business|working)", re.I)

# "async" alone is a Python keyword far more often than a way of working:
# "async Python (asyncio)" gave a role the "async / no core hours" badge.
_ASYNC = (
    r"\basync(?:hronous)?[- ](?:first|by default|culture|communication|collaboration|"
    r"work(?:ing|place)?|team|company|environment|organi[sz]ation)\b",
    r"\b(?:work|collaborate|communicate)s? (?:fully |mostly |primarily )?"
    r"async(?:hronously)?\b",
    r"no core hours",
    r"work (?:when|whenever) (?:you|it) ",
    r"fully flexible hours",
    r"results[- ]only",
)

_CORE = (
    r"core (?:working )?hours",
    r"(?:must|need to) overlap",
    r"\d\s*(?:\+\s*)?hours? of overlap",
    r"overlap (?:of |with )?.{0,20}(?:hours|time zone)",
    r"available (?:from|between) \d{1,2}[:.]?\d{0,2}\s*(?:am|pm)?",
)

# The candidate's own offset, from profile.py - the one place it is set.
PKT = TZ_OFFSET


def _overlap(their_offset: float) -> float:
    """Hours a 09:00-18:00 PKT day shares with a 09:00-18:00 day at that offset."""
    start = max(9.0, 9.0 + their_offset - PKT)
    end = min(18.0, 18.0 + their_offset - PKT)
    return max(0.0, end - start)


def _zones_named(original: str) -> list[tuple[str, float]]:
    """(zone as written, UTC offset) for every zone the text names."""
    found = []
    for pattern, offset in _NAMED.items():
        hit = rx(pattern, re.I).search(original)
        if hit:
            found.append((hit.group(0), offset))
    for pattern, offset in _ABBREV.items():
        hit = rx(pattern).search(original)
        if hit:
            found.append((hit.group(0), offset))
    for abbrev, offset in _SHORT.items():
        for hit in rx(rf"\b{abbrev}\b").finditer(original):
            before = original[max(0, hit.start() - 20):hit.start()]
            after = original[hit.end():hit.end() + 20]
            if _NEAR_TIME.search(before) or _AFTER_TIME.search(after):
                found.append((abbrev, offset))
                break
    return found


def classify(posting) -> tuple[str, str]:
    text = posting.haystack

    for pattern in _ASYNC:
        if rx(pattern).search(text):
            return ASYNC, "async / no core hours"

    named = _zones_named(f"{posting.title}\n{posting.location}\n{posting.text}")

    if named:
        # The best overlap among the zones named — a posting that mentions both
        # CET and PT is usually a European company with a US office, and the
        # European half is the one that matters here.
        zone, offset = max(named, key=lambda z: _overlap(z[1]))
        hours = _overlap(offset)
        if hours >= 5:
            return GOOD, f"{zone.upper()}: ~{hours:.0f}h overlap with a PKT day"
        if hours >= 3:
            return PARTIAL, f"{zone.upper()}: ~{hours:.0f}h overlap"
        return POOR, f"{zone.upper()}: ~{hours:.0f}h overlap - nights"

    if any(rx(p).search(text) for p in _CORE):
        return UNSTATED, "core hours required, zone not named"
    return UNSTATED, "no working-hours requirement stated"
