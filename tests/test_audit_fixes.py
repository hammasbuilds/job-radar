"""Regressions from the 2026-10-06 audit, each on the phrase that broke.

Every case here was found by replaying the real cache and reading the output,
then rewritten with an invented company so no real posting is kept in git.
"""

from __future__ import annotations

import pytest

from jobradar import pipeline
from jobradar.filters import employment, fit, remote, seniority, timezone
from jobradar.posting import Posting, clean
from jobradar.sources import boards


def make(title="ML Engineer", location="", text="", tags=(), hint=None, source="test"):
    return Posting(
        source=source, company="Acme", title=title, location=location,
        url="https://example.com/1", text=text, tags=tags, remote_hint=hint,
    )


def sections_of(posting):
    return pipeline.route(pipeline.judge(posting))


# --- one named country is a country, contractor or not ----------------------


def test_us_based_contract_role_is_not_rescued_into_remote():
    """Filed as REGION, "must be US-based" + "contract role" reached the
    Remote tab through the contractor path, which exists for "EU only"."""
    posting = make(title="AI Engineer", location="Remote",
                   text="This is a contract role. Candidates must be US-based.")
    assert remote.classify(posting)[0] == remote.COUNTRY
    where, reason = sections_of(posting)
    assert where == [] and reason == "remote, country-locked"


def test_a_us_based_company_hiring_worldwide_is_not_country_locked():
    posting = make(text="We are a US-based company. Work from anywhere in the world.")
    assert remote.classify(posting)[0] == remote.GLOBAL


# --- B2B the market is not B2B the contract --------------------------------


@pytest.mark.parametrize("text", [
    "We are a B2B SaaS company.",
    "We sell through B2B channels across Europe.",
    "Our team focuses on B2B.",
    "We operate on a B2B model.",
])
def test_b2b_as_a_market_is_not_a_contractor_offer(text):
    assert employment.classify(make(text=text))[0] == employment.UNSTATED, text


@pytest.mark.parametrize("text", [
    "We hire on a B2B basis.",
    "Contract type: B2B.",
    "B2B contract or employment, your choice.",
    "You can work with us via B2B.",
])
def test_b2b_as_a_contract_form_still_counts(text):
    assert employment.classify(make(text=text))[0] in (employment.CONTRACTOR,
                                                       employment.EITHER), text


def test_b2b_saas_does_not_open_the_remote_tab_for_an_eu_only_role():
    posting = make(title="NLP Engineer", location="Remote - EU",
                   text="We are a B2B SaaS company. Remote within the EU.")
    where, reason = sections_of(posting)
    assert remote.REMOTE not in where if where else reason


# --- an office role is not "remote, country-locked" -------------------------


def test_a_located_role_with_no_remote_signal_is_onsite():
    posting = make(location="Paris, France", text="Build ranking models in our office.")
    scope, why = remote.classify(posting)
    assert scope == remote.ONSITE
    assert "france" in why and "no remote" in why


def test_a_located_hybrid_role_is_hybrid():
    posting = make(location="London, UK", text="Hybrid, three days a week in the office.")
    assert remote.classify(posting)[0] == remote.HYBRID


def test_a_located_role_that_mentions_remote_keeps_the_country_lock():
    posting = make(location="Berlin, Germany", text="Remote within Germany is possible.")
    assert remote.classify(posting)[0] == remote.COUNTRY


def test_relocation_is_the_reason_shown_for_a_located_office_role():
    """Before, every such role read "remote, country-locked" and the
    relocation verdict could not be reached from a location field."""
    posting = make(location="Munich, Germany", text="A relocation package is included.")
    assert sections_of(posting) == ([], "relocation offered, sponsorship unstated")


# --- the role gate: team names after a comma do not veto --------------------


@pytest.mark.parametrize("title", [
    "Data Scientist, Marketing",
    "Data Scientist, Policy",
    "Data Scientist, GTM",
    "Senior Data Scientist - Commercial",
    "Senior Machine Learning Engineer - Policy & Safety",
    "Lead Machine Learning Scientist, Customer Operations",
    "Machine Learning Fellow - Frontier Collective (UK)",
    "Fellows Program, ML Systems & Reinforcement Learning",
])
def test_a_team_qualifier_does_not_kill_the_role(title):
    assert fit.role_match(title), title


@pytest.mark.parametrize("title", [
    "Solutions Architect, AI/ML",
    "Partner Solutions Architect, AI Partnerships",
    "Associate Applied (AI) Value Engineer (DACH) - Orbit Program",
    "IT Support Engineer - Enterprise AI",
    "Recruiter, AI Research",
    "People Research Scientist, Recruiting",
    "Sr. Developer Advocate, AI and Machine Learning",
    "https://example.com/ | design, engineering, GTM, sales | SF Bay, Toronto",
])
def test_the_veto_still_applies_to_the_role_itself(title):
    assert fit.role_match(title) is None, title


# --- years: the company's history is not the candidate's --------------------


def test_backed_by_n_years_is_not_a_requirement():
    text = ("Spektrum is backed by 25 years of developer tooling expertise. "
            "You have 2+ years of experience with Python.")
    assert seniority.years_required(text) == 2


def test_our_n_years_is_not_a_requirement():
    assert seniority.years_required("We draw on our 15 years of experience in fintech.") is None


def test_join_our_team_with_n_years_still_is():
    assert seniority.years_required("Join our team with 5+ years of experience in ML.") == 5


# --- async Python is not an async team ----------------------------------------


@pytest.mark.parametrize("text", [
    "Async Python (asyncio) experience required.",
    "You know asynchronous programming and event loops.",
])
def test_async_code_is_not_async_work(text):
    assert timezone.classify(make(text=text))[0] != timezone.ASYNC


@pytest.mark.parametrize("text", [
    "We work asynchronously across time zones.",
    "We are an async-first company.",
])
def test_async_work_is_still_async(text):
    assert timezone.classify(make(text=text))[0] == timezone.ASYNC


# --- Hacker News: <p> opens a paragraph ---------------------------------------


HN = ("Fjordtech | ML Engineer, Backend Engineer | Oslo | ONSITE | Full-time | VISA"
      "<p>We build forecasting models.<p>Email us.")


def test_an_opening_p_is_a_line_break():
    assert clean(HN).split("\n")[0].endswith("| VISA")


def test_the_hn_visa_header_is_read_once_the_header_is_its_own_line():
    body = clean(HN)
    company, roles, where = boards.hn_roles(body)
    assert company == "Fjordtech"
    assert roles == ["ML Engineer", "Backend Engineer"]
    # The employment field is not a place.
    assert "full" not in where.lower()
    posting = Posting(source="hn", company=company, title=roles[0], location=where,
                      url="https://news.ycombinator.com/item?id=1", text=body)
    assert pipeline.judge(posting)["auth_why"] == "VISA in the header"


def test_everywhere_is_global():
    assert remote.classify(make(location="Remote (Everywhere)"))[0] == remote.GLOBAL
