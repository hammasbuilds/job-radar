"""Accelerator and investor portfolios read from job-board sitemaps."""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

from jobradar import store
from jobradar.sources import portfolios

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from fetch_portfolios import judge  # noqa: E402

BOARD = "https://jobs.example.vc"
INDEX = f"""<?xml version="1.0"?><sitemapindex>
<sitemap><loc>{BOARD}/sitemap_companies.xml</loc></sitemap>
<sitemap><loc>{BOARD}/sitemap_jobs.xml</loc></sitemap>
<sitemap><loc>{BOARD}/sitemap_companies.xml</loc></sitemap>
</sitemapindex>"""
COMPANIES = f"""<urlset>
<url><loc>{BOARD}/companies/helgen-technologies</loc></url>
<url><loc>{BOARD}/companies/xairos-2-ca2f9510-1b2c-4d3e-8f90-123456789abc</loc></url>
<url><loc>{BOARD}/jobs</loc></url>
</urlset>"""
JOBS = f"""<urlset>
<url><loc> {BOARD}/companies/helgen-technologies/jobs/4411-senior-ml-engineer </loc></url>
<url><loc>{BOARD}/companies/helgen-technologies/jobs/4412-account-executive</loc></url>
<url><loc>{BOARD}/companies/quiet-labs/jobs/77-junior-computer-vision-engineer-ii</loc></url>
</urlset>"""
PAGES = {f"{BOARD}/sitemap.xml": INDEX, f"{BOARD}/sitemap_companies.xml": COMPANIES,
         f"{BOARD}/sitemap_jobs.xml": JOBS}
PROGRAMME = ("Example VC", "investor", BOARD)


def test_names_and_titles_come_back_readable_from_addresses():
    assert portfolios.name_from_slug("helgen-technologies") == "Helgen Technologies"
    assert portfolios.name_from_slug("xairos-2-ca2f9510-1b2c-4d3e-8f90-123456789abc") == "Xairos"
    assert portfolios.name_from_slug("acme-3") == "Acme"
    assert portfolios.name_from_slug("spindle-ai-spindle-ai") == "Spindle Ai"
    assert portfolios.name_from_slug("walla-walla") == "Walla Walla"
    assert portfolios.title_from_slug("head-of-ai-and-ml-for-search") == \
        "Head of AI and ML for Search"
    assert portfolios.title_from_slug("the-llm-engineer-ii") == "The LLM Engineer II"


def test_fetch_follows_the_index_once_and_keeps_companies_without_jobs(monkeypatch):
    asked: list[str] = []

    def fake(url, **kw):
        asked.append(url)
        return PAGES[url]

    monkeypatch.setattr(portfolios, "get_text", fake)
    p = portfolios.fetch(PROGRAMME)
    assert asked.count(f"{BOARD}/sitemap_companies.xml") == 1      # repeated child read once
    assert set(p.companies) == {"helgen-technologies", "quiet-labs",
                                "xairos-2-ca2f9510-1b2c-4d3e-8f90-123456789abc"}
    assert p.companies["quiet-labs"] == f"{BOARD}/companies/quiet-labs"  # known only from a job
    assert [j["title"] for j in p.jobs] == ["Senior ML Engineer", "Account Executive",
                                            "Junior Computer Vision Engineer II"]
    assert p.read == 3 and p.failed == []      # the index and its two children


def test_an_unreadable_or_missing_sitemap_is_reported_and_the_others_still_count(monkeypatch):
    index = INDEX.replace("sitemap_jobs.xml", "sitemap_jobs1.xml") + \
        f"<sitemapindex><sitemap><loc>{BOARD}/sitemap_jobs2.xml</loc></sitemap></sitemapindex>"
    pages = {f"{BOARD}/sitemap.xml": index, f"{BOARD}/sitemap_jobs1.xml": JOBS,
             f"{BOARD}/sitemap_jobs2.xml": "<html>Page not found</html>"}

    def fake(url, **kw):
        if "companies" in url:
            raise OSError("connection reset")
        return pages[url]

    monkeypatch.setattr(portfolios, "get_text", fake)
    p = portfolios.fetch(PROGRAMME)
    assert len(p.jobs) == 3 and p.read == 2
    assert len(p.failed) == 2
    assert "connection reset" in p.failed[0] and "not a sitemap" in p.failed[1]


def test_a_board_that_lists_company_job_pages_still_yields_its_companies(monkeypatch):
    flat = f"""<urlset><url><loc>{BOARD}/</loc></url><url><loc>{BOARD}/jobs</loc></url>
    <url><loc>{BOARD}/company/valon</loc></url><url><loc>{BOARD}/jobs/valon</loc></url>
    <url><loc>{BOARD}/jobs/base-power</loc></url></urlset>"""
    monkeypatch.setattr(portfolios, "get_text", lambda url, **kw: flat)
    p = portfolios.fetch(PROGRAMME)
    assert set(p.companies) == {"valon", "base-power"} and p.jobs == []


def test_judging_separates_ai_roles_and_senior_titles():
    rows = {t: judge({"title": t, "company": "c", "company_slug": "c", "url": t})
            for t in ("Senior ML Engineer", "Account Executive",
                      "Junior Computer Vision Engineer II")}
    assert rows["Senior ML Engineer"]["ai"] and not rows["Senior ML Engineer"]["junior"]
    assert not rows["Account Executive"]["ai"] and not rows["Account Executive"]["junior"]
    assert rows["Junior Computer Vision Engineer II"]["junior"]


def test_saving_replaces_a_portfolio_but_a_failed_read_keeps_the_last_copy(tmp_path, monkeypatch):
    db = tmp_path / "radar.sqlite3"
    monkeypatch.setattr(portfolios, "get_text", lambda url, **kw: PAGES[url])
    p = portfolios.fetch(PROGRAMME)
    store.save_portfolio(p, [judge(j) for j in p.jobs], db)

    conn = sqlite3.connect(db)
    helgen = conn.execute("SELECT name, roles, ai_roles, junior_ai FROM portfolio_company "
                          "WHERE slug = 'helgen-technologies'").fetchone()
    assert helgen == ("Helgen Technologies", 2, 1, 0)
    assert conn.execute("SELECT companies, roles, ai_roles, junior_ai FROM portfolio_programme"
                        ).fetchone() == (3, 3, 2, 1)
    conn.close()

    nothing = portfolios.Portfolio("Example VC", "investor", BOARD, failed=["all down"])
    store.save_portfolio(nothing, [], db)
    conn = sqlite3.connect(db)
    assert conn.execute("SELECT COUNT(*) FROM portfolio_company").fetchone()[0] == 3
    conn.close()
    assert store.portfolio_age_hours(db) < 1
