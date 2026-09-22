"""The store, whose only real job is answering "what is new?".

The postings could be recomputed from cache in seconds, so the database exists
for one reason: the note requires this to report **what is new since
yesterday** rather than showing the same list again. That makes `first_seen`
the load-bearing column, and the test that matters is that a re-fetch never
moves it.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from jobradar import pipeline, store
from jobradar.posting import Posting


@pytest.fixture
def db(tmp_path):
    return tmp_path / "test.sqlite3"


def make(company="Acme", title="ML Engineer", url=None, score=0.7, section="remote"):
    posting = Posting(
        source="greenhouse", company=company, title=title, location="Anywhere",
        url=url or f"https://example.com/{company}/{title}".replace(" ", "-"),
        text="body", posted=datetime.now(timezone.utc),
    )
    posting.score = score
    posting.section = section
    posting.verdict = {"scope": "global", "auth": "silent", "employment": "either",
                       "timezone": "good", "score": score, "scope_why": "",
                       "auth_why": "", "employment_why": "", "timezone_why": "",
                       "fit_why": "matched"}
    posting.evidence = "matched"
    return posting


def funnel(rejected=()):
    f = pipeline.Funnel(fetched=1 + len(rejected), after_dedup=1 + len(rejected))
    for posting in rejected:
        f.kill(posting, "onsite, no sponsorship")
    return f


def test_first_seen_survives_a_refetch(db):
    """The whole reason the database exists.

    If a re-fetch moved `first_seen`, every posting would look new every
    morning and the Today screen would be the full list again — which is the
    behaviour the tool was built to avoid.
    """
    posting = make()
    assert store.save([posting], funnel(), db) == 1
    first = store.section("remote", path=db)[0]["first_seen"]

    assert store.save([make()], funnel(), db) == 0, "second sight must not be new"
    again = store.section("remote", path=db)[0]
    assert again["first_seen"] == first
    assert again["last_seen"] >= first


def test_a_changed_score_updates_without_resetting_first_seen(db):
    store.save([make(score=0.5)], funnel(), db)
    store.save([make(score=0.9)], funnel(), db)
    rows = store.section("remote", path=db)
    assert len(rows) == 1
    assert rows[0]["score"] == 0.9


def test_the_key_ignores_tracking_parameters(db):
    """Two URLs differing only by a query string are one posting."""
    a = make(url="https://example.com/job/1")
    b = make(url="https://example.com/job/1?utm_source=x")
    assert a.key == b.key
    store.save([a], funnel(), db)
    assert store.save([b], funnel(), db) == 0


def test_a_posting_in_both_sections_is_found_by_either(db):
    posting = make(section="remote,sponsorship")
    store.save([posting], funnel(), db)
    assert len(store.section("remote", path=db)) == 1
    assert len(store.section("sponsorship", path=db)) == 1


def test_section_matching_is_not_a_loose_substring(db):
    """'remote' must not match a row whose only section is 'sponsorship'."""
    store.save([make(section="sponsorship")], funnel(), db)
    assert store.section("remote", path=db) == []


def test_rejections_are_stored_with_their_reason(db):
    killed = make(company="Nope")
    store.save([make()], funnel([killed]), db)
    rows = store.killed(path=db)
    assert len(rows) == 1
    assert rows[0]["reason"] == "onsite, no sponsorship"
    assert store.kill_reasons(path=db)[0]["n"] == 1


def test_the_killed_table_reflects_the_latest_run_only(db):
    """A posting that stops being rejected must not linger on the trust screen
    saying it was."""
    killed = make(company="Nope")
    store.save([make()], funnel([killed]), db)
    store.save([make()], funnel(), db)
    assert store.killed(path=db) == []


def test_the_pipeline_is_written_only_by_a_person(db):
    posting = make()
    store.save([posting], funnel(), db)
    assert store.pipeline(db) == [], "a crawl must never add to the pipeline"

    store.set_application(posting.key, "applied", "sent CV", db)
    rows = store.pipeline(db)
    assert len(rows) == 1
    assert rows[0]["applied"] == "applied"
    assert rows[0]["noted"] == "sent CV"


def test_an_application_state_can_be_changed(db):
    posting = make()
    store.save([posting], funnel(), db)
    store.set_application(posting.key, "applied", path=db)
    store.set_application(posting.key, "rejected", path=db)
    rows = store.pipeline(db)
    assert len(rows) == 1 and rows[0]["applied"] == "rejected"


def test_the_full_description_is_never_sent_to_the_browser(db):
    """It is up to 20 KB a row and nothing in the UI shows it."""
    store.save([make()], funnel(), db)
    assert "text" not in store.section("remote", path=db)[0]


def test_one_employer_cannot_fill_the_screen(db):
    """Anthropic repeats "we sponsor visas" in every posting, which is true
    and which put 161 of 170 sponsorship rows under one name. A correct filter
    producing an unreadable list is still a broken screen."""
    postings = [make(company="Flood", title=f"Role {i}", score=0.9 - i / 100)
                for i in range(12)]
    postings.append(make(company="Other", title="One role", score=0.5))
    store.save(postings, funnel(), db)

    rows = store.section("remote", path=db)
    from collections import Counter
    per = Counter(r["company"] for r in rows)
    assert per["Flood"] == store.PER_COMPANY
    assert per["Other"] == 1


def test_the_folded_rows_are_counted_not_hidden(db):
    """A cap that silently drops rows is the same sin as a silent filter."""
    postings = [make(company="Flood", title=f"Role {i}", score=0.9 - i / 100)
                for i in range(12)]
    store.save(postings, funnel(), db)
    rows = store.section("remote", path=db)
    assert rows[0]["more_at_company"] == 12 - store.PER_COMPANY
    # Only the first row from a company carries the count, so the screen says
    # it once rather than on every line.
    assert [r["more_at_company"] for r in rows[1:]] == [0] * (len(rows) - 1)


def test_nothing_is_deleted_by_the_cap(db):
    postings = [make(company="Flood", title=f"Role {i}") for i in range(12)]
    store.save(postings, funnel(), db)
    everything = store.section("remote", per_company=99, path=db)
    assert len(everything) == 12
