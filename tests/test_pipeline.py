"""Dedup, routing, and the funnel.

The dedup rule is borrowed from `comms-desk`, which measured it: company is a
hard barrier, never a similarity feature, because merging on text similarity
alone was wrong 87% of the time on real data. The tests below are mostly about
keeping that barrier in place, since the tempting "improvement" is always to
relax it.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from jobradar import dedup, pipeline
from jobradar.filters import authorisation, employment, remote
from jobradar.posting import Posting


def make(company, title, source="greenhouse", location="", text="", url=None,
         posted=None, tags=()):
    return Posting(
        source=source, company=company, title=title, location=location,
        url=url or f"https://example.com/{company}/{title}".replace(" ", "-"),
        text=text, posted=posted, tags=tags,
    )


# --- dedup ------------------------------------------------------------------


def test_two_companies_with_identical_titles_are_two_jobs():
    """The rule comms-desk proved. Identical postings across companies are
    normal — the same template, the same agency — and merging them loses a
    real opportunity every time."""
    postings = [make("Monzo", "AI Engineer"), make("Wise", "AI Engineer")]
    kept, removed = dedup.deduplicate(postings)
    assert removed == 0
    assert len(kept) == 2


def test_the_same_job_on_two_boards_is_one_job():
    postings = [
        make("Monzo", "AI Engineer", source="greenhouse"),
        make("Monzo", "AI Engineer", source="arbeitnow"),
    ]
    kept, removed = dedup.deduplicate(postings)
    assert removed == 1
    # The originating board wins: aggregators sometimes truncate the
    # description, and every filter here reads prose.
    assert kept[0].source == "greenhouse"


def test_one_role_advertised_per_country_is_one_job():
    """Straight from the corpus. Three ScaleAI fellowships appeared as three
    dashboard rows because the country sat inside the title and made the
    identity key differ."""
    postings = [
        make("Scale AI", "Machine Learning Fellow - Human Frontier Collective (Canada)"),
        make("Scale AI", "Machine Learning Fellow - Human Frontier Collective (UK)"),
        make("Scale AI", "Machine Learning Fellow - Human Frontier Collective (US)"),
    ]
    kept, removed = dedup.deduplicate(postings)
    assert removed == 2
    assert len(kept) == 1


def test_seniority_is_not_part_of_a_job_s_identity():
    postings = [
        make("Monzo", "Senior ML Engineer (m/f/d)"),
        make("Monzo", "ML Engineer"),
    ]
    _, removed = dedup.deduplicate(postings)
    assert removed == 1


def test_legal_suffixes_do_not_defeat_the_company_barrier():
    assert dedup.company_key("Vivid Money GmbH") == dedup.company_key("Vivid Money")


def test_different_roles_at_one_company_are_kept():
    postings = [make("Monzo", "ML Engineer"), make("Monzo", "Data Scientist")]
    _, removed = dedup.deduplicate(postings)
    assert removed == 0


def test_a_posting_missing_a_title_is_never_merged():
    """Without both halves the barrier cannot be applied, and merging on a
    missing key would merge unrelated jobs."""
    postings = [make("Monzo", ""), make("Monzo", "")]
    kept, removed = dedup.deduplicate(postings)
    assert removed == 0 and len(kept) == 2


# --- routing ----------------------------------------------------------------


def verdict(scope, auth, form=employment.UNSTATED, score=0.8):
    return {"scope": scope, "auth": auth, "employment": form, "score": score,
            "scope_why": "", "auth_why": "", "employment_why": "",
            "timezone": "unstated", "timezone_why": "", "fit_why": ""}


def test_an_explicit_sponsor_lands_in_the_sponsorship_section():
    where = pipeline.sections_for(verdict(remote.COUNTRY, authorisation.SPONSORS))
    assert pipeline.SPONSORSHIP in where


def test_silence_does_not_qualify_as_sponsorship():
    """The section's whole promise is that relocation is genuinely on the
    table. Filling it with maybes makes it an unfiltered search again."""
    where = pipeline.sections_for(verdict(remote.COUNTRY, authorisation.SILENT))
    assert pipeline.SPONSORSHIP not in where


def test_a_relocation_hint_is_not_sponsorship_either():
    where = pipeline.sections_for(verdict(remote.COUNTRY, authorisation.RELOCATION_HINT))
    assert where == []


def test_the_contractor_path_rescues_a_region_locked_role():
    """Section 4 of the design note: an EU-only employer will often engage a
    contractor anywhere, because an invoice has no residency requirement."""
    where = pipeline.sections_for(
        verdict(remote.REGION, authorisation.REFUSES, employment.CONTRACTOR)
    )
    assert pipeline.REMOTE in where


def test_the_contractor_path_does_not_rescue_a_country_locked_role():
    """"Remote (UK)" means they want somebody in the UK. Letting contractor
    status override that put three fellowships which said "we do not sponsor"
    straight onto the dashboard."""
    where = pipeline.sections_for(
        verdict(remote.COUNTRY, authorisation.REFUSES, employment.CONTRACTOR)
    )
    assert where == []


def test_global_remote_needs_no_rescue_at_all():
    where = pipeline.sections_for(verdict(remote.GLOBAL, authorisation.SILENT))
    assert where == [pipeline.REMOTE]


def test_a_role_can_be_in_both_sections():
    where = pipeline.sections_for(verdict(remote.REGION, authorisation.SPONSORS))
    assert set(where) == {pipeline.SPONSORSHIP, pipeline.REMOTE}


# --- the funnel -------------------------------------------------------------


def test_the_funnel_accounts_for_every_posting():
    """A funnel that does not add up is a funnel that is hiding something."""
    postings = [
        make("A", "ML Engineer", text="Work from anywhere. We love ML and python."),
        make("B", "Cook", location="Berlin, Germany", text="Kitchen work onsite."),
        make("C", "ML Engineer", location="United States", text="We do not sponsor."),
    ]
    kept, funnel = pipeline.run(postings)
    assert funnel.fetched == 3
    assert funnel.after_dedup + funnel.duplicates == funnel.fetched
    assert len(kept) + len(funnel.rejected) == funnel.after_dedup
    assert sum(funnel.killed.values()) == len(funnel.rejected)


def test_every_rejection_records_why():
    postings = [make("B", "Cook", location="Berlin, Germany", text="Onsite kitchen.")]
    _, funnel = pipeline.run(postings)
    assert funnel.rejected
    for posting in funnel.rejected:
        assert posting.verdict["killed_by"]


def test_freshness_outranks_a_slightly_better_match():
    """A perfect match from three weeks ago ranks below a good match from
    this morning, because applying within 48 hours changes response rates."""
    now = datetime.now(timezone.utc)
    stale = make("A", "ML Engineer", text="Work from anywhere. machine learning pytorch llm python",
                 posted=now - timedelta(days=30))
    fresh = make("B", "ML Engineer", text="Work from anywhere. machine learning python",
                 posted=now - timedelta(hours=5))
    kept, _ = pipeline.run([stale, fresh])
    assert [p.company for p in kept][0] == "B", [(p.company, p.score) for p in kept]
