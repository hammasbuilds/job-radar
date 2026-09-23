"""The Mustakbil adapter, tested on the shapes its pages actually take.

Every fixture below is trimmed from a real page fetched during development,
including the awkward ones. The board's JSON-LD is well-formed but it omits
fields a reader would expect — most postings carry no `jobLocation` at all —
and the adapter has to do something defensible with that rather than emit an
empty string that reads downstream as "location unknown".
"""

from __future__ import annotations

from jobradar.sources import mustakbil

PAGE = """<html><head>
<script type="application/ld+json">
{"@context":"https://schema.org","@type":"JobPosting",
 "title":"Machine Learning Engineer",
 "description":"<p>Build and ship models.</p><li>PyTorch</li>",
 "datePosted":"2026-09-01T10:00:00+00:00",
 "validThrough":"2027-01-01T14:00:00.0000000Z",
 "employmentType":"FULL_TIME",
 "hiringOrganization":{"@type":"Organization","name":"Some Firm "},
 "jobLocation":{"@type":"Place","address":{"addressLocality":"Lahore",
   "addressRegion":"Punjab","addressCountry":"PK"}}}
</script></head><body>...</body></html>"""

NO_LOCATION = """<script type="application/ld+json">
{"@type":"JobPosting","title":"Data Scientist","description":"x",
 "datePosted":"2026-08-02T00:00:00+00:00",
 "jobLocationType":"TELECOMMUTE",
 "hiringOrganization":{"name":"Remote Co"}}
</script>"""

NOT_A_JOB = """<script type="application/ld+json">
{"@type":"BreadcrumbList","itemListElement":[]}</script>"""

BROKEN_JSON = """<script type="application/ld+json">{"@type": "JobPosting",</script>"""


def test_reads_the_structured_record():
    p = mustakbil._posting_from(PAGE, "https://x/jobs/job/1")
    assert p is not None
    assert p.title == "Machine Learning Engineer"
    assert p.company == "Some Firm"          # trailing space stripped
    assert p.location == "Lahore, Punjab"
    assert p.source == "mustakbil"
    assert "PyTorch" in p.text and "<li>" not in p.text
    assert p.posted is not None and p.posted.year == 2026
    assert p.tags == ("FULL_TIME",)


def test_a_missing_location_becomes_pakistan_not_empty():
    """An empty string here would read downstream as 'unknown', and the one
    thing that is certain about a job on this board is the country."""
    p = mustakbil._posting_from(NO_LOCATION, "https://x/jobs/job/2")
    assert p.location == "Pakistan"
    assert p.remote_hint is True


def test_a_page_with_no_job_posting_is_skipped_not_raised():
    assert mustakbil._posting_from(NOT_A_JOB, "https://x/1") is None
    assert mustakbil._posting_from("<html></html>", "https://x/2") is None


def test_malformed_json_ld_does_not_end_the_run():
    """A sitemap is generated ahead of the crawl, so some pages will be
    half-rendered or gone by the time they are fetched."""
    assert mustakbil._posting_from(BROKEN_JSON, "https://x/3") is None


def test_seven_digit_fractional_seconds_parse():
    """Their validThrough is .0000000Z, which fromisoformat rejects. The
    adapter truncates to microseconds rather than dropping the date."""
    assert mustakbil._iso("2027-01-01T14:00:00.0000000Z") is not None
    assert mustakbil._iso("2026-09-01T10:00:00+00:00") is not None
    assert mustakbil._iso("") is None
    assert mustakbil._iso("not a date") is None


def test_only_job_urls_come_out_of_the_sitemap(monkeypatch):
    xml = ("<urlset><url><loc>https://www.mustakbil.com/jobs/job/1</loc></url>"
           "<url><loc>https://www.mustakbil.com/companies/x</loc></url>"
           "<url><loc>https://www.mustakbil.com/jobs/job/2</loc></url></urlset>")
    monkeypatch.setattr(mustakbil, "get_text", lambda *a, **k: xml)
    urls = mustakbil.job_urls()
    assert urls == ["https://www.mustakbil.com/jobs/job/1",
                    "https://www.mustakbil.com/jobs/job/2"]
    assert mustakbil.job_urls(limit=1) == urls[:1]


def test_an_unreachable_sitemap_returns_nothing_rather_than_raising(monkeypatch):
    monkeypatch.setattr(mustakbil, "get_text", lambda *a, **k: None)
    assert mustakbil.job_urls() == []


FEED = """<rss><channel>
<item><title><![CDATA[ Senior AI Engineer Jobs in Lahore, Pakistan]]></title>
<link>https://www.mustakbil.com/jobs/job/9</link>
<company><![CDATA[Nokhba &amp; Co]]></company>
<city>Lahore</city><country>Pakistan</country><category>IT - Other</category>
<pubdate>Tue, 22 Sep 2026 11:09:07 &#x2B;0000</pubdate>
<description><![CDATA[<p>Ship models.</p>]]></description></item>
<item><title>No link here</title></item>
</channel></rss>"""


def test_the_feed_reads_one_request_into_postings(monkeypatch):
    monkeypatch.setattr(mustakbil, "get_text", lambda *a, **k: FEED)
    ps = mustakbil.fetch_feed()
    assert len(ps) == 1                      # the item with no link is skipped
    p = ps[0]
    assert p.company == "Nokhba & Co"        # entity decoded
    assert p.location == "Lahore, Pakistan"
    assert p.posted is not None and p.posted.day == 22
    assert p.tags == ("IT - Other",)


def test_the_location_is_stripped_out_of_the_title(monkeypatch):
    """Every title on this feed ends '... Jobs in <city>, <country>'. Left in,
    the fit score sees the city twice and every posting part-matches its own
    location."""
    monkeypatch.setattr(mustakbil, "get_text", lambda *a, **k: FEED)
    assert mustakbil.fetch_feed()[0].title == "Senior AI Engineer"


def test_an_escaped_rfc822_timezone_still_parses():
    """Their pubdate arrives as '+0000' HTML-escaped to '&#x2B;0000'."""
    assert mustakbil._rss_date("Tue, 22 Sep 2026 11:09:07 &#x2B;0000") is not None
    assert mustakbil._rss_date("Tue, 22 Sep 2026 11:09:07 +0000") is not None
    assert mustakbil._rss_date("nonsense") is None
    assert mustakbil._rss_date("") is None


def test_an_empty_feed_is_not_an_error(monkeypatch):
    monkeypatch.setattr(mustakbil, "get_text", lambda *a, **k: None)
    assert mustakbil.fetch_feed() == []
