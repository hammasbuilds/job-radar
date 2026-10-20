"""Programmes, platforms, accelerators, grants and Pakistani public-sector sources.

Written into the `directory` table by every crawl, with a live count: how many postings in
the lens right now come from that organisation (for fellowships, only its programme
postings). The list is curated by hand and its links are checked by
`scripts/check_directory.py`.

**Pay is stated only where it was verified**, with where and when. Everything else says to
check the official page, because a stipend typed from memory and wrong by a factor of two is
worse than none. `who` says who may apply as the official page states it; where the page is
silent it says so rather than guessing. Verified 2026-10-21:

  Anthropic Fellows  $3,850/week stipend (about $16,700/month) and ~$15k/month compute, from
                     Anthropic's own Greenhouse postings; rolling applications for a January
                     2027 cohort; needs US, UK or Canada work authorisation, no visa sponsorship.
  Astra              $8,400/month stipend and ~$15k/month compute (Constellation's Astra page).
  Pivotal            GBP 15,000-18,000 for 15 weeks in London plus GBP 1,800/month housing for
                     non-Londoners; applications close 1 Nov 2026 (its fellowship page).
  MATS               $1,250/week stipend and $2k/week compute on the home page; its FAQ says
                     $1,600/week. The site disagrees with itself, so both are given.
  OpenAI Residency   $18.3k/month base, six months, San Francisco (its 2026 posting, read via a
                     VC jobs-board mirror because openai.com refuses scripted requests).
  AI work platforms  hourly ranges only where the platform's own site prints them.
"""

from __future__ import annotations

AI_WORK = "AI work platform"
FELLOWSHIP = "Fellowship / paid programme"
ACCELERATOR = "Accelerator"
PK_GRANT = "Pakistan grant / funding"
PK_GOV = "Pakistan government jobs"

KINDS = (AI_WORK, FELLOWSHIP, ACCELERATOR, PK_GRANT, PK_GOV)
CHECK = "check the official page"
NOT_STATED = "Not stated on the official site"


def E(kind, name, url, what, *, jobs_url="", region="global", pay="", pay_source="",  # noqa: N802
      who="", match=""):
    return {"kind": kind, "name": name, "url": url, "jobs_url": jobs_url, "region": region,
            "what": what, "pay": pay or CHECK, "pay_source": pay_source, "who": who,
            "match": match}


