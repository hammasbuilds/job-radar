"""What to match jobs against. The one file that is meant to be edited.

Everything else in this project is about the market. This is the half about
you, and it is deliberately a plain dictionary rather than a parsed CV: a CV
parser is a project of its own, and the terms that matter for matching are a
short list that a person can read and correct in a minute.

`core` terms are weighted most heavily and `tools` least, because a job asking
for PyTorch and computer vision is a different match from one that merely
mentions Docker. They only rank; the gates are `ACCEPT_LEVELS`, `MAX_YEARS`
and `TARGET_ROLES`.
"""

from __future__ import annotations

# Which seniority levels to keep. Entry to mid: assistant, junior, associate,
# and titles with no level word at all — "AI Engineer" rather than "Senior AI
# Engineer".
#
# `mid` is in the list and it matters most: a title with no level word is the
# common case and is exactly what is wanted. Absence of a word is not a
# missing qualification.
#
# Senior, staff, lead, principal and executive titles are rejected rather than
# ranked down, because they are most of what gets advertised — roughly four
# senior postings for every junior one — and they score identically on every
# other filter, so a ranking penalty just buries the junior roles further
# down the same list. They land in the Killed tab with their level shown, so
# the decision is visible and reversible.
#
# Add "senior" here to see them again.
ACCEPT_LEVELS = ("assistant", "junior", "associate", "mid")

# Fresher to three years. A posting demanding more than this is rejected even
# when its title reads junior — "AI Engineer" that asks for eight years in
# paragraph three is a senior role that forgot to say so in its title.
#
# A posting that states no requirement at all is kept: most do not state one,
# and silence is not a demand.
MAX_YEARS = 3

# The roles actually being looked for. A posting whose *title* is one of these
# is the thing; everything else is a stack match that happens to mention ML.
#
# Kept separate from `core` below and weighted far more heavily, because the
# first version scored a "Senior Marketing Data Analyst" at 0.59 on the words
# "llm", "agent" and "benchmark" appearing somewhere in its body. Matching the
# vocabulary of a field is not the same as being a job in it.
TARGET_ROLES = [
    "ai engineer",
    "ml engineer",
    "dl engineer",
    "ml/dl engineer",
    "machine learning engineer",
    "deep learning engineer",
    "generative ai engineer",
    "gen ai engineer",
    "genai engineer",
    "computer vision engineer",
    "llm engineer",
    "llm evaluation engineer",
    "agentic ai engineer",
    "agentic engineer",
    "ai agent engineer",
    "agent engineer",
    # Research titles. "All researchers" was asked for explicitly, so these
    # are first-class targets rather than near-misses - in AI the research
    # title is often the same job as the engineering one. Bare "researcher" is
    # not here: it matched "UX Researcher" and "Market Researcher". An AI
    # researcher title names its field, and the compositional rule in fit.py
    # catches the ones this list does not.
    "research scientist",
    "ai researcher",
    "ml researcher",
    "machine learning researcher",
    "research fellow",
    "postdoctoral researcher",
    "postdoc",
    # The same jobs under the titles companies actually post them as.
    "machine learning scientist",
    "applied scientist",
    # Absent from the first version, which killed every one of them: 340
    # Pakistan postings and 183 Gulf ones were fetched and "Data Scientist"
    # matched nothing at all.
    "data scientist",
    "data science engineer",
    "ai automation engineer",
    "ai automation specialist",
    "ai developer",
    "machine learning developer",
    "research engineer",
    "applied ai engineer",
    "ai/ml engineer",
    "ml research engineer",
    "nlp engineer",
    "mlops engineer",
    "ai research engineer",
    "founding ai engineer",
    "founding engineer, ai",
    "member of technical staff",
]

PROFILE = {
    "roles": TARGET_ROLES,
    # The work itself — drawn from the portfolio's actual centre of gravity:
    # classical CV (43 projects), NLP (23), ML (20), agents (11), RAG (8).
    "core": [
        "machine learning", "deep learning", "computer vision", "nlp",
        "natural language processing", "llm", "large language model",
        "pytorch", "tensorflow", "python", "ml engineer", "research engineer",
        "applied scientist", "mlops",
    ],
    "domains": [
        "rag", "retrieval augmented generation", "retrieval-augmented",
        "agent", "agentic", "multimodal", "diffusion", "gan",
        "image generation", "segmentation", "object detection", "ocr",
        "vision language", "vlm", "fine-tuning", "finetuning", "lora",
        "embeddings", "vector database", "transformers", "inference",
        "evaluation", "benchmark", "hallucination", "prompt engineering",
        "speech", "asr", "time series", "recommendation",
    ],
    "tools": [
        "huggingface", "hugging face", "langchain", "langgraph", "llamaindex",
        "fastapi", "docker", "kubernetes", "sqlite", "postgres", "aws", "gcp",
        "azure", "ollama", "vllm", "onnx", "opencv", "numpy", "pandas",
        "scikit-learn", "sklearn", "mlflow", "weights & biases", "wandb",
        "triton", "ray", "spark", "airflow", "git",
    ],
}

# Your UTC offset. The timezone badge measures a 09:00-18:00 day here against
# the employer's; PKT is UTC+5 with no daylight saving.
TZ_OFFSET = 5.0
