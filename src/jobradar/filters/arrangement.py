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
    r"\b(?:part[- ]time|hourly|per hour|an hour|/\s?h(?:ou)?r\b|"
    r"short[- ]term|\d+[- ]?(?:to[- ]\d+[- ]?)?(?:week|month)s?[- ](?:contract|project|"
    r"engagement|assignment)|project[- ]based|task[- ]based|per task|gig|"
    r"flexible hours|set your own (?:hours|schedule)|freelance project|"
    r"(?:\d+|ten|twenty)\s*(?:-|to)?\s*\d*\s*hours? (?:a|per) week)\b",
    re.I,
)
_FULL = re.compile(r"\b(?:full[- ]time|permanent|fulltime|unbefristet|vollzeit)\b", re.I)


def workplace(scope: str) -> str:
    if scope in (remote.GLOBAL, remote.REGION, remote.COUNTRY):
        return REMOTE
    if scope == remote.HYBRID:
        return HYBRID
    if scope == remote.ONSITE:
        return ONSITE
    return NOT_STATED


def terms(posting, form: str) -> tuple[str, str]:
    """(terms, the phrase that decided it)."""
    blob = " ".join([posting.title or "", " ".join(posting.tags or ()), posting.text or ""])
    small = _SMALL.search(blob)
    if small:
        return SMALL, small.group(0)
    if form in (employment.CONTRACTOR, employment.EITHER):
        return CONTRACT, "contract or freelance welcome"
    full = _FULL.search(blob)
    if full or form == employment.EMPLOYEE:
        return FULL_TIME, full.group(0) if full else "employment contract"
    return UNSTATED, "terms not stated"