ENTRIES = [
    # --- AI work platforms: contract and small-contract work training and checking models ----
    # `who` is from each platform's own eligibility, FAQ or help page, checked 2026-10-21.
    # Pakistan, UAE and Malaysia are named wherever the page lists countries.
    E(AI_WORK, "Mercor", "https://www.mercor.com", "Expert contract work for AI labs: "
      "coding, research, domain experts", jobs_url="https://work.mercor.com/explore",
      pay="Average contracted rate $107/hr (listings range widely by field)",
      pay_source="mercor.com home page, checked 2026-10-21",
      who="Only in supported countries: Pakistan is on Mercor's unsupported list; UAE and "
      "Malaysia are supported (talent.docs.mercor.com supported-countries policy)",
      match="mercor"),
    E(AI_WORK, "DataAnnotation", "https://www.dataannotation.tech",
      "Paid tasks writing and rating AI responses; coding and STEM tracks",
      jobs_url="https://www.dataannotation.tech/faq",
      pay="General from $25-50/hr; coding $40-150+/hr; STEM and professional $40-125+/hr",
      pay_source="DataAnnotation FAQ, checked 2026-10-21",
      who="Bachelor's or equivalent experience for general work; STEM needs master's/PhD "
      "(or bachelor's + 10 years); fluent English. Countries not stated on the official "
      "site; secondary guides (aitrainer.work) say US, UK, Canada, Australia, NZ, Ireland",
      match="dataannotation"),
    E(AI_WORK, "Alignerr", "https://www.alignerr.com", "Labelbox's expert network for AI "
      "training data", jobs_url="https://www.alignerr.com/en/jobs",
      pay="Listed roles $20-120/hr; site states $80/hr average",
      pay_source="alignerr.com home page job list, checked 2026-10-21",
      who="FAQ: applicants worldwide who meet skill and English requirements; students may "
      "apply; no visa sponsorship. Its visa FAQ says identity checks accept only US IDs",
      match="alignerr"),
    E(AI_WORK, "micro1", "https://www.micro1.ai", "AI-vetted contract engineers and "
      "experts for AI training", jobs_url="https://www.micro1.ai/experts/opportunities",
      who=NOT_STATED + "; rate shown per project before you accept, paid twice a month",
      match="micro1"),
    E(AI_WORK, "AfterQuery", "https://www.afterquery.com", "Expert data for frontier "
      "labs; contract research and coding work",
      who=NOT_STATED + " (it links no expert sign-up page); secondary listings (aitrainer.work, remowork.life) show "
      "licensed-professional roles, e.g. engineers needing a US state PE licence",
      match="afterquery"),
    E(AI_WORK, "Datacurve", "https://datacurve.ai", "Coding data for AI labs; runs Shipd",
      jobs_url="https://datacurve.ai/careers",
      who="Its careers page lists staff roles in San Francisco; contract coding work goes "
      "through Shipd", match="datacurve"),
    E(AI_WORK, "Shipd", "https://shipd.ai", "Paid coding challenges and bounties (by Datacurve)",
      pay="Bounties of $80-220 per listed issue or challenge",
      pay_source="shipd.ai challenge list, checked 2026-10-21",
      who="Terms: 18+, not located in or resident of a US-embargoed country; projects are "
      "by invitation to top contributors", match="shipd"),
    E(AI_WORK, "Outlier", "https://outlier.ai", "Scale AI's contributor platform for AI "
      "training tasks", jobs_url="https://outlier.ai/legal/flexible-working-guidelines",
      who="At least an associate degree; ID and phone from your country. Pakistan is NOT on "
      "its list of countries you may work from; UAE and Malaysia are", match="outlier"),
    E(AI_WORK, "Turing", "https://www.turing.com", "Remote engineers and AGI-lab data work",
      jobs_url="https://www.turing.com/jobs",
      who=NOT_STATED + " (no country list); Turing does not provide visas and requires "
      "strong English; country limits are set per posting", match="turing"),
    E(AI_WORK, "Toloka", "https://toloka.ai", "Data labelling and expert tasks; its "
      "contributor sign-up now redirects to Mindrift", jobs_url="https://mindrift.ai",
      who="Same Toloka eligibility rules as Mindrift: 18+, not in a sanctioned country",
      match="toloka"),
    E(AI_WORK, "Mindrift", "https://mindrift.ai", "Expert AI training tasks (Toloka)",
      jobs_url="https://mindrift.ai/apply",
      pay="Entry level $15-30/hr; domain experts $60-100+/hr",
      pay_source="mindrift.ai home page, checked 2026-10-21",
      who="18+. Restricted list (Afghanistan, China, Iran, Russia and others) does not "
      "include Pakistan, UAE or Malaysia; projects can add their own country limits",
      match="mindrift"),
    E(AI_WORK, "Prolific", "https://www.prolific.com", "Paid research studies and AI tasks",
      jobs_url="https://participant-help.prolific.com/en/article/628d72",
      who="18+, living in a supported country: UAE, India and Indonesia are listed; "
      "Pakistan and Malaysia are not (waitlist only)", match="prolific"),
    E(AI_WORK, "Invisible Technologies", "https://invisibletech.ai",
      "AI training operations; expert contractors through its Meridial network",
      jobs_url="https://www.meridial.ai",
      who=NOT_STATED + "; Meridial says project availability depends on geographic "
      "eligibility", match="invisible"),
    E(AI_WORK, "Surge AI", "https://surgehq.ai", "Expert human data for LLMs",
      jobs_url="https://surgehq.ai/careers", who=NOT_STATED + "; remote contractor roles "
      "are listed on its careers page", match="surge"),
    E(AI_WORK, "Handshake AI", "https://joinhandshake.com/ai/", "Handshake's AI fellowship "
      "work for students and graduates",
      pay="Listed roles up to $17/hr (AI evaluation) to $125/hr (specialist)",
      pay_source="joinhandshake.com/ai trending roles, checked 2026-10-21",
      who="Must be based in the US with US work authorisation Handshake supports (SSN or "
      "ITIN); work must be done from the US; STEM OPT not supported", match="handshake"),
    E(AI_WORK, "Snorkel AI", "https://snorkel.ai", "Expert data development; contributor "
      "network", jobs_url="https://snorkel.ai/expert-community/",
      who="Projects typically need an advanced degree; only select locations, confirmed "
      "during the application (no country list published)", match="snorkel"),
    E(AI_WORK, "SuperAnnotate", "https://www.superannotate.com", "Annotation platform and "
      "expert workforce", who=NOT_STATED, match="superannotate"),
    E(AI_WORK, "Appen (CrowdGen)", "https://www.appen.com", "Long-running data work "
      "platform; contributor work is on CrowdGen", jobs_url="https://crowdgen.com",
      pay="Expert domains listed up to $90-400/hr; rate depends on location and skills",
      pay_source="crowdgen.com (Appen) home page, checked 2026-10-21",
      who=NOT_STATED + " (no country list on CrowdGen's home page)", match="appen"),
    E(AI_WORK, "TELUS Digital AI", "https://www.telusdigital.com",
      "AI community tasks (formerly TELUS International)",
      who=NOT_STATED + "; its AI Community job search refuses scripted requests",
      match="telus"),
    E(AI_WORK, "Pareto", "https://pareto.ai", "Expert data for AI labs",
      jobs_url="https://pareto.ai/experts",
      who=NOT_STATED + "; applications reviewed on a rolling basis", match="pareto"),
    E(AI_WORK, "Revelo", "https://www.revelo.com", "Remote engineers, LatAm-weighted",
      jobs_url="https://www.revelo.com/work",
      pay="Full-time contract roles up to US$95,000 a year; AI training paid by hour or task",
      pay_source="revelo.com/work, checked 2026-10-21",
      who="Engineers in Latin America working remotely from their home country; no visa "
      "or relocation", match="revelo"),
    E(AI_WORK, "Andela", "https://www.andela.com", "Remote engineering talent marketplace",
      jobs_url="https://help.andela.com/hc/en-us/articles/32941472534035",
      who="Must live in an approved region: Pakistan and UAE are approved; Malaysia is not "
      "listed (Andela help centre, updated 11 Mar 2026)", match="andela"),
    E(AI_WORK, "Toptal", "https://www.toptal.com", "Freelance engineering network",
      jobs_url="https://www.toptal.com/talent/apply",
      who=NOT_STATED + " (no country list); FAQ: experts in 100+ countries, under 3% of "
      "applicants accepted", match="toptal"),
    E(AI_WORK, "Braintrust", "https://www.usebraintrust.com", "Freelance tech network",
      who=NOT_STATED + "; says its talent pool spans 100+ countries", match="braintrust"),
    E(AI_WORK, "Deccan AI", "https://www.deccan.ai", "Expert data and evaluation",
      jobs_url="https://deccanexperts.ai", who=NOT_STATED, match="deccan"),

    # --- fellowships and funded programmes ---------------------------------------------------
    E(FELLOWSHIP, "Anthropic Fellows Program", "https://www.anthropic.com/careers",
      "Four months of AI safety, security or economics research with an Anthropic mentor",
      jobs_url="https://job-boards.greenhouse.io/anthropic",
      pay="$3,850/week stipend (about $16,700/month) + ~$15k/month compute",
      pay_source="Anthropic Greenhouse postings, read 2026-10-21",
      who="Rolling applications for the cohort starting January 2027; work authorisation "
      "in the US, UK or Canada and located there; no visa sponsorship", match="anthropic"),
    E(FELLOWSHIP, "Astra Fellowship (Constellation)", "https://constellation.org/programs/astra",
      "Mentored AI safety research or strategy fellowship, Berkeley",
      pay="$8,400/month stipend + ~$15k/month compute (empirical fellows)",
      pay_source="Constellation Astra page, read 2026-10-21",
      who="January 2026 cohort closed (applications ran 28 Aug-26 Sep); register for the "
      "next cohort; visa support and guidance for international applicants",
      match="constellation"),
    E(FELLOWSHIP, "Pivotal Research Fellowship",
      "https://pivotal-research.org/fellowships/ai-safety-fellowship",
      "15-week AI safety research fellowship in London, 18 Jan-30 Apr 2027",
      pay="GBP 15,000-18,000 for 15 weeks + GBP 1,800/month housing if not in London",
      pay_source="Pivotal AI Safety Fellowship page, read 2026-10-21", region="europe",
      who="Anyone 18+; applications close 1 Nov 2026; entry requirements are the fellow's "
      "responsibility (no employment, stipend agreement)", match="pivotal"),
    E(FELLOWSHIP, "OpenAI Residency", "https://openai.com/residency",
      "Six-month research residency as a full-time employee, San Francisco",
      pay="$18.3k/month base + equity",
      pay_source="OpenAI's 2026 Residency posting, read 2026-10-21 via the Thrive Capital "
      "jobs-board mirror (openai.com returns 403 to scripts)",
      who="2026 posting no longer accepts applications; full-time, not alongside a degree",
      match="openai"),
    E(FELLOWSHIP, "MATS", "https://www.matsprogram.org",
      "ML Alignment & Theory Scholars: 12 weeks of mentored alignment research, Berkeley "
      "or London",
      pay="$1,250/week stipend + $2k/week compute (FAQ says $1,600/week)",
      pay_source="matsprogram.org home page and FAQ, read 2026-10-21; the two disagree",
      who="18+ by the start date; US and non-US citizens; J-1 visas for Berkeley, no visa "
      "support for London; Winter 2027 applications closed", match="mats"),
    E(FELLOWSHIP, "SPAR", "https://sparai.org", "Part-time remote AI safety research projects",
      match="spar"),
    E(FELLOWSHIP, "ERA Cambridge", "https://erafellowship.org",
      "Summer AI safety and governance research fellowship, Cambridge", region="europe",
      match="era"),
    E(FELLOWSHIP, "LASR Labs", "https://www.lasrlabs.org",
      "Full-time AI safety research programme, London", region="europe", match="lasr"),
    E(FELLOWSHIP, "Cohere Labs Scholars Program", "https://cohere.com/research",
      "Research scholars at Cohere's research lab", match="cohere"),
    E(FELLOWSHIP, "Google PhD Fellowship",
      "https://research.google/programs-and-events/phd-fellowship/",
      "Funding for PhD students in computing",
      who="University nomination only; the listed regions (Africa, Australia/NZ, Canada, "
      "East Asia, Europe, India, Latin America, Middle East, Southeast Asia, US) do not "
      "include Pakistan", match="google"),
    E(FELLOWSHIP, "Microsoft Research PhD Fellowship",
      "https://www.microsoft.com/en-us/research/academic-program/phd-fellowship/",
      "Funding for PhD students in computing research", match="microsoft"),
    E(FELLOWSHIP, "AI Safety Camp", "https://www.aisafety.camp",
      "Remote, part-time AI safety research teams", match="ai safety camp"),
    E(FELLOWSHIP, "Apart Research", "https://apartresearch.com",
      "Research sprints and lab fellowships in AI safety", match="apart"),

    # --- accelerators: who they back, and their jobs boards -------------------------------------
    E(ACCELERATOR, "Y Combinator", "https://www.ycombinator.com/companies",
      "The largest accelerator; full recent cohort in the YC dashboard",
      jobs_url="https://www.workatastartup.com"),
    E(ACCELERATOR, "Techstars", "https://www.techstars.com/portfolio",
      "Global accelerator network", jobs_url="https://jobs.techstars.com"),
    E(ACCELERATOR, "Antler", "https://www.antler.co/portfolio",
      "Day-zero investor in 30 cities, incl. Singapore, KL, Riyadh, Abu Dhabi",
      jobs_url="https://careers.antler.co"),
    E(ACCELERATOR, "Entrepreneur First", "https://www.joinef.com/companies",
      "Talent investor, London and Bangalore cohorts", region="europe"),
    E(ACCELERATOR, "500 Global", "https://500.co/companies", "Early-stage investor with MENA "
      "and Southeast Asia programmes"),
    E(ACCELERATOR, "Plug and Play", "https://www.plugandplaytechcenter.com",
      "Corporate innovation platform and accelerator"),
    E(ACCELERATOR, "Seedcamp", "https://seedcamp.com", "European pre-seed fund",
      region="europe"),
    E(ACCELERATOR, "South Park Commons", "https://www.southparkcommons.com",
      "Founder fellowship and community"),
    E(ACCELERATOR, "HF0", "https://www.hf0.com", "Residency for AI founders"),
    E(ACCELERATOR, "Neo", "https://neo.com", "Accelerator and scholars for technical founders"),
    E(ACCELERATOR, "AI Grant", "https://aigrant.com", "Accelerator for AI-native products"),
    E(ACCELERATOR, "a16z speedrun", "https://speedrun.a16z.com", "a16z's accelerator"),
    E(ACCELERATOR, "Sequoia Arc", "https://www.sequoiacap.com/arc/", "Sequoia's catalyst "
      "programme for pre-seed founders"),
    E(ACCELERATOR, "Station F Founders Program", "https://stationf.co",
      "Paris campus programmes", region="europe"),
    E(ACCELERATOR, "Creative Destruction Lab", "https://creativedestructionlab.com",
      "Objectives-based programme for science startups"),
    E(ACCELERATOR, "Alchemist Accelerator", "https://www.alchemistaccelerator.com",
      "Enterprise-focused accelerator"),
    E(ACCELERATOR, "MassChallenge", "https://masschallenge.org", "Zero-equity accelerator"),
    E(ACCELERATOR, "Founders Factory", "https://foundersfactory.com",
      "Venture studio and accelerator, London", region="europe"),
    E(ACCELERATOR, "Flat6Labs", "https://flat6labs.com", "MENA seed programmes", region="gulf"),
    E(ACCELERATOR, "Hub71", "https://www.hub71.com", "Abu Dhabi tech ecosystem and incentive "
      "programme", region="gulf"),
    E(ACCELERATOR, "Block71", "https://www.block71.com", "NUS Enterprise startup hubs, "
      "Singapore and beyond", region="asia"),
    E(ACCELERATOR, "Iterative", "https://www.iterative.vc", "Southeast Asia accelerator",
      region="asia"),
    E(ACCELERATOR, "Peak XV Surge", "https://surge.peakxv.com", "Rapid-scale programme for "
      "Southeast Asia and beyond", region="asia"),
    E(ACCELERATOR, "National Incubation Centers", "https://ignite.org.pk",
      "Ignite-funded incubators in Pakistani cities, listed on Ignite's site",
      region="pakistan"),

    # --- Pakistan: grants and funding for junior scientists and researchers -------------------
    # Faculty and startup funding first, then what a graduate without a faculty post can
    # apply to directly. Eligibility is from each official page, checked 2026-10-21.
    E(PK_GRANT, "HEC NRPU research grants",
      "https://www.hec.gov.pk/english/services/universities/nrpu/Pages/Introduction.aspx",
      "National Research Program for Universities; the 2026-27 call has published FAQs",
      region="pakistan", who="Principal investigator must be faculty at an HEC-recognised "
      "university; junior staff and students join as team members"),
    E(PK_GRANT, "HEC scholarships and grants",
      "https://www.hec.gov.pk/english/scholarshipsgrants/Pages/default.aspx",
      "HEC's index of scholarships, research grants and travel grants", region="pakistan",
      who="Varies by scheme; the index links each scheme's own eligibility page"),
    E(PK_GRANT, "Ignite National Technology Fund", "https://ignite.org.pk",
      "Funds technology R&D and startups; runs the National Incubation Centers",
      region="pakistan", who="Startups and deep-tech project teams; Pakistan Startup Fund "
      "grants go only to eligible startups. Not a personal research grant"),
    E(PK_GRANT, "Pakistan Science Foundation", "https://psf.gov.pk",
      "Research project grants and science funding", region="pakistan",
      who=NOT_STATED + " on the home page; terms are in each call's guidelines PDF"),
    E(PK_GRANT, "National Centre of Artificial Intelligence", "https://ncai.pk",
      "HEC-funded AI research labs across Pakistani universities; posts paid research "
      "student and engineer roles", jobs_url="https://ncai.pk/careers/", region="pakistan",
      who="Roles list their own degree requirements (some for enrolled bachelor's "
      "students); the careers page said no current vacancies on 2026-10-21"),
    E(PK_GRANT, "HEC Overseas Scholarships (Phase-III)",
      "https://www.hec.gov.pk/english/scholarshipsgrants/OSSPhase-III/Pages/default.aspx",
      "MS/MPhil and PhD scholarships at top-200 QS/THE universities abroad",
      region="pakistan", who="Pakistani/AJK nationals. MS: 16 years of education, CGPA 3.0, "
      "age 30 or under (35 for public-sector staff). PhD: 18 years, age 35 or under (40). "
      "Batch-IV closed 28 Aug 2026; HAT test held 19 Sep 2026"),
    E(PK_GRANT, "HEC Indigenous PhD Fellowship (Phase-II)",
      "https://www.hec.gov.pk/english/scholarshipsgrants/IPHDFP5000F/Pages/default.aspx",
      "Funds PhD study at Pakistani universities", region="pakistan",
      who="Pakistani/AJK nationals with 16 years of education and no third division; "
      "direct PhD needs CGPA 3.0 in MS/MPhil. See its Current Status page for intake"),
    E(PK_GRANT, "HEC US-Pakistan Knowledge Corridor PhD",
      "https://www.hec.gov.pk/english/scholarshipsgrants/US-Pakcorridor/Pages/default.aspx",
      "PhD scholarships at top-100 QS-ranked US universities", region="pakistan",
      who="Admission to a top-100 QS US university plus GRE General 300+ or HAT 60%+; "
      "the page said scholarships are open on 2026-10-21"),
    E(PK_GRANT, "Fulbright Pakistan (USEFP)",
      "https://www.usefp.org/scholarships/fulbright-degree.cfm",
      "Master's or PhD in the US: tuition, textbooks, airfare, living stipend, insurance",
      region="pakistan", who="Pakistani citizens living in Pakistan. Master's: 16 years of "
      "education; PhD: 18 years; GRE required; no clinical medicine. Last deadline "
      "1 Apr 2026, now closed"),
    E(PK_GRANT, "Chevening (Pakistan)", "https://www.chevening.org/scholarship/pakistan/",
      "UK government master's scholarships", region="pakistan",
      who="Citizen of an eligible country (Pakistan has a country page); undergraduate "
      "degree; 2 years' work experience (2,800 hours); return home for 2 years. 2027-28 "
      "round closed"),
    E(PK_GRANT, "Commonwealth Master's Scholarships",
      "https://cscuk.fcdo.gov.uk/scholarships/commonwealth-masters-scholarships/",
      "UK master's: airfare, full tuition, monthly stipend, travel grant",
      region="pakistan", pay="GBP 1,712/month stipend (GBP 2,000 in London) + tuition",
      pay_source="CSC Commonwealth Master's page, checked 2026-10-21",
      who="Citizens permanently resident in an eligible Commonwealth country (Pakistan is "
      "listed); 2:1 first degree; unable to afford UK study. 2027/28 closed 20 Oct 2026"),
    E(PK_GRANT, "DAAD Pakistan",
      "https://www.daad.pk/en/find-funding/daad-scholarship-programmes-for-pakistan/",
      "German master's (EPOS etc.) and doctoral scholarships for Pakistani graduates",
      region="pakistan", who="Programmes listed for Pakistan; doctoral programmes in "
      "Germany usually close at the end of August"),
    E(PK_GRANT, "MEXT Japanese Government Scholarship",
      "https://www.studyinjapan.go.jp/en/smap-stopj-applications-research.html",
      "Research-student scholarships for graduate study in Japan", region="pakistan",
      who="Apply through the Embassy of Japan in Pakistan, not MEXT; recruitment in "
      "April-May, embassy screening May-July. The embassy announced 2026 awards to "
      "Pakistani students"),
    E(PK_GRANT, "Erasmus Mundus Joint Masters",
      "https://www.eacea.ec.europa.eu/scholarships/erasmus-mundus-catalogue_en",
      "EU-funded joint master's scholarships across European universities",
      region="pakistan", who="Master's students from all over the world; apply to each "
      "programme directly; most open October-January"),
    E(PK_GRANT, "KAUST graduate admissions", "https://admissions.kaust.edu.sa/",
      "Funded MS and PhD in Saudi Arabia: tuition, monthly stipend, housing",
      region="pakistan", who="International students (120+ nationalities on campus); over "
      "90% of admitted students get full tuition and a stipend. Nationality rules not "
      "stated on the admissions home page"),

    # --- Pakistan: where government CS / IT / AI jobs are advertised -------------------------
    E(PK_GOV, "National Job Portal", "https://njp.gov.pk/jobs/live",
      "Federal government job portal - crawled; CS/IT posts appear in the public-sector list",
      region="pakistan", match="", who="Read by job-radar on every crawl"),
    E(PK_GOV, "FPSC", "https://fpsc.gov.pk", "Federal Public Service Commission",
      region="pakistan"),
    E(PK_GOV, "PPSC", "https://www.ppsc.gop.pk", "Punjab Public Service Commission",
      region="pakistan"),
    E(PK_GOV, "PITB careers", "https://www.pitb.gov.pk", "Punjab Information Technology Board",
      region="pakistan"),
    E(PK_GOV, "KPITB", "https://kpitb.gov.pk", "Khyber Pakhtunkhwa IT Board",
      region="pakistan"),
    E(PK_GOV, "NITB", "https://nitb.gov.pk", "National Information Technology Board",
      region="pakistan"),
    E(PK_GOV, "PSEB", "https://www.pseb.org.pk", "Pakistan Software Export Board",
      region="pakistan"),
    E(PK_GOV, "NASTP", "https://nastp.gov.pk/", "National Aerospace Science & Technology Park",
      region="pakistan"),
    E(PK_GOV, "PAEC", "https://paec.gov.pk", "Pakistan Atomic Energy Commission",
      region="pakistan"),
    E(PK_GOV, "SUPARCO", "https://suparco.gov.pk", "Space & Upper Atmosphere Research "
      "Commission", region="pakistan"),
    E(PK_GOV, "NUST careers", "https://nust.edu.pk", "National University of Sciences and "
      "Technology", region="pakistan"),
]
