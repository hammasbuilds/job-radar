"""Will they sponsor, or do they need someone who can already work there?

This filter decides which of the route sections a posting lands in, so it is
the one the whole dashboard is organised around.

**Silence is the hard case and it is the common one.** Most postings say
nothing about sponsorship. Reading silence as "maybe" would put thousands of
jobs into the sponsorship section that will never reply; reading it as "no"
would throw away real opportunities, because plenty of companies that sponsor
simply do not advertise it. Silence is `SILENT`, a third value, never quietly
folded into either.

**Read one sentence at a time, and read the negation.** The first version
matched phrases anywhere in the text, so "Unfortunately, no sponsorship is
available" matched the *offer* "sponsorship is available", "EU Blue Card
holders only" matched the offer "blue card", and "we offer 30 days holiday, a
visa-friendly process" matched "offer ... visa" across thirty characters of
unrelated words. Now each sentence is tested on its own, an offer only counts
when no negation governs it, and a refusal can be written with the negation
after the noun ("Candidates requiring sponsorship will not be considered",
"Visa sponsorship: No").

**Citizenship is a refusal too, and the strictest one.** "Only nationals of a
NATO member state", "(Emirati National)", "EU citizens or holders of a
Belgian work permit", "must be a U.S. citizen", an ITAR or security-clearance
requirement: none mentions sponsorship, all of them close the door. They get
their own verdict, `NATIONALS`, because no route - remote, contractor or
Gulf - opens a door that is shut by passport.
"""

from __future__ import annotations

import re

SPONSORS = "sponsors"            # says it will
REFUSES = "refuses"              # will not sponsor / needs existing right to work
NATIONALS = "nationals_only"     # citizenship, nationality or clearance required
NOT_NEEDED = "not_needed"        # global remote: authorisation is moot
RELOCATION_HINT = "relocation_hint"
SILENT = "silent"

BLOCKING = (REFUSES, NATIONALS)

# Sentences end at . ! ? ; newlines and bullets. Abbreviations with inner dots
# are folded first, or "U.S. citizens" would split into "u.s." and "citizens".
_ABBREV = (
    (re.compile(r"\bu\.\s?s\.(?:\s?a\.)?", re.I), "US"),
    (re.compile(r"\bu\.\s?k\.", re.I), "UK"),
    (re.compile(r"\be\.g\.", re.I), "eg"),
    (re.compile(r"\bi\.e\.", re.I), "ie"),
)
_SENTENCE = re.compile(r"(?<=[.!?])\s+|[\n;•]+|\s\|\s")

_NEG = (r"(?:no|not|unable|cannot|can't|can not|won't|will not|do not|don't|"
        r"does not|doesn't|are not|aren't|is not|isn't|without|unfortunately|never|nor)")
_AUTH_WORD = r"(?:visas?|sponsor\w*|work permits?|blue cards?|work authori[sz]ation)"

# A negation that governs the sponsorship word: at most five words before it.
_NEGATED = re.compile(rf"\b{_NEG}\b(?:\W+\w+){{0,5}}?\W+{_AUTH_WORD}")
# "for every role", "not always": a partial statement, not a refusal. Anthropic
# writes "we aren't able to successfully sponsor visas for every role", which
# sits in the same paragraph as "We do sponsor visas!".
_PARTIAL = re.compile(r"\b(?:every|all|each|always|any) (?:role|position|candidate|case|country|location)s?\b"
                      r"|\bnot always\b|\bno matter\b|\bregardless\b|\bwhether or not\b")

