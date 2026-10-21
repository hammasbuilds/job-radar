# job-radar

> Not a search engine. A rejection engine with the reasons shown.

There is no discovery problem. There are thousands of AI roles in Europe and they can be
found by hand in an afternoon. The problem is **qualification**: applying from Pakistan, the
overwhelming majority of those postings will never hire you, and establishing that costs
about twenty minutes each.

So the value here is not the thousands of jobs it finds. It is the thousands it **kills
before you read them, with the reason visible**.

Private repository. See [DO-NOT-PUBLISH.md](DO-NOT-PUBLISH.md).

## Input / Output

Two ways to see it run without touching the network.

**The dry run** uses nine small invented API responses in `tests/fixtures/dryrun/`
(fictional companies, each source's real shape) and a throwaway database, so it runs
anywhere and never reads or writes your data:

```
$ python scripts/fetch.py --dry-run

the funnel, in pipeline order
       20  fetched
       19  after dedup                (-1, 5.0% of fetched)
       15  after the role filter            (-4, 21.1% of deduplicated)
           - not one of the target roles                   4
       14  after the level filter           (-1, 5.3% of deduplicated)
           - senior level                                  1
        9  after the route filter           (-5, 26.3% of deduplicated)
           - remote, country-locked                        2
           - refuses sponsorship                           1
           - relocation offered, sponsorship unstated      1
           - remote, region-locked, no contractor route      1
        9  kept, in sections:
           - europe                                        5
           - sponsorship                                   4
           - remote                                        3
           - pakistan                                      2

kept, 9 new:
  1.00  Machine Learning Engineer - acme-ai  [sponsorship,europe]
  1.00  ML Engineer - Fjordtech  [sponsorship,europe]
  1.00  Computer Vision Engineer - nordlicht  [remote]
  1.00  Founding ML Engineer - Spektrum GmbH  [sponsorship,europe]
  0.94  LLM Engineer - Quokka Systems  [remote]
  0.88  Applied Scientist - Orbital Notes  [remote,europe]
  0.78  Junior AI Engineer - nordlicht  [pakistan]
  0.74  Data Scientist - Indus Analytics  [pakistan]
  0.55  Data Scientist, Marketing - acme-ai  [sponsorship,europe]

killed, with the phrase that decided it:
  not one of the target roles                 - acme-ai  (title is not a target role)
  senior level                               Senior ML Engineer - acme-ai  (senior)
  remote, country-locked                     AI Engineer - acme-ai  (us-based)
  not one of the target roles                Account Executive, AI - acme-ai  (title is not a target role)
  refuses sponsorship                        Research Engineer - acme-ai  (unfortunately we cannot offer visa)
  relocation offered, sponsorship unstated   ML Engineer - acme-ai  (relocation package - relocation offered, sponsorship not stated)
  remote, region-locked, no contractor route NLP Engineer - nordlicht  (location names region(s): eu)
  remote, country-locked                     MLOps Engineer - Tannenbaum Data  (location is germany only)
  not one of the target roles                Backend Engineer - Fjordtech  (title is not a target role)
  not one of the target roles                Accountant - Ravi Traders  (title is not a target role)
```

**The replay** reads the real HTTP cache from the 2026-09-22/23 crawl
(`python scripts/fetch.py --offline --db <scratch.sqlite3>`), so the numbers below are
reproducible on this machine. With the code as of 2026-10-06:

```
    9,898  fetched          greenhouse 7,069 · lever 1,367 · mustakbil 500 · hn 431 · arbeitnow 250 · …
    9,516  after dedup
      500  after the role filter      (-9,016: not one of the target roles)
      241  after the level filter     (-259: senior 111, staff 90, lead 40, principal 12, executive 6)
      165  after the years filter     (-76: wants 4+ to 10+ years)
       56  after the route filter     (-109: onsite 46, remote country-locked 25, scope not stated 11,
                                        refuses 10, nationals only 8, hybrid 4, region-locked 3, …)
       56  kept: sponsorship 46 · europe 17 · pakistan 5 · remote 3 · gulf 2
```

**9,898 → 56.** Himalayas is absent from that replay: its request changed to follow the
API's 20-row pages, so the old cached response no longer matches. The cache predates the
2026-10-06 fixes; a live crawl will differ.

### One employer must not fill the screen

Of those 46 sponsorship rows, **41 are Anthropic** — it repeats *"we do sponsor visas"*
in every posting. The filter is right and the list is useless: a correct filter
producing an unreadable screen is still a broken screen.

The view shows at most **three per company** and says how many it folded
(*"+ 38 more open at anthropic, folded"*). Nothing is deleted — the rows stay in the
table, and a cap that silently drops rows is the same sin as a silent filter.

## Five sections

| | |
|---|---|
| **Sponsorship** | They will sponsor a visa, so relocation is the route. **Only explicit offers** — silence does not qualify, and neither does "relocation assistance" |
| **Remote** | You stay where you are. Either the role is genuinely open worldwide, or it is region-locked ("EU only") and they will engage a contractor, which needs no work permit. A *country*-locked role ("must be US-based") is not rescued by the contractor path |
| **Europe** | Where the work is. Same route rules: a European role appears only with a sponsorship offer or a remote route |
| **Gulf** | Silence counts as a route (employer-sponsored work visas are how expatriates are hired); a refusal or a nationals-only role does not |
| **Pakistan** | No route needed |

A posting can be in several, and the best ones are. Forcing one bucket would hide exactly
the roles that will either relocate you *or* take you remote.

## Run it

Needs **Python 3.11+** and two packages. Everything else is standard library.

```bash
pip install -e ".[dev]"               # fastapi, uvicorn, pytest; puts `jobradar` on the path
cp config.example.toml config.toml    # optional: contact address, CV and portfolio paths
python scripts/fetch.py --dry-run     # offline, on the bundled fixtures, scratch data only
python scripts/fetch.py               # crawl, filter, store
job-radar                             # dashboard at http://127.0.0.1:8000 (or python -m jobradar.api)
python -m pytest                      # 209 tests, offline, against a scratch data directory

python scripts/probe_companies.py --wide   # which company boards are real
```

`install.bat` puts a shortcut on the Desktop that does the fetch and opens the
dashboard in one click.

## Ten tabs

| Tab | What it is for |
|---|---|
| **Today** | New since the last run, ranked. The only screen used daily |
| **Sponsorship** | Explicit visa offers |
| **Remote** | Global roles, and the contractor path |
| **Europe / Gulf / Pakistan** | The same survivors, by where the work is |
| **YC** | YC companies that are hiring, company-first, every open role |
| **Killed** | Every rejection with the phrase that caused it — the trust screen |
| **Pipeline** | What you applied to. Written by hand and by nothing else |
| **Funnel** | The numbers above, for the last run |

## Seed lists rot, so they are probed

A list of ATS slugs is hand-written and goes stale: companies change provider,
get acquired, or use a slug nobody guessed. The first version had 67 entries
and **42 returned nothing** — invisible during a run, because a dead board and
a board with no open roles look identical.

`scripts/probe_companies.py` checks every slug and prints a ready-to-paste list
of the ones that resolve. `--wide` also tries a candidate list. Growing this is
the highest-leverage change available, well ahead of adding a model.

## There aren't 200 sources. There are about ten.

Most boards do not originate postings, they mirror them. Greenhouse, Lever, Ashby, Workable
and the rest are where a job is actually *created*, and most have free public JSON APIs.
LinkedIn, Indeed, Glassdoor and 190 others are downstream copies. Query the origin and you
get structured data, no blocking, no breakage. Scrape the mirrors and you maintain 200
fragile parsers forever.

| Source | What it gives | Auth |
|---|---|---|
| Greenhouse board API | Full job text — `content=true` is the whole reason to use it | none |
| Lever postings API | Full text, plus `workplaceType` and `commitment` as structured fields | none |
| Arbeitnow | Germany and the wider EU, companies nobody thought to seed | none |
| Remotive | `candidate_required_location` — the geographic restriction as *data* | none |

**LinkedIn is never requested programmatically.** It is the one source where getting caught
costs the profile you are building, and every signal people scrape it for has a better free
source here.

**No credential anywhere.** There is no auth argument in the HTTP layer, no token slot, no
session. If a source needs a password, it is the wrong source.

**robots.txt is obeyed, and every host is paced.** The HTTP layer reads each host's
robots.txt before its first request (RFC 9309: a 4xx means no rules, a 5xx means stay out
this run), never requests a disallowed URL, and leaves at least a second — or the host's
`Crawl-delay` — between requests to one host. 429 and 5xx are retried with backoff and
`Retry-After` is honoured up to a minute. The one source this removed is
**SmartRecruiters**: `api.smartrecruiters.com/robots.txt` disallows every agent except
LinkedInBot, so its three Pakistani employers (Devsinc, PureLogics, Securiti) are listed in
`companies.BLOCKED` and are a manual check. Remotive, Jobicy and RemoteOK ask to be
credited as the source; the dashboard shows the source on every row and links to their URL.

## The five filters are the actual product

None of these live in the structured API fields. They are buried in job text.

| Filter | Distinguishes | Why it is hard |
|---|---|---|
| **Remote scope** | global · region · country · hybrid · onsite | "Remote" in the title, "must reside in Germany" in paragraph six |
| **Work authorisation** | sponsors · refuses · relocation-hint · silent | Silence is the common case and means neither yes nor no |
| **Employment form** | contractor/B2B · either · employee | The highest-value field in the system — see below |
| **Timezone** | good · partial · poor · async | PKT is UTC+5; a CET day overlaps almost entirely. A **plus**, never a kill |
| **Seniority + stack** | against the real profile | The only filter needing [`profile.py`](src/jobradar/profile.py) |

### The contractor path

A European company that will not sponsor a visa will often happily engage a **contractor**
anywhere in the world: no immigration, no payroll entity, an invoice. Applying from
Pakistan that is frequently the realistic route, and it is usually one line buried in the
posting.

It is also what turns one crawl into two products. The same data, asked *"who will take a
contractor"*, answers **"find me clients"** instead of "find me a job".

Contract work is accepted alongside employment, never instead of it — it is a badge and a
ranking weight, and it never kills a posting.

## The Pakistan tab, with numbers

It is not that the local sources could not be read. That was re-checked, and the
earlier answer was wrong in two places:

- `registry.py` recorded **Mustakbil** as "HTML only, no feed". It publishes a sitemap
  index, an RSS feed carrying the 500 most recent postings with company, city, category
  and full description in **one request**, and JobPosting JSON-LD on all 1,403 live job
  pages. It is now wired and runs on every crawl.
- The employer probe asked **16 Pakistani companies, on two ATS providers**. Re-probing
  **65 employers across six** found **seven readable boards**: Tajir on Ashby, Motive and
  Careem on Greenhouse, Educative on Lever — and Devsinc, PureLogics and Securiti on
  SmartRecruiters, which are no longer read because its API's robots.txt forbids it.

In the replay above Pakistan keeps **five** postings: a data scientist, three AI
automation roles and a robotics field engineer. None is an ML engineering job in the
narrow sense; they are on screen because the role rule now reads "a domain word and a
craft word" rather than an exact phrase, and the Killed tab is where to check that call.

**Rozee.pk stays unread.** It is bigger than Mustakbil and every path, `robots.txt`
included, answers with a Cloudflare managed challenge. Getting past that means
impersonating a browser, which is where reading a public record turns into evading a
control.

**LinkedIn stays unread too**, and that is where the AI roles people see in Pakistan
actually are. Their terms forbid automated collection, they publish no open jobs API, and
the account at risk is the one this tool exists to get a job with. The honest summary is
that the volume visible there does not exist on any board that permits being read — those
employers post to LinkedIn and nowhere else. Links only, as before.

## Four things that went wrong on real data

Each was found by reading the output, and each is now a test using the exact string that
broke it.

**"Relocation assistance" is not visa sponsorship.** A Berlin role and a Seattle role both
reached the Sponsorship section on that phrase. Companies pay for the moving van for people
who already hold the right to work. It is now its own weaker verdict, `relocation_hint`,
with its own kill reason so those 87 postings stay reviewable instead of vanishing into the
country-locked pile.

**A location parser that failed *open*.** `"Cardiff, London or Remote (UK)"` was classified
region-wide — it is UK-only. `"USA, Canada, Argentina, Mexico, Peru"` was classified
region-wide because Argentina and Peru were missing from a word list, so an `all()` test
passed on an unrecognised token. Both are the same bug: **an unknown value satisfied the
check meant to reject it.** [`places.py`](src/jobradar/filters/places.py) now returns
`UNKNOWN` explicitly and the caller falls back to prose.

**One role, three dashboard rows.** Three ScaleAI fellowships appeared separately because
the country sat inside the title — `(Canada)`, `(UK)`, `(US)` — so the identity key differed.
Location tokens are now stripped from the title the same way seniority always was.

**The contractor path rescuing a country-locked role.** Those same fellowships said *"we do
not sponsor"* and reached the Remote section anyway, because contractor status was
overriding the location. It rescues a **region**-locked role — "EU only" has no meaning on an
invoice — but not a country-locked one. "Remote (UK)" means they want somebody in the UK.

## Dedup is the problem that actually bites

One role appears on the company's Greenhouse board, on Arbeitnow, on Remotive and on four
other aggregators. Here, **1,290 of 3,764 rows were duplicates — 34%.**

The rule is borrowed from `comms-desk`, which measured it:

> Company is a **hard barrier**, never a similarity feature. Two companies posting
> identically worded "AI Engineer" roles are two jobs. Same company, same title, two boards,
> within a week — one job. Dropping the barrier and merging on text similarity alone was
> wrong **87%** of the time on real data.

So company equality is a *precondition* for merging, not a signal that raises a score.
Identical postings across companies are normal — the same recruiter template, the same JD
bought from the same agency.

## The Killed screen is the trust screen

Silent drops destroy confidence; a visible *"rejected: remote EU-only"* does not. Every
rejection is stored with the phrase that caused it, grouped by reason.

It is also the only place a **false negative** can be found, which for a tool whose entire
job is rejection is the error that matters. The audit that produced the four fixes above was
done by sorting rejections by score and reading the top of the list.

## Freshness is a ranking weight, not metadata

Applying within 48 hours changes response rates sharply. So a perfect match posted three
weeks ago ranks **below** a good match posted this morning, and the tool reports what is new
since the last run rather than showing the same list again.

## What it will not do

- **No auto-apply.** Manual application is the intent and the correct one
- **No programmatic LinkedIn access** — links only
- **No unsupervised cover letters**
- **No password, OAuth or session token, anywhere.** If a design needs one, that design is wrong
- **The pipeline is updated by hand.** That is the one part that should not be automated

## Layout

```
src/jobradar/
  sources/      ATS boards (greenhouse, lever, ats.py), key-free board APIs, HN,
                Mustakbil, YC, registry.py, and one HTTP layer (robots, pacing, cache)
  filters/      the five filters, plus places.py — reading a location string
  posting.py    one shape, whatever the source was
  dedup.py      company as a hard barrier
  pipeline.py   judge, route into the five sections, count the kills
  store.py      SQLite: what is new, and every rejection
  dryrun.py     the offline fixture run
  api.py        FastAPI, 127.0.0.1 only, Host header checked
  web/          the dashboard — ten tabs, no build step
scripts/
  fetch.py           the whole tool in one command (--dry-run, --offline, --fresh)
  fetch_yc.py        the YC directory and its boards
  probe_companies.py which seeded slugs resolve
  evaluate.py        scores against a hand-labelled set kept outside git (eval/)
  install-hooks.sh   the pre-push guard that keeps this private
tests/fixtures/dryrun/  invented API responses for the dry run
```

## Where the AI is, and is not

There is none, and the tool works. The five filters are regular expressions and word lists,
which was the point: the deterministic half needs no GPU and takes 9,898 postings down
to 56 in the replay above.

A local 14B reading the job text would improve the hard cases — a posting that explains its
visa position in a paragraph rather than a phrase — and that is the next piece of work. The
README will say so until it is true.
