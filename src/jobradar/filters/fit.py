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


# A domain word plus a craft word, anywhere in the title, in either order.
#
# The exhaustive phrase list below could not keep up with reality. It required
# a contiguous match, so "AI & System Engineer" failed because the title never
# says "ai engineer", and "AI Automation Engineer" failed for the same reason.
# Worse, "Data Scientist" was simply absent from the list — a core ML title
# missing outright, which killed every one of it in Pakistan and the Gulf.
#
# So: does the title name an AI/data domain AND an engineering craft? That
# generalises without loosening, because the craft list is what does the
# rejecting. "Creative Designer, Video Editor & AI Specialist" and "Pre-Sales
# Specialist (AI / Software Platforms)" both name a domain and are still
# rejected, because designer, editor and specialist are not crafts here.
_DOMAIN = re.compile(
    r"\b(?:a\.?i\.?|ml|machine[- ]learning|deep[- ]learning|llms?|nlp|"
    r"computer[- ]vision|generative(?:[- ]ai)?|gen[- ]?ai|agentic|"
    r"data[- ]scien\w*|mlops|robotics|perception|speech|vision)\b",
    re.I,
)
_CRAFT = re.compile(
    r"\b(?:engineer|engineering|scientist|researcher|research|developer|"
    r"architect|programmer)\b",
    re.I,
)

# Titles that name a domain and a craft and are still not the job. "Sales
# Engineer" and "Solutions Architect" sit in front of customers; a "Support
# Engineer" answers tickets.
_NOT_THE_JOB = re.compile(
    r"\b(?:sales|pre[- ]sales|account|customer|support|solutions?|marketing|"
    r"recruit\w*|teacher|tutor|trainer|instructor|intern(?:ship)?)\b",
    re.I,
)


def composite_role(title: str) -> str | None:
    """A domain word and a craft word in one title, e.g. "AI & System Engineer"."""
    if _NOT_THE_JOB.search(title):
        return None
    domain = _DOMAIN.search(title)
    craft = _CRAFT.search(title)
    if domain and craft:
        return f"{domain.group(0).lower()} {craft.group(0).lower()}"
    return None


def role_match(title: str) -> str | None:
    """The target role this title *is*, if any.

    Matched against the title alone and on a word boundary. A body that says
    "you will work with our ML engineers" is not an ML engineer posting, and
    an earlier version scored a Senior Marketing Data Analyst at 0.59 by
    counting field vocabulary wherever it appeared.
    """
    low = f" {re.sub(r'[^a-z0-9/+ ]+', ' ', title.lower())} "
    low = re.sub(r"\s+", " ", low)
    best = None
    for role in PROFILE["roles"]:
        if f" {role} " in low or low.strip().endswith(role):
            if best is None or len(role) > len(best):
                best = role
    # The named list wins when it matches — its answer is the specific role.
    # Otherwise fall back to the compositional rule, which catches the titles
    # no finite list will ever contain.
    return best or composite_role(title)


def score(posting) -> tuple[float, str]:
    """0.0–1.0, with one sentence of evidence.

    The weights are deliberately blunt. This ranks a list that a human then
    reads; pretending to three decimal places of precision about whether a job
    is a good fit would be false confidence dressed as arithmetic.
    """
    text = posting.haystack
    bits: list[str] = []
    total = 0.0

    # The title carries most of the signal. A posting that *is* one of the
    # target roles starts more than half way; one that merely uses the
    # vocabulary has to earn every point from the body.
    role = role_match(posting.title)
    if role:
        total += 0.55
        bits.append(f"role: {role}")

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

    # A title that is not one of the target roles but still names the field —
    # "Data Scientist, Vision" — is worth something, just much less.
    if not role:
        title = _terms_present(posting.title.lower(),
                               PROFILE["core"] + PROFILE["domains"])
        if title:
            total += 0.12
            bits.append("in title: " + ", ".join(title[:3]))
        else:
            # No target role and nothing from the field in the title. Whatever
            # the body says, this is not one of the seven roles being looked
            # for, and it should not outrank one that is.
            total -= 0.20
            bits.append("title is not a target role")

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