_REFUSES = (
    _NEGATED,
    re.compile(r"(?:requir\w*|need\w*)\s+(?:\w+\s+){0,2}(?:visa\s+)?sponsorship\W+(?:\w+\W+){0,5}?"
               r"(?:not|ineligible|unable)"),
    re.compile(r"sponsorship(?:\s+(?:available|offered|provided))?\s*[:?-]\s*(?:no|none|not)\b"),
    re.compile(r"must (?:already )?(?:have|hold|possess|be in possession of) (?:the |a |an |valid |full |"
               r"existing |current |unrestricted |legal |permanent )*(?:right to work|work permit|"
               r"work authori[sz]ation|authori[sz]ation to work|work visa|residence permit|blue card)"),
    re.compile(r"must (?:currently )?be (?:legally |fully )?(?:authori[sz]ed|eligible|entitled|permitted|allowed) to work"),
    re.compile(r"(?:existing|valid|current|full|unrestricted) (?:right to work|work authori[sz]ation|work permit)"
               r"(?: in [\w ]{2,25})? (?:is )?(?:required|essential|mandatory|needed)"),
    re.compile(r"(?:right|authori[sz]ation|eligib\w+) to work in [\w .]{2,30}? (?:is )?(?:required|essential|mandatory)"),
    re.compile(r"eligible to work in [\w .]{2,30}? without (?:\w+ )?sponsorship"),
    re.compile(r"(?:require|requires|requiring) (?:the |a |an )?(?:right|authori[sz]ation|permission) to work"),
    re.compile(r"\b(?:blue card|work permit|visa|residence permit)s? holders? only"),
    re.compile(r"only (?:consider|accept|hire|employ) (?:\w+ ){0,3}(?:who|with) (?:already )?(?:have|hold|possess)"
               r" (?:\w+ ){0,3}(?:right to work|work permit|authori[sz]ation)"),
)

_COUNTRY_ADJ = (r"(?:us|american|united states|uk|british|eu|european|german|french|dutch|swiss|"
                r"canadian|australian|israeli|indian|emirati|uae|saudi|qatari|kuwaiti|omani|bahraini|"
                r"nato|belgian|polish|irish|swedish)")
_NATIONALS = (
    re.compile(rf"\b{_COUNTRY_ADJ} (?:citizens?(?:hip)?|nationals?|nationality|passport holders?)\b"),
    re.compile(r"\bcitizens? (?:of|in) (?:the |a |an )?[\w ]{2,30}"),
    re.compile(r"\bnationals? of (?:the |a |an )?[\w ]{2,30}"),
    re.compile(r"\b(?:emiratis?|saudis?|qataris?|kuwaitis?|omanis?|bahrainis?) only\b"),
    re.compile(r"\b(?:emiratisation|emiratization|saudisation|saudization|nationals only|citizens only)\b"),
    re.compile(r"\bcitizenship (?:is )?(?:required|mandatory|essential)\b"),
    re.compile(r"\b(?:must|required to|need to|able to|eligible to) (?:\w+ ){0,3}(?:obtain|hold|have|maintain|get)"
               r" (?:an? |the )?(?:active |current |valid )?(?:us |uk |government |federal )?"
               r"(?:security|secret|top secret|ts/sci|sc|dv|nv1|baseline) clearance"),
    re.compile(r"\b(?:security|government|secret|top secret|ts/sci) clearance (?:is )?(?:required|mandatory)"),
    re.compile(r"\bus persons?\b|\bitar\b"),
    re.compile(r"\bgreen card holders?\b|\bpermanent residents?\b"),
    # Singapore and Malaysia write it as "Citizens or SPR" / "Singaporean or PR" / "Malaysian only".
    re.compile(r"\b(?:singapore(?:an)?|malaysian?) citizens?(?: or| and|/| &) ?(?:s?pr|permanent)\b"
               r"|\bsingaporeans?(?: or| and|/) ?(?:s?pr)\b|\b(?:open to|only for) "
               r"(?:singapore(?:an)?|malaysian|emirati|saudi|qatari) (?:citizens|nationals)\b"
               r"|\b(?:malaysians?|singaporeans?|emiratis?|saudis?) only\b"),
)
# Equal-opportunity boilerplate names citizenship as something *not* held
# against you. It is the opposite of a restriction.
_NOT_A_RESTRICTION = re.compile(
    r"regardless of|without regard|irrespective of|all nationalities|any nationality|"
    r"not (?:required|necessary|needed|a requirement)|discriminat|equal opportunit|"
    r"protected (?:class|characteristic|veteran)|national origin|e-verify")

