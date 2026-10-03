"""Score the pipeline against the hand-labelled evaluation set.

    python scripts/evaluate.py                         # current code
    python scripts/evaluate.py --out results/eval.json # and write the numbers
    python scripts/evaluate.py --src ../old/src        # any other version of the code

The evaluation set (`eval/postings.jsonl.gz` + `eval/labels.csv`) is real
postings from the 2026-09-23 crawl, stored as the *raw* item each source
returned, and labelled by reading them - never by running the filters. Each
raw item is fed through the source adapter of whichever code is being scored
(the adapter's HTTP call is replaced by the stored item), so HTML handling and
Hacker News splitting are measured along with the filters, and an old commit
can be scored on exactly the same inputs as the current one.

Reported: keep/kill precision and recall, first-kill-reason accuracy, and
per-filter accuracy, each with a 95% Wilson interval; plus two baselines that
see the same postings - "kill everything" and a title-keyword rule.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import importlib
import json
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "eval" / "postings.jsonl.gz"
LABELS = ROOT / "eval" / "labels.csv"

# Where each source keeps its list of jobs, so one stored item can be handed
# back to the adapter wrapped exactly as the live API would have sent it.
_ENVELOPE = {
    "greenhouse": lambda it: {"jobs": [it]},
    "lever": lambda it: [it],
    "ashby": lambda it: {"jobs": [it], "name": it.get("_board_name")},
    "smartrecruiters": lambda it: {"content": [it]},
    "workable": lambda it: {"results": [it]},
    "recruitee": lambda it: {"offers": [it]},
    "arbeitnow": lambda it: {"data": [it]},
    "remotive": lambda it: {"jobs": [it]},
    "himalayas": lambda it: {"jobs": [it]},
    "jobicy": lambda it: {"jobs": [it]},
    "remoteok": lambda it: [it],
    "themuse": lambda it: {"results": [it]},
}

LEVELS_OK = {"assistant", "junior", "associate", "mid"}


def load_package(src: Path):
    """Import `jobradar` from `src`, whatever version of the code lives there."""
    for name in [m for m in sys.modules if m == "jobradar" or m.startswith("jobradar.")]:
        del sys.modules[name]
    sys.path.insert(0, str(src.resolve()))
    return importlib.import_module("jobradar")


def parse_item(record: dict) -> list:
    """Run one stored raw item through the loaded code's own source adapter."""
    source, slug, item = record["source"], record.get("slug", ""), record["item"]
    if source in ("greenhouse", "lever"):
        mod = importlib.import_module(f"jobradar.sources.{source}")
        mod.get_json = lambda *a, **k: _ENVELOPE[source](item)
        return mod.fetch(slug)
    if source in ("ashby", "smartrecruiters", "workable", "recruitee"):
        mod = importlib.import_module("jobradar.sources.ats")
        mod.get_json = lambda *a, **k: _ENVELOPE[source](item)
        return getattr(mod, source)(slug)
    if source in ("arbeitnow", "remotive"):
        mod = importlib.import_module("jobradar.sources.aggregators")
        mod.get_json = lambda *a, **k: _ENVELOPE[source](item)
        return getattr(mod, f"fetch_{source}")()
    if source in ("himalayas", "jobicy", "remoteok"):
        mod = importlib.import_module("jobradar.sources.boards")
        mod.get_json = lambda *a, **k: _ENVELOPE[source](item)
        return getattr(mod, source)()
    if source == "themuse":
        mod = importlib.import_module("jobradar.sources.boards")
        pages = iter([_ENVELOPE[source](item)])
        mod.get_json = lambda *a, **k: next(pages, None)
        return mod.themuse()
    if source == "hn":
        mod = importlib.import_module("jobradar.sources.boards")
        calls = iter([{"hits": [{"title": slug or "Ask HN: Who is hiring?", "objectID": "0"}]},
                      {"children": [item]}])
        mod.get_json = lambda *a, **k: next(calls, None)
        return mod.hacker_news()
    if source == "mustakbil":
        mod = importlib.import_module("jobradar.sources.mustakbil")
        mod.get_text = lambda *a, **k: f"<rss><channel><item>{item}</item></channel></rss>"
        return mod.fetch_feed()
    raise ValueError(f"no adapter for source {source!r}")


def reason_group(killed_by: str) -> str:
    """Collapse a kill reason to the stage that produced it."""
    if not killed_by:
        return ""
    if "target role" in killed_by:
        return "role"
    if killed_by.endswith(" level"):
        return "level"
    if killed_by.startswith("wants ") and "years" in killed_by:
        return "years"
    if "fit threshold" in killed_by:
        return "fit"
    return "route"


