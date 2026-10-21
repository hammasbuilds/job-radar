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


def test_a_truncated_download_is_retried_not_fatal(monkeypatch, tmp_path):
    import http.client

    from jobradar.sources import http as layer

    monkeypatch.setenv("JOBRADAR_CACHE", str(tmp_path))
    # The suite is offline by default; this test fakes the network itself, below the layer.
    monkeypatch.setenv("JOBRADAR_OFFLINE", "0")
    monkeypatch.setattr(layer, "allowed", lambda url: (True, 0.0))
    monkeypatch.setattr(layer, "_pace", lambda host, interval: None)
    monkeypatch.setattr(layer.time, "sleep", lambda s: None)
    calls = []

    class Body:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return b'{"ok": true}'

    def fake_open(request, timeout):
        calls.append(1)
        if len(calls) == 1:
            raise http.client.IncompleteRead(b"partial", 100)
        return Body()

    monkeypatch.setattr(layer, "_open", fake_open)
    assert layer.get_json("https://jobs.example/api", cache=False) == {"ok": True}
    assert len(calls) == 2


@pytest.mark.parametrize(("text", "terms"), [
    ("Fellows work 40 hours a week for four months.", arrangement.UNSTATED),
    ("Benefits: flexible hours, gym.", arrangement.UNSTATED),
    ("About 10-20 hours a week, paid per task.", arrangement.SMALL),
    ("Commit 15 hours per week.", arrangement.SMALL),
])
def test_hours_decide_small_contracts_by_the_number(text, terms):
    p = job("ML Fellow", text=text)
    assert arrangement.terms(p, "unstated")[0] == terms


def test_public_lane_needs_a_computing_title_not_any_analyst():
    assert not families.is_public_computing("Deputy Director (Financial Analyst)", "Ministry",
                                            "njp")
    assert families.is_public_computing("Data Analyst (BPS-17)", "Ministry", "njp")


def test_a_research_fellowship_outside_ai_is_not_an_ai_programme():
    assert not families.is_program("Research Fellow (Ecology/Soil Science)", "NTU")
    assert families.is_program("Research Fellow (AI for Materials)", "NTU")


def test_the_lens_shows_target_countries_only():
    kept, funnel = pipeline.run([
        job("Machine Learning Engineer", "London, UK; Bengaluru, India", "We sponsor visas.")])
    assert funnel.lens[0].verdict["lens_countries"] == ["United Kingdom"]


@pytest.mark.parametrize(("text", "terms"), [
    ("In the short term, we have focused on interpretability.", arrangement.UNSTATED),
    ("Our office is an hour from the airport.", arrangement.UNSTATED),
    ("This is a short-term contract for three months.", arrangement.SMALL),
    ("Paid hourly, about 25 dollars per hour.", arrangement.SMALL),
])
def test_small_contract_phrases_must_name_the_arrangement(text, terms):
    assert arrangement.terms(job("ML Engineer", text=text), "unstated")[0] == terms


@pytest.mark.parametrize(("title", "tags", "text", "terms"), [
    ("Associate Data Scientist", (), "Internships or part-time roles count as experience.",
     arrangement.UNSTATED),
    ("AI Engineer", (), "Full-time and part-time study modes are offered.", arrangement.FULL_TIME),
    ("AI Engineer (Part-time)", (), "", arrangement.SMALL),
    ("AI Engineer", ("Part Time",), "", arrangement.SMALL),
    ("AI Engineer", (), "This is a part-time position.", arrangement.SMALL),
])
def test_part_time_must_describe_this_role(title, tags, text, terms):
    assert arrangement.terms(job(title, text=text, tags=tags), "unstated")[0] == terms


def test_workable_by_country_asks_each_country_and_follows_pages(monkeypatch):
    from jobradar.sources import open_apis

    asked = []

    def fake(url, **kw):
        asked.append(url)
        if "pageToken" in url:
            return {"jobs": [{"id": "b", "title": "ML Engineer", "url": "https://w/b",
                              "location": {"countryName": "Pakistan"}}]}
        return {"jobs": [{"id": "a", "title": "ML Engineer", "url": "https://w/a",
                          "location": {"city": "Lahore", "countryName": "Pakistan"}}],
                "nextPageToken": "t1"}

    monkeypatch.setattr(open_apis, "get_json", fake)
    got = open_apis.workable_by_country(pages=2, countries=("Pakistan",), queries=("ml",))
    assert [p.url for p in got] == ["https://w/a", "https://w/b"]
    assert all("location=Pakistan" in u for u in asked)
    assert "pageToken=t1" in asked[1]


