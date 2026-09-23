"""How well does this job match, and what is missing?

Shown under a posting when it is opened, because the question a person asks
on seeing a job is not "what is the score" but **"could I get this, and what
would I have to learn?"**

Two rules shape the output.

**A bare percentage is not actionable.** The same discipline as the rest of
this project: every number here comes with the evidence that produced it.
"78% match" tells you nothing; "PyTorch, proven in qlora-finetune-suite;
Kubernetes missing, asked for 4 times" tells you whether to apply and what to
do about it.

**Weight by how hard the posting asks.** A skill named once in a
nice-to-have list is not the same as one named five times and again in the
title. Counting mentions is crude but it is honest, and it is visible.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from . import inventory as inventory_mod
from . import skills

# Sentences that introduce a genuine requirement, as against a wish.
_REQUIRED = re.compile(
    r"(?:required|requirements|must have|you have|you will need|essential|"
    r"we expect|minimum qualifications|qualifications)", re.I
)
_NICE = re.compile(
    r"(?:nice[- ]to[- ]have|bonus|plus|preferred|desirable|advantageous|"
    r"would be great|not required)", re.I
)


@dataclass
class Need:
    """One skill the posting asks for."""

    skill: str
    mentions: int
    in_title: bool
    nice_to_have: bool
    have: bool
    proof: str = ""

    @property
    def weight(self) -> float:
        """How much this skill counts toward the match.

        A title mention is worth a lot, a nice-to-have very little, and
        repetition counts but with diminishing returns — a word repeated
        eight times is not eight times more important than one said twice.
        """
        base = 1.0 + min(self.mentions - 1, 4) * 0.25
        if self.in_title:
            base += 1.5
        if self.nice_to_have:
            base *= 0.35
        return base


@dataclass
class Gap:
    """The whole report for one posting."""

    percent: int
    have: list[Need] = field(default_factory=list)
    missing: list[Need] = field(default_factory=list)
    inventory_size: int = 0
    cv_used: str = ""
    note: str = ""

    # Below this, the percentage is arithmetic on too little. A posting whose
    # text names one skill you happen to have scores 100%, which is the
    # denominator doing the work rather than a match — and the 100% is more
    # misleading than no number at all.
    MIN_SIGNAL = 4

    @property
    def thin(self) -> bool:
        return len(self.have) + len(self.missing) < self.MIN_SIGNAL

    @property
    def verdict(self) -> str:
        """A sentence, because a number alone invites over-reading."""
        if not self.have and not self.missing:
            return "This posting names no recognisable skills — nothing to compare."
        if self.thin:
            named = len(self.have) + len(self.missing)
            return (f"Only {named} recognisable skill"
                    f"{'s' if named != 1 else ''} in this posting — too few to "
                    f"score. Read it yourself.")
        top = self.missing[0].skill if self.missing else ""
        if self.percent >= 75:
            return f"Strong match. {'Only gap: ' + top if top else 'Nothing material missing.'}"
        if self.percent >= 50:
            return f"Worth applying. Biggest gap: {top}." if top else "Worth applying."
        if self.percent >= 30:
            return f"A stretch. You would be learning {top} on the job."
        return "Weak match — most of what they ask for is not in the portfolio."


def _nice_context(text: str, skill: str) -> bool:
    """Is this skill only ever named in a nice-to-have sentence?"""
    pattern = skills._PATTERNS.get(skill)
    if not pattern:
        return False
    for match in pattern.finditer(text):
        # Backwards only. A "nice to have" heading comes *before* the skills
        # it governs, never after — and looking 60 characters forward meant
        # "Python required. Nice-to-have: Kubernetes" marked **Python** as
        # optional, because the later heading fell inside its window.
        window = text[max(0, match.start() - 220):match.start()]
        if _NICE.search(window):
            continue
        return False          # at least one mention is not a nice-to-have
    return True


def analyse(title: str, text: str, inv=None) -> Gap:
    """Compare one posting against the portfolio and CV."""
    inv = inv or inventory_mod.build()
    body = f"{title}\n{text}"
    wanted = skills.found_in(body)

    if not wanted:
        return Gap(percent=0, inventory_size=len(inv.skills), cv_used=inv.cv_path,
                   note="no recognisable skills in the posting")

    needs: list[Need] = []
    for skill in wanted:
        needs.append(
            Need(
                skill=skill,
                mentions=skills.mentions(body, skill),
                in_title=bool(skills.mentions(title, skill)),
                nice_to_have=_nice_context(text, skill),
                have=skill in inv.skills,
                proof=inv.proof(skill),
            )
        )

    total = sum(n.weight for n in needs)
    earned = sum(n.weight for n in needs if n.have)
    percent = round(100 * earned / total) if total else 0

    have = sorted([n for n in needs if n.have], key=lambda n: -n.weight)
    missing = sorted([n for n in needs if not n.have], key=lambda n: -n.weight)

    return Gap(
        percent=percent,
        have=have,
        missing=missing,
        inventory_size=len(inv.skills),
        cv_used=inv.cv_path,
        note="" if inv.cv_chars else "no CV found — portfolio only",
    )


def as_dict(gap: Gap) -> dict:
    return {
        # `thin` rides along so the screen can show the caveat rather than a
        # confident number built on two words.
        "percent": gap.percent,
        "thin": gap.thin,
        "verdict": gap.verdict,
        "note": gap.note,
        "inventory_size": gap.inventory_size,
        "have": [
            {"skill": n.skill, "proof": n.proof, "mentions": n.mentions,
             "in_title": n.in_title, "nice": n.nice_to_have}
            for n in gap.have
        ],
        "missing": [
            {"skill": n.skill, "mentions": n.mentions,
             "in_title": n.in_title, "nice": n.nice_to_have}
            for n in gap.missing
        ],
    }
