"""One shape, whatever the source was.

Four sources describe a job four different ways. Greenhouse gives HTML content
and a location string; Lever gives structured categories; Arbeitnow gives tags
and a boolean `remote`; Remotive gives a candidate-region field. If that
difference survives into the filters, every filter has to know about every
source and the project becomes unmaintainable at four sources, let alone ten.

So each source normalises to `Posting` and nothing downstream knows where a
job came from — except `source`, which exists only so the funnel can report
kill rates per source and so a broken adapter is visible rather than silent.

**`text` is the whole posting, tags stripped, lower-cased on demand.** Every
interesting fact in this project — "must reside in Germany", "we cannot
sponsor", "freelance/B2B welcome" — lives in prose, not in a structured field.
That is the entire reason this tool needs to read job text at all.
"""

from __future__ import annotations

import hashlib
import html
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

_TAG = re.compile(r"<[^>]+>")
_BLOCK = re.compile(r"(?i)<(?:br|/p|/li|li|/div|/h[1-6]|/tr|/ul|/ol)\b[^>]*>")
_INVISIBLE = re.compile(r"(?is)<(script|style|template)\b.*?</\1\s*>")
_WS = re.compile(r"[ \t\r\f\v\u00a0]+")


def clean(markup: str | None) -> str:
    """HTML to readable text. Deliberately not a parser.

    Job descriptions are simple documents and a real parser is a dependency
    this project does not need. Block tags become newlines first so that
    "Remote</li><li>Germany" does not become the single token
    "RemoteGermany" — which would make a location phrase match on text that
    never contained it.

    **Entity-escaped markup is decoded before tags are stripped.** Greenhouse
    sends its content field escaped (`&lt;p&gt;6+ years&lt;/p&gt;`). Stripping
    tags first found none, then decoding turned the entities into real tags,
    so every Greenhouse posting — 7,069 of 9,755 in the 2026-09-23 corpus —
    was filtered and stored as markup. A body that contains escaped tags and
    no real ones is unescaped once up front; everything else is unescaped
    once, after the tags are gone, which is also how "&#x2F;" in Hacker News
    comments becomes a slash.
    """
    if not markup:
        return ""
    text = markup
    if "&lt;" in text and not _TAG.search(text):
        text = html.unescape(text)
    text = _INVISIBLE.sub(" ", text)
    text = _BLOCK.sub("\n", text)
    text = _TAG.sub(" ", text)
    text = html.unescape(text)
    text = _WS.sub(" ", text)
    text = re.sub(r" *\n *", "\n", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


# Query parameters that say how someone arrived, not which job it is. Every
# other parameter is kept, because on several boards the job id lives only in
# the query string: Databricks and Stripe (`?gh_jid=N`), and every Hacker News
# comment (`item?id=N`).
_TRACKING = re.compile(
    r"^(?:utm_\w+|gh_src|src|source|ref|referrer|lever-source(?:\[\])?|"
    r"lever-origin|fbclid|gclid|mc_cid|mc_eid|trk|trackingid)$",
    re.I,
)


def identity(url: str) -> str:
    """The part of a URL that names one job.

    Scheme and host are case-folded and a trailing slash dropped; tracking
    parameters are removed and the rest are sorted. The job id is *never*
    dropped, wherever it lives. An earlier version cut everything after "?",
    which merged 2,253 of 9,755 postings into six database rows and grafted
    one job's verdict onto another's title.
    """
    parts = urlsplit((url or "").strip())
    query = sorted(
        (k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if not _TRACKING.match(k)
    )
    return urlunsplit((
        parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"),
        urlencode(query), parts.fragment,
    ))


def key_for(url: str, fallback: str = "") -> str:
    """Hash of `identity(url)`; `fallback` identifies a posting with no URL."""
    ident = identity(url) or f"no-url:{fallback}"
    return hashlib.blake2b(ident.encode(), digest_size=12).hexdigest()


@dataclass
class Posting:
    """One job, as this project understands a job."""

    source: str                  # greenhouse | lever | arbeitnow | remotive
    company: str
    title: str
    location: str
    url: str
    text: str                    # the full description, tags stripped
    posted: datetime | None = None
    remote_hint: bool | None = None   # what the source claimed, if anything
    tags: tuple[str, ...] = ()

    # Filled in by the pipeline, never by a source.
    verdict: dict = field(default_factory=dict)
    score: float = 0.0
    evidence: str = ""
    section: str = ""

    def __post_init__(self) -> None:
        """Flatten `tags` to plain strings, whatever the source sent.

        Sources disagree about the shape of a tag. Lever sends strings,
        Jobicy sends `["Full-Time"]`, and Himalayas sends `employmentType`
        as a list — which put a list inside the tuple and crashed the
        employment filter on `t.strip()` after 786 postings had been
        fetched. Normalising here means no filter has to defend itself,
        and a new source cannot reintroduce it.
        """
        flat: list[str] = []
        for tag in self.tags or ():
            if isinstance(tag, str):
                flat.append(tag)
            elif isinstance(tag, (list, tuple, set)):
                flat += [str(t) for t in tag if t]
            elif tag is not None:
                flat.append(str(tag))
        object.__setattr__(self, "tags", tuple(t.strip() for t in flat if t.strip()))

    @property
    def key(self) -> str:
        """Stable identity for a posting, used for 'new since last run'.

        The URL with its job id, whether the id sits in the path or in the
        query string (see `identity`). A posting with no URL at all falls
        back to its source, company, title and location, so two URL-less
        postings never share a row.
        """
        return key_for(self.url, f"{self.source}|{self.company}|{self.title}|{self.location}")

    @property
    def haystack(self) -> str:
        """Everything a filter may read, lower-cased, in one string.

        Title and location are included because the decisive phrase is as
        often in the title ("Remote, EU only") as in the body.
        """
        return f"{self.title}\n{self.location}\n{self.text}".lower()

    @property
    def age_days(self) -> float | None:
        if not self.posted:
            return None
        now = datetime.now(UTC)
        return (now - self.posted).total_seconds() / 86400