def test_paid_ai_training_work_is_its_own_lane_and_ordinary_trainers_are_not():
    for title in ("AI Data Trainer", "Mathematics Model Evaluators AI Data Trainers",
                  "LLM AI Quality Analyst Personalization German", "Thai AI Data Annotator"):
        assert families.is_data_work(title), title
    for title in ("Personal Trainer", "Corporate Trainer, Sales", "Data Quality Analyst",
                  "Machine Learning Engineer"):
        assert not families.is_data_work(title), title
    kept, funnel = pipeline.run([
        job("AI Data Trainer", "Remote (worldwide)", "Hourly pay. Set your own schedule.",
            company="Mercor"),
        job("Personal Trainer", "Remote (worldwide)", "Coach clients.", company="Gym"),
        job("ML Engineer, Data Annotation Platform", "Remote (worldwide)", "Build tools.",
            company="Labelco"),
    ])
    lane = {p.company: p.verdict["family"] for p in funnel.lens}
    assert lane.get("Mercor") == families.DATA_WORK
    assert "Gym" not in lane
    # An engineer on an annotation team is an engineer, not data work.
    assert lane.get("Labelco") not in (None, families.DATA_WORK)


def test_the_boards_own_workplace_field_beats_the_prose(monkeypatch):
    from jobradar.filters import remote
    from jobradar.sources import ats

    payload = {"name": "Cusp", "jobs": [
        {"title": "ML Engineer", "location": "Amsterdam", "jobUrl": "https://j/1",
         "descriptionPlain": "Remote-friendly team.", "isRemote": True,
         "workplaceType": "Hybrid"},
        {"title": "ML Engineer", "location": "Belgrade", "jobUrl": "https://j/2",
         "descriptionPlain": "Join us.", "isRemote": True, "workplaceType": "Remote"},
        {"title": "ML Engineer", "location": "Dubai", "jobUrl": "https://j/3",
         "descriptionPlain": "Remote work possible.", "isRemote": False,
         "workplaceType": "OnSite"},
    ]}
    monkeypatch.setattr(ats, "get_json", lambda url, **kw: payload)
    hybrid, remote_job, onsite = ats.ashby("cusp")
    # Ashby flags hybrid jobs isRemote=True; its workplaceType is the answer.
    assert hybrid.workplace == "hybrid" and hybrid.remote_hint is False
    assert remote.classify(hybrid)[0] == remote.HYBRID
    assert remote.classify(remote_job)[0] in (remote.GLOBAL, remote.REGION, remote.COUNTRY)
    assert remote.classify(onsite)[0] == remote.ONSITE


def test_remote_procedure_calls_are_not_remote_work():
    from jobradar.filters import remote

    rpc = job("Agentic AI Engineer", "", "Build services over Remote Procedure Calls (RPC) "
              "and remote sensing data.")
    assert remote.classify(rpc)[0] not in (remote.GLOBAL, remote.REGION, remote.COUNTRY)
    assert remote.classify(job("ML Engineer", "", "This is a remote role."))[0] == remote.REGION


@pytest.mark.parametrize(("title", "text", "tags", "expected"), [
    ("AI Engineer", "Full-time role. Benefits: project-based skill transfer.", (), arrangement.FULL_TIME),
    ("AI Engineer", "We serve project-based industries.", ("Full Time",), arrangement.FULL_TIME),
    ("ML Engineer", "This is a 12-month fixed-term contract.", (), arrangement.CONTRACT),
    ("ML Engineer", "A 3-month contract to start.", (), arrangement.SMALL),
    ("AI Tutor", "Paid hourly. Set your own schedule.", (), arrangement.SMALL),
    ("Data Annotator", "Work on a project basis.", (), arrangement.SMALL),
])
def test_small_contract_needs_the_arrangement_not_a_stray_phrase(title, text, tags, expected):
    from jobradar.filters import employment

    p = job(title, "", text, tags=tags)
    assert arrangement.terms(p, employment.classify(p)[0])[0] == expected


def test_worldwide_remote_work_is_open_even_without_sponsorship():
    tutor = job("AI Tutor - Croatian", "Remote International",
                "Tutor roles may be performed remotely from any location worldwide. For US-based "
                "candidates, please note that we are unable to hire in Wyoming. We are unable to "
                "provide visa sponsorship. US-based candidates: $35/hour.", company="xai")
    v = pipeline.judge(tutor)
    assert v["scope"] == "global"
    assert pipeline.route(v)[0] == ["remote"]


@pytest.mark.parametrize("text", [
    "This role is open to Singapore Citizens or SPR only.",
    "Applicants must be Singaporean or PR.",
    "Malaysians only.",
])
def test_south_east_asian_citizens_only_wording_closes_the_route(text):
    v = pipeline.judge(job("Computer Vision Engineer", "Singapore", text))
    assert pipeline.route(v) == ([], "citizens / nationals only")


@pytest.mark.parametrize(("title", "years"), [
    ("Full-Stack Engineer (5년 이상)", 5),
    ("AI Engineer (경력 7년 이상)", 7),
    ("ML Engineer 5+ years", 5),
    ("ML Engineer (3 years minimum)", 3),
    ("Machine Learning Engineer II", None),
    ("ML Engineer, Model Year 2027", None),
])
def test_years_written_in_the_title_are_read(title, years):
    from jobradar.filters import seniority

    assert seniority.years_in_title(title) == years