_SPONSORS = (
    re.compile(r"\b(?:we|company|they|employer|team)\s+(?:will\s+|do\s+|can\s+|are able to\s+|are happy to\s+|"
               r"would\s+|may\s+|also\s+)?(?:offer|provide|support|sponsor|cover|handle|arrange)s?\s+"
               r"(?:\w+\s+){0,3}?(?:visas?|work permits?|visa sponsorship|sponsorship|blue cards?|immigration)\b"),
    re.compile(r"\bvisa sponsorship (?:is |will be |can be )?(?:available|offered|provided|possible|"
               r"included|supported|on offer)"),
    re.compile(r"\bsponsorship (?:is |will be |can be )?(?:available|possible|offered|provided)"),
    re.compile(r"\bsponsor(?:ship)? (?:for |of )?(?:your |the |a )?(?:visas?|work permits?|blue cards?)"),
    re.compile(r"\b(?:happy|able|willing|glad|open) to sponsor\b"),
    re.compile(r"\b(?:can|will|we)\s+(?:help|assist|support)\s+(?:you\s+)?(?:with|in|to)\s+(?:\w+\s+){0,3}?"
               r"(?:visas?|work permits?|blue cards?|immigration)"),
    re.compile(r"\b(?:full |complete )?(?:visa|immigration) (?:support|assistance|sponsorship provided)\b"),
    re.compile(r"\bvisa sponsorship\s*(?:\+|&|and)\s*(?:relocation|30% ruling)"),
    re.compile(r"\bvisa\s*(?:\||/|&|\+|and)\s*relocation\b"),
    re.compile(r"\bsponsorship\s*[:?-]\s*(?:yes|available|offered)\b"),
)
# A bare "VISA" field in a Hacker News header ("Acme | ML Engineer | London |
# ONSITE | VISA") is that thread's convention for "we sponsor".
_HEADER_VISA = re.compile(r"(?:^|\|)\s*visa(?: sponsorship)?(?: (?:ok|available|provided|possible))?\s*(?:\||$)")

# Relocation support is NOT sponsorship. Companies offer relocation to people
# who already hold the right to work - it pays for the moving van, not the
# visa - so it is kept as a weaker signal that never alone puts a posting in
# the sponsorship section.
_RELOCATION_ONLY = (
    re.compile(r"relocation (?:package|support|assistance|bonus|allowance|budget|stipend)"),
    re.compile(r"we (?:offer|provide|cover|pay for) relocation"),
)


def sentences(text: str) -> list[str]:
    """Lower-cased sentences, with dotted abbreviations folded first."""
    for pattern, repl in _ABBREV:
        text = pattern.sub(repl, text)
    return [s.strip().lower() for s in _SENTENCE.split(text) if s and s.strip()]


def _refusal(sentence: str) -> str | None:
    if _PARTIAL.search(sentence):
        return None
    for pattern in _REFUSES:
        found = pattern.search(sentence)
        if found:
            return found.group(0)
    return None


def _nationals(sentence: str) -> str | None:
    if _NOT_A_RESTRICTION.search(sentence):
        return None
    for pattern in _NATIONALS:
        found = pattern.search(sentence)
        if found:
            return found.group(0)
    return None


def _offer(sentence: str) -> str | None:
    for pattern in _SPONSORS:
        found = pattern.search(sentence)
        if not found:
            continue
        # An offer governed by a negation is not an offer: "we are not able to
        # provide visa sponsorship" contains "provide visa sponsorship".
        before = sentence[:found.end()]
        if _NEGATED.search(before) and not _PARTIAL.search(sentence):
            continue
        return found.group(0)
    return None


def classify(posting, scope: str | None = None) -> tuple[str, str]:
    """Return (status, the phrase that decided it).

    Order: nationality restrictions, then refusals, then offers. Postings that
    mention both an offer and a restriction nearly always read "we sponsor
    visas for some roles, but for this one you must already have the right to
    work" - the restriction is the operative half.
    """
    header = posting.text.split("\n", 1)[0] if posting.source == "hn" else ""
    parts = sentences(f"{posting.title}\n{posting.location}\n{posting.text}")

    for sentence in parts:
        phrase = _nationals(sentence)
        if phrase:
            return NATIONALS, phrase.strip()
    for sentence in parts:
        phrase = _refusal(sentence)
        if phrase:
            return REFUSES, phrase.strip()
    for sentence in parts:
        phrase = _offer(sentence)
        if phrase:
            return SPONSORS, phrase.strip()
    for line in (posting.title, header):
        if line and _HEADER_VISA.search(line.lower()):
            return SPONSORS, "VISA in the header"

    # Work authorisation is a question about *being in the country*. For a
    # genuinely global-remote role it does not arise, and marking it SILENT
    # would imply a doubt that is not real.
    if scope == "global":
        return NOT_NEEDED, "global remote - no work permit at issue"

    for sentence in parts:
        for pattern in _RELOCATION_ONLY:
            found = pattern.search(sentence)
            if found:
                return RELOCATION_HINT, (f"{found.group(0)} - relocation offered, "
                                         "sponsorship not stated")
    return SILENT, "sponsorship not mentioned"
