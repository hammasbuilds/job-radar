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
"""

from __future__ import annotations

import gzip
import hashlib
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

CACHE = Path(__file__).resolve().parents[3] / "data" / "cache"

# A real contact address rather than a browser string. SEC EDGAR requires one,
# several ATS providers ask for it in their terms, and a tool that pretends to
# be Chrome while hitting a public API is starting a fight it does not need.
UA = "job-radar/0.1 (personal job search tool; jigglybear157@gmail.com)"

TIMEOUT = 30.0
RETRIES = 3
BACKOFF = 2.0


class SourceError(RuntimeError):
    """The source could not be read. Never raised for 'no jobs'."""


def _slot(url: str) -> Path:
    return CACHE / f"{hashlib.blake2b(url.encode(), digest_size=10).hexdigest()}.json.gz"


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
    # A POST is cached under a different key from a GET of the same URL.
    # Workable's listing is a POST with an empty body; without this it would
    # read a GET's cached failure and return nothing forever.
    slot = _slot(f"{method}:{url}:{(body or b'').decode('utf-8', 'replace')}")
    if cache and slot.exists() and time.time() - slot.stat().st_mtime < max_age:
        with gzip.open(slot, "rt", encoding="utf-8") as handle:
            raw = handle.read()
        return json.loads(raw) if parse else raw

    # A seed list is hand-written and will contain a slug with a space or an
    # accent in it. urllib raises InvalidURL for those, which is not an
    # exception any caller should have to expect — and unhandled it ended a
    # 67-board run on its first bad entry. Encode, and let the source decide
    # what to do with the 404 that follows.
    url = urllib.parse.quote(url, safe=":/?&=%~+,._-")

    last: Exception | None = None
    for attempt in range(RETRIES):
        try:
            headers = {"User-Agent": UA}
            if body is not None:
                headers["Content-Type"] = "application/json"
            request = urllib.request.Request(
                url, headers=headers, data=body, method=method
            )
            with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
                text = response.read().decode("utf-8", "replace")
            payload = json.loads(text) if parse else text
            if cache:
                CACHE.mkdir(parents=True, exist_ok=True)
                with gzip.open(slot, "wt", encoding="utf-8") as handle:
                    handle.write(text)
            return payload
        except urllib.error.HTTPError as exc:
            # 404 means this company has no board here. Not an error.
            if exc.code in (404, 410):
                return None
            # 429 is the one worth waiting out; everything else fails fast.
            if exc.code == 429 and attempt < RETRIES - 1:
                time.sleep(BACKOFF ** (attempt + 1))
                last = exc
                continue
            raise SourceError(f"{url}: HTTP {exc.code}") from exc
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
            last = exc
            if attempt < RETRIES - 1:
                time.sleep(BACKOFF**attempt)
    raise SourceError(f"{url}: {last}")


def cached_urls() -> int:
    return len(list(CACHE.glob("*.json.gz"))) if CACHE.exists() else 0
