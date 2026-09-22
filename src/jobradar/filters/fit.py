"""Does this match the actual profile — and can it quote why?

The note is explicit that a bare number is not actionable:

    A bare number is not actionable. A quoted reason tells you in two
    seconds whether to open it.

So `score()` returns a number *and* the evidence that produced it, and the
dashboard shows the evidence. This is the same discipline as the faithfulness
work: a score nobody can check is a score nobody should act on.

Seniority is handled as a **penalty, not a gate.** A posting asking for ten
years is not worth applying to, but the difference between "senior" and "staff"
is not real enough to kill on, and a hard seniority filter would throw away
most of the interesting roles at small companies who title everything "Senior".
"""

from __future__ import annotations

import re

from ..profile import PROFILE


def _terms_present(text: str, terms) -> list[str]:
    """Whole-word matching. Substring matching makes 'R' match 'React' and
    'Go' match 'Django', which quietly inflates every score."""
    found = []
    for term in terms:
        pattern = rf"(?<![a-z0-9+#]){re.escape(term.lower())}(?![a-z0-9+#])"
        if re.search(pattern, text):
            found.append(term)
    return found


# Asking for a lot more experience than you have is the one seniority signal
# worth reading, and it is stated numerically often enough to be reliable.
_YEARS = re.compile(r"(\d{1,2})\+?\s*(?:-\s*\d{1,2}\s*)?years?(?:'| of)?\s+(?:of\s+)?experience")

_TOO_JUNIOR = re.compile(
    r"\b(?:intern(?:ship)?|graduate scheme|working student|werkstudent|apprentice)\b"
)
_TOO_SENIOR = re.compile(
    r"\b(?:vp|vice president|head of|director of|chief|cto|principal architect)\b"
)


def score(posting) -> tuple[float, str]:
    """0.0–1.0, with one sentence of evidence.

    The weights are deliberately blunt. This ranks a list that a human then
    reads; pretending to three decimal places of precision about whether a job
    is a good fit would be false confidence dressed as arithmetic.
    """
    text = posting.haystack
    bits: list[str] = []
    total = 0.0

    core = _terms_present(text, PROFILE["core"])
    if core:
        total += min(0.45, 0.15 * len(core))
        bits.append("core: " + ", ".join(core[:4]))

    domain = _terms_present(text, PROFILE["domains"])
    if domain:
        total += min(0.25, 0.09 * len(domain))
        bits.append("domain: " + ", ".join(domain[:3]))

    tools = _terms_present(text, PROFILE["tools"])
    if tools:
        total += min(0.15, 0.04 * len(tools))
        bits.append("tools: " + ", ".join(tools[:4]))

    # Title is worth more than body: a match in the title is what the role IS,
    # a match in the body may be one line of a tech-stack list.
    title = _terms_present(posting.title.lower(), PROFILE["core"] + PROFILE["domains"])
    if title:
        total += 0.15
        bits.append("in title: " + ", ".join(title[:3]))

    years = _YEARS.search(text)
    if years:
        wanted = int(years.group(1))
        if wanted > PROFILE["years"] + 3:
            total -= 0.25
            bits.append(f"wants {wanted}y experience")
        elif wanted <= PROFILE["years"] + 1:
            bits.append(f"{wanted}y asked, within range")

    if _TOO_JUNIOR.search(text):
        total -= 0.4
        bits.append("internship/working-student level")
    if _TOO_SENIOR.search(posting.title.lower()):
        total -= 0.35
        bits.append("executive-level title")

    total = max(0.0, min(1.0, total))
    return round(total, 3), "; ".join(bits) if bits else "nothing in the profile matched"
