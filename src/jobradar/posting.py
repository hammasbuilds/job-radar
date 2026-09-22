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
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone

_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"[ \t\r\f\v]+")
_ENTITY = {
    "&amp;": "&", "&lt;": "<", "&gt;": ">", "&quot;": '"', "&#39;": "'",
    "&nbsp;": " ", "&rsquo;": "'", "&ldquo;": '"', "&rdquo;": '"', "&mdash;": "—",
    "&ndash;": "–", "&hellip;": "…",
}


def clean(html: str | None) -> str:
    """HTML to readable text. Deliberately not a parser.

    Job descriptions are simple documents and a real parser is a dependency
    this project does not need. Block tags become newlines first so that
    "Remote</li><li>Germany" does not become the single token
    "RemoteGermany" — which would make a location phrase match on text that
    never contained it.
    """
    if not html:
        return ""
    text = re.sub(r"(?i)<(br|/p|/li|/div|/h[1-6]|/tr)[^>]*>", "\n", html)
    text = _TAG.sub(" ", text)
    for entity, char in _ENTITY.items():
        text = text.replace(entity, char)

    # Numeric entities, decimal and hex. Hex was missing and Hacker News uses
    # it heavily: every slash in a posting arrived as "&#x2F;", so a title read
    # "Remote, PT&#x2F;ET hours" and a location phrase that spanned a slash
    # never matched.
    def _char(match: re.Match) -> str:
        body = match.group(1)
        try:
            code = int(body[1:], 16) if body[:1].lower() == "x" else int(body)
        except ValueError:
            return " "
        return chr(code) if 0 < code < 0x110000 else " "

    text = re.sub(r"&#(x[0-9a-fA-F]+|\d+);", _char, text)
    text = _WS.sub(" ", text)
    return re.sub(r"\n\s*\n+", "\n\n", text).strip()


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

        The URL is the natural key and is stable on every source here. It is
        hashed rather than stored raw so the id column has a fixed width and
        two postings cannot differ only by a tracking parameter.
        """
        url = self.url.split("?")[0].rstrip("/").lower()
        return hashlib.blake2b(url.encode(), digest_size=12).hexdigest()

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
        now = datetime.now(timezone.utc)
        return (now - self.posted).total_seconds() / 86400
