"""The 2026-10-20 additions: six title families, junior-only, Asia and per-country reading,
India and Bangladesh left out, work arrangement, the Pakistan public-sector lane, fellowships,
the National Job Portal parser, recent YC, and the directory."""

from pathlib import Path

import pytest

from jobradar import directory, families, pipeline, profile
from jobradar.filters import arrangement, places
from jobradar.posting import Posting
from jobradar.sources import njp, yc_recent

FIXTURES = Path(__file__).parent / "fixtures"


def job(title, location="", text="", company="Acme", source="greenhouse", tags=()):
    return Posting(source=source, company=company, title=title, location=location,
                   url=f"https://example.com/{abs(hash((title, location, company)))}",
                   text=text, posted=None, remote_hint=False, tags=tuple(tags))


@pytest.mark.parametrize(("title", "family", "track"), [
    ("ML/DL Engineer", families.ML_DL, families.ENGINEER),
    ("Machine Learning Engineer", families.ML, families.ENGINEER),
    ("Machine Learning Researcher", families.ML, families.RESEARCHER),
    ("Deep Learning Engineer", families.DL, families.ENGINEER),
    ("Deep Learning Researcher", families.DL, families.RESEARCHER),
    ("Computer Vision Engineer", families.CV, families.ENGINEER),
    ("Computer Vision Research Scientist", families.CV, families.RESEARCHER),
    ("Generative AI Engineer", families.GENAI, families.ENGINEER),
    ("LLM Engineer", families.GENAI, families.ENGINEER),
    ("Agentic AI Engineer", families.AGENTIC, families.ENGINEER),
    ("Agentic AI Researcher", families.AGENTIC, families.RESEARCHER),
    ("NLP Engineer", families.OTHER, families.ENGINEER),
    ("Anthropic Fellows Program - AI Safety", families.PROGRAM, families.RESEARCHER),
])
def test_title_families(title, family, track):
    assert families.classify(title, "Anthropic") == (family, track)


def test_junior_only_means_at_most_two_years():
    assert profile.MAX_YEARS == 2
    kept, funnel = pipeline.run([
        job("Machine Learning Engineer", "Berlin, Germany", "We will sponsor your visa. "
            "You have 2 years of experience with PyTorch."),
        job("Machine Learning Engineer II", "Berlin, Germany", "We will sponsor your visa. "
            "You have 3+ years of experience with PyTorch."),
        job("Senior Machine Learning Engineer", "Berlin, Germany", "We sponsor visas."),
    ])
    assert [p.title for p in kept] == ["Machine Learning Engineer"]
    assert "wants 3+ years" in funnel.killed and "senior level" in funnel.killed


@pytest.mark.parametrize(("location", "countries", "regions"), [
    ("Kuala Lumpur", ["Malaysia"], {places.R_ASIA}),
    ("Shenzhen, China; Singapore", ["China", "Singapore"], {places.R_ASIA}),
    ("Seoul, Republic of Korea", ["South Korea"], {places.R_ASIA}),
    ("Dubai / London", ["United Arab Emirates", "United Kingdom"],
     {places.R_GULF, places.R_EUROPE}),
    ("Zagreb, City of Zagreb, Croatia", ["Croatia"], {places.R_EUROPE}),
    ("Istanbul", ["Turkey"], {places.R_EUROPE}),
    ("Bengaluru, India", ["India"], {places.R_EXCLUDED}),
    ("Dhaka", ["Bangladesh"], {places.R_EXCLUDED}),
    ("Cambridge, MA", ["United States"], {places.R_OTHER}),
])
def test_countries_and_regions(location, countries, regions):
    assert places.countries_of(location) == countries
    assert places.regions_of(location) == regions


def test_india_and_bangladesh_only_roles_are_left_out_but_not_mixed_or_global_ones():
    roles = [
        job("Machine Learning Engineer", "Bengaluru, India"),
        job("Machine Learning Engineer", "Dhaka, Bangladesh", company="Beta"),
        job("Machine Learning Engineer", "Bengaluru, India; Singapore", company="Gamma"),
        job("Machine Learning Engineer", "Remote - worldwide", company="Delta",
            text="Work from anywhere in the world."),
    ]
    kept, funnel = pipeline.run(roles)
    assert funnel.killed.get(pipeline.EXCLUDED) == 2
    lens = {p.company for p in funnel.lens}
    assert lens == {"Gamma", "Delta"}


def test_asia_routes_like_the_gulf_silence_is_a_route_refusal_is_not():
    kept, funnel = pipeline.run([
        job("Computer Vision Engineer", "Singapore", "Build perception models."),
        job("Computer Vision Engineer", "Singapore", "We are unable to sponsor visas.",
            company="Beta"),
    ])
    assert [p.company for p in kept] == ["Acme"]
    assert "asia" in kept[0].section


