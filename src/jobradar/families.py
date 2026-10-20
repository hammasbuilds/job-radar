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
DATA_WORK = "AI data work (contract)"

FAMILIES = (ML_DL, ML, DL, CV, GENAI, AGENTIC)
ALL = (*FAMILIES, OTHER, PROGRAM, PUBLIC, DATA_WORK)

# Training and checking AI models for pay - the Mercor / DataAnnotation kind of work: "AI Data
# Trainer", "Mathematics Model Evaluator", "LLM Quality Analyst", "Thai AI Data Annotator".
# fit.py vetoes "trainer" (a corporate trainer is not the job there), so this lane has its own
# rule: a data-work noun, next to an AI word.
_DATA_NOUN = re.compile(
    r"\b(?:trainers?|tutors?|annotators?|annotation|label(?:l)?ers?|label(?:l)?ing|raters?|"
    r"evaluators?|red[- ]teamers?|quality analysts?|response writers?|prompt writers?|"
    # Askable's "AI Coding Tasks": paid per task, remote from anywhere.
    r"(?:coding|writing|reasoning) tasks?)\b",
    re.I,
)
_DATA_AI = re.compile(
    r"\b(?:a\.?i\.?|llms?|models?|ai data|chatbots?|gen[- ]?ai|machine learning|rlhf)\b", re.I)


def is_data_work(title: str) -> bool:
    """Paid work training or checking AI models, whatever the title calls it."""
    t = title or ""
    return bool(_DATA_NOUN.search(t) and _DATA_AI.search(t))

# Government, university and state-enterprise employers in Pakistan, and the computing titles
# they advertise. Their posts are rarely titled "ML engineer" ("Assistant Director (IT)",
# "Lecturer Computer Science"), so this lane has its own title rule.
# A bare "university" or "institute" is not public: Northern University Nowshera is private and
# was listed as public sector. Universities count when the name says they are the state's or
# they are among the federal and provincial public ones named here.
_PUBLIC_EMPLOYER = re.compile(
    r"\b(?:government|govt|ministry|division|authority|commission|board|council|directorate|"
    r"department|corporation|cantonment|municipal|public sector university|"
    r"university of (?:the punjab|karachi|peshawar|sindh|balochistan|engineering and technology|"
    r"agriculture|education|health sciences|veterinary)|uet|quaid[- ]i[- ]azam|"
    r"bahauddin zakariya|allama iqbal open|virtual university|air university|"
    r"bahria university|national university of (?:sciences and technology|modern languages|"
    r"technology)|federal urdu|islamia university|"
    r"metropolitan|district|federal|provincial|punjab|sindh|khyber|balochistan|gilgit|"
    r"nadra|paec|suparco|nust|pieas|comsats|wapda|pta|secp|sbp|state bank|nescom|hec|"
    r"higher education|ignite|pitb|kpitb|nitb|pseb|ncai|nastp|pcsir|pakistan science)\b",
    re.I,
)
_COMPUTING = re.compile(
    r"\b(?:it|i\.t\.|ict|information technology|computer|computing|software|developer|"
    r"programmer|data|database|dba|network|system|systems|cyber|web|digital|gis|ai|"
    r"artificial intelligence|machine learning|deep learning|computer vision|robotics|"
    r"cloud|devops|data analyst|systems analyst|business intelligence)\b",
    re.I,
)


def is_public_computing(title: str, company: str, source: str = "", tags=()) -> bool:
    """A computing post at a Pakistani public-sector employer."""
    public = source == "njp" or "public sector" in tags or bool(_PUBLIC_EMPLOYER.search(company))
    return public and bool(_COMPUTING.search(title or ""))

ENGINEER = "Engineer"
RESEARCHER = "Researcher"

_RULES = (
    # Making images or video is generative work even though it names images: Black Forest Labs'
    # "Image / Video Generation" was filed Computer Vision and a GenAI filter missed it.
    (GENAI, r"\b(?:image|video|audio|speech|music|3d)(?:\s*/\s*\w+)?\s+generation\b|"
            r"\btext[- ]to[- ](?:image|video|speech|3d)\b"),
    (CV,r"\b(?:computer[- ]vision|cv|vision|perception|image|video|3d|multimodal|vlm)\b"),
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
    r"llms?|computer vision|nlp|robotics|generative|neural|data science)\b",
    re.I,
)


def is_program(title: str, company: str = "") -> bool:
    """A fellowship or residency in AI, whatever its title calls it."""
    if not _PROGRAM.search(title or ""):
        return False
    return bool(_AI_CONTEXT.search(f"{title} {company}"))


def classify(title: str, company: str = "", public: bool = False,
             data_work: bool = False) -> tuple[str, str]:
    """(family, track) for a title already accepted as a target role, or as a programme.

    `data_work` is for a title accepted only by the data-work lane: an ML engineer on an
    annotation team is still an ML engineer, so the caller decides, not the words alone.
    """
    t = title or ""
    track = RESEARCHER if _RESEARCH.search(t) else ENGINEER
    if is_program(t, company):
        return PROGRAM, track
    if public:
        return PUBLIC, track
    if data_work:
        return DATA_WORK, track
    for family, pattern in _COMPILED:
        if pattern.search(t):
            return family, track
    return OTHER, track
