"""The network layer and the adapters, with the network replaced.

`http._open` is the one function that touches the network; these tests swap
it for a fake that answers from a dict, so robots.txt handling, pacing and
retries are exercised exactly as a live crawl would hit them.
"""

from __future__ import annotations

import io
import json
import urllib.error
from email.message import Message

import pytest

from jobradar.sources import ats, boards, greenhouse, http


class FakeNet:
    """URL -> (status, body, headers). Records every URL asked for."""

    def __init__(self, routes):
        self.routes = routes
        self.asked: list[str] = []

    def __call__(self, request, timeout):
        url = request.full_url
        self.asked.append(url)
        answers = self.routes.get(url)
        if answers is None:
            raise urllib.error.HTTPError(url, 404, "not found", Message(), io.BytesIO(b""))
        status, body, headers = answers.pop(0) if isinstance(answers, list) else answers
        if status >= 400:
            msg = Message()
            for key, value in (headers or {}).items():
                msg[key] = value
            raise urllib.error.HTTPError(url, status, "err", msg, io.BytesIO(body.encode()))
        return io.BytesIO(body.encode())


@pytest.fixture
def online(monkeypatch):
    """Network mode with a fake network and no real sleeping."""
    monkeypatch.setenv("JOBRADAR_OFFLINE", "0")
    http._robots.clear()
    http._last_request.clear()
    slept: list[float] = []
    monkeypatch.setattr(http.time, "sleep", lambda s: slept.append(s))

    def install(routes):
        net = FakeNet(routes)
        monkeypatch.setattr(http, "_open", net)
        return net, slept

    yield install
    http._robots.clear()
    http._last_request.clear()


API = "https://api.example.test/v1/jobs"
ROBOTS = "https://api.example.test/robots.txt"


def test_a_url_robots_txt_disallows_is_never_requested(online):
    net, _ = online({ROBOTS: (200, "User-agent: *\nDisallow: /\n", None),
                     API: (200, "{}", None)})
    with pytest.raises(http.Blocked):
        http.get_json(API)
    assert API not in net.asked


def test_a_rule_for_another_agent_does_not_apply(online):
    """SmartRecruiters' shape: LinkedInBot allowed, everyone else not."""
    body = ("User-agent: LinkedInBot\nAllow: /v1/companies/\n"
            "User-agent: *\nDisallow: /\n")
    online({ROBOTS: (200, body, None)})
    assert http.allowed(API)[0] is False


def test_robots_txt_answering_4xx_means_no_rules(online):
    """Ashby answers 401 for robots.txt; RFC 9309 reads any 4xx as "none"."""
    net, _ = online({ROBOTS: (401, "Unauthorized", None), API: (200, '{"jobs": []}', None)})
    assert http.get_json(API) == {"jobs": []}


def test_robots_txt_answering_5xx_means_disallow_everything(online):
    online({ROBOTS: (503, "down", None)})
    with pytest.raises(http.Blocked):
        http.get_json(API)


def test_crawl_delay_is_the_interval_when_longer_than_the_default(online):
    online({ROBOTS: (200, "User-agent: *\nCrawl-delay: 3\nAllow: /\n", None)})
    assert http.allowed(API) == (True, 3.0)


def test_two_requests_to_one_host_are_spaced(online):
    second = API + "?page=2"
    _, slept = online({ROBOTS: (404, "", None), API: (200, "{}", None),
                       second: (200, "{}", None)})
    http.get_json(API, cache=False)
    http.get_json(second, cache=False)
    assert slept and max(slept) > 0.5


def test_a_server_error_is_retried_and_retry_after_is_honoured(online):
    net, slept = online({
        ROBOTS: (404, "", None),
        API: [(503, "busy", {"Retry-After": "7"}), (200, '{"ok": true}', None)],
    })
    assert http.get_json(API, cache=False) == {"ok": True}
    assert net.asked.count(API) == 2
    assert 7.0 in slept


def test_retry_after_is_capped(online):
    _, slept = online({
        ROBOTS: (404, "", None),
        API: [(429, "slow down", {"Retry-After": "86400"}), (200, "{}", None)],
    })
    http.get_json(API, cache=False)
    assert max(slept) <= http.RETRY_AFTER_CAP


def test_robots_txt_is_cached_for_the_next_process(online):
    net, _ = online({ROBOTS: (200, "User-agent: *\nAllow: /\n", None),
                     API: (200, "{}", None)})
    http.get_json(API, cache=False)
    http._robots.clear()                      # a new process
    http.get_json(API, cache=False)
    assert net.asked.count(ROBOTS) == 1


def test_offline_mode_never_asks_for_robots_txt(monkeypatch):
    http.prime(API, '{"cached": 1}')
    monkeypatch.setattr(http, "_open", lambda *a, **k: pytest.fail("network touched"))
    assert http.get_json(API) == {"cached": 1}


# --- adapters -----------------------------------------------------------------


def test_greenhouse_dates_a_job_by_first_publication(monkeypatch):
    """`updated_at` moves on every edit; a May posting ranked as September."""
    payload = {"jobs": [{
        "title": "ML Engineer", "location": {"name": "Berlin"},
        "absolute_url": "https://boards.greenhouse.io/x/jobs/1", "content": "",
        "first_published": "2026-05-22T09:16:29-04:00",
        "updated_at": "2026-09-14T16:01:39-04:00",
    }]}
    monkeypatch.setattr(greenhouse, "get_json", lambda *a, **k: payload)
    (posting,) = greenhouse.fetch("x")
    assert posting.posted.month == 5


def test_greenhouse_survives_null_fields(monkeypatch):
    payload = {"jobs": [{"title": None, "location": {"name": None},
                         "absolute_url": None, "content": None}]}
    monkeypatch.setattr(greenhouse, "get_json", lambda *a, **k: payload)
    (posting,) = greenhouse.fetch("x")
    assert posting.title == "" and posting.location == ""


def test_himalayas_follows_the_cursor(monkeypatch):
    """The API caps limit at 20; asking for 200 in one call returned 20."""
    pages = {
        boards.HIMALAYAS: {"jobs": [{"title": "A", "pubDate": 1}], "nextCursor": "c2"},
        boards.HIMALAYAS + "&cursor=c2": {"jobs": [{"title": "B", "pubDate": 1}],
                                          "nextCursor": None},
    }
    monkeypatch.setattr(boards, "get_json", lambda url, **k: pages[url])
    assert [p.title for p in boards.himalayas()] == ["A", "B"]


def test_himalayas_stops_at_the_limit(monkeypatch):
    page = {"jobs": [{"title": str(i)} for i in range(20)], "nextCursor": "again"}
    calls = []
    monkeypatch.setattr(boards, "get_json", lambda url, **k: calls.append(url) or page)
    assert len(boards.himalayas(limit=40)) == 40
    assert len(calls) == 2


def test_smartrecruiters_is_not_in_the_crawl():
    """Its API host disallows every agent but LinkedInBot in robots.txt."""
    from jobradar import companies

    assert "smartrecruiters" not in companies.SEEDS
    assert companies.BLOCKED["smartrecruiters"]
    assert callable(ats.smartrecruiters)       # the adapter is kept, not called


def test_prime_and_replay_round_trip():
    http.prime(API, json.dumps({"a": 1}))
    assert http.get_json(API) == {"a": 1}
