"""The five filters, and the location parser they all lean on.

Every fixture in this file is a string that came off a real board during
development. The ones that look oddly specific are the ones that were
getting through, and each is kept because it broke something:

  "Cardiff, London or Remote (UK)"        called region-wide; it is UK-only
  "USA, Canada, Argentina, Mexico, Peru"  called region-wide; a missing country
                                          made an `all()` test pass
  "Paris office"                          unparseable, so read as region-wide
  "relocation assistance"                 read as visa sponsorship, which it
                                          is not

A filter whose job is rejection has to be tested on what it wrongly *keeps*
and what it wrongly *kills*, so both directions appear below.
"""

from __future__ import annotations

import pytest

from jobradar.filters import authorisation, employment, places, remote, timezone
from jobradar.posting import Posting


def make(title="ML Engineer", location="", text="", tags=(), hint=None) -> Posting:
    return Posting(
        source="test", company="Acme", title=title, location=location,
        url="https://example.com/1", text=text, tags=tags, remote_hint=hint,
    )


# --- the location parser ----------------------------------------------------


@pytest.mark.parametrize(
    "location,expected",
    [
        ("Cardiff, London or Remote (UK)", places.COUNTRY),
        ("London; Remote (UK)", places.COUNTRY),
        ("Berlin, Germany", places.COUNTRY),
        ("Berlin", places.COUNTRY),
        ("Paris office", places.COUNTRY),
        ("United States", places.COUNTRY),
        ("San Francisco, CA; Seattle, WA; New York, NY", places.COUNTRY),
        ("USA, Canada, Argentina, Mexico, Peru", places.COUNTRY),
        ("Americas, Europe, Israel", places.REGION),
        ("Remote - EU", places.REGION),
        ("Anywhere", places.GLOBAL),
        ("Remote (Global)", places.GLOBAL),
        ("", places.UNKNOWN),
        ("Somewhere Odd", places.UNKNOWN),
        ("Remote", places.UNKNOWN),
    ],
)
def test_location_strings_seen_on_real_boards(location, expected):
    assert places.classify(location)[0] == expected


def test_an_unreadable_location_fails_closed():
    """The bug that produced two wrong sections, twice.

    Both earlier versions let an unrecognised token satisfy the test that was
    meant to reject it, so anything the word lists did not cover was reported
    as region-wide — confidently, and wrongly. Unknown must stay unknown so
    the caller falls back to reading prose.
    """
    scope, why = places.classify("Mars Colony Nine")
    assert scope == places.UNKNOWN
    assert "unrecognised" in why


def test_a_single_unknown_token_does_not_erase_known_ones():
    scope, _ = places.classify("Berlin, Neverwhere")
    assert scope == places.COUNTRY


# --- remote scope -----------------------------------------------------------


def test_remote_in_the_title_loses_to_a_residency_rule_in_the_body():
    """The posting this whole tool exists to kill."""
    posting = make(
        title="Senior ML Engineer — Remote",
        text="We are remote-first. You must be based in Germany for this role.",
    )
    scope, why = remote.classify(posting)
    assert scope == remote.COUNTRY
    assert "germany" in why.lower()


def test_the_location_field_beats_a_vague_body():
    posting = make(location="Cardiff, London or Remote (UK)",
                   text="This is a remote role at a remote-first company.")
    scope, _ = remote.classify(posting)
    assert scope == remote.COUNTRY


def test_an_onsite_phrase_still_overrides_the_location_field():
    """The location field is trusted, but not over an explicit refusal."""
    posting = make(location="Remote (UK)", text="This position is not remote.")
    scope, _ = remote.classify(posting)
    assert scope == remote.ONSITE


def test_a_bare_remote_claim_is_region_not_global():
    """Guessing generously fills the daily list with jobs that never reply."""
    posting = make(text="Fully remote role, work from home.")
    assert remote.classify(posting)[0] == remote.REGION


def test_eu_only_is_found_however_it_is_phrased():
    for phrase in (
        "You must reside in the EU.",
        "This role is EU-only.",
        "Remote within Europe.",
        "Applicants must be eligible to work in the EEA.",
    ):
        assert remote.classify(make(text=phrase))[0] == remote.REGION, phrase


# --- work authorisation -----------------------------------------------------


def test_relocation_assistance_is_not_visa_sponsorship():
    """The first false positive found on real data.

    A Berlin role and a Seattle role both reached the sponsorship section on
    the phrase "relocation assistance". Companies pay for the moving van for
    people who already hold the right to work; it says nothing about a visa.
    """
    status, why = authorisation.classify(make(text="We offer relocation assistance."))
    assert status == authorisation.RELOCATION_HINT
    assert status != authorisation.SPONSORS
    assert "relocation" in why


def test_an_explicit_offer_is_sponsorship():
    status, _ = authorisation.classify(make(text="We can sponsor your visa."))
    assert status == authorisation.SPONSORS


def test_a_refusal_beats_an_offer_in_the_same_posting():
    """Postings that mention both nearly always mean the restriction.

    "We sponsor visas for some roles, but for this one you must already have
    the right to work" — matching the offer first files it under sponsorship,
    which is the opposite of what it says.
    """
    text = ("We sponsor visas across the company. For this role you must "
            "already have the right to work in Ireland.")
    assert authorisation.classify(make(text=text))[0] == authorisation.REFUSES


def test_silence_is_its_own_answer():
    status, _ = authorisation.classify(make(text="Join our team of engineers."))
    assert status == authorisation.SILENT


def test_a_global_remote_role_does_not_need_a_permit():
    status, _ = authorisation.classify(make(text="Work from anywhere."), scope="global")
    assert status == authorisation.NOT_NEEDED


# --- employment form --------------------------------------------------------


def test_b2b_is_recognised_as_the_contractor_route():
    assert employment.classify(make(text="B2B contract available."))[0] == employment.CONTRACTOR


def test_both_offered_is_not_collapsed_to_whichever_matched_first():
    """The best possible answer, and easy to lose."""
    text = "Permanent employment or B2B — your choice."
    status, why = employment.classify(make(text=text))
    assert status == employment.EITHER
    assert "both" in why


def test_a_structured_tag_is_read_when_the_prose_says_nothing():
    """Lever states this outright in categories.commitment."""
    status, _ = employment.classify(make(tags=("Contract", "Engineering")))
    assert status == employment.CONTRACTOR


def test_a_refusal_of_contractors_is_recorded():
    assert employment.classify(
        make(text="We do not work with contractors.")
    )[0] == employment.EMPLOYEE


# --- timezone ---------------------------------------------------------------


def test_european_hours_are_a_plus_not_a_kill():
    """PKT is UTC+5; a CET working day overlaps almost entirely."""
    status, why = timezone.classify(make(text="Core hours are 9-18 CET."))
    assert status == timezone.GOOD
    assert "overlap" in why


def test_us_pacific_hours_are_nights():
    status, _ = timezone.classify(make(text="You must overlap 9am-5pm PST."))
    assert status == timezone.POOR


def test_async_is_detected():
    assert timezone.classify(make(text="We are async-first, no core hours."))[0] == timezone.ASYNC
