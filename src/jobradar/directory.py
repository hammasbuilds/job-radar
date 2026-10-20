"""Programmes, platforms, accelerators, grants and Pakistani public-sector sources.

Written into the `directory` table by every crawl, with a live count: how many postings in
the lens right now come from that organisation (for fellowships, only its programme
postings). The list is curated by hand and its links are checked by
`scripts/check_directory.py`.

**Pay is stated only where it was verified**, with where and when. Everything else says to
check the official page, because a stipend typed from memory and wrong by a factor of two is
worse than none. Verified 2026-10-20:

  Anthropic Fellows  $3,850/week stipend (about $15,400/month) and ~$15k/month compute, from
                     Anthropic's own Greenhouse postings; needs US, UK or Canada work
                     authorisation and does not sponsor visas.
  Astra              $8,400/month stipend and ~$15k/month compute (Constellation, via the EA
                     opportunities listing).
  Pivotal            GBP 6,000-8,000 for nine weeks in London (Feb-Apr 2026 cohort listing).
  OpenAI Residency   $18.3k/month base, six months, San Francisco (its 2026 posting).
"""

from __future__ import annotations

AI_WORK = "AI work platform"
FELLOWSHIP = "Fellowship / paid programme"
ACCELERATOR = "Accelerator"
PK_GRANT = "Pakistan grant / funding"
PK_GOV = "Pakistan government jobs"

KINDS = (AI_WORK, FELLOWSHIP, ACCELERATOR, PK_GRANT, PK_GOV)
CHECK = "check the official page"


def E(kind, name, url, what, *, jobs_url="", region="global", pay="", pay_source="",  # noqa: N802
      who="", match=""):
    return {"kind": kind, "name": name, "url": url, "jobs_url": jobs_url, "region": region,
            "what": what, "pay": pay or CHECK, "pay_source": pay_source, "who": who,
            "match": match}