def test_a_title_asking_for_five_years_leaves_the_junior_lens():
    kept, funnel = pipeline.run([job("AI Engineer (5년 이상)", "Seoul, South Korea",
                                     "We will sponsor your visa.")])
    assert not funnel.lens


@pytest.mark.parametrize(("title", "is_target"), [
    ("Salesforce Developer - Service Cloud, Experience Cloud & AI (100% Remote within Poland)", False),
    ("Full-Stack Developer | Mid-Senior | AI Tools", False),
    ("Software Engineer - Backend + AI", False),
    ("Research Fellow (Ecology/Biogeochemistry/Earth/Soil Science/Hydrology/Computer Science)", False),
    ("Cybersecurity Consultant (AI), Cybersecurity Engineering Centre", False),
    ("Research Fellow (AI for Materials)", True),
    ("Field Engineer - Robotics And AI", True),
    ("Software Engineer, Machine Learning", True),
    ("Research Engineer, Cybersecurity RL (Reinforcement Learning)", True),
])
def test_an_ai_word_in_the_tail_does_not_make_another_job_an_ai_one(title, is_target):
    from jobradar.filters import fit

    assert bool(fit.role_match(title)) is is_target


@pytest.mark.parametrize(("location", "countries"), [
    ("*HQ - San Francisco, CA", ["United States"]),
    ("US-CA-Menlo Park", ["United States"]),
    ("San Mateo", ["United States"]),
    ("Ottawa", ["Canada"]),
    ("London & San Francisco", ["United Kingdom", "United States"]),
    ("R&D Centre, Munich", ["Germany"]),
])
def test_us_and_canadian_hubs_are_placed_so_they_leave_the_target_lens(location, countries):
    assert places.countries_of(location) == countries


@pytest.mark.parametrize(("body", "company"), [
    ("DevOps Engineer (QVAC): | AI Inference Engineer (QVAC) | Remote", "QVAC"),
    ("Founding Engineer (Security / AI / Distributed Systems) — Stealth Project\nWe hire.",
     "(unnamed, HN thread)"),
    ("Rebar | Software Engineer, Applied AI | New York", "Rebar"),
])
def test_a_hacker_news_role_is_not_read_as_the_company(body, company):
    from jobradar.sources.boards import hn_roles

    assert hn_roles(body)[0] == company


@pytest.mark.parametrize(("company", "public"), [
    ("Northern University Nowshera", False),
    ("Beaconhouse National University", False),
    ("University of the Punjab", True),
    ("COMSATS University Islamabad", True),
    ("National University of Modern Languages", True),
])
def test_a_university_is_public_sector_only_when_it_is_a_public_one(company, public):
    assert families.is_public_computing("Lecturer Computer Science", company) is public


def test_image_and_video_generation_is_generative_ai():
    assert families.classify("Member of Technical Staff - Image / Video Generation")[0] == \
        families.GENAI
    assert families.classify("Computer Vision Engineer")[0] == families.CV


def test_korean_years_in_the_body_are_read():
    from jobradar.filters import seniority

    assert seniority.korean_years("자격요건: 관련 경력 2년 이상") == 2
    assert seniority.korean_years("3년 계약직") is None


def test_a_programme_at_an_ai_lab_counts_whatever_its_field():
    assert families.is_program("Anthropic Fellows Program, Economics & Policy", "anthropic")
    assert not families.is_program("Research Fellow (Ecology/Soil Science)", "NTU")


def test_yc_one_liners_that_never_say_ai_are_still_ai():
    from jobradar.sources import yc_recent

    for text in ("Agentic video editor", "Foundation models for 24/7 Earth Observation",
                 "Interpretability and reasoning infra for foundation models."):
        assert yc_recent._AI.search(text), text
    assert not yc_recent._AI.search("Tankless Dive Gear - Breath Autonomy at Sea")


@pytest.mark.parametrize(("text", "flags"), [
    ("A PhD in Computer Science is required.", ["phd"]),
    ("You have a PhD with publications in top-tier venues.", ["phd"]),
    ("PhD or Master's degree in CS.", []),
    ("PhD preferred.", []),
    ("Extensive and proven track record of shipping deep learning systems.", ["experienced"]),
    ("We are seeking experienced AI scientists.", ["experienced"]),
    ("Mentorship from experienced AI engineers and architects.", []),
    ("DeepLight AI is a specialist consultancy with extensive experience in data.", []),
    ("Proven experience with Python is a plus.", []),
    ("Some experience with PyTorch.", []),
])
def test_what_a_posting_asks_for_in_words(text, flags):
    from jobradar.filters import seniority

    assert seniority.bar_flags(text) == flags
