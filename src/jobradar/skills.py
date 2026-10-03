"""A skill vocabulary, and what counts as the same skill.

Matching a job description against a CV falls apart on synonyms. A posting
says "K8s", the CV says "Kubernetes"; a posting says "torch", the portfolio
says "PyTorch". Without a canonical form the gap report tells you to learn
something you already know, which is worse than saying nothing.

So each entry is `canonical: (aliases…)` and everything is compared in
canonical form. The list is deliberately finite and readable rather than
scraped from anywhere: a vocabulary you can audit is one whose mistakes you
can find.

Matching is whole-word. Substring matching makes "R" match "React", "Go"
match "Django" and "AI" match "chain", which inflates every score.
"""

from __future__ import annotations

import re

SKILLS: dict[str, tuple[str, ...]] = {
    # --- languages ---
    "Python": ("python", "python3"),
    # No trailing \b: a word boundary cannot follow "++", because both the
    # plus and whatever comes after it are non-word characters. With the
    # wrapper applied, "C/C++ experience" matched C and not C++.
    "C++": (r"\bc\+\+", r"\bcpp\b"),
    # One-letter and common-word names need a programming context or they
    # match ordinary prose. "Go" alone found a match in "go live", and
    # reported Go as a missing requirement for an AI research role; "C" and
    # "R" are worse. Each must appear beside a word that makes it a language.
    "C": (r"\bc\b(?=\s*(?:/|,|and|or)?\s*(?:c\+\+|programming|language))",
          r"\bc/c\+\+"),
    "JavaScript": ("javascript", r"\bjs\b", "es6", "node\\.?js"),
    "TypeScript": ("typescript", r"\bts\b(?!\s*=)"),
    "Java": (r"\bjava\b(?!script)",),
    "Go": ("golang",
           r"\bgo\b(?=\s*(?:programming|language|developer|engineer|\)|,\s*rust))",
           r"(?:in|with|using)\s+go\b"),
    "Rust": ("rust",),
    "SQL": ("sql",),
    "Bash": ("bash", "shell scripting"),
    "Scala": ("scala",),
    # Fixed-width lookbehind only — Python's re rejects a variable one, which
    # is why this is written as two forward-looking alternatives instead.
    "R": (r"\br\b(?=\s*(?:/|,|and|or)?\s*(?:python|statistical|programming|shiny))",
          r"(?:python|matlab|sas)\s*(?:,|/|and|or)\s*r\b"),

    # --- ML frameworks ---
    "PyTorch": ("pytorch", "torch"),
    "TensorFlow": ("tensorflow", "\\btf\\b", "keras"),
    "JAX": ("jax", "flax"),
    "scikit-learn": ("scikit-learn", "sklearn", "scikit learn"),
    "Hugging Face": ("hugging ?face", "transformers library", "\\bhf\\b"),
    "NumPy": ("numpy",),
    "pandas": ("pandas",),
    "OpenCV": ("opencv", "cv2"),
    "spaCy": ("spacy",),
    "NLTK": ("nltk",),
    "XGBoost": ("xgboost", "lightgbm", "catboost"),

    # --- LLM / GenAI ---
    "LLMs": ("llm", "large language model", "foundation model"),
    "RAG": ("rag", "retrieval[- ]augmented"),
    "LangChain": ("langchain",),
    "LangGraph": ("langgraph",),
    "LlamaIndex": ("llamaindex", "llama[- ]index"),
    "Fine-tuning": ("fine[- ]tun", "lora", "qlora", "peft", "sft"),
    "Prompt engineering": ("prompt engineering", "prompting"),
    "Embeddings": ("embedding", "sentence[- ]transformer"),
    "Vector databases": ("vector (?:db|database|store)", "pinecone", "weaviate",
                         "qdrant", "chroma", "faiss", "pgvector", "milvus"),
    "Agents": ("agentic", "\\bagent\\b", "multi[- ]agent", "tool use"),
    "MCP": ("mcp", "model context protocol"),
    "Evaluation": ("evaluation", "\\beval\\b", "benchmark", "rubric", "rlhf"),
    "Diffusion models": ("diffusion", "stable diffusion", "latent diffusion"),
    "GANs": ("\\bgan\\b", "generative adversarial"),
    "Ollama": ("ollama", "llama.cpp", "vllm"),
    "OpenAI API": ("openai api", "gpt-4", "gpt4"),
    # Not the bare word "anthropic": every Anthropic posting names its own
    # employer, and each one then "required" the Anthropic API twenty times.
    "Anthropic API": ("anthropic api", "claude api", "anthropic sdk", "claude sdk"),

    # --- CV / NLP tasks ---
    "Computer vision": ("computer vision", "\\bcv\\b(?! ?/)", "image processing"),
    "Object detection": ("object detection", "yolo", "detectron"),
    "Segmentation": ("segmentation", "\\bunet\\b", "\\bsam\\b"),
    "OCR": ("\\bocr\\b", "tesseract"),
    "NLP": ("nlp", "natural language processing"),
    "Speech": ("speech recognition", "\\basr\\b", "whisper", "text[- ]to[- ]speech"),
    "Time series": ("time series", "forecasting"),
    "Recommenders": ("recommend(?:er|ation) system",),

    # --- engineering ---
    "FastAPI": ("fastapi",),
    "Flask": ("flask",),
    "Django": ("django",),
    "REST APIs": ("rest api", "restful"),
    "Docker": ("docker", "container"),
    "Kubernetes": ("kubernetes", "k8s"),
    "AWS": ("\\baws\\b", "amazon web services", "sagemaker", "\\bs3\\b", "ec2"),
    "GCP": ("\\bgcp\\b", "google cloud", "vertex ai", "bigquery"),
    "Azure": ("azure",),
    "CI/CD": ("ci/cd", "continuous integration", "github actions", "jenkins"),
    "Terraform": ("terraform", "infrastructure as code"),
    "MLOps": ("mlops", "mlflow", "weights ?& ?biases", "wandb", "model serving",
              "model registry"),
    "Airflow": ("airflow", "dagster", "prefect"),
    "Spark": ("spark", "pyspark", "databricks"),
    "Kafka": ("kafka", "event streaming"),
    "PostgreSQL": ("postgres", "postgresql"),
    "Redis": ("redis",),
    "MongoDB": ("mongodb", "mongo"),
    "SQLite": ("sqlite",),
    "Git": ("\\bgit\\b", "version control"),
    "Testing": ("pytest", "unit test", "test coverage"),
    "Linux": ("linux", "unix"),

    # --- ways of working ---
    # Not the bare word "research", which is in half of all AI postings as a
    # department name and made "Research" the top skill of every gap report.
    "Research": ("publications?", "published (?:papers|research)", "phd", "mphil",
                 "research experience", "peer[- ]reviewed", "first[- ]author"),
    "Data annotation": ("annotation", "labeling", "labelling", "inter[- ]annotator"),
    "Technical writing": ("technical writing", "documentation"),
}

# Compiled once. Word-boundary anchored unless the alias supplies its own,
# because a substring match here silently inflates every match percentage.
_PATTERNS: dict[str, re.Pattern] = {
    canonical: re.compile(
        "|".join(a if a.startswith("\\b") or "\\b" in a else rf"\b{a}\b"
                 for a in aliases),
        re.I,
    )
    for canonical, aliases in SKILLS.items()
}


def found_in(text: str) -> set[str]:
    """Every skill named in this text, in canonical form."""
    if not text:
        return set()
    return {name for name, pattern in _PATTERNS.items() if pattern.search(text)}


def mentions(text: str, skill: str) -> int:
    pattern = _PATTERNS.get(skill)
    return len(pattern.findall(text)) if pattern and text else 0
