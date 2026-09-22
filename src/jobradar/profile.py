"""What to match jobs against. The one file that is meant to be edited.

Everything else in this project is about the market. This is the half about
you, and it is deliberately a plain dictionary rather than a parsed CV: a CV
parser is a project of its own, and the terms that matter for matching are a
short list that a person can read and correct in a minute.

`core` terms are weighted most heavily and `tools` least, because a job asking
for PyTorch and computer vision is a different match from one that merely
mentions Docker.

**`years` is a stated assumption, not a fact read from anywhere.** It only
affects the penalty for postings demanding far more experience, so setting it
wrong makes the ranking worse and kills nothing.
"""

from __future__ import annotations

# Years of professional experience to compare a posting's stated requirement
# against. Change this. Nothing else in the project depends on it.
YEARS = 3

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
    # are first-class targets rather than near-misses — in AI the research
    # title is often the same job as the engineering one.
    "research scientist",
    "ai researcher",
    "ml researcher",
    "machine learning researcher",
    "research fellow",
    "postdoctoral researcher",
    "postdoc",
    "researcher",
    # The same jobs under the titles companies actually post them as.
    "machine learning scientist",
    "applied scientist",
    "research engineer",
    "applied ai engineer",
    "ai/ml engineer",
    "ml research engineer",
    "vision engineer",
    "nlp engineer",
    "mlops engineer",
    "ai research engineer",
    "founding ai engineer",
    "founding engineer, ai",
    "member of technical staff",
]

PROFILE = {
    "years": YEARS,
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

# Where you are, which decides the timezone arithmetic and why the work
# authorisation filter matters at all.
BASED_IN = "Pakistan"
TZ_OFFSET = 5.0   # PKT, UTC+5, no DST
