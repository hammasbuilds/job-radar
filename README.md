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

```
$ python scripts/fetch.py

asking 53 boards plus 2 aggregators…
fetched 8,555 postings in 4s
  greenhouse    6,929
  lever         1,358
  arbeitnow       250
  remotive         18

the funnel
    8,555  fetched
    6,252  after dedup                                (-2,303, 26.9% of input)
    3,075  after no route in (country-locked)         (-3,177, 50.8% of input)
      902  after onsite, no sponsorship               (-2,173, 34.8% of input)
      392  after below fit threshold                  (-510, 8.2% of input)
      305  after relocation offered, sponsorship unstated (-87, 1.4% of input)
      221  after refuses sponsorship                  (-84, 1.3% of input)
      173  after hybrid, no sponsorship               (-48, 0.8% of input)
        3  in section: remote
      170  in section: sponsorship
```

**8,555 → 173**, and **9 on screen** after the per-company cap below. Every
lead-generation tool quotes the first number. None publish the last.

### One employer must not fill the screen

Of those 170 sponsorship rows, **161 were Anthropic** — it repeats *"we do
sponsor visas"* in every posting. The filter is right and the list is useless:
a correct filter producing an unreadable screen is still a broken screen.

The view shows at most **three per company** and says how many it folded
(*"+ 158 more at Anthropic, folded"*). Nothing is deleted — the rows stay in
the table, and a cap that silently drops rows is the same sin as a silent
filter.

## Two sections

| | |
|---|---|
| **Sponsorship** | They will sponsor a visa, so relocation is the route. **Only explicit offers** — silence does not qualify, and neither does "relocation assistance" |
| **Remote** | You stay where you are. Either the role is genuinely open worldwide, or they will engage a contractor, which needs no work permit |

A posting can be in both, and the best ones are. Forcing one bucket would hide exactly the
roles that will either relocate you *or* take you remote.

## Run it

Needs **Python 3.11+** and two packages. Everything else is standard library.

```bash
pip install fastapi uvicorn
python scripts/fetch.py               # crawl, filter, store
python -m jobradar.api                # dashboard at http://127.0.0.1:8000
python -m pytest                      # 64 tests

python scripts/probe_companies.py --wide   # which company boards are real
```

`install.bat` puts a shortcut on the Desktop that does the fetch and opens the
dashboard in one click.

## Six tabs

| Tab | What it is for |
|---|---|
| **Today** | New since the last run, ranked. The only screen used daily |
| **Sponsorship** | Explicit visa offers |
| **Remote** | Global roles, and the contractor path |
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
  sources/      greenhouse, lever, the two aggregators, and one HTTP layer
  filters/      the five filters, plus places.py — reading a location string
  posting.py    one shape, whatever the source was
  dedup.py      company as a hard barrier
  pipeline.py   judge, route into the two sections, count the kills
  store.py      SQLite: what is new, and every rejection
  api.py        FastAPI, 127.0.0.1 only
  web/          the dashboard — five tabs, no build step
scripts/
  fetch.py           the whole tool in one command
  install-hooks.sh   the pre-push guard that keeps this private
```

## Where the AI is, and is not

There is none, and the tool works. The five filters are regular expressions and word lists,
which was the point: the deterministic half needs no GPU and already takes 3,764 postings
down to 11.

A local 14B reading the job text would improve the hard cases — a posting that explains its
visa position in a paragraph rather than a phrase — and that is the next piece of work. The
README will say so until it is true.
