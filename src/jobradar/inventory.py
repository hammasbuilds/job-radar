"""What you can actually prove, and what proves it.

A gap report that says "you lack Kubernetes" is only worth reading if the
other half — "you have PyTorch" — is backed by something. So every skill
found here carries its evidence: the repository whose stack line names it, or
the sentence in the CV that does.

Two sources, and they are different kinds of claim:

  **The portfolio** — `D:\\github\\PROJECTS.md`, which lists every repo with a
  `**Stack:**` line. This is the strong evidence: the code exists and is
  pushed, so the skill is demonstrable rather than asserted.

  **The CV** — a .docx or .pdf. This covers what the portfolio cannot show:
  employment, degrees, and work done for other people. Read directly from the
  file with no dependency; a .docx is a zip holding XML.

Where both name a skill, the repository is cited, because "here is the code"
beats "I wrote it on my CV" in any conversation that follows.
"""

from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from . import skills

PROJECTS_MD = Path(r"D:\github\PROJECTS.md")

# Where to look for a CV, newest first. Nothing here is required — the report
# still works from the portfolio alone, and says which halves it had.
CV_DIRS = (
    Path.home() / "Downloads",
    Path.home() / "Documents",
    Path.home() / "Desktop",
)
CV_PATTERNS = ("*CV*.docx", "*CV*.pdf", "*cv*.docx", "*resume*.docx", "*Resume*.pdf")


@dataclass
class Inventory:
    """Every skill you can show, with where it is shown."""

    # skill -> the things that prove it ("classical-computer-vision", "CV")
    evidence: dict[str, list[str]] = field(default_factory=dict)
    repos: int = 0
    cv_path: str = ""
    cv_chars: int = 0

    @property
    def skills(self) -> set[str]:
        return set(self.evidence)

    def proof(self, skill: str, limit: int = 3) -> str:
        where = self.evidence.get(skill) or []
        head = ", ".join(where[:limit])
        extra = f" +{len(where) - limit} more" if len(where) > limit else ""
        return head + extra


def _docx_text(path: Path) -> str:
    """A .docx is a zip of XML. No dependency needed to read one."""
    try:
        with zipfile.ZipFile(path) as archive:
            xml = archive.read("word/document.xml").decode("utf-8", "replace")
    except (zipfile.BadZipFile, KeyError, OSError):
        return ""
    xml = re.sub(r"</w:p>", "\n", xml)
    text = re.sub(r"<[^>]+>", " ", xml)
    text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    return re.sub(r"[ \t]+", " ", text)


def _pdf_text(path: Path) -> str:
    """Enough of a PDF to find skill words in it.

    Deliberately crude: uncompressed text operators only. A real PDF parser
    is a dependency this project does not need, and a CV usually exists as a
    .docx too. If this returns little, the .docx is used instead.
    """
    try:
        raw = path.read_bytes()
    except OSError:
        return ""
    chunks = re.findall(rb"\(([^)\\]{2,})\)\s*Tj", raw)
    return " ".join(c.decode("latin-1", "replace") for c in chunks)


def find_cv() -> Path | None:
    """The newest CV-looking file. .docx is preferred: it always reads."""
    found: list[Path] = []
    for folder in CV_DIRS:
        if not folder.exists():
            continue
        for pattern in CV_PATTERNS:
            found += list(folder.glob(pattern))
    if not found:
        return None
    docx = [p for p in found if p.suffix.lower() == ".docx"]
    return max(docx or found, key=lambda p: p.stat().st_mtime)


def read_cv(path: Path | None = None) -> tuple[str, str]:
    path = path or find_cv()
    if not path or not path.exists():
        return "", ""
    text = _docx_text(path) if path.suffix.lower() == ".docx" else _pdf_text(path)
    return text, str(path)


_STACK = re.compile(r"^\s*-\s*\*\*Stack:\*\*\s*(.+)$", re.M)
_REPO = re.compile(r"^#{2,4}\s*`?([A-Za-z0-9._-]+)`?", re.M)


def read_portfolio(path: Path | None = None) -> tuple[dict[str, list[str]], int]:
    """Skills to the repositories that prove them, from PROJECTS.md.

    Each repo section is followed by a `**Stack:**` line. Walking the file in
    order lets a stack line be attributed to the heading above it, which is
    what makes the evidence specific — "PyTorch (classical-computer-vision)"
    rather than "PyTorch (somewhere)".
    """
    path = path or PROJECTS_MD
    if not path.exists():
        return {}, 0

    text = path.read_text(encoding="utf-8", errors="replace")
    evidence: dict[str, list[str]] = {}
    current = "PROJECTS.md"
    seen_repos: set[str] = set()
    body: list[str] = []

    def flush() -> None:
        # The whole section, not only its Stack line. Reading stack lines
        # alone found 31 skills and missed the obvious ones: `rag-forge` did
        # not prove RAG and `mcp-lab` did not prove MCP, because those words
        # are in the repo's name and description rather than its dependency
        # list. What a repo *is* counts as evidence as much as what it imports.
        if not body:
            return
        for skill in skills.found_in(f"{current} " + " ".join(body)):
            where = evidence.setdefault(skill, [])
            if current not in where:
                where.append(current)

    # PROJECTS.md has prose headings as well as repo headings — "Practical",
    # "Gaps", "Conventions" — and citing those as evidence reads as nonsense:
    # "RAG <- Gaps". A heading counts as a repository only if a folder of that
    # name exists beside the file, which is the same check a reader would make.
    root = path.parent
    real = {p.name for p in root.iterdir() if p.is_dir()} if root.exists() else set()

    for line in text.splitlines():
        heading = _REPO.match(line)
        if heading:
            name = heading.group(1)
            if real and name not in real:
                continue        # a prose heading; keep attributing to the repo above
            flush()
            current = name
            seen_repos.add(current)
            body = []
            continue
        stack = _STACK.match(line)
        if stack:
            body.append(stack.group(1))
        elif line.strip().startswith(("-", "*", ">")) or line.strip().startswith("**"):
            body.append(line)
    flush()
    return evidence, len(seen_repos)


def build(projects: Path | None = None, cv: Path | None = None) -> Inventory:
    """The whole inventory: portfolio first, CV filling what it cannot show."""
    evidence, repos = read_portfolio(projects)
    inv = Inventory(evidence=evidence, repos=repos)

    cv_text, cv_path = read_cv(cv)
    inv.cv_path, inv.cv_chars = cv_path, len(cv_text)
    for skill in skills.found_in(cv_text):
        where = inv.evidence.setdefault(skill, [])
        # "CV" goes last so a repository is always cited first — code beats a
        # claim in any conversation that follows.
        if "CV" not in where:
            where.append("CV")
    return inv
