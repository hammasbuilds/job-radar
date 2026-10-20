"""Which ATS boards to ask, and which provider each company uses.

There is no directory mapping companies to their ATS, so the slug list is
built by hand and verified by fetching. `scripts/probe_companies.py` checks
every entry and reports which are dead, because a seed list silently rotting
is how a crawler starts returning less every month while looking healthy.

The bias is deliberate: European companies, and companies known to hire
remotely or across borders. A US-only startup with a Greenhouse board
contributes nothing but postings this tool will kill.
"""

from __future__ import annotations

import json
from pathlib import Path

# provider -> slugs. The company name shown in the UI comes from the board
# itself where the API provides it, so these are identifiers, not labels.
# Every slug below was verified by `scripts/probe_companies.py --wide`, which
# asked all of them and kept only the ones that returned at least one posting.
#
# The first hand-written version of this list had 67 entries and 42 returned
# nothing — the companies were real, but they use a different ATS or a slug
# nobody guessed. That is invisible during a run, because a dead board and a
# board with no open roles both come back empty, so the crawl looked healthy
# while fetching 40% less than it claimed.
#
# Probed 2026-09-22: 53 live boards, 8,287 postings.
SEEDS: dict[str, tuple[str, ...]] = {
    "greenhouse": (
        # Large boards — most of the corpus comes from these
        "databricks", "stripe", "anthropic", "datadog", "hellofresh",
        "cloudflare", "elastic", "sumup", "canonical", "celonis",
        "scaleai", "adyen", "gitlab", "remotecom", "graphcore",
        "grafanalabs", "deliveroo", "oura",
        # UK / EU fintech
        "tide", "n26", "monzo", "wise", "gocardless", "raisin",
        "solarisbank", "form3", "cleo", "traderepublic",
        # EU product and platform
        "jetbrains", "trustpilot", "neo4j", "relex", "getyourguide",
        "peak", "catawiki", "commercetools", "algolia", "staffbase",
        "typeform", "contentful", "speechmatics", "grover", "spryker",
        # Gulf. 26 Gulf companies were probed and three have a readable board:
        # the region's employers overwhelmingly use other ATS providers, so
        # most Gulf roles in this tool arrive from European and global
        # companies advertising a Dubai or Riyadh office rather than from
        # Gulf-headquartered firms. That is a limit of the sources, and the
        # Gulf tab says so rather than looking empty for no reason.
        "tamara", "careem", "hala",
        # Pakistan-linked, found in the second pass: Motive (ex-KeepTruckin)
        # runs its largest engineering office in Lahore, Careem in Karachi.
        "motive",
    ),
    "lever": (
        "gopuff", "palantir", "spotify", "qonto", "agicap",
        "contentsquare", "swile", "jobandtalent", "matillion", "younited",
        # Pakistan. 16 probed, one readable board.
        "educative",
    ),
    # Pakistan, second pass. The first pass asked 16 employers and only
    # Greenhouse and Lever, which is why the section read as almost empty:
    # the answer was not "Pakistani employers do not publish boards", it was
    # "they do not publish them on the two providers we asked". Re-probing 65
    # employers across six providers found seven readable boards.
    # Devsinc, PureLogics and Securiti were found on SmartRecruiters, and are
    # not asked: api.smartrecruiters.com serves `User-agent: * / Disallow: /`
    # (only LinkedInBot is allowed), and this tool obeys robots.txt. Their
    # careers pages are the manual route. See BLOCKED below.
    "ashby": (
        "tajir",
    ),
}


# Boards that resolve but that robots.txt forbids this agent to read. Kept as
# data rather than deleted, so the probe's finding is not lost and a policy
# change on their side is a one-line move back into SEEDS.
BLOCKED: dict[str, tuple[str, ...]] = {
    "smartrecruiters": ("devsinc", "purelogics", "securiti"),
}


def SEEDS_ONLY() -> list[tuple[str, str]]:  # noqa: N802 - reads as a constant at call sites
    return [(provider, slug) for provider, slugs in SEEDS.items() for slug in slugs]


# Boards found by `scripts/discover_boards.py` from the names in candidates.py. Generated, and
# committed so a crawl needs no discovery pass first; re-run discovery when counts drop.
_FOUND = Path(__file__).with_name("boards_found.json")


def found() -> dict[str, dict]:
    try:
        return json.loads(_FOUND.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def all_slugs() -> list[tuple[str, str]]:
    out = SEEDS_ONLY()
    seen = set(out)
    for provider, boards in found().items():
        for slug in boards:
            if (provider, slug) not in seen and provider in _READABLE:
                seen.add((provider, slug))
                out.append((provider, slug))
    return out


# What the crawl can read. SmartRecruiters is absent on purpose: its robots.txt forbids it.
_READABLE = {"greenhouse", "lever", "ashby", "workable", "recruitee", "personio"}


def count() -> int:
    return len(all_slugs())
