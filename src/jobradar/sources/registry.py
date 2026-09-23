"""Every source considered, and what happened when it was asked.

A master list of ~330 job sites is a list of names. This is the same list
after each one was actually probed, which is a different and much shorter
document — and the honest answer to "are you covering everything?".

Four statuses:

  WIRED       fetched on every run, code exists, verified returning data
  NO_API      real site, no public API; HTML only, or it blocks automation
  NEEDS_KEY   has an API, requires registration this project has not done
  PROHIBITED  terms forbid unauthorised scraping
  OUT_OF_SCOPE  a region deliberately excluded

**Asia is Pakistan only.** India, South-East Asia, East Asia and ANZ were
removed on request, so their entries are recorded as out of scope rather than
quietly dropped — a source that vanishes from a list looks like an oversight.

The point of keeping the rejected ones is that the next person to read the
master list can see the work was done, and why a name is not wired.
"""

from __future__ import annotations

from dataclasses import dataclass

WIRED = "wired"
NO_API = "no-api"
NEEDS_KEY = "needs-key"
PROHIBITED = "prohibited"
OUT_OF_SCOPE = "out-of-scope"


@dataclass(frozen=True)
class Source:
    name: str
    group: str
    status: str
    note: str = ""


SOURCES: tuple[Source, ...] = (
    # --- wired: ATS platforms, company boards at the source ----------------
    Source("Greenhouse", "ats", WIRED, "53 seeded boards, no key"),
    Source("Lever", "ats", WIRED, "workplaceType and commitment as fields"),
    Source("Ashby", "ats", WIRED,
           "GET not POST — the error that cost 74 YC boards"),
    Source("SmartRecruiters", "ats", WIRED, "listing has no body text"),
    Source("Workable", "ats", WIRED, "POST with an empty body"),
    Source("Personio", "ats", WIRED, "XML, common in Germany"),
    Source("Recruitee", "ats", WIRED, "needs an exact subdomain"),

    # --- wired: key-free board APIs ----------------------------------------
    Source("Arbeitnow", "board", WIRED, "250 rows, EU-weighted"),
    Source("Remotive", "board", WIRED, "~18 rows; its own job-count says 18"),
    Source("Himalayas", "board", WIRED, "locationRestrictions as data"),
    Source("Jobicy", "board", WIRED, "jobGeo, supports a geo parameter"),
    Source("RemoteOK", "board", WIRED, "first array element is a legal notice"),
    Source("The Muse", "board", WIRED,
           "20,639 pages unfiltered — category filter is mandatory"),
    Source("Hacker News Who-is-hiring", "board", WIRED, "via the Algolia API"),
    Source("Y Combinator", "directory", WIRED,
           "yc-oss mirror; 1,483 hiring, no LinkedIn field"),

    # --- prohibited ---------------------------------------------------------
    Source("LinkedIn Jobs", "generalist", PROHIBITED,
           "terms forbid scraping; links only, never requested"),
    Source("Indeed", "generalist", PROHIBITED, "terms forbid scraping; API is partner-only"),
    Source("Glassdoor", "generalist", PROHIBITED, "terms forbid scraping"),

    # --- needs a key --------------------------------------------------------
    Source("Adzuna", "generalist", NEEDS_KEY, "free key, 20 countries — best next add"),
    Source("Jooble", "generalist", NEEDS_KEY, "free key on request"),
    Source("Careerjet", "generalist", NEEDS_KEY, "affiliate id required"),
    Source("Reed (UK)", "europe", NEEDS_KEY, "free key"),
    Source("USAJobs", "north-america", NEEDS_KEY, "free key, US federal only"),
    Source("France Travail", "europe", NEEDS_KEY, "OAuth client credentials"),
    Source("EURES", "europe", NEEDS_KEY, "EU official portal"),
    Source("Canada Job Bank", "north-america", NEEDS_KEY, ""),
    Source("Wellfound", "startups", NEEDS_KEY, "partner API; has a YC-funded tag"),
    Source("ZipRecruiter", "generalist", NEEDS_KEY, ""),
    Source("LinkUp", "generalist", NEEDS_KEY, ""),

    # --- probed and unavailable --------------------------------------------
    Source("ReliefWeb", "ngo", NO_API, "jobs endpoint returns 410 Gone"),
    Source("Arbetsförmedlingen", "europe", NO_API, "DNS did not resolve from here"),
    Source("NAV Arbeidsplassen", "europe", NO_API, "public-feed path 404s"),
    Source("We Work Remotely", "remote", NO_API, "RSS host did not resolve"),
    Source("Work at a Startup", "startups", NO_API,
           "companies.json did not resolve; YC covered via yc-oss instead"),
    Source("Jobs.ac.uk", "academia", NO_API, "RSS path 404s"),
    Source("EURAXESS", "academia", NO_API, "HTML only"),
    Source("Teamtailor", "ats", NO_API, "per-company RSS; no directory to enumerate"),

    # --- Pakistan: the one Asian region kept -------------------------------
    Source("Rozee.pk", "pakistan", NO_API,
           "Cloudflare managed challenge on every path, robots.txt included; "
           "getting past it means pretending to be a browser"),
    Source("Mustakbil", "pakistan", WIRED,
           "re-probed: publishes a sitemap index, and every job page carries "
           "JobPosting JSON-LD. 1,403 live postings. Was recorded here as "
           "'HTML only, no feed', which was wrong"),
    Source("BrightSpyre", "pakistan", NO_API, "HTML only, no feed"),
    Source("NJP (National Job Portal)", "pakistan", NO_API,
           "government portal, HTML only — the legitimate route if scraped"),
    Source("Bayrozgar / Jobz.pk / PaperPk", "pakistan", NO_API, "HTML only"),

    # --- Gulf ---------------------------------------------------------------
    Source("Bayt.com", "gulf", NO_API, "largest MENA board, no public API"),
    Source("GulfTalent", "gulf", NO_API, ""),
    Source("Naukrigulf", "gulf", NO_API, ""),
    Source("Jadarat (Saudi HRDF)", "gulf", NO_API,
           "government portal — meant to be polled, but HTML"),
    Source("UAE MOHRE", "gulf", NO_API, "government portal, HTML"),

    # --- Asia, removed on request ------------------------------------------
    Source("Naukri / Foundit / Instahyre (India)", "asia", OUT_OF_SCOPE, ""),
    Source("JobStreet / JobsDB / Glints (SE Asia)", "asia", OUT_OF_SCOPE, ""),
    Source("51job / Zhaopin / BOSS Zhipin (China)", "asia", OUT_OF_SCOPE, ""),
    Source("JobKorea / Saramin / Wanted (Korea)", "asia", OUT_OF_SCOPE, ""),
    Source("Rikunabi / Doda / TokyoDev (Japan)", "asia", OUT_OF_SCOPE, ""),
    Source("Bdjobs / Topjobs.lk / Merojob", "asia", OUT_OF_SCOPE, ""),
    Source("Seek / Trade Me (AU/NZ)", "apac", OUT_OF_SCOPE, ""),
)


def by_status(status: str) -> list[Source]:
    return [s for s in SOURCES if s.status == status]


def summary() -> dict[str, int]:
    out: dict[str, int] = {}
    for source in SOURCES:
        out[source.status] = out.get(source.status, 0) + 1
    return out