def judge(record: dict, label: dict) -> dict:
    """The loaded code's verdict on one labelled item."""
    pipeline = importlib.import_module("jobradar.pipeline")
    postings = parse_item(record)
    runs = []
    for posting in postings:
        kept, _ = pipeline.run([posting])
        runs.append((posting, bool(kept)))
    if not runs:
        return {"keep": False, "reason": "role", "title": "", "verdict": {},
                "note": "adapter produced no posting"}

    wanted = (label.get("role_title") or "").strip().lower()
    chosen = None
    if wanted:
        for posting, keep in runs:
            title = posting.title.lower()
            if wanted in title or (title and title in wanted):
                chosen = (posting, keep)
                break
        if chosen is None:
            return {"keep": False, "reason": "role", "title": "", "verdict": {},
                    "note": f"no extracted title matches {wanted!r}"}
    else:
        chosen = next(((p, k) for p, k in runs if k), runs[0])
    posting, keep = chosen
    killed_by = posting.verdict.get("killed_by", "")
    return {
        "keep": keep,
        "reason": "" if keep else reason_group(killed_by),
        "killed_by": killed_by,
        "title": posting.title,
        "section": posting.section,
        # Every filter's reading, whether or not the pipeline got that far:
        # per-filter accuracy is about the filter, not about the funnel.
        "verdict": pipeline.judge(posting),
    }


# --- the baselines ---------------------------------------------------------

_KW_DOMAIN = re.compile(
    r"\b(?:ai|a\.i\.|ml|machine learning|deep learning|data scien\w*|llm|nlp|"
    r"computer vision|genai|generative|research)\b", re.I)
_KW_SENIOR = re.compile(
    r"\b(?:senior|sr|staff|lead|principal|head|director|manager|vp|chief|intern)\b", re.I)


def keyword_baseline(title: str) -> bool:
    """What a keyword search on a job board gives you: an AI word in the
    title and no seniority word. No route, years or authorisation logic."""
    return bool(_KW_DOMAIN.search(title)) and not _KW_SENIOR.search(title)


# --- statistics ------------------------------------------------------------

def wilson(hits: int, n: int, z: float = 1.96) -> list[float]:
    if n == 0:
        return [0.0, 0.0]
    p = hits / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return [round(max(0.0, centre - half), 3), round(min(1.0, centre + half), 3)]


def rate(hits: int, n: int) -> dict:
    return {"value": round(hits / n, 3) if n else None, "hits": hits, "n": n,
            "ci95": wilson(hits, n)}


def keep_kill(pairs: list[tuple[bool, bool]]) -> dict:
    """pairs of (gold keep, predicted keep)."""
    tp = sum(g and p for g, p in pairs)
    fp = sum(p and not g for g, p in pairs)
    fn = sum(g and not p for g, p in pairs)
    tn = sum(not g and not p for g, p in pairs)
    return {
        "precision_keep": rate(tp, tp + fp),
        "recall_keep": rate(tp, tp + fn),
        "precision_kill": rate(tn, tn + fn),
        "recall_kill": rate(tn, tn + fp),
        "accuracy": rate(tp + tn, len(pairs)),
        "confusion": {"tp": tp, "fp": fp, "fn": fn, "tn": tn},
    }


def _years_over(value, limit: int = 3) -> bool:
    return value not in (None, "") and int(value) > limit


def per_filter(rows: list[tuple[dict, dict]]) -> dict:
    """Each filter's reading against the label for the same question."""
    out = {}

    def tally(name, pairs):
        out[name] = rate(sum(g == p for g, p in pairs), len(pairs))

    tally("role", [(r["is_role"] == "y", bool(p["verdict"].get("role")))
                   for r, p in rows if r["is_role"] and p["verdict"]])
    tally("level", [(r["level_ok"] == "y", p["verdict"].get("level") in LEVELS_OK)
                    for r, p in rows if r["level_ok"] and p["verdict"]])
    tally("years_over_3", [(_years_over(r["years"]), _years_over(p["verdict"].get("years")))
                           for r, p in rows if r["years"] != "" and p["verdict"]])
    tally("authorisation", [(r["auth"], _auth(p["verdict"].get("auth")))
                            for r, p in rows if r["auth"] and p["verdict"]])
    tally("where", [(r["where"], _where(p["verdict"].get("scope"), p["verdict"].get("scope_why")))
                    for r, p in rows if r["where"] and p["verdict"]])
    return out


def _auth(value) -> str:
    if value in ("refuses", "nationals_only"):
        return "refuses"
    return "sponsors" if value == "sponsors" else "silent"


# The two phrases both versions of the code use when "remote" is all a
# posting says: the scope is a guess, not a reading.
_UNSCOPED = ("says remote, states no scope", "source flags remote, text says nothing")


def _where(scope, why=None) -> str:
    if scope == "region" and why in _UNSCOPED:
        return "remote-unscoped"
    if scope == "global":
        return "remote-global"
    if scope in ("region", "country"):
        return "remote-restricted"
    if scope in ("hybrid", "onsite"):
        return "onsite"
    return "unknown"


def load_fixture(path: Path) -> dict[str, dict]:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as handle:
        return {rec["id"]: rec for rec in map(json.loads, handle)}


