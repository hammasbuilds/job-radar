"""Where may the person actually sit?

The hardest of the five and the one that decides most outcomes. A posting
titled "Senior ML Engineer — Remote" whose sixth paragraph reads "you must be
based in Germany" is not remote in any sense useful to someone in Pakistan,
and the structured `remote` flag on every source in this project says True for
it.

So the source's own flag is never trusted on its own. It is a tiebreak, used
only when the text says nothing either way.

Five outcomes, and the order they are tested in matters: the most specific
restriction wins, because a posting will often say "remote" three times and
"within the EU" once, and the once is the operative sentence.
"""

from __future__ import annotations

import re

from . import places, rx

GLOBAL = "global"          # work from anywhere
REGION = "region"          # EU/EEA, Europe, EMEA — not Pakistan
COUNTRY = "country"        # one named country
HYBRID = "hybrid"
ONSITE = "onsite"
UNKNOWN = "unknown"

# The two ways a REGION verdict can be a guess rather than a reading. The
# pipeline gives these their own kill reason: "remote, scope not stated" is a
# different statement from "EU only", and filing it as "country-locked" put a
# reason on the trust screen that the posting never gave.
NO_SCOPE = "says remote, states no scope"
NO_SCOPE_FLAG = "source flags remote, text says nothing"

# Phrases are matched against title + location + body, lower-cased.
#
# Every pattern here was written against real postings fetched from the four
# sources, not invented. The ones that look oddly specific are the ones that
# were getting through.

_GLOBAL = (
    r"work from anywhere",
    r"fully remote,? (?:from )?anywhere",
    r"remote[, ]+(?:from )?anywhere in the world",
    r"anywhere in the world",
    r"globally remote",
    r"remote \(global\)",
    r"location[- ]independent",
    r"we are (?:a )?(?:fully )?(?:remote|distributed)[- ]first.{0,40}anywhere",
)

# "EU only" and friends. This is the single largest kill bucket in the corpus
# and the reason the tool exists: it reads as remote and is not open to us.
_REGION = (
    r"\b(?:eu|eea|european union)[- ]?(?:only|based|resident)",
    r"(?:must|need to|required to) (?:be |reside |live )?(?:based |located |resident )?(?:in|within) (?:the )?(?:eu|eea|europe)\b",
    r"within the (?:eu|eea|european union|european economic area)\b",
    r"remote (?:in|within|across) (?:the )?(?:eu|eea|europe|emea)\b",
    r"europe[- ]based",
    r"anywhere in europe",
    r"eligible to work in (?:the )?(?:eu|eea|europe)\b",
    r"\bemea\b.{0,20}only",
    r"(?:us|usa|united states|uk|canada)[- ](?:only|based)\b",
    r"authoriz(?:ed|ation) to work in the (?:us|united states|uk)\b",
)

_COUNTRY_NAMES = (
    "germany", "netherlands", "france", "spain", "portugal", "poland",
    "sweden", "denmark", "norway", "finland", "ireland", "italy", "belgium",
    "austria", "switzerland", "czechia", "czech republic", "romania",
    "united kingdom", "england", "estonia", "lithuania", "latvia", "greece",
    # Outside Europe. Without these, "Remote. You must be based in the US" and
    # "Must be located in Pakistan" read as "says remote, states no scope".
    "united states", "usa", "us", "america", "canada", "mexico", "brazil",
    "india", "pakistan", "uk", "israel", "australia", "singapore",
    "uae", "united arab emirates", "saudi arabia", "qatar",
)
_THE = r"(?:the )?"
_COUNTRY = tuple(
    rf"(?:must|need to|should|required to|have to|you'll need to|will need to) "
    rf"(?:be |reside |live |located |based |currently |physically )*"
    rf"(?:in|within) {_THE}{name}\b" for name in _COUNTRY_NAMES
) + tuple(
    rf"\bremote[, ]+(?:\(|-\s*|in\s+|within\s+)?{_THE}{name}\)?\b" for name in _COUNTRY_NAMES
) + tuple(
    rf"\b(?:candidates|applicants|you) (?:must |should |need to )?"
    rf"(?:reside|live|be located|be based) (?:in|within) {_THE}{name}\b" for name in _COUNTRY_NAMES
) + tuple(
    rf"\bbased in {_THE}{name}\b" for name in _COUNTRY_NAMES if name not in ("us", "uk")
) + (
    r"\bresidents? of \w+ only",
    r"you (?:must|will need to) (?:hold|have) (?:a|the) right to work in \w+",
)

