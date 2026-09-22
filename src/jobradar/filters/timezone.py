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

GOOD = "good"          # substantial overlap with a PKT working day
PARTIAL = "partial"    # some overlap, awkward
POOR = "poor"          # nights
ASYNC = "async"        # explicitly does not care
UNSTATED = "unstated"

# UTC offsets of the zones a posting is likely to name, and what a 09:00-18:00
# PKT (UTC+5) day overlaps with each.
_ZONES = {
    r"\b(?:cet|cest|central european)\b": 1,
    r"\b(?:eet|eest|eastern european)\b": 2,
    r"\b(?:gmt|bst|utc|uk time|london time)\b": 0,
    r"\b(?:ist|india standard)\b": 5.5,
    r"\b(?:est|edt|eastern time|et)\b": -5,
    r"\b(?:cst|cdt|central time)\b": -6,
    r"\b(?:pst|pdt|pacific time|pt)\b": -8,
}

_ASYNC = (
    r"\basync(?:hronous)?(?:[- ]first)?\b",
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

PKT = 5.0
WORKDAY = 9.0   # hours


def _overlap(their_offset: float) -> float:
    """Hours a 09:00-18:00 PKT day shares with a 09:00-18:00 day at that offset."""
    start = max(9.0, 9.0 + their_offset - PKT)
    end = min(18.0, 18.0 + their_offset - PKT)
    return max(0.0, end - start)


def classify(posting) -> tuple[str, str]:
    text = posting.haystack

    for pattern in _ASYNC:
        if re.search(pattern, text):
            return ASYNC, "async / no core hours"

    named = [(re.search(p, text), off) for p, off in _ZONES.items()]
    named = [(m.group(0), off) for m, off in named if m]

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
        return POOR, f"{zone.upper()}: ~{hours:.0f}h overlap — nights"

    if any(re.search(p, text) for p in _CORE):
        return UNSTATED, "core hours required, zone not named"
    return UNSTATED, "no working-hours requirement stated"
