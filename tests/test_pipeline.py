"""Dedup, routing, and the funnel.

The dedup rule is borrowed from `comms-desk`, which measured it: company is a
hard barrier, never a similarity feature, because merging on text similarity
alone was wrong 87% of the time on real data. The tests below keep that
barrier in place, and keep seniority and place inside a job's identity.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from jobradar import dedup, pipeline
from jobradar.filters import authorisation, employment, remote
from jobradar.posting import Posting


def make(company, title, source="greenhouse", location="", text="", url=None,
         posted=None, tags=()):
    return Posting(
        source=source, company=company, title=title, location=location,
        url=url or f"https://example.com/{company}/{title}/{location}".replace(" ", "-"),
        text=text, posted=posted, tags=tags,
    )


# --- dedup ------------------------------------------------------------------


def test_two_companies_with_identical_titles_are_two_jobs():
    """The rule comms-desk proved. Identical postings across companies are
    normal - the same template, the same agency - and merging them loses a
    real opportunity every time."""
    kept, removed = dedup.deduplicate([make("Monzo", "AI Engineer"), make("Wise", "AI Engineer")])
    assert removed == 0 and len(kept) == 2


def test_the_same_job_on_two_boards_is_one_job():
    postings = [
        make("Monzo", "AI Engineer", source="arbeitnow", location="Berlin, Germany"),
        make("Monzo", "AI Engineer", source="greenhouse", location="Berlin"),
    ]
    kept, removed = dedup.deduplicate(postings)
    assert removed == 1
    # The originating board wins: aggregators sometimes truncate the
    # description, and every filter here reads prose.
    assert kept[0].source == "greenhouse"


def test_senior_and_junior_are_two_jobs_and_the_junior_survives_the_pipeline():
    """The reviewer's case. Stripping seniority merged these, the Senior copy
    survived dedup, was killed as senior, and the junior role vanished as a
    "duplicate" without ever reaching a filter."""
    text = "We sponsor visas for this role. Onsite in Berlin."
    postings = [
        make("Acme GmbH", "Senior ML Engineer", location="Berlin", text=text),
        make("Acme", "Junior ML Engineer", location="Berlin", text=text),
    ]
    kept, removed = dedup.deduplicate(postings)
    assert removed == 0 and len(kept) == 2
    survivors, _ = pipeline.run(postings)
    assert [p.title for p in survivors] == ["Junior ML Engineer"]


def test_different_places_are_different_jobs():
    """"Research Scientist (Zurich)" and "(Remote, Worldwide)" were merged and
    only the Zurich one survived - the reachable one was the one dropped."""
    postings = [
        make("Acme", "Research Scientist (Zurich)", location="Zurich"),
        make("Acme", "Research Scientist (Remote, Worldwide)", location="Remote, Worldwide"),
    ]
    _, removed = dedup.deduplicate(postings)
    assert removed == 0


def test_one_role_per_country_is_kept_per_country():
    """Each country copy is its own route question: "(UK)" may refuse where
    "(Canada)" does not, so they are never folded into one."""
    postings = [
        make("Scale AI", "Machine Learning Fellow (Canada)", location="Canada"),
        make("Scale AI", "Machine Learning Fellow (UK)", location="UK"),
    ]
    _, removed = dedup.deduplicate(postings)
    assert removed == 0


def test_the_same_title_a_month_apart_is_two_postings():
    """The rule is "same company, same title, two boards, within a week"."""
    now = datetime.now(UTC)
    postings = [
        make("Monzo", "AI Engineer", source="arbeitnow", posted=now - timedelta(days=40)),
        make("Monzo", "AI Engineer", source="greenhouse", posted=now),
        make("Monzo", "AI Engineer", source="remotive", posted=now - timedelta(days=3)),
    ]
    kept, removed = dedup.deduplicate(postings)
    assert removed == 1 and len(kept) == 2


def test_legal_suffixes_do_not_defeat_the_company_barrier():
    assert dedup.company_key("Vivid Money GmbH") == dedup.company_key("Vivid Money")


def test_gender_markers_are_not_identity():
    _, removed = dedup.deduplicate([make("Monzo", "ML Engineer (m/f/d)"), make("Monzo", "ML Engineer")])
    assert removed == 1


def test_a_posting_missing_a_title_is_never_merged():
    kept, removed = dedup.deduplicate([make("Monzo", ""), make("Monzo", "")])
    assert removed == 0 and len(kept) == 2


# --- routing ----------------------------------------------------------------


def verdict(scope, auth, form=employment.UNSTATED, regions=(), why=""):
    return {"scope": scope, "auth": auth, "employment": form, "regions": list(regions),
            "scope_why": why}


def test_an_explicit_sponsor_lands_in_the_sponsorship_section():
    where, reason = pipeline.route(verdict(remote.COUNTRY, authorisation.SPONSORS))
    assert pipeline.SPONSORSHIP in where and not reason


def test_silence_does_not_qualify_as_sponsorship():
    where, reason = pipeline.route(verdict(remote.ONSITE, authorisation.SILENT))
    assert where == [] and reason == "onsite, sponsorship not offered"


def test_a_relocation_hint_is_not_sponsorship_either():
    where, reason = pipeline.route(verdict(remote.ONSITE, authorisation.RELOCATION_HINT))
    assert where == [] and reason == "relocation offered, sponsorship unstated"


def test_the_contractor_path_rescues_a_region_locked_role():
    """An EU-only employer will often engage a contractor anywhere, because an
    invoice has no residency requirement."""
    where, _ = pipeline.route(verdict(remote.REGION, authorisation.REFUSES, employment.CONTRACTOR))
    assert pipeline.REMOTE in where


def test_the_contractor_path_does_not_rescue_a_country_locked_role():
    """"Remote (UK)" means they want somebody in the UK."""
    where, reason = pipeline.route(verdict(remote.COUNTRY, authorisation.REFUSES, employment.CONTRACTOR))
    assert where == [] and reason == "refuses sponsorship"


def test_global_remote_needs_no_rescue_at_all():
    where, _ = pipeline.route(verdict(remote.GLOBAL, authorisation.NOT_NEEDED))
    assert where == [pipeline.REMOTE]


def test_a_role_can_be_in_both_sections():
    where, _ = pipeline.route(verdict(remote.REGION, authorisation.SPONSORS))
    assert set(where) == {pipeline.SPONSORSHIP, pipeline.REMOTE}


def test_nationals_only_closes_every_route():
    """A US-citizens-only DoD contract reached the Remote tab as a contractor."""
    for scope, form in ((remote.GLOBAL, employment.CONTRACTOR), (remote.REGION, employment.EITHER)):
        where, reason = pipeline.route(verdict(scope, authorisation.NATIONALS, form))
        assert where == [] and reason == "citizens / nationals only"


def test_the_europe_tab_obeys_the_route_rules():
    """Graphcore: UK, "unable to provide visa sponsorship" - was in Europe."""
    where, reason = pipeline.route(verdict(remote.ONSITE, authorisation.REFUSES, regions=["europe"]))
    assert where == [] and reason == "refuses sponsorship"
    where, reason = pipeline.route(verdict(remote.ONSITE, authorisation.SILENT, regions=["europe"]))
    assert where == [] and reason == "onsite, sponsorship not offered"
    where, _ = pipeline.route(verdict(remote.ONSITE, authorisation.SPONSORS, regions=["europe"]))
    assert set(where) == {pipeline.SPONSORSHIP, pipeline.EUROPE}


def test_the_gulf_tab_accepts_silence_but_not_a_nationals_only_role():
    where, _ = pipeline.route(verdict(remote.ONSITE, authorisation.SILENT, regions=["gulf"]))
    assert where == [pipeline.GULF]
    where, reason = pipeline.route(verdict(remote.ONSITE, authorisation.NATIONALS, regions=["gulf"]))
    assert where == [] and reason == "citizens / nationals only"
    where, _ = pipeline.route(verdict(remote.ONSITE, authorisation.REFUSES, regions=["gulf"]))
    assert where == []


def test_pakistan_needs_no_route():
    where, _ = pipeline.route(verdict(remote.ONSITE, authorisation.SILENT, regions=["pakistan"]))
    assert where == [pipeline.PAKISTAN]


@pytest.mark.parametrize("why,reason", [
    (remote.NO_SCOPE, "remote, scope not stated"),
    ("within the eu", "remote, region-locked, no contractor route"),
])
def test_a_remote_kill_says_which_kind_it_is(why, reason):
    """Benzinga said "Remote" and nothing else; it was filed as
    "country-locked", a reason it never gave."""
    assert pipeline.route(verdict(remote.REGION, authorisation.SILENT, why=why)) == ([], reason)


def test_a_country_named_in_prose_puts_the_posting_in_that_region():
    posting = make("Acme", "AI Engineer", text="Must be located in Pakistan. Hybrid in Lahore office.")
    assert "pakistan" in pipeline.judge(posting)["regions"]


# --- whole postings, end to end ---------------------------------------------


def test_a_b2b_saas_company_is_not_a_contractor_offer_end_to_end():
    """Axmed: full-time, EU-preferred, "No visa sponsorship", and "B2B" only
    as a description of the company. It reached the Remote tab."""
    posting = make("Axmed", "AI Engineer", location="Remote",
                   text="Axmed is a B2B marketplace for medicines. Full-time. Remote within the EU. "
                        "No visa sponsorship or relocation.")
    kept, funnel = pipeline.run([posting])
    assert kept == []
    assert posting.verdict["killed_by"] == "refuses sponsorship"


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
    assert len(kept) + len(funnel.rejected) == funnel.after_dedup == funnel.surviving + len(funnel.rejected)
    assert sum(funnel.killed.values()) == len(funnel.rejected)


def test_the_funnel_prints_stages_in_pipeline_order():
    """Sorting kill reasons by count put the route kills before the role
    filter and made every running "after" total a fiction."""
    funnel = pipeline.Funnel(fetched=10, after_dedup=10)
    funnel.killed = {"remote, country-locked": 5, "senior level": 1, pipeline.ROLE: 2}
    funnel.sections = {"remote": 2}
    lines = funnel.as_lines()
    stages = [ln for ln in lines if "after the" in ln]
    assert [s.split("after the ")[1].split()[0] for s in stages] == ["role", "level", "route"]
    assert stages[0].split()[0] == "8" and stages[-1].split()[0] == "2"


def test_every_rejection_records_why():
    _, funnel = pipeline.run([make("B", "Cook", location="Berlin, Germany", text="Onsite kitchen.")])
    assert funnel.rejected and all(p.verdict["killed_by"] for p in funnel.rejected)


def test_freshness_outranks_a_slightly_better_match():
    """A perfect match from three weeks ago ranks below a good match from
    this morning, because applying within 48 hours changes response rates."""
    now = datetime.now(UTC)
    stale = make("A", "ML Engineer", text="Work from anywhere. machine learning pytorch llm python",
                 posted=now - timedelta(days=30))
    fresh = make("B", "ML Engineer", text="Work from anywhere. machine learning python",
                 posted=now - timedelta(hours=5))
    kept, _ = pipeline.run([stale, fresh])
    assert [p.company for p in kept][0] == "B", [(p.company, p.score) for p in kept]