_HYBRID = (
    r"\bhybrid\b",
    r"\d\s*(?:days?|x)\s*(?:a|per)\s*week in the office",
    r"in[- ]office \d\s*days",
    r"office[- ]based.{0,30}(?:some|partial) remote",
)

# "Virtual onsite" is an interview stage and "in-person offsite" is a team
# trip; neither says where the work is done. Lucia's fully remote MLOps role
# was read as onsite from "virtual onsite".
_ONSITE = (
    r"(?<!virtual )(?<!virtual-)\bon[- ]?site\b(?!\s*(?:interview|visit|event|meet|offsite|retreat|"
    r"day|gather|round|loop|stage|final|travel))",
    r"\bin[- ]person\b(?!\s*(?:interview|offsite|off-site|meet|event|gather|retreat|"
    r"team (?:week|event)|onboarding|workshop|conference))",
    r"relocation (?:is )?(?:required|mandatory|expected)",
    r"this (?:role|position) is not remote",
    r"no remote work",
    r"fully (?:office|onsite)[- ]based",
)

_REMOTE_WORD = re.compile(r"\bremote\b|\bwork from home\b|\bwfh\b|\bdistributed team\b")


def _hit(patterns, text: str) -> str | None:
    for pattern in patterns:
        found = rx(pattern).search(text)
        if found:
            return found.group(0)
    return None


# The location field is read by `places`, which parses compound strings and
# reports UNKNOWN rather than guessing. Two versions of this lived here as
# regexes over bare names and both failed open on anything compound —
# "Cardiff, London or Remote (UK)" became region-wide, and a country list
# missing Argentina turned "USA, Canada, Argentina" into region-wide too.
_PLACE_SCOPE = {
    places.GLOBAL: GLOBAL,
    places.REGION: REGION,
    places.COUNTRY: COUNTRY,
}


def _from_location(location: str) -> tuple[str, str] | None:
    scope, why = places.classify(location)
    if scope == places.UNKNOWN:
        return None
    return _PLACE_SCOPE[scope], why


def classify(posting) -> tuple[str, str]:
    """Return (scope, the phrase that decided it).

    The evidence string is returned with the verdict on purpose. A filter that
    says "rejected" without showing the sentence it read cannot be trusted or
    debugged, and the note this project came from makes the killed-with-reasons
    screen the trust mechanism of the whole tool.
    """
    text = posting.haystack

    # The location field first when it states a bare place. It is the most
    # reliable signal any source gives and it is structured, so no prose
    # pattern can beat it — and an onsite phrase elsewhere in the body should
    # not override "Remote (UK)" in the field that exists to say where.
    stated = _from_location(posting.location)
    if stated and not _hit(_ONSITE, text):
        return stated

    # Most specific first. A posting saying both "remote" and "must be in
    # Germany" is a Germany posting; testing "remote" first would call it
    # global and let exactly the wrong thing through.
    for patterns, scope in (
        (_ONSITE, ONSITE),
        (_COUNTRY, COUNTRY),
        (_REGION, REGION),
        (_HYBRID, HYBRID),
        (_GLOBAL, GLOBAL),
    ):
        phrase = _hit(patterns, text)
        if phrase:
            return scope, phrase.strip()

    # Nothing explicit. Now the source's own flag may speak, and a bare
    # "remote" with no stated restriction is treated as REGION rather than
    # GLOBAL: unrestricted global hiring is rare, and guessing generously here
    # fills the daily list with jobs that will not reply.
    if _REMOTE_WORD.search(text):
        return REGION, NO_SCOPE
    if posting.remote_hint:
        return REGION, NO_SCOPE_FLAG
    if posting.remote_hint is False:
        return ONSITE, "source flags non-remote"
    return UNKNOWN, "no location signal found"