ENTRIES = [
    # --- AI work platforms: contract and small-contract work training and checking models ----
    E(AI_WORK, "Mercor", "https://www.mercor.com", "Expert contract work for AI labs: "
      "coding, research, domain experts", jobs_url="https://work.mercor.com", match="mercor"),
    E(AI_WORK, "DataAnnotation", "https://www.dataannotation.tech",
      "Paid tasks writing and rating AI responses; coding and STEM tracks", match="dataannotation"),
    E(AI_WORK, "Alignerr", "https://www.alignerr.com", "Labelbox's expert network for AI "
      "training data", match="alignerr"),
    E(AI_WORK, "micro1", "https://www.micro1.ai", "AI-vetted contract engineers and "
      "experts for AI training", jobs_url="https://www.micro1.ai/jobs", match="micro1"),
    E(AI_WORK, "AfterQuery", "https://www.afterquery.com", "Expert data for frontier "
      "labs; contract research and coding work", match="afterquery"),
    E(AI_WORK, "Datacurve", "https://datacurve.ai", "Coding data for AI labs; runs Shipd",
      match="datacurve"),
    E(AI_WORK, "Shipd", "https://shipd.ai", "Paid coding challenges and bounties (by Datacurve)",
      match="shipd"),
    E(AI_WORK, "Outlier", "https://outlier.ai", "Scale AI's contributor platform for AI "
      "training tasks", match="outlier"),
    E(AI_WORK, "Turing", "https://www.turing.com", "Remote engineers and AGI-lab data work",
      jobs_url="https://www.turing.com/jobs", match="turing"),
    E(AI_WORK, "Toloka", "https://toloka.ai", "Data labelling and expert tasks", match="toloka"),
    E(AI_WORK, "Mindrift", "https://mindrift.ai", "Expert AI training tasks (Toloka)",
      match="mindrift"),
    E(AI_WORK, "Prolific", "https://www.prolific.com", "Paid research studies and AI tasks",
      match="prolific"),
    E(AI_WORK, "Invisible Technologies", "https://www.invisible.co",
      "AI training operations; contract trainers", match="invisible"),
    E(AI_WORK, "Surge AI", "https://www.surgehq.ai", "Expert human data for LLMs",
      match="surge"),
    E(AI_WORK, "Handshake AI", "https://joinhandshake.com", "Handshake's AI fellowship "
      "work for students and graduates", match="handshake"),
    E(AI_WORK, "Snorkel AI", "https://snorkel.ai", "Expert data development; contributor "
      "network", match="snorkel"),
    E(AI_WORK, "SuperAnnotate", "https://www.superannotate.com", "Annotation platform and "
      "expert workforce", match="superannotate"),
    E(AI_WORK, "Appen", "https://www.appen.com", "Long-running data work platform",
      match="appen"),
    E(AI_WORK, "TELUS Digital AI", "https://www.telusdigital.com",
      "AI community tasks (formerly TELUS International)", match="telus"),
    E(AI_WORK, "Pareto", "https://pareto.ai", "Expert data for AI labs", match="pareto"),
    E(AI_WORK, "Revelo", "https://www.revelo.com", "Remote engineers, LatAm-weighted",
      match="revelo"),
    E(AI_WORK, "Andela", "https://andela.com", "Remote engineering talent marketplace",
      match="andela"),
    E(AI_WORK, "Toptal", "https://www.toptal.com", "Freelance engineering network",
      match="toptal"),
    E(AI_WORK, "Braintrust", "https://www.usebraintrust.com", "Freelance tech network",
      match="braintrust"),
    E(AI_WORK, "Deccan AI", "https://deccan.ai", "Expert data and evaluation", match="deccan"),

    # --- fellowships and funded programmes ---------------------------------------------------
    E(FELLOWSHIP, "Anthropic Fellows Program", "https://www.anthropic.com/careers",
      "Four months of AI safety, security or economics research with an Anthropic mentor",
      jobs_url="https://job-boards.greenhouse.io/anthropic",
      pay="$3,850/week stipend (~$15,400/month) + ~$15k/month compute",
      pay_source="Anthropic Greenhouse postings, read 2026-10-20",
      who="Work authorisation in the US, UK or Canada; no visa sponsorship", match="anthropic"),
    E(FELLOWSHIP, "Astra Fellowship (Constellation)", "https://constellation.org/programs/astra",
      "Mentored AI safety research or strategy fellowship, Berkeley",
      pay="$8,400/month stipend + ~$15k/month compute",
      pay_source="EA opportunities listing, read 2026-10-20",
      who="2026 deadline (3 May) has passed; watch for the next cohort", match="constellation"),
    E(FELLOWSHIP, "Pivotal Research Fellowship", "https://www.pivotal-research.org",
      "Nine-week AI safety research fellowship in London",
      pay="GBP 6,000-8,000 for 9 weeks, plus meals, accommodation, compute",
      pay_source="Feb-Apr 2026 cohort listing, read 2026-10-20", region="europe",
      match="pivotal"),
    E(FELLOWSHIP, "OpenAI Residency", "https://openai.com/residency",
      "Six-month research residency as a full-time employee, San Francisco",
      pay="$18.3k/month base + equity", pay_source="OpenAI's 2026 Residency posting",
      who="2026 window appears closed; full-time, not alongside a degree", match="openai"),
    E(FELLOWSHIP, "MATS", "https://www.matsprogram.org",
      "ML Alignment & Theory Scholars: mentored alignment research", match="mats"),
    E(FELLOWSHIP, "SPAR", "https://sparai.org", "Part-time remote AI safety research projects",
      match="spar"),
    E(FELLOWSHIP, "ERA Cambridge", "https://erafellowship.org",
      "Summer AI safety and governance research fellowship, Cambridge", region="europe",
      match="era"),
    E(FELLOWSHIP, "LASR Labs", "https://www.lasrlabs.org",
      "Full-time AI safety research programme, London", region="europe", match="lasr"),
    E(FELLOWSHIP, "Cohere Labs Scholars Program", "https://cohere.com/research",
      "Research scholars at Cohere's research lab", match="cohere"),
    E(FELLOWSHIP, "Google PhD Fellowship", "https://research.google/programs-and-events/",
      "Funding for PhD students in computing", match="google"),
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
    E(PK_GRANT, "HEC NRPU research grants",
      "https://www.hec.gov.pk/english/services/universities/nrpu/Pages/Introduction.aspx",
      "National Research Program for Universities; the 2026-27 call has published FAQs",
      region="pakistan", who="Principal investigator must be faculty at an HEC-recognised "
      "university; junior staff and students join as team members"),
    E(PK_GRANT, "HEC scholarships and grants",
      "https://www.hec.gov.pk/english/scholarshipsgrants/Pages/default.aspx",
      "HEC's index of scholarships, research grants and travel grants", region="pakistan"),
    E(PK_GRANT, "Ignite National Technology Fund", "https://ignite.org.pk",
      "Funds technology R&D and startups; runs the National Incubation Centers",
      region="pakistan"),
    E(PK_GRANT, "Pakistan Science Foundation", "https://psf.gov.pk",
      "Research project grants and science funding", region="pakistan"),
    E(PK_GRANT, "National Centre of Artificial Intelligence", "https://ncai.pk",
      "HEC-funded AI research labs across Pakistani universities", region="pakistan"),

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
