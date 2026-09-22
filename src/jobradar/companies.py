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

# provider -> slugs. The company name shown in the UI comes from the board
# itself where the API provides it, so these are identifiers, not labels.
SEEDS: dict[str, tuple[str, ...]] = {
    "greenhouse": (
        # UK / EU fintech and infrastructure
        "monzo", "wise", "starlingbank", "gocardless", "checkout", "tide",
        "revolut", "n26", "traderepublic", "moonpay", "form3",
        # EU product and platform companies
        "hellofresh", "getyourguide", "personio", "celonis", "sennder",
        "contentful", "sumup", "zalando", "deliveryhero", "flixbus",
        "bolt", "pleo", "templafy", "unity", "trustpilot", "zendesk",
        # AI / ML weighted
        "huggingface", "weightsandbiases", "scaleai", "cohere", "eleven-labs",
        "synthesia", "poolside", "mistralai", "deepl", "aleph-alpha",
        "graphcore", "speechmatics", "faculty", "quantexa", "peak",
        # remote-first
        "gitlab", "elastic", "grafanalabs", "hashicorp", "sourcegraph",
        "docker", "canonical", "automattic", "doist", "remotecom",
    ),
    "lever": (
        "spotify", "shopify", "palantir", "netflix", "mistral",
        "veriff", "wolt", "swordhealth", "kry", "vinted",
        "typeform", "factorial", "jobandtalent", "glovo", "cabify",
    ),
}


def all_slugs() -> list[tuple[str, str]]:
    return [(provider, slug) for provider, slugs in SEEDS.items() for slug in slugs]


def count() -> int:
    return sum(len(s) for s in SEEDS.values())
