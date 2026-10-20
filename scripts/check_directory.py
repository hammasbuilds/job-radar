"""Open every link in directory.py and report the ones that do not answer.

    python scripts/check_directory.py

A directory of dead links is worse than a short one, so this runs before the list is trusted.
It is a plain GET with the tool's user agent and redirects followed; a 403 from a site that
refuses scripts is reported separately from a 404, because the first is usually fine in a
browser and the second never is.
"""

from __future__ import annotations

import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from jobradar import directory  # noqa: E402
from jobradar.sources.http import user_agent  # noqa: E402


def status(url: str) -> tuple[str, int, str]:
    req = urllib.request.Request(url, headers={"User-Agent": user_agent()})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return url, resp.status, resp.geturl()
    except urllib.error.HTTPError as exc:
        return url, exc.code, ""
    except Exception as exc:  # DNS, TLS, timeout: all mean "does not answer"
        return url, 0, type(exc).__name__


def main() -> None:
    urls = sorted({u for e in directory.ENTRIES for u in (e["url"], e["jobs_url"]) if u})
    with ThreadPoolExecutor(8) as pool:
        results = list(pool.map(status, urls))
    bad = [(u, s, why) for u, s, why in results if not 200 <= s < 400]
    print(f"{len(urls)} links, {len(urls) - len(bad)} answer")
    for url, code, why in sorted(bad, key=lambda r: r[1]):
        print(f"  {code or 'no answer':>9}  {url}  {why}")


if __name__ == "__main__":
    main()
