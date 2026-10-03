"""Fetch, dedup, judge, route into sections - and count the kills.

The route sections are the organising decision of this tool:

  **SPONSORSHIP** - they will sponsor a visa, so relocation is the route.
  **REMOTE**      - you stay where you are: the role is open worldwide, or it
                    is region-locked and they will engage a contractor.

The geographic sections (Europe, Gulf, Pakistan) group the same postings by
where the work is. **They obey the same route rules**; an earlier version
exempted them from every route kill, so a UK role that said "unable to provide
visa sponsorship" and a US role that required US work authorisation (filed in
Europe as "Cambridge") sat on the dashboard. What differs per region is only
what counts as a route in:

  Pakistan  - none is needed. The candidate lives there.
  Gulf      - employer-sponsored work visas are how every expatriate is hired,
              so silence is a route. An explicit refusal or a nationals-only
              role (Emiratisation, Saudisation) is not.
  elsewhere - an explicit sponsorship offer, or a remote route as above.

A nationality, citizenship or security-clearance requirement closes every
route, remote and contractor included.

**Every filter publishes its kill rate.** `Funnel` records how many entered,
how many each stage removed and why, in pipeline order.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .filters import authorisation, employment, fit, places, remote, seniority, timezone
from .profile import ACCEPT_LEVELS, MAX_YEARS

SPONSORSHIP = "sponsorship"
REMOTE = "remote"
GULF = places.R_GULF
EUROPE = places.R_EUROPE
PAKISTAN = places.R_PAKISTAN

REGIONS = (GULF, EUROPE, PAKISTAN)
SECTIONS = (SPONSORSHIP, REMOTE, *REGIONS)

# Kill reasons, grouped by the stage that produces them, in pipeline order.
ROLE = "not one of the target roles"
STAGES = ("role", "level", "years", "route")


def stage_of(reason: str) -> str:
    """Which stage produced a kill reason."""
    if reason == ROLE:
        return "role"
    if reason.endswith(" level"):
        return "level"
    if reason.startswith("wants ") and reason.endswith(" years"):
        return "years"
    return "route"


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
    # The rejected postings themselves, not just the counts: the Killed screen
    # is the trust screen, and the only place a false negative can be found.
    rejected: list = field(default_factory=list)

    def kill(self, posting, reason: str) -> None:
        self.killed[reason] = self.killed.get(reason, 0) + 1
        posting.section = ""
        posting.verdict["killed_by"] = reason
        self.rejected.append(posting)

    @property
    def surviving(self) -> int:
        return self.after_dedup - sum(self.killed.values())

    @property
    def order(self) -> list[str]:
        """Kill reasons in pipeline order; within a stage, largest first."""
        return sorted(self.killed, key=lambda r: (STAGES.index(stage_of(r)), -self.killed[r], r))

    def as_lines(self) -> list[str]:
        out = [
            f"{self.fetched:>7,}  fetched",
            f"{self.after_dedup:>7,}  after dedup                "
            f"(-{self.duplicates:,}, {self._pct(self.duplicates, self.fetched)} of fetched)",
        ]
        running = self.after_dedup
        for stage in STAGES:
            reasons = [r for r in self.order if stage_of(r) == stage]
            if not reasons:
                continue
            removed = sum(self.killed[r] for r in reasons)
            running -= removed
            out.append(f"{running:>7,}  after the {stage} filter"
                       f"{' ' * (16 - len(stage))}(-{removed:,}, "
                       f"{self._pct(removed, self.after_dedup)} of deduplicated)")
            for reason in reasons:
                out.append(f"{'':>9}- {reason:<40} {self.killed[reason]:>6,}")
        out.append(f"{self.surviving:>7,}  kept, in sections:")
        for name, count in sorted(self.sections.items(), key=lambda kv: -kv[1]):
            out.append(f"{'':>9}- {name:<40} {count:>6,}")
        return out

    @staticmethod
    def _pct(part: int, whole: int) -> str:
        return f"{part / whole:.1%}" if whole else "n/a"


# "must be located in pakistan", "remote (uk)": the place a prose scope names.
_SCOPE_PLACE = re.compile(r"(?:in|within|remote[, (-]*|based in)\s+(?:the\s+)?([a-z .]+?)\)?$")


def _regions(posting, scope: str, scope_why: str) -> set[str]:
    """Dashboard regions: from the location field, else the title, else the
    country a prose scope named ("Must be located in Pakistan")."""
    found = places.regions_of(posting.location) or places.regions_of(posting.title)
    if not found and scope == remote.COUNTRY:
        named = _SCOPE_PLACE.search(scope_why.lower())
        if named:
            found = places.regions_of(named.group(1))
    return found


def judge(posting) -> dict:
    """Run every filter over one posting. Never mutates the verdict later."""
    scope, scope_why = remote.classify(posting)
    auth, auth_why = authorisation.classify(posting, scope)
    form, form_why = employment.classify(posting)
    zone, zone_why = timezone.classify(posting)
    score, fit_why = fit.score(posting)
    level, level_why = seniority.classify(posting.title)
    years = seniority.years_required(posting.text)

    return {
        "regions": sorted(_regions(posting, scope, scope_why)),
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


def route(verdict: dict) -> tuple[list[str], str]:
    """(sections, kill reason). Exactly one of the two is empty.

    **Sponsorship** needs an explicit offer; silence never qualifies.
    **Remote** needs a role that can be done from outside the company's
    country: open worldwide, or region-locked ("EU only") with a contractor
    arrangement, because an invoice has no residency requirement. A
    *country*-locked role is not rescued by the contractor path - "Remote
    (UK)" means they want someone in the UK.
    """
    auth, scope = verdict["auth"], verdict["scope"]
    contractor = verdict["employment"] in (employment.CONTRACTOR, employment.EITHER)
    regions = set(verdict.get("regions", []))

    if auth == authorisation.NATIONALS and PAKISTAN not in regions:
        return [], "citizens / nationals only"

    out: list[str] = []
    if auth == authorisation.SPONSORS:
        out.append(SPONSORSHIP)

    remote_ok = (
        (scope == remote.GLOBAL and auth not in authorisation.BLOCKING)
        or (scope in (remote.GLOBAL, remote.REGION) and contractor)
        or (scope == remote.REGION and auth == authorisation.SPONSORS)
    )
    if remote_ok:
        out.append(REMOTE)

    for region in REGIONS:
        if region not in regions:
            continue
        if region == PAKISTAN:
            out.append(PAKISTAN)
        elif region == GULF and auth not in authorisation.BLOCKING:
            out.append(GULF)
        elif region == EUROPE and (auth == authorisation.SPONSORS or remote_ok):
            out.append(EUROPE)

    if out:
        return out, ""
    return [], _why_no_route(verdict)


def _why_no_route(verdict: dict) -> str:
    """The most specific true reason, in the words the posting gave."""
    auth, scope = verdict["auth"], verdict["scope"]
    if auth == authorisation.REFUSES:
        return "refuses sponsorship"
    if scope == remote.ONSITE:
        if auth == authorisation.RELOCATION_HINT:
            return "relocation offered, sponsorship unstated"
        return "onsite, sponsorship not offered"
    if scope == remote.HYBRID:
        if auth == authorisation.RELOCATION_HINT:
            return "relocation offered, sponsorship unstated"
        return "hybrid, sponsorship not offered"
    if scope == remote.COUNTRY:
        return "remote, country-locked"
    if scope == remote.REGION:
        if verdict.get("scope_why") in (remote.NO_SCOPE, remote.NO_SCOPE_FLAG):
            return "remote, scope not stated"
        return "remote, region-locked, no contractor route"
    return "no location or route stated"


def run(postings: list) -> tuple[list, Funnel]:
    """The whole pipeline. Returns (kept postings, the funnel)."""
    from .dedup import deduplicate

    funnel = Funnel(fetched=len(postings))
    kept_postings, removed = deduplicate(postings)
    funnel.duplicates = removed
    funnel.after_dedup = len(kept_postings)

    survivors = []
    for posting in kept_postings:
        # The title must be one of the target roles. This is a harder rule
        # than a score threshold and it is the right one: a score lets a
        # "Senior Customer Engineer, Saudi Arabia" into the Gulf tab on body
        # vocabulary alone. It is by far the largest filter in the funnel -
        # most of what a company advertises is not AI - so it runs before the
        # other filters read the body, which is what keeps a 9,000-posting
        # replay to seconds rather than minutes.
        if not fit.role_match(posting.title):
            posting.verdict = {"role": "", "fit_why": "title is not a target role"}
            funnel.kill(posting, ROLE)
            continue

        verdict = judge(posting)
        posting.verdict = verdict
        posting.score = verdict["score"]
        posting.evidence = verdict["fit_why"]

        # Entry to mid only. Senior, staff and lead titles are most of what is
        # advertised and would bury the junior roles further down one list.
        if verdict["level"] not in ACCEPT_LEVELS:
            funnel.kill(posting, f"{verdict['level']} level")
            continue

        # Checked against the body, not the title, because the two disagree
        # often: a role titled "AI Engineer" that asks for eight years is
        # senior and did not say so.
        if verdict["years"] is not None and verdict["years"] > MAX_YEARS:
            funnel.kill(posting, f"wants {verdict['years']}+ years")
            continue

        where, reason = route(verdict)
        if reason:
            funnel.kill(posting, reason)
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