def load_labels(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as handle:
        rows = [r for r in csv.DictReader(handle)]
    for row in rows:
        for key in ("role_title", "reason", "is_role", "level_ok", "years", "auth", "where"):
            row[key] = (row.get(key) or "").strip()
        if row["expected"] not in ("keep", "kill"):
            raise ValueError(f"{row['id']}: expected must be keep or kill")
    return rows


def evaluate(fixture: dict[str, dict], labels: list[dict]) -> dict:
    rows = []
    for label in labels:
        pred = judge(fixture[label["id"]], label)
        rows.append((label, pred))

    gold_keep = [lab["expected"] == "keep" for lab, _ in rows]
    killed = [(lab, pred) for lab, pred in rows if lab["expected"] == "kill"]
    reason_hits = sum(1 for lab, pred in killed if not pred["keep"] and pred["reason"] == lab["reason"])

    by_stratum: dict[str, list] = {}
    for lab, pred in rows:
        by_stratum.setdefault(lab["stratum"], []).append((lab["expected"] == "keep", pred["keep"]))

    per_reason = {}
    for reason in ("role", "level", "years", "route"):
        subset = [(lab, pred) for lab, pred in killed if lab["reason"] == reason]
        per_reason[reason] = rate(
            sum(1 for lab, pred in subset if not pred["keep"] and pred["reason"] == reason),
            len(subset))

    # The baseline reads the title as labelled (for a Hacker News comment,
    # its first line), so it sees the same text whichever code is scored.
    keyword = [(g, keyword_baseline(lab["title"])) for g, (lab, _) in zip(gold_keep, rows, strict=True)]
    return {
        "items": len(rows),
        "gold_keep": sum(gold_keep),
        "pipeline": keep_kill([(g, pred["keep"]) for g, (_, pred) in zip(gold_keep, rows, strict=True)]),
        "kill_reason_accuracy": rate(reason_hits, len(killed)),
        "kill_reason_by_gold_reason": per_reason,
        "per_filter": per_filter(rows),
        "by_stratum": {k: keep_kill(v) for k, v in sorted(by_stratum.items())},
        "baseline_kill_everything": keep_kill([(g, False) for g in gold_keep]),
        "baseline_title_keywords": keep_kill(keyword),
        "errors": [
            {"id": lab["id"], "company": lab["company"], "title": lab["title"],
             "gold": lab["expected"] + (f" ({lab['reason']})" if lab["reason"] else ""),
             "predicted": "keep" if pred["keep"] else f"kill ({pred.get('killed_by', pred['reason'])})",
             "note": lab["note"]}
            for lab, pred in rows
            if (lab["expected"] == "keep") != pred["keep"]
            or (lab["expected"] == "kill" and pred["reason"] != lab["reason"])
        ],
    }


def _fmt(r: dict) -> str:
    if r["value"] is None:
        return "   n/a"
    lo, hi = r["ci95"]
    return f"{r['value']:.3f} ({r['hits']}/{r['n']}, 95% CI {lo:.2f}-{hi:.2f})"


def report(result: dict) -> list[str]:
    p = result["pipeline"]
    lines = [f"{result['items']} labelled postings, {result['gold_keep']} should be kept", ""]
    for name, block in (("pipeline", p),
                        ("baseline: title keywords", result["baseline_title_keywords"]),
                        ("baseline: kill everything", result["baseline_kill_everything"])):
        lines.append(name)
        for key in ("precision_keep", "recall_keep", "precision_kill", "recall_kill", "accuracy"):
            lines.append(f"  {key:<15} {_fmt(block[key])}")
        lines.append(f"  confusion       {block['confusion']}")
        lines.append("")
    lines.append(f"kill reason right  {_fmt(result['kill_reason_accuracy'])}")
    for reason, r in result["kill_reason_by_gold_reason"].items():
        lines.append(f"  gold {reason:<6}      {_fmt(r)}")
    lines.append("")
    lines.append("per filter")
    for name, r in result["per_filter"].items():
        lines.append(f"  {name:<15} {_fmt(r)}")
    lines.append("")
    lines.append(f"{len(result['errors'])} disagreements")
    for e in result["errors"]:
        lines.append(f"  {e['id']}  gold {e['gold']:<14} got {e['predicted']:<40} "
                     f"{e['company'][:18]} | {e['title'][:50]}")
    return lines


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--src", type=Path, default=ROOT / "src",
                        help="the package source directory to score (default: this repo's src)")
    parser.add_argument("--fixture", type=Path, default=FIXTURE,
                        help="raw postings, JSON lines, optionally gzipped")
    parser.add_argument("--labels", type=Path, default=LABELS, help="the hand labels (CSV)")
    parser.add_argument("--out", type=Path, default=None, metavar="FILE",
                        help="write the full result, disagreements included, as JSON")
    args = parser.parse_args()

    for path in (args.src, args.fixture, args.labels):
        if not path.exists():
            parser.error(f"{path} does not exist")
    load_package(args.src)
    result = evaluate(load_fixture(args.fixture), load_labels(args.labels))
    result["code"] = str(args.src)
    print("\n".join(report(result)))
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n",
                            encoding="utf-8")
        print(f"\nwritten to {args.out}")


if __name__ == "__main__":
    # A Windows console defaults to the ANSI code page; the output has arrows and ellipses.
    for _stream in (sys.stdout, sys.stderr):
        _stream.reconfigure(encoding="utf-8", errors="replace")
    main()
