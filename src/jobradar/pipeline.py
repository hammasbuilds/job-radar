"""Fetch, dedup, judge, route into the two sections — and count the kills.

The two sections are the organising decision of this tool:

  **SPONSORSHIP** — they will sponsor a visa, so relocation is the route.
  **REMOTE**      — you stay where you are, so the question is whether they
                    can hire someone outside their country at all.

A posting can qualify for both, and when it does it appears in both. Forcing a
single bucket would hide the best outcomes, which are precisely the roles that
will either relocate you or take you remote.

**Every filter publishes its kill rate.** That is the house style and it is
also the honest way to run a tool whose value is rejection: a filter nobody can
audit is a filter that is quietly throwing away good jobs. `Funnel` records
how many entered, how many each stage removed and why, and the README prints
it.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .filters import authorisation, employment, fit, places, remote, seniority, timezone
from .profile import ACCEPT_LEVELS, MAX_YEARS

SPONSORSHIP = "sponsorship"
REMOTE = "remote"

# Geographic sections, alongside the two route sections above. A posting can
# be in several: a Dubai-and-London role is genuinely two opportunities, and
# a remote EU role that sponsors appears under europe, remote and sponsorship.
#
# These are kept even when no route in exists, because "who is hiring AI in
# the Gulf" is a useful question on its own — you may know somebody, or the
# company may answer an email. A posting with a region but no route is marked
# rather than killed.
GULF = places.R_GULF
EUROPE = places.R_EUROPE
PAKISTAN = places.R_PAKISTAN

REGIONS = (GULF, EUROPE, PAKISTAN)
SECTIONS = (SPONSORSHIP, REMOTE, *REGIONS)

# Below this the posting is not worth a line in a list a human reads daily.
MIN_SCORE = 0.30


@dataclass
class Funnel:
    """What went in, what came out, and what each stage removed.

    Kept as counts plus reasons rather than just a final number, because
    "10,000 postings became 23" is only believable if you can see where the
    9,977 went.
    """

    fetched: int = 0
    after_dedup: int = 0
    duplicates: int = 0
    killed: dict[str, int] = field(default_factory=dict)
    sections: dict[str, int] = field(default_factory=dict)
    # The rejected postings themselves, not just the counts. The note calls
    # the Killed screen "the trust screen": silent drops destroy confidence,
    # and a visible "rejected: remote EU-only" with an override does not.
    # Keeping them is also the only way to audit for false negatives, which
    # for a tool whose entire job is rejection is the error that matters.
    rejected: list = field(default_factory=list)

    def kill(self, posting, reason: str) -> None:
        self.killed[reason] = self.killed.get(reason, 0) + 1
        posting.section = ""
        posting.verdict["killed_by"] = reason
        self.rejected.append(posting)

    @property
    def surviving(self) -> int:
        return sum(self.sections.values())

    def as_lines(self) -> list[str]:
        out = [
            f"{self.fetched:>7,}  fetched",
            f"{self.after_dedup:>7,}  after dedup            "
            f"(-{self.duplicates:,}, {self._pct(self.duplicates, self.fetched)})",
        ]
        running = self.after_dedup
        for reason, count in sorted(self.killed.items(), key=lambda kv: -kv[1]):
            running -= count
            out.append(f"{running:>7,}  after {reason:<22} (-{count:,}, "
                       f"{self._pct(count, self.after_dedup)})")
        for name, count in sorted(self.sections.items()):
            out.append(f"{count:>7,}  in section: {name}")
        return out

    @staticmethod
    def _pct(part: int, whole: int) -> str:
        return f"{part / whole:.1%} of input" if whole else "n/a"


def judge(posting) -> dict:
    """Run all five filters over one posting. Never mutates the verdict later."""
    scope, scope_why = remote.classify(posting)
    auth, auth_why = authorisation.classify(posting, scope)
    form, form_why = employment.classify(posting)
    zone, zone_why = timezone.classify(posting)
    score, fit_why = fit.score(posting)
    where = places.regions_of(posting.location) or places.regions_of(posting.title)
    level, level_why = seniority.classify(posting.title)
    years = seniority.years_required(posting.text)

    return {
        "regions": sorted(where),
        "role": fit.role_match(posting.title) or "",
        "level": level, "level_why": level_why,
        "years": years,
        "years_why": (f"asks for {years}+ years" if years
                      else "no experience requirement stated"),
        "scope": scope, "scope_why": scope_why,
        "auth": auth, "auth_why": auth_why,
        "employment": form, "employment_why": form_why,
        "timezone": zone, "timezone_why": zone_why,
        "score": score, "fit_why": fit_why,
    }


def sections_for(verdict: dict) -> list[str]:
    """Which of the two sections this posting belongs in. May be both, or neither.

    **Sponsorship** needs an explicit offer. Silence does not qualify: the
    whole point of the section is roles where relocation is actually on the
    table, and filling it with maybes makes it as useless as an unfiltered
    search.

    **Remote** needs a role that can be done from outside the company's
    country. A contractor arrangement qualifies a posting that would otherwise
    fail on work authorisation — that is the contractor path from section 4 of
    the note, and it is why employment form is read before this decision.
    """
    out = []

    if verdict["auth"] == authorisation.SPONSORS:
        out.append(SPONSORSHIP)

    scope = verdict["scope"]
    if scope in (remote.GLOBAL, remote.REGION):
        contractor = verdict["employment"] in (employment.CONTRACTOR, employment.EITHER)
        # A region-locked role is out of reach on an employment contract —
        # "EU only" means resident in the EU. As a contractor it is reachable,
        # because there is no residency requirement in an invoice.
        #
        # A *country*-locked role is not rescued this way, which is why COUNTRY
        # is absent from the test above. "Remote (UK)" means they want someone
        # in the UK; a contractor in Lahore does not satisfy that, and letting
        # the contractor path override it put three country-locked fellowships
        # that said "we do not sponsor" straight onto the dashboard.
        if scope == remote.GLOBAL or contractor or verdict["auth"] == authorisation.SPONSORS:
            out.append(REMOTE)

    # Geographic sections are about *where the work is*, not about whether a
    # route in exists. A Gulf role that will not sponsor still belongs in the
    # Gulf tab: the question that tab answers is "who is hiring AI there", and
    # a route can be made by an email that a filter cannot see.
    out += [r for r in verdict.get("regions", []) if r in REGIONS]
    return out


def run(postings: list, min_score: float = MIN_SCORE) -> tuple[list, Funnel]:
    """The whole pipeline. Returns (kept postings, the funnel)."""
    from .dedup import deduplicate

    funnel = Funnel(fetched=len(postings))
    kept_postings, removed = deduplicate(postings)
    funnel.duplicates = removed
    funnel.after_dedup = len(kept_postings)

    survivors = []
    for posting in kept_postings:
        verdict = judge(posting)
        posting.verdict = verdict
        posting.score = verdict["score"]
        posting.evidence = verdict["fit_why"]

        # The title must be one of the target roles. This is a harder rule
        # than a score threshold and it is the right one: the roles were
        # chosen deliberately, and a score lets a "Senior Customer Engineer,
        # Saudi Arabia" into the Gulf tab on body vocabulary alone. Matching
        # the words of a field is not the same as being a job in it.
        #
        # It is by far the largest filter in the funnel, which is expected —
        # most of what a company advertises is not an AI role.
        if not verdict["role"]:
            funnel.kill(posting, "not one of the target roles")
            continue

        # Entry to mid only. Senior, staff and lead titles are most of what is
        # advertised and score identically on every other filter, so ranking
        # them down would just bury the junior roles further down one list.
        if verdict["level"] not in ACCEPT_LEVELS:
            funnel.kill(posting, f"{verdict['level']} level")
            continue

        # Fresher to three years. Checked against the body, not the title,
        # because the two disagree often: a role titled "AI Engineer" that
        # asks for eight years is senior and did not say so.
        if verdict["years"] is not None and verdict["years"] > MAX_YEARS:
            funnel.kill(posting, f"wants {verdict['years']}+ years")
            continue
        if verdict["score"] < min_score:
            funnel.kill(posting, "below fit threshold")
            continue

        where = sections_for(verdict)
        in_region = any(r in REGIONS for r in where)

        # The route kills below decide whether *you* can take the job. They are
        # skipped for a posting that sits in a geographic section, because that
        # tab answers a different question — who is hiring AI there — and an
        # onsite Gulf role is a true answer to it even when no filter can see a
        # way in. It still shows its scope and sponsorship badges, so the
        # difference is visible rather than assumed.
        if not in_region:
            if verdict["scope"] == remote.ONSITE and verdict["auth"] != authorisation.SPONSORS:
                funnel.kill(posting, "onsite, no sponsorship")
                continue
            if verdict["scope"] == remote.HYBRID and verdict["auth"] != authorisation.SPONSORS:
                funnel.kill(posting, "hybrid, no sponsorship")
                continue
            if verdict["auth"] == authorisation.REFUSES and verdict["scope"] != remote.GLOBAL:
                if verdict["employment"] not in (employment.CONTRACTOR, employment.EITHER):
                    funnel.kill(posting, "refuses sponsorship")
                    continue

        if not where:
            # A relocation offer without a sponsorship statement gets its own
            # reason rather than being swept into the country-locked pile.
            # These are the best leads that get rejected — a senior role in
            # Berlin offering a relocation package is exactly what somebody
            # reviewing the Killed screen would want to override — and burying
            # them under the largest bucket is how a rejection engine loses
            # the user's trust.
            if verdict["auth"] == authorisation.RELOCATION_HINT:
                funnel.kill(posting, "relocation offered, sponsorship unstated")
            else:
                funnel.kill(posting, "no route in (country-locked)")
            continue

        posting.section = ",".join(where)
        for name in where:
            funnel.sections[name] = funnel.sections.get(name, 0) + 1
        survivors.append(posting)

    # Freshness is a ranking weight, not metadata: a perfect match from three
    # weeks ago ranks below a good match from this morning.
    survivors.sort(key=lambda p: (-_ranked(p), p.company.lower()))
    return survivors, funnel


def _ranked(posting) -> float:
    age = posting.age_days
    if age is None:
        freshness = 0.5
    elif age <= 2:
        freshness = 1.0
    elif age <= 7:
        freshness = 0.8
    elif age <= 21:
        freshness = 0.5
    else:
        freshness = 0.2
    return posting.score * 0.75 + freshness * 0.25
