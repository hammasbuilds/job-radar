"""Which ATS slugs are real? Ask, and print a seed list that works.

    python scripts/probe_companies.py            # check the current seeds
    python scripts/probe_companies.py --wide     # also try the candidate list

A seed list is hand-written, so it rots: companies change ATS provider, get
acquired, or simply use a slug nobody guessed. The first version of
`companies.py` had 67 entries and **42 of them returned nothing** — which is
invisible during a run, because a dead board and a board with no open roles
look identical.

This makes the difference visible, and prints a ready-to-paste list of the
slugs that actually resolve.
"""

from __future__ import annotations

import argparse
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from jobradar import companies  # noqa: E402
from jobradar.sources import greenhouse, lever  # noqa: E402
from jobradar.sources.http import SourceError  # noqa: E402

FETCH = {"greenhouse": greenhouse.fetch, "lever": lever.fetch}

# Candidates to try with --wide. European-weighted and AI-weighted, because a
# US-only startup contributes nothing but postings this tool will kill.
CANDIDATES = {
    "greenhouse": (
        "deepmind", "anthropic", "openai", "stripe", "databricks", "datadog",
        "cloudflare", "snyk", "algolia", "typeform", "hopin", "babbel",
        "blinkist", "soundcloud", "researchgate", "delivery-hero", "adjust",
        "tier", "raisin", "solarisbank", "scalable-capital", "clark",
        "omio", "sennder-technologies", "gorillas", "choco", "grover",
        "wefox", "taxfix", "mambu", "signavio", "staffbase", "zenjob",
        "commercetools", "instana", "camunda", "neo4j", "elastic-nv",
        "jetbrains", "kiwicom", "productboard", "rohlik", "mews",
        "deliveroo", "depop", "farfetch", "improbable", "onfido", "paddle",
        "primer", "railsbank", "thoughtmachine", "yapily", "zego", "zilch",
        "beamery", "cleo", "curve", "habito", "hometree", "marshmallow",
        "multiverse", "peak-ai", "snyk-2", "tessian", "tractable", "trint",
        "vinterior", "yulife", "bought-by-many", "cazoo", "lendable",
        "smartly", "supermetrics", "aiven", "relex", "swappie", "oura",
        "iceye", "varjo", "unity-technologies", "tomtom", "booking",
        "adyen", "messagebird", "backbase", "bynder", "catawiki", "picnic",
        "sendcloud", "framer", "miro", "castor", "otrium", "bitvavo",
        "spryker", "personio-gmbh", "forto", "everphone", "enpal",
    ),
    "lever": (
        "attentive", "ramp", "checkr", "gopuff", "nielsen", "matillion",
        "smartrecruiters", "hiya", "sardine", "tink", "lunar", "pleo-io",
        "bolt-eu", "zego-2", "wise-com", "gousto", "cognism", "hibob",
        "riskified", "similarweb", "payfit", "alan", "qonto", "ledger",
        "sorare", "shift-technology", "dataiku", "contentsquare", "ivalua",
        "younited", "swile", "spendesk", "agicap", "pennylane", "lydia",
        "voodoo", "mirakl", "algolia-1", "back-market", "manomano",
    ),
}


def probe(item: tuple[str, str]) -> tuple[str, str, int, str]:
    provider, slug = item
    try:
        got = FETCH[provider](slug, max_age=24 * 3600)
    except SourceError as exc:
        return provider, slug, -1, str(exc)[:50]
    except Exception as exc:  # a bad slug can still produce a parse error
        return provider, slug, -1, f"{type(exc).__name__}: {exc}"[:50]
    return provider, slug, len(got), ""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wide", action="store_true",
                        help="probe the candidate list as well as the seeds")
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()

    targets = list(companies.all_slugs())
    if args.wide:
        seen = set(targets)
        targets += [(p, s) for p, slugs in CANDIDATES.items()
                    for s in slugs if (p, s) not in seen]

    print(f"probing {len(targets)} boards with {args.workers} workers…\n")
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        results = list(pool.map(probe, targets))

    live = [r for r in results if r[2] > 0]
    empty = [r for r in results if r[2] == 0]
    broken = [r for r in results if r[2] < 0]

    live.sort(key=lambda r: (-r[2], r[1]))
    print(f"{'LIVE':<6}{len(live):>4}   boards returning at least one posting")
    for provider, slug, n, _ in live:
        print(f"        {provider:<11} {slug:<26} {n:>5}")
    print(f"\n{'EMPTY':<6}{len(empty):>4}   resolved but no open roles, or wrong slug")
    print(f"{'ERROR':<6}{len(broken):>4}")
    for provider, slug, _, why in broken[:10]:
        print(f"        {provider:<11} {slug:<26} {why}")

    total = sum(r[2] for r in live)
    print(f"\n{total:,} postings across {len(live)} live boards")

    print("\n--- paste into companies.py ---")
    for provider in sorted({p for p, _, _, _ in live}):
        slugs = [s for p, s, _, _ in live if p == provider]
        print(f'    "{provider}": (')
        for i in range(0, len(slugs), 4):
            print("        " + " ".join(f'"{s}",' for s in slugs[i:i + 4]))
        print("    ),")


if __name__ == "__main__":
    main()
