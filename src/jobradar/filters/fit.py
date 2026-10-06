"""Is this one of the target roles, and how well does it match the profile?

Two questions, kept apart.

**`role_match` is a gate.** The title must name one of the roles being looked
for, or the posting is killed. It reads the title alone: a body that says "you
will work with our ML engineers" is not an ML engineer posting.

**`score` is a ranking weight, never a gate.** It orders the survivors by how
much of the profile's vocabulary the posting uses, and it returns the evidence
with the number, because a bare number is not actionable:

    A bare number is not actionable. A quoted reason tells you in two
    seconds whether to open it.

Level and years are not part of the score. They are hard filters of their
own (`seniority.py`), so a penalty here would only ever double-count them.
"""

from __future__ import annotations

import re

from ..profile import PROFILE
from . import rx


def _terms_present(text: str, terms) -> list[str]:
    """Whole-word matching. Substring matching makes 'R' match 'React' and
    'Go' match 'Django', which quietly inflates every score."""
    found = []
    for term in terms:
        pattern = rf"(?<![a-z0-9+#]){re.escape(term.lower())}(?![a-z0-9+#])"
        if rx(pattern).search(text):
            found.append(term)
    return found


# A domain word plus a craft word, anywhere in the title, in either order.
#
# The exhaustive phrase list below could not keep up with reality. It required
# a contiguous match, so "AI & System Engineer" failed because the title never
# says "ai engineer", and "AI Automation Engineer" failed for the same reason.
#
# So: does the title name an AI/data domain AND an engineering craft? That
# generalises without loosening, because the craft list is what does the
# rejecting. "Creative Designer, Video Editor & AI Specialist" names a domain
# and is still rejected: designer, editor and specialist are not crafts here.
# Bare "vision" is not a domain ("Vision Care Engineer"); "computer vision" is.
_DOMAIN = re.compile(
    r"\b(?:a\.?i\.?|ml|machine[- ]learning|deep[- ]learning|llms?|nlp|"
    r"computer[- ]vision|generative(?:[- ]ai)?|gen[- ]?ai|agentic|"
    r"data[- ]scien\w*|mlops|robotics|perception|speech)\b",
    re.I,
)
_CRAFT = re.compile(
    r"\b(?:engineers?|engineering|scientists?|researchers?|research|developers?|"
    r"architect|programmer|fellows?)\b",
    re.I,
)

# Titles that name a domain and a craft and are still not the job. Checked
# against every match, named or compositional. "Sales Engineer" and
# "Solutions Architect" sit in front of customers; a "Value Engineer" is
# presales; a "Developer Advocate" writes talks; a "Research Economist" and a
# "UX Researcher" research something other than models.
_NOT_THE_JOB = re.compile(
    r"\b(?:sales|pre[- ]sales|account|customer|support|solutions?|marketing|"
    r"recruit\w*|teacher|tutor|trainer|instructor|intern(?:ship)?|advocate|"
    r"developer relations|devrel|evangelist|value|economist|economics|policy|"
    r"legal|counsel|ux|user experience|designer|commercial|partner|partnerships|"
    r"go[- ]to[- ]market|gtm|therap\w*|clinical|nurse|writer|editor|people)\b",
    re.I,
)

# Where a title's role ends and its team or place begins: "Data Scientist,
# Marketing", "ML Engineer - Policy & Safety", "Research Engineer: Agents".
# Parentheses stay with the role, so "Applied (AI) Value Engineer (DACH)" is
# still read as a value engineer.
_QUALIFIER_SPLIT = re.compile(r"\s*(?:,|:|\|| [-–—] )\s*")

_PLURAL = re.compile(r"\b(engineer|scientist|researcher|developer)s\b")


def _normalise(title: str) -> str:
    """Lower-case words separated by single spaces, padded for whole-word tests.

    Slashes and punctuation become spaces, so "Research Engineer/Research
    Scientist, Pre-training" contains " research engineer " and " research
    scientist " - the first version kept the slash, and Anthropic's
    slash-titled research roles were killed as "not a target role".
    """
    low = re.sub(r"[^a-z0-9+ ]+", " ", title.lower())
    low = _PLURAL.sub(r"\1", low)
    low = re.sub(r"\s+", " ", low).strip()
    return f" {low} "


_ROLES = sorted({_normalise(r).strip() for r in PROFILE["roles"]}, key=len, reverse=True)


def composite_role(title: str) -> str | None:
    """A domain word and a craft word in one title, e.g. "AI & System Engineer"."""
    domain = _DOMAIN.search(title)
    craft = _CRAFT.search(title)
    if domain and craft:
        return f"{domain.group(0).lower()} {craft.group(0).lower()}"
    return None


def _match(title: str) -> str | None:
    low = _normalise(title)
    for role in _ROLES:
        if f" {role} " in low:
            return role
    return composite_role(title)


def role_match(title: str) -> str | None:
    """The target role this title *is*, if any.

    The named list wins when it matches - its answer is the specific role.
    Otherwise the compositional rule catches the titles no finite list will
    ever contain. A customer-facing or non-engineering word vetoes the match
    when it is part of the role itself ("Solutions Architect", "Sales
    Engineer"), but not when it only names the team after a comma or dash:
    "Data Scientist, Marketing" and "ML Engineer - Policy & Safety" are a
    data scientist and an ML engineer, and the veto anywhere in the title
    killed both as "not a target role".
    """
    if not title:
        return None
    head = _QUALIFIER_SPLIT.split(title.strip(), maxsplit=1)[0]
    if _NOT_THE_JOB.search(head):
        return None
    named = _match(head)
    if named:
        return named
    # The role is not readable from the head alone (a Hacker News header, a
    # title that starts with the team), so the whole title is judged, and
    # then a veto word anywhere counts.
    if _NOT_THE_JOB.search(title):
        return None
    return _match(title)


def score(posting) -> tuple[float, str]:
    """0.0-1.0, with one sentence of evidence. Ranks; never kills.

    The weights are deliberately blunt. This orders a list that a human then
    reads; pretending to three decimal places of precision about whether a job
    is a good fit would be false confidence dressed as arithmetic.
    """
    text = posting.haystack
    bits: list[str] = []
    total = 0.0

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

    total = max(0.0, min(1.0, total))
    return round(total, 3), "; ".join(bits) if bits else "nothing in the profile matched"
