"""The dashboard, served locally. No auth, because there is nothing to protect.

    python -m jobradar.api

This is a tool one person runs on their own machine against their own SQLite
file. There is no login, no session and no token anywhere in this project —
that is a constraint from the design note rather than an oversight:

    No password, OAuth or session token, anywhere. If a design needs one,
    that design is wrong.

It binds to 127.0.0.1 for the same reason. Nothing here should be reachable
from outside the machine, and a tool that quietly listens on 0.0.0.0 is one
misconfigured router away from being a public website.
"""

from __future__ import annotations

import argparse
import webbrowser
from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import gap, inventory, pipeline, store

WEB = Path(__file__).resolve().parent / "web"

app = FastAPI(title="job-radar", docs_url=None, redoc_url=None)


class Applied(BaseModel):
    state: str
    noted: str = ""


@app.get("/")
def index() -> FileResponse:
    return FileResponse(WEB / "index.html")


@app.get("/api/today")
def today() -> JSONResponse:
    """New since the last run. The only screen used daily."""
    return JSONResponse({"postings": store.newest(limit=60), "run": store.last_run()})


@app.get("/api/section/{name}")
def section(name: str) -> JSONResponse:
    if name not in pipeline.SECTIONS:
        return JSONResponse({"error": "unknown section"}, status_code=404)
    return JSONResponse({
        "postings": store.section(name, limit=200),
        "total": store.section_total(name),
    })


@app.get("/api/yc")
def yc(bucket: str | None = None, ai_only: bool = False) -> JSONResponse:
    """YC companies. Company-first: every open role, no description filter."""
    return JSONResponse({
        "companies": store.yc_companies(bucket=bucket, ai_only=ai_only),
        "counts": store.yc_counts(),
    })


@app.get("/api/gap/{posting_id}")
def gap_for(posting_id: str) -> JSONResponse:
    """How this posting matches the portfolio and CV, and what is missing.

    Computed when a row is opened rather than during the crawl: the inventory
    changes whenever a repo is pushed or the CV is edited, and a match score
    cached at crawl time would quietly go stale against a moving profile.
    """
    row = store.posting(posting_id)
    if not row:
        return JSONResponse({"error": "unknown posting"}, status_code=404)
    report = gap.analyse(row["title"], row.get("text") or "", _inventory())
    return JSONResponse(gap.as_dict(report))


@lru_cache(maxsize=1)
def _inventory():
    """Built once per process. Restart the server after editing the CV."""
    return inventory.build()


@app.get("/api/killed")
def killed(reason: str | None = None) -> JSONResponse:
    """The trust screen. Every rejection, with the phrase that caused it."""
    return JSONResponse(
        {"reasons": store.kill_reasons(), "postings": store.killed(reason, limit=300)}
    )


@app.get("/api/market")
def market() -> JSONResponse:
    """The funnel, and where the corpus actually sits."""
    run = store.last_run()
    return JSONResponse({"run": run})


@app.get("/api/pipeline")
def pipeline_view() -> JSONResponse:
    # Not named `pipeline`: that shadowed the imported `pipeline` module and
    # every section endpoint started returning 500, because `pipeline.SECTIONS`
    # was resolving to an attribute of this function.
    return JSONResponse({"postings": store.pipeline()})


@app.post("/api/applied/{posting_id}")
def applied(posting_id: str, body: Applied) -> JSONResponse:
    """The pipeline, updated by hand.

    The note is explicit that this is the one part that should not be
    automated, so this endpoint exists only because a human clicks it.
    """
    try:
        store.set_application(posting_id, body.state, body.noted)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=422)
    except KeyError:
        return JSONResponse({"error": "unknown posting"}, status_code=404)
    return JSONResponse({"ok": True})


def main() -> None:
    import uvicorn

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    if not args.no_browser:
        webbrowser.open(f"http://127.0.0.1:{args.port}")
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")


if WEB.exists():
    app.mount("/static", StaticFiles(directory=WEB), name="static")

if __name__ == "__main__":
    main()
