"""Which of the six title families a role belongs to, and whether it is the engineering or the
research version of it.

The six families are the titles asked for: ML/DL, machine learning, deep learning, computer
vision, generative AI and agentic AI - each as an engineer and as a researcher. A target role
outside them (an NLP engineer, an applied scientist, a data scientist) is still kept and lands
in "Other AI", so the family filter narrows the list rather than silently shrinking it.

The order matters and runs most specific first: "Computer Vision ML Engineer" is computer
vision, "ML/DL Engineer" is ML/DL rather than machine learning, "Generative AI Agent Engineer"
is agentic (the agent is the job; generative is the material).
"""

from __future__ import annotations

import re

ML_DL = "ML/DL"
ML = "Machine Learning"
DL = "Deep Learning"
CV = "Computer Vision"
GENAI = "Generative AI"
AGENTIC = "Agentic AI"
OTHER = "Other AI"
PROGRAM = "Fellowship / programme"
PUBLIC = "Pakistan public sector (CS/IT/AI)"

FAMILIES = (ML_DL, ML, DL, CV, GENAI, AGENTIC)
ALL = (*FAMILIES, OTHER, PROGRAM, PUBLIC)

# Government, university and state-enterprise employers in Pakistan, and the computing titles
# they advertise. Their posts are rarely titled "ML engineer" ("Assistant Director (IT)",
# "Lecturer Computer Science"), so this lane has its own title rule.
_PUBLIC_EMPLOYER = re.compile(
    r"\b(?:government|govt|ministry|division|authority|commission|board|council|directorate|"
    r"department|corporation|university|institute|college|academy|cantonment|municipal|"
    r"metropolitan|district|federal|provincial|punjab|sindh|khyber|balochistan|gilgit|"
    r"nadra|paec|suparco|nust|pieas|comsats|wapda|pta|secp|sbp|state bank|nescom|hec|"
    r"higher education|ignite|pitb|kpitb|nitb|pseb|ncai|nastp|pcsir|pakistan science)\b",
    re.I,
)
_COMPUTING = re.compile(
    r"\b(?:it|i\.t\.|ict|information technology|computer|computing|software|developer|"
    r"programmer|data|database|dba|network|system|systems|cyber|web|digital|gis|ai|"
    r"artificial intelligence|machine learning|deep learning|computer vision|robotics|"
    r"cloud|devops|analyst)\b",
    re.I,
)


def is_public_computing(title: str, company: str, source: str = "", tags=()) -> bool:
    """A computing post at a Pakistani public-sector employer."""
    public = source == "njp" or "public sector" in tags or bool(_PUBLIC_EMPLOYER.search(company))
    return public and bool(_COMPUTING.search(title or ""))

ENGINEER = "Engineer"
RESEARCHER = "Researcher"

_RULES = (
    (CV, r"\b(?:computer[- ]vision|cv|vision|perception|image|video|3d|multimodal|vlm)\b"),
    (AGENTIC, r"\b(?:agentic|agents?|autonomous agents?|multi[- ]agent)\b"),
    (GENAI, r"\b(?:generative|gen[- ]?ai|llms?|large language|foundation models?|"
            r"diffusion|genai|prompt)\b"),
    (ML_DL, r"\b(?:ml\s*/\s*dl|ml\s*&\s*dl|ml and dl|machine learning\s*/\s*deep learning)\b"),
    (DL, r"\b(?:deep[- ]learning|dl|neural networks?)\b"),
    (ML, r"\b(?:machine[- ]learning|ml|mlops|applied ml)\b"),
)
_COMPILED = tuple((family, re.compile(pattern, re.I)) for family, pattern in _RULES)

_RESEARCH = re.compile(r"\b(?:research\w*|scientist|postdoc\w*|phd|fellow\w*|scholar\w*)\b",
                       re.I)

# Fellowships, residencies and funded research programmes: the junior route into frontier labs,
# and titled nothing like a job ("Anthropic Fellows Program", "AI Residency 2027").
_PROGRAM = re.compile(
    r"\b(?:fellows?(?:hip)?s?(?: program(?:me)?)?|residency|residents? program|"
    r"scholars? program(?:me)?|research program(?:me)?|summer research|"
    r"research grant|grant program(?:me)?)\b",
    re.I,
)
_AI_CONTEXT = re.compile(
    r"\b(?:a\.?i\.?|ml|machine learning|deep learning|safety|alignment|interpretability|"
    r"llms?|research|computer vision|nlp|robotics)\b",
    re.I,
)


def is_program(title: str, company: str = "") -> bool:
    """A fellowship or residency in AI, whatever its title calls it."""
    if not _PROGRAM.search(title or ""):
        return False
    return bool(_AI_CONTEXT.search(f"{title} {company}"))


def classify(title: str, company: str = "", public: bool = False) -> tuple[str, str]:
    """(family, track) for a title already accepted as a target role, or as a programme."""
    t = title or ""
    track = RESEARCHER if _RESEARCH.search(t) else ENGINEER
    if is_program(t, company):
        return PROGRAM, track
    if public:
        return PUBLIC, track
    for family, pattern in _COMPILED:
        if pattern.search(t):
            return family, track
    return OTHER, track
