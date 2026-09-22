"""Employee, or will they take an invoice?

The design note calls this "the highest-value field in the whole system" and
the reason is section 4 of that note: a European company that will not sponsor
a visa will often happily engage a **contractor** anywhere in the world. No
immigration, no payroll entity, an invoice. From Pakistan that is frequently
the realistic route, so a posting that refuses sponsorship but welcomes B2B is
not a rejection — it is a different kind of lead.

It is also what turns one crawl into two products. The same data, asked "who
will take a contractor", answers "find me clients" instead of "find me a job".

This never kills a posting. It is a badge and a ranking weight, because the
user's answer to "is contract acceptable" was yes-alongside-employment, not
contract-only.
"""

from __future__ import annotations

import re

CONTRACTOR = "contractor"    # explicitly welcomes freelance / B2B
EITHER = "either"            # says both are possible
EMPLOYEE = "employee"        # explicitly an employment contract only
UNSTATED = "unstated"

_CONTRACTOR = (
    r"\bb2b\b",
    r"\bfreelanc(?:e|er|ing)\b",
    r"\bcontractor\b",
    r"contract (?:role|position|basis|work)\b",
    r"self[- ]employed",
    r"\bumbrella (?:company|contract)",
    r"independent contractor",
    r"(?:via|through) (?:a|your) (?:own )?(?:company|limited company|entity)",
    r"invoice (?:us|monthly|the company)",
    r"\bdaily rate\b",
    r"\bday rate\b",
    r"outside ir35",
    r"\bcontract of services\b",
    r"\bcontract type:?\s*(?:b2b|contract|freelance)",
)

_EMPLOYEE = (
    r"permanent (?:employment|contract|position|role)\b",
    r"employment contract only",
    r"this is (?:a )?(?:full[- ]time )?(?:permanent )?employ(?:ment|ee) (?:role|position)",
    r"we do not (?:work with|engage|hire) (?:contractors|freelancers)",
    r"no (?:contractors|freelancers|b2b|agencies)",
    r"(?:employee|staff) position only",
)

# Lever and Arbeitnow put this in a structured tag, which is worth reading
# before any regex: it is the company's own word for it.
_TAG_CONTRACT = {"contract", "contractor", "freelance", "b2b", "temporary", "interim"}
_TAG_PERMANENT = {"permanent", "full time", "full-time", "fulltime", "employee"}


def _hit(patterns, text: str) -> str | None:
    for pattern in patterns:
        found = re.search(pattern, text)
        if found:
            return found.group(0)
    return None


def classify(posting) -> tuple[str, str]:
    text = posting.haystack
    tags = {t.strip().lower() for t in posting.tags}

    contractor = _hit(_CONTRACTOR, text) or (
        next((t for t in tags if t in _TAG_CONTRACT), None)
    )
    employee = _hit(_EMPLOYEE, text) or (
        next((t for t in tags if t in _TAG_PERMANENT), None)
    )

    # Both present is the interesting case and it is common: "permanent
    # employment or B2B, your choice". That is the best possible answer, so it
    # must not be collapsed into whichever pattern happened to match first.
    if contractor and employee:
        return EITHER, f"both offered ({contractor} / {employee})"
    if contractor:
        return CONTRACTOR, contractor
    if employee:
        return EMPLOYEE, employee
    return UNSTATED, "employment form not stated"