def test_the_lens_keeps_target_countries_only_with_the_route_as_a_value():
    kept, funnel = pipeline.run([
        job("Machine Learning Engineer", "Paris, France", "Onsite in Paris."),
        job("Machine Learning Engineer", "Austin, TX", "Onsite.", company="Beta"),
    ])
    assert [p.company for p in funnel.lens] == ["Acme"]
    v = funnel.lens[0].verdict
    assert v["countries"] == ["France"] and v["route"].startswith("onsite")
    assert v["workplace"] == arrangement.ONSITE


@pytest.mark.parametrize(("text", "tags", "terms"), [
    ("Part-time, 10-20 hours a week, paid hourly.", (), arrangement.SMALL),
    ("A 3-month contract to label driving data.", (), arrangement.SMALL),
    ("Freelancers and B2B contractors welcome.", (), arrangement.CONTRACT),
    ("This is a full-time permanent role.", (), arrangement.FULL_TIME),
    ("Build models.", (), arrangement.UNSTATED),
])
def test_terms(text, tags, terms):
    from jobradar.filters import employment

    p = job("ML Engineer", text=text, tags=tags)
    form, _ = employment.classify(p)
    assert arrangement.terms(p, form)[0] == terms


def test_pakistan_public_sector_lane_takes_computing_posts_from_government():
    roles = [
        job("Assistant Director (IT)", "Islamabad, Pakistan", source="njp",
            company="Ministry of IT & Telecom", tags=("public sector",)),
        job("Lecturer Computer Science", "Lahore, Pakistan",
            company="University of the Punjab"),
        job("Assistant Director (Legal)", "Islamabad, Pakistan", source="njp",
            company="EXIM Bank of Pakistan", tags=("public sector",)),
        job("IT Systems Engineer", "Oxford, UK", company="University of Oxford"),
    ]
    kept, funnel = pipeline.run(roles)
    lane = {(p.title, p.verdict["family"]) for p in funnel.lens}
    assert ("Assistant Director (IT)", families.PUBLIC) in lane
    assert ("Lecturer Computer Science", families.PUBLIC) in lane
    titles = {t for t, _ in lane}
    assert "Assistant Director (Legal)" not in titles  # not a computing post
    assert "IT Systems Engineer" not in titles  # public employer, but not in Pakistan


def test_fellowships_skip_the_title_rule():
    kept, funnel = pipeline.run([
        job("Anthropic Fellows Program - AI Safety", "London, UK; Remote (US)",
            "We are not currently able to sponsor visas for fellows.", company="anthropic"),
    ])
    assert pipeline.ROLE not in funnel.killed
    assert funnel.lens and funnel.lens[0].verdict["family"] == families.PROGRAM


def test_njp_job_page_parses():
    page = (FIXTURES / "njp_job.html").read_text(encoding="utf-8")
    p = njp.parse(page, "https://njp.gov.pk/jobs/9844")
    assert p.title == "Team Lead Legal/Senior Manager Legal/Manager Legal"
    assert p.company == "EXIM Bank of Pakistan"
    assert p.location == "Islamabad, Pakistan"
    assert "Grade: M4" in p.text and "Apply by:" in p.text
    assert "public sector" in p.tags
    assert njp.parse("<html>nothing</html>", "x") is None


def test_yc_page_linkedin_skips_ycs_own_profile(monkeypatch):
    page = ('<a href="https://www.linkedin.com/company/y-combinator/">YC</a>'
            '<a href="https://www.linkedin.com/company/stormy-ai/">LinkedIn</a>')
    monkeypatch.setattr(yc_recent, "get_text", lambda url, **kw: page)
    assert yc_recent.linkedin_from_page("stormy") == "https://www.linkedin.com/company/stormy-ai/"
    assert yc_recent.search_link("Stormy AI").endswith("keywords=Stormy%20AI")


def test_directory_states_pay_only_with_a_source():
    for e in directory.ENTRIES:
        assert e["kind"] in directory.KINDS
        assert e["url"].startswith("http")
        if e["pay"] != directory.CHECK:
            assert e["pay_source"], f"{e['name']}: a stated amount needs its source"
    names = {e["name"] for e in directory.ENTRIES}
    for wanted in ("Mercor", "DataAnnotation", "Alignerr", "micro1", "AfterQuery", "Shipd",
                   "Datacurve", "Anthropic Fellows Program", "HEC NRPU research grants",
                   "National Job Portal", "Y Combinator"):
        assert wanted in names
    kinds = {e["kind"] for e in directory.ENTRIES}
    assert kinds == set(directory.KINDS)
    assert sum(e["kind"] == directory.ACCELERATOR for e in directory.ENTRIES) >= 20
