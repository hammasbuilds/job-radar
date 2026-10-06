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

from . import rx

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

# Ordered from most senior to most junior, and the first pattern that matches
# wins: "Senior Staff Engineer" is staff and "Lead Data Scientist, Graduate
# Programme" is lead. Reading the senior word first is the conservative
# choice for a list that keeps only entry-to-mid roles. A title that states a
# *range* ("Junior to Senior ML Engineer", "Junior/Mid Data Scientist") is
# handled before this table by `_RANGE`: it is open to the junior end.
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
    # "Member of Technical Staff" is the flat title AI labs give everyone,
    # new graduates included. Read as the rank "staff" it could never pass,
    # although the owner lists it as a target role.
    r"technical staff",
)

_RANGE = re.compile(
    r"\b(?:junior|jr|entry[- ]level|graduate|mid(?:[- ]level)?)\s*(?:to|-|–|/|or|&|and)\s*"
    r"(?:mid(?:[- ]level)?|senior|sr|intermediate)\b"
)


def classify(title: str) -> tuple[str, str]:
    """(level, the word that decided it). MID when no level word appears."""
    low = f" {title.lower()} "
    for pattern in _NOT_A_RANK:
        low = rx(pattern).sub(" ", low)

    ranged = _RANGE.search(low)
    if ranged:
        word = ranged.group(0).strip()
        return (MID if word.startswith("mid") else JUNIOR), word

    for level, patterns in _LEVELS:
        for pattern in patterns:
            found = rx(pattern).search(low)
            if found:
                return level, found.group(0).strip()
    return MID, "no level stated"


# --- years demanded ---------------------------------------------------------
#
# A title is only half the answer. "AI Engineer" reads as mid-level and then
# asks for eight years in paragraph three, which is a senior role that forgot
# to say so in its title.
#
# **The requirement is the largest number the posting *requires*, not the
# smallest it mentions.** The first version took the minimum across all
# mentions, so "5+ years of software engineering, including 2+ with LLMs"
# became 2 and three roles asking for five to eight years reached the list.
# Every required mention is a bar the candidate has to clear, so the highest
# one is the bar. A number in a nice-to-have sentence ("8 years would be
# ideal") is a wish, not a bar, and is ignored; a range counts from its low
# end ("3-5 years" is 3).

_WORD_NUM = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "twelve": 12, "fifteen": 15,
}

_YEARS = re.compile(
    r"(\d{1,2}|one|two|three|four|five|six|seven|eight|nine|ten|twelve|fifteen)"
    r"(?:\s*(?:\+|-?\s*plus))?"
    r"(?:\s*(?:-|–|to)\s*\d{1,2})?"
    r"\s*\+?\s*(?:years?|yrs?)\b['’]?",
    re.I,
)

# What must come right after "N years" for it to be about the candidate:
# "of experience", "in ML", "as an engineer", "building ...", "industry".
_AFTER = re.compile(
    r"^\s*(?:\+\s*)?(?:of\s+)?(?:(?:relevant|professional|industry|industrial|hands[- ]on|practical|"
    r"proven|commercial|post[- ]grad\w*|full[- ]time|progressive|working|work|combined|total|"
    r"prior|previous|demonstrated|applied|research|engineering|software|production)\W+){0,3}"
    r"(?:experience|exp\b|in\b|as\b|with\b|working|building|developing|designing|leading|"
    r"writing|shipping|running|delivering|deploying|managing|of\s+(?!history|operation|"
    r"existence|funding|growth|success|age|data)\w+|industry|professional|hands|at\b|within\b|"
    r"post|doing|coding|programming|(?:is |are )?(?:required|minimum|needed|essential|must))",
    re.I,
)
# "backed by 25 years of developer tooling expertise", "our 15 years in
# fintech": the company's experience, not the candidate's. It killed a
# founding ML role as "wants 25+ years".
_COMPANY_BEFORE = re.compile(
    r"(?:backed by|built on|draw(?:s|ing)? on|leverag\w+|\bour)\s+"
    r"(?:over |more than |nearly |almost |about |around )?$", re.I)
# "for 10 years", "for over a decade": how long the company has been at it.
_FOR_DURATION = re.compile(r"\bfor (?:over |more than |nearly |almost |about |around )?$", re.I)
# ... or what comes right before it: "experience: 5+ years", "at least",
# "minimum of", "requires".
_BEFORE = re.compile(
    r"(?:experience|exp|at least|minimum(?: of)?|min\.?|requires?|required|need|"
    r"bring|have|with|over|more than)\W{0,3}(?:\w+\W+){0,2}$",
    re.I,
)
# Company history and contract terms that look like a requirement.
_NOT_A_REQUIREMENT = re.compile(
    r"(?:founded|established|since|ago|history|for the (?:past|last)|in the (?:past|last|next|first)|"
    r"within the (?:first|next)|contract (?:length|duration)|every|anniversary|old\b|age\b|"
    r"we(?:'ve| have) (?:been|spent)|over the (?:past|last))",
    re.I,
)
_PREFERRED = re.compile(
    r"prefer|nice[- ]to[- ]have|bonus|ideal(?:ly)?|a plus|is a plus|plus if|desirabl|"
    r"advantage|great if|would be great|not required|not a must|optional",
    re.I,
)
_SENTENCE = re.compile(r"(?<=[.!?])\s+|\n+|;|•")


def _value(raw: str) -> int | None:
    raw = raw.lower()
    value = _WORD_NUM.get(raw) or (int(raw) if raw.isdigit() else None)
    return value if value is not None and 0 < value <= 25 else None


def years_required(text: str) -> int | None:
    """The experience the posting requires, in years, or None if it states none."""
    required: list[int] = []
    for sentence in _SENTENCE.split(text or ""):
        preferred = bool(_PREFERRED.search(sentence))
        for match in _YEARS.finditer(sentence):
            before = sentence[max(0, match.start() - 40):match.start()]
            after = sentence[match.end():match.end() + 60]
            if _NOT_A_REQUIREMENT.search(before[-25:] + " " + after[:25]):
                continue
            if _FOR_DURATION.search(before) and "experience" not in after[:30].lower():
                continue
            if _COMPANY_BEFORE.search(before):
                continue
            if not (_AFTER.search(after) or _BEFORE.search(before)):
                continue
            value = _value(match.group(1))
            if value is None:
                continue
            if preferred:
                continue
            required.append(value)
    return max(required) if required else None


