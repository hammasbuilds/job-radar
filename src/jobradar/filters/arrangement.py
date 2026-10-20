"""How the work is arranged: where (onsite, hybrid, remote) and on what terms (full-time,
contract, or a small contract - part-time, hourly, a few weeks' project).

Where comes from the remote filter's scope, which already reads the prose; this only names it
in the words the dashboard filters use. Terms come from the employment filter plus one more
reading: a *small* contract, the kind the AI training platforms and short research projects
post, which a full-time seeker and a side-income seeker want to see or hide separately.
"""

from __future__ import annotations

import re

from . import employment, remote

ONSITE, HYBRID, REMOTE, NOT_STATED = "Onsite", "Hybrid", "Remote", "Not stated"
FULL_TIME, CONTRACT, SMALL, UNSTATED = "Full-time", "Contract", "Small contract", "Not stated"

_SMALL = re.compile(
    # Each phrase names the work arrangement itself. Bare "short term" matched Anthropic's
    # "In the short term, we have focused on..." and made a research role a small contract;
    # bare "project-based" matched "project-based skill transfer" in a full-time job's benefits.
    r"\b(?:(?:paid )?hourly (?:rate|pay|basis|wage|contract)|paid hourly|"
    r"per hour|/\s?h(?:ou)?r\b|"
    r"short[- ]term (?:contract|project|role|position|engagement|assignment|work|gig)|"
    r"\d+[- ]?(?:to[- ]\d+[- ]?)?weeks?[- ](?:contract|project|engagement|assignment)|"
    r"on a (?:per[- ])?project basis|"
    r"project[- ]based (?:contract|role|position|engagement|work|assignment|basis|pay)|"
    r"task[- ]based (?:work|pay|contract)|per task|gig work|"
    r"set your own (?:hours|schedule)|freelance project)\b",
    re.I,
)
# "3-month contract" is small; "12-month fixed-term contract" is an ordinary contract job.
_MONTHS = re.compile(
    r"\b(\d{1,2})[- ]?(?:to[- ](\d{1,2})[- ]?)?months?[- ](?:fixed[- ]term )?"
    r"(?:contract|project|engagement|assignment)\b", re.I)
SMALL_MONTHS = 6
_FULL = re.compile(r"\b(?:full[- ]time|permanent|fulltime|unbefristet|vollzeit)\b", re.I)


def workplace(scope: str) -> str:
    if scope in (remote.GLOBAL, remote.REGION, remote.COUNTRY):
        return REMOTE
    if scope == remote.HYBRID:
        return HYBRID
    if scope == remote.ONSITE:
        return ONSITE
    return NOT_STATED


# "10-20 hours a week" is a small contract; "40 hours a week" is a full-time fellowship. The
# number decides, so it is read rather than matched: the first version called the Anthropic
# Fellows Program a small contract on "40 hours a week", and "flexible hours" in a benefits list
# made full-time roles small contracts too.
_HOURS = re.compile(r"\b(\d{1,2})\s*(?:-|to)?\s*(\d{1,2})?\s*hours? (?:a|per) week\b", re.I)


# "Part-time" in a body is usually about something else - "internships or part-time roles count"
# as experience, "full-time and part-time study modes" - so in the body it must describe this
# role; in the title or the source's own tags it is trusted.
_PART = re.compile(r"\bpart[- ]time\b", re.I)
_PART_BODY = re.compile(
    r"\b(?:(?:this|the) (?:is a |role is |position is )?part[- ]time|"
    r"part[- ]time (?:position|contract|basis|engagement|freelance|assignment)|"
    r"on a part[- ]time basis|work part[- ]time)\b",
    re.I,
)


def terms(posting, form: str) -> tuple[str, str]:
    """(terms, the phrase that decided it)."""
    head = " ".join([posting.title or "", " ".join(posting.tags or ())])
    part = _PART.search(head) or _PART_BODY.search(posting.text or "")
    if part:
        return SMALL, part.group(0)
    # The board's own employment type outranks a phrase in the body: a role the employer
    # tagged full-time is not a small contract because its benefits mention a project.
    tagged_full = _FULL.search(head.replace("_", "-").replace("FullTime", "full-time"))
    blob = " ".join([head, posting.text or ""])
    if not tagged_full:
        small = _SMALL.search(blob)
        if small:
            return SMALL, small.group(0)
        for hours in _HOURS.finditer(blob):
            most = int(hours.group(2) or hours.group(1))
            if most <= 30:
                return SMALL, hours.group(0)
        for months in _MONTHS.finditer(blob):
            if int(months.group(2) or months.group(1)) <= SMALL_MONTHS:
                return SMALL, months.group(0)
            return CONTRACT, months.group(0)
    if form in (employment.CONTRACTOR, employment.EITHER):
        return CONTRACT, "contract or freelance welcome"
    full = _FULL.search(blob)
    if full or form == employment.EMPLOYEE:
        return FULL_TIME, full.group(0) if full else "employment contract"
    return UNSTATED, "terms not stated"
