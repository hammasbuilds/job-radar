"""One way out to the network, with the failure modes already handled.

Every source in this package goes through `get_json`. That is deliberate: the
retry policy, the timeout, the User-Agent and the on-disk cache are decisions
that should be made once, not eight times with small differences.

**The cache is not an optimisation.** A run that fetches ten thousand postings
takes minutes, and developing a filter means running it repeatedly against the
same data. Without a cache the tenth run hammers other people's servers to ask
a question already answered, and the filters get tuned against a corpus that
quietly changes underneath them. With one, a re-run is offline and the numbers
are comparable.

**Nothing here sends a credential.** There is no auth argument, no header slot
for a token and no session. That is a design constraint from the note this
project came from: if a source needs a password, it is the wrong source.

**robots.txt is obeyed, per host, before the first request.** Read the way
RFC 9309 says to: a 4xx for robots.txt means there are no rules (Ashby
answers 401 for it), a 5xx or an unreachable host means *assume everything is
disallowed* for this run. A disallowed URL raises `Blocked` rather than being
fetched. SmartRecruiters is the case that made this matter: its API host
serves `User-agent: * / Disallow: /`, and it was being polled on every run.

**One request per host per second, or the host's Crawl-delay if longer.**
Lever and RemoteOK both publish `Crawl-delay: 1`; the Greenhouse loop asked
one host 46 times back to back. A 429 or 5xx is retried with backoff, and a
`Retry-After` header is honoured up to a minute.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from functools import lru_cache
from pathlib import Path

from .. import config


@lru_cache(maxsize=1)
def user_agent() -> str:
    """An honest User-Agent, with a contact address only if one is configured.

    Several ATS providers ask for a way to reach whoever is polling them, and
    a tool that pretends to be Chrome while hitting a public API is starting
    a fight it does not need. The address comes from `config.toml`, never
    from the code, so a clone does not send somebody else's email.
    """
    email = config.load().contact_email
    return f"job-radar/0.1 (personal job search tool{'; ' + email if email else ''})"

TIMEOUT = 30.0
RETRIES = 3
BACKOFF = 2.0
# Seconds between two requests to the same host; a robots.txt Crawl-delay
# longer than this wins.
MIN_INTERVAL = 1.0
RETRY_AFTER_CAP = 60.0
ROBOTS_MAX_AGE = 24 * 3600
# The product token robots.txt groups are matched against.
ROBOTS_AGENT = "job-radar"
_RETRY_STATUS = (429, 500, 502, 503, 504)


class SourceError(RuntimeError):
    """The source could not be read. Never raised for 'no jobs'."""


class Blocked(SourceError):
    """robots.txt disallows this URL for this agent, or could not be read."""


# Per-process state: when each host was last asked, and its parsed rules.
_last_request: dict[str, float] = {}
_robots: dict[str, urllib.robotparser.RobotFileParser | None] = {}


def _open(request: urllib.request.Request, timeout: float):
    """The one call that touches the network. Tests replace it."""
    return urllib.request.urlopen(request, timeout=timeout)


def _pace(host: str, interval: float) -> None:
    last = _last_request.get(host)
    if last is not None:
        wait = interval - (time.monotonic() - last)
        if wait > 0:
            time.sleep(wait)
    _last_request[host] = time.monotonic()


def _robots_for(scheme: str, host: str) -> urllib.robotparser.RobotFileParser | None:
    """The host's rules, or None when it publishes none.

    Raises `Blocked` when robots.txt could not be fetched for a server or
    network reason, which RFC 9309 says to read as "disallow everything".
    The text is cached on disk for a day like any other response.
    """
    if host in _robots:
        return _robots[host]
    url = f"{scheme}://{host}/robots.txt"
    slot = _slot(f"ROBOTS:{url}")
    text: str | None
    if slot.exists() and time.time() - slot.stat().st_mtime < ROBOTS_MAX_AGE:
        with gzip.open(slot, "rt", encoding="utf-8") as handle:
            text = handle.read()
    else:
        _pace(host, MIN_INTERVAL)
        request = urllib.request.Request(url, headers={"User-Agent": user_agent()})
        try:
            with _open(request, TIMEOUT) as response:
                text = response.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as exc:
            if 400 <= exc.code < 500:
                text = ""             # "unavailable": no rules, crawl allowed
            else:
                raise Blocked(f"{url}: HTTP {exc.code}, so everything is disallowed") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise Blocked(f"{url}: unreachable ({exc}), so everything is disallowed") from exc
        slot.parent.mkdir(parents=True, exist_ok=True)
        with gzip.open(slot, "wt", encoding="utf-8") as handle:
            handle.write(text)
    rules = None
    if text.strip():
        rules = urllib.robotparser.RobotFileParser(url)
        rules.parse(text.splitlines())
    _robots[host] = rules
    return rules


def allowed(url: str) -> tuple[bool, float]:
    """(may this URL be fetched, seconds to leave between requests to its host)."""
    parts = urllib.parse.urlsplit(url)
    rules = _robots_for(parts.scheme or "https", parts.netloc.lower())
    if rules is None:
        return True, MIN_INTERVAL
    delay = rules.crawl_delay(ROBOTS_AGENT)
    return rules.can_fetch(ROBOTS_AGENT, url), max(MIN_INTERVAL, float(delay or 0))


def _retry_after(exc: urllib.error.HTTPError, attempt: int) -> float:
    header = exc.headers.get("Retry-After") if exc.headers is not None else None
    try:
        seconds = float(header) if header else BACKOFF ** (attempt + 1)
    except ValueError:            # an HTTP date; not worth parsing for a minute
        seconds = BACKOFF ** (attempt + 1)
    return min(max(seconds, 0.0), RETRY_AFTER_CAP)


def _slot(url: str) -> Path:
    return config.cache_dir() / f"{hashlib.blake2b(url.encode(), digest_size=10).hexdigest()}.json.gz"


def _request_slot(url: str, method: str = "GET", body: bytes | None = None) -> Path:
    # A POST is cached under a different key from a GET of the same URL.
    # Workable's listing is a POST with an empty body; without this it would
    # read a GET's cached failure and return nothing forever.
    return _slot(f"{method}:{url}:{(body or b'').decode('utf-8', 'replace')}")


def prime(url: str, text: str, *, method: str = "GET", body: bytes | None = None) -> Path:
    """Put a response in the cache as if `url` had answered with `text`.

    How the offline dry run serves fixtures: it fills a scratch cache with
    this and replays it, so the fixtures go through exactly the code path a
    cached live response does.
    """
    slot = _request_slot(url, method, body)
    slot.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(slot, "wt", encoding="utf-8") as handle:
        handle.write(text)
    return slot


def get_text(url: str, *, max_age: float = 6 * 3600, cache: bool = True) -> str | None:
    """The same fetch, for a source that is not JSON.

    Personio publishes XML. Rather than give that one provider its own
    retry, timeout and cache, it shares this module's and the JSON layer is
    written on top of it.
    """
    payload = _fetch(url, max_age=max_age, cache=cache, parse=False)
    return payload


def get_json(url: str, *, max_age: float = 6 * 3600, cache: bool = True,
             method: str = "GET", body: bytes | None = None):
    """Fetch and parse JSON, from cache when it is fresh enough.

    `max_age` is in seconds. A 404 or an empty board is a legitimate answer
    about a company and is returned as None rather than raised, because a seed
    list of a few hundred ATS slugs will always contain some that have gone
    away, and one dead slug must not end the run.
    """
    return _fetch(url, max_age=max_age, cache=cache, parse=True,
                  method=method, body=body)


def _fetch(url: str, *, max_age: float, cache: bool, parse: bool,
           method: str = "GET", body: bytes | None = None):
    slot = _request_slot(url, method, body)
    # Offline mode replays whatever is cached, however old, and never touches
    # the network. It is how a crawl is reproduced exactly: the same bytes in
    # give the same funnel out, which a live crawl never can.
    offline = config.offline()
    if cache and slot.exists() and (offline or time.time() - slot.stat().st_mtime < max_age):
        with gzip.open(slot, "rt", encoding="utf-8") as handle:
            raw = handle.read()
        return json.loads(raw) if parse else raw
    if offline:
        raise SourceError(f"{url}: not in the cache (offline mode)")

    # A seed list is hand-written and will contain a slug with a space or an
    # accent in it. urllib raises InvalidURL for those, which is not an
    # exception any caller should have to expect — and unhandled it ended a
    # 67-board run on its first bad entry. Encode, and let the source decide
    # what to do with the 404 that follows.
    url = urllib.parse.quote(url, safe=":/?&=%~+,._-")

    may, interval = allowed(url)
    if not may:
        raise Blocked(f"{url}: disallowed by robots.txt")
    host = urllib.parse.urlsplit(url).netloc.lower()

    last: Exception | None = None
    for attempt in range(RETRIES):
        _pace(host, interval)
        try:
            headers = {"User-Agent": user_agent()}
            if body is not None:
                headers["Content-Type"] = "application/json"
            request = urllib.request.Request(
                url, headers=headers, data=body, method=method
            )
            with _open(request, TIMEOUT) as response:
                text = response.read().decode("utf-8", "replace")
            payload = json.loads(text) if parse else text
            if cache:
                slot.parent.mkdir(parents=True, exist_ok=True)
                with gzip.open(slot, "wt", encoding="utf-8") as handle:
                    handle.write(text)
            return payload
        except urllib.error.HTTPError as exc:
            # 404 means this company has no board here. Not an error.
            if exc.code in (404, 410):
                return None
            # Rate limits and server errors are worth waiting out, for as
            # long as the server asks; any other status fails fast.
            if exc.code in _RETRY_STATUS and attempt < RETRIES - 1:
                time.sleep(_retry_after(exc, attempt))
                last = exc
                continue
            raise SourceError(f"{url}: HTTP {exc.code}") from exc
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
            last = exc
            if attempt < RETRIES - 1:
                time.sleep(BACKOFF**attempt)
    raise SourceError(f"{url}: {last}")

