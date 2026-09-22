"""Will they sponsor, or do they need someone who can already work there?

This filter decides which of the two sections a posting lands in, so it is the
one the whole dashboard is organised around.

**Silence is the hard case and it is the common one.** Most postings say
nothing about sponsorship. Reading silence as "maybe" would put thousands of
jobs into the sponsorship section that will never reply; reading it as "no"
would throw away real opportunities, because plenty of companies that sponsor
simply do not advertise it.

The resolution: silence is `SILENT`, a third value, never quietly folded into
either. It ranks below an explicit sponsor and above an explicit refusal, and
the dashboard shows which it is. A tool whose confident answers and its guesses
look identical is worse than one that admits the difference.
"""

from __future__ import annotations

import re

SPONSORS = "sponsors"        # says it will
REFUSES = "refuses"          # says it will not
NOT_NEEDED = "not_needed"    # contractor/global remote: authorisation is moot
SILENT = "silent"

_SPONSORS = (
    # `relocation` is deliberately absent from this alternation. Leaving it in
    # meant "we offer relocation assistance" matched here and was reported as
    # visa sponsorship — the exact false positive the separate hint below
    # exists to stop, surviving because it was also spelled out in a broader
    # pattern further up.
    r"(?:we|company) (?:will |do |can |are able to )?(?:offer|provide|support|sponsor)s?\b.{0,30}"
    r"(?:visa|work permit|sponsorship)",
    r"visa sponsorship (?:is )?(?:available|offered|provided|possible)",
    r"we sponsor (?:visas|work permits)",
    r"happy to sponsor",
    r"sponsorship (?:is )?(?:available|possible)",
    r"we (?:can|will) help (?:you )?(?:with )?(?:your )?visa",
    r"blue card",
    r"(?:assist|help) with (?:the )?visa process",
)

# Relocation support is NOT sponsorship, and treating it as such was the first
# thing that went wrong on real data: a Berlin role and a Seattle role both
# landed in the sponsorship section on the phrase "relocation assistance".
# Companies offer relocation to people who already hold the right to work —
# it pays for the moving van, not the visa. It is kept as a weaker signal
# because it does correlate, but it never alone puts a posting in the section
# whose whole promise is that relocation is genuinely on the table.
_RELOCATION_ONLY = (
    r"relocation (?:package|support|assistance|bonus|allowance)",
    r"we (?:offer|provide) relocation",
)
RELOCATION_HINT = "relocation_hint"

# Ordered so that the refusals people actually write are matched, including the
# polite ones that do not contain the word "sponsor" at all.
_REFUSES = (
    r"(?:not|unable to|cannot|can't|won't|do not|don't) (?:be able to )?(?:offer|provide|support)\b.{0,30}"
    r"(?:visa|sponsorship|work permit|relocation)",
    r"no visa sponsorship",
    r"(?:we )?do(?:es)? not sponsor",
    r"unable to sponsor",
    r"sponsorship (?:is )?not (?:available|offered|provided|possible)",
    r"without (?:the )?need for (?:visa )?sponsorship",
    r"must (?:already )?(?:have|hold|possess) (?:the |a |valid )?(?:legal )?right to work",
    r"must be (?:legally )?(?:authoriz|authoris)ed to work",
    r"(?:existing|valid|current) work (?:authoriz|authoris)ation (?:is )?required",
    r"you (?:must|will) (?:already )?have (?:a )?valid work (?:visa|permit)",
    r"we are (?:currently )?(?:not|unable) .{0,20}sponsor",
    r"eligible to work in .{0,25} without sponsorship",
)


def _hit(patterns, text: str) -> str | None:
    for pattern in patterns:
        found = re.search(pattern, text)
        if found:
            return found.group(0)
    return None


def classify(posting, scope: str | None = None) -> tuple[str, str]:
    """Return (status, the phrase that decided it).

    A refusal is tested before an offer. Postings that mention both nearly
    always read "we sponsor visas for some roles, but for this one you must
    already have the right to work" — the restriction is the operative half,
    and matching the offer first would file it under sponsorship wrongly.
    """
    text = posting.haystack

    phrase = _hit(_REFUSES, text)
    if phrase:
        return REFUSES, phrase.strip()

    phrase = _hit(_SPONSORS, text)
    if phrase:
        return SPONSORS, phrase.strip()

    # Work authorisation is a question about *being in the country*. For a
    # genuinely global-remote role, or one hiring a contractor, it does not
    # arise — and marking those SILENT would imply a doubt that is not real.
    if scope == "global":
        return NOT_NEEDED, "global remote — no work permit at issue"

    phrase = _hit(_RELOCATION_ONLY, text)
    if phrase:
        return RELOCATION_HINT, f"{phrase.strip()} — relocation offered, sponsorship not stated"

    return SILENT, "sponsorship not mentioned"
