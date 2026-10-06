"""Employee, or will they take an invoice?

The design note calls this "the highest-value field in the whole system" and
the reason is section 4 of that note: a European company that will not sponsor
a visa will often happily engage a **contractor** anywhere in the world. No
immigration, no payroll entity, an invoice. From Pakistan that is frequently
the realistic route, so a posting that refuses sponsorship but welcomes B2B is
not a rejection - it is a different kind of lead.

This never kills a posting. It is a badge, and it decides whether the
contractor path can rescue a region-locked role into the Remote section.

**"B2B" is a contract form only when it is said about the contract.** The
first version matched the bare word, so "we are a B2B SaaS company" and
"a B2B marketplace" read as contractor offers - and that rescued a full-time,
EU-preferred role that refused sponsorship straight into the Remote tab.
"No B2B contracts, permanent employment only" read as *both* offered. Every
contractor phrase is now checked for a negation in front of it, and B2B
counts only next to a word about the engagement ("B2B contract", "on a B2B
basis", "B2B or UoP", "contract type: B2B").
"""

from __future__ import annotations

import re

from . import rx

CONTRACTOR = "contractor"    # explicitly welcomes freelance / B2B
EITHER = "either"            # says both are possible
EMPLOYEE = "employee"        # explicitly an employment contract only
UNSTATED = "unstated"

_CONTRACTOR = (
    r"\bb2b\s+(?:contract|agreement|cooperation|co-operation|basis|invoic\w*|model|engagement|"
    r"arrangement|terms|form|setup|option|rate)",
    # "on a B2B basis" is a contract; "we sell through B2B channels" and "a
    # B2B SaaS company" are a market. The words after B2B tell them apart.
    r"\b(?:on|via|through|under) (?:a )?b2b\b(?![- /&]*(?:saas|sales|market\w*|customers?|"
    r"clients?|compan\w*|software|products?|platforms?|space|segments?|business\w*|"
    r"e-?commerce|fintech|startups?|tech\w*|brands?|enterprises?|partner\w*|payments?|"
    r"leads?|growth|go[- ]to[- ]market|b2c|channels?|deals?|accounts?|solutions?|"
    r"services?|buyers?|sellers?|commerce|marketplaces?|retail|models?|focus))",
    r"\b(?:contract type|type of contract|employment type|form of employment|type of employment|"
    r"engagement)\s*:?\s*(?:[\w ]{0,30}(?:,|/|or)\s*)?b2b\b",
    r"\bb2b\s*(?:/|or|and|\+|,)\s*(?:uop|coe|employment contract|permanent|full[- ]time|umowa)",
    r"\b(?:uop|coe|employment contract|permanent contract|permanent employment|umowa o prac\w)"
    r"\s*(?:/|or|and|\+|,)\s*b2b\b",
    r"\bb2b\s*:\s*\d",
    r"\bfreelanc(?:e|er|ing)\s+(?:role|position|basis|contract|engagement|work|project|opportunity)",
    r"\b(?:as an?|hire an?|hiring an?|engage an?|work as an?|this is an?|join us as an?) "
    r"(?:independent |freelance |remote |full[- ]time |part[- ]time )?(?:contractor|freelancer)\b",
    r"\bindependent contractor",
    r"\bcontract(?:or)? (?:role|position|basis|engagement|agreement|opportunity)\b",
    r"\bcontract[- ]to[- ]hire\b",
    r"\bcontractors? (?:are )?welcome",
    r"\bself[- ]employed",
    r"\bumbrella (?:company|contract)",
    r"(?:via|through) (?:a|your) (?:own )?(?:company|limited company|ltd|entity)",
    r"\binvoice (?:us|monthly|the company)",
    r"\b(?:daily|day) rate\b",
    r"\boutside ir35",
    r"\bcontract of services\b",
    r"\b1099\b",
)

_EMPLOYEE = (
    r"permanent (?:employment|contract|position|role)\b",
    r"employment contract only",
    r"this is (?:a )?(?:full[- ]time )?(?:permanent )?employ(?:ment|ee) (?:role|position)",
    r"we do not (?:work with|engage|hire|accept) (?:contractors|freelancers|b2b)",
    r"\bno (?:contractors|freelancers|b2b|agencies)\b",
    r"(?:employee|staff) position only",
    r"\b(?:w-?2|full[- ]time employee|fte) (?:only|position|role)\b",
)

# A negation just before a contractor phrase turns it into its opposite:
# "no B2B contracts", "not a contract role", "we don't hire freelancers".
_NEGATION = re.compile(
    r"\b(?:no|not|never|without|don't|do not|doesn't|does not|cannot|can't|won't|isn't|is not)"
    r"\W+(?:\w+\W+){0,2}$")

# Lever and Arbeitnow put this in a structured tag, which is worth reading
# before any regex: it is the company's own word for it.
_TAG_CONTRACT = {"contract", "contractor", "freelance", "b2b", "temporary", "interim"}
_TAG_PERMANENT = {"permanent", "full time", "full-time", "fulltime", "employee"}


# "We focus on B2B." is the market again, with nothing after it to say so.
_MARKET_VERB = re.compile(
    r"\b(?:focus\w*|speciali[sz]\w*|sell\w*|serv(?:e|es|ing)|operat\w*|compet\w*|"
    r"expand\w*|position\w*|built|grow\w*)\W+(?:\w+\W+){0,2}$")


def _unnegated(patterns, text: str) -> str | None:
    for pattern in patterns:
        for found in rx(pattern).finditer(text):
            before = text[max(0, found.start() - 30):found.start()]
            if _NEGATION.search(before):
                continue
            if "b2b" in found.group(0) and _MARKET_VERB.search(before + found.group(0)
                                                                .split("b2b")[0]):
                continue
            return found.group(0)
    return None


def _hit(patterns, text: str) -> str | None:
    for pattern in patterns:
        found = rx(pattern).search(text)
        if found:
            return found.group(0)
    return None


def classify(posting) -> tuple[str, str]:
    text = posting.haystack
    tags = {t.strip().lower() for t in posting.tags}

    contractor = _unnegated(_CONTRACTOR, text) or (
        next((t for t in sorted(tags) if t in _TAG_CONTRACT), None)
    )
    employee = _hit(_EMPLOYEE, text) or (
        next((t for t in sorted(tags) if t in _TAG_PERMANENT), None)
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
