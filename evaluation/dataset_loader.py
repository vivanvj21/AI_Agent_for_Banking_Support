"""
Multi-format evaluation dataset loader.

Loads samples from:
  - JSONL  (.jsonl)   — one JSON object per line
  - JSON   (.json)    — a JSON array or a {"samples": [...]} object
  - CSV    (.csv)     — header row + data rows

All three formats also understand the LangSmith export layout produced by
``observability.dataset.DatasetBuilder.to_jsonl()``:

    {"inputs": {"question": "...", "context": [...]},
     "outputs": {"answer": "...", "expected": "..."},
     "metadata": {...}}

as well as a simpler flat layout (used when writing evaluation fixtures):

    {"question": "...", "answer": "...",
     "retrieved_contexts": ["..."],
     "ground_truth": "...", "metadata": {...}}

Sensitive data is redacted using the shared redaction utility before any
sample is stored in memory.

Usage::

    from evaluation.dataset_loader import load_dataset, EvalSample

    samples = load_dataset("eval_data.jsonl")
    # samples : list[EvalSample]
"""

from __future__ import annotations

import csv
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from observability.redaction import redact

LOGGER = logging.getLogger(__name__)


# ── Data model ────────────────────────────────────────────────────────────────


@dataclass
class EvalSample:
    """A single evaluation example.

    Attributes:
        question:           The user question sent to the assistant.
        answer:             The assistant's actual response.
        retrieved_contexts: List of text chunks retrieved by the RAG pipeline.
        ground_truth:       Gold-standard reference answer (optional).
        metadata:           Arbitrary metadata for filtering / reporting.
    """

    question: str
    answer: str
    retrieved_contexts: list[str] = field(default_factory=list)
    ground_truth: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_valid(self) -> bool:
        """Return True if the sample has the minimum required fields."""
        return bool(self.question.strip()) and bool(self.answer.strip())

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable dict (redacted)."""
        return {
            "question": redact(self.question),
            "answer": redact(self.answer),
            "retrieved_contexts": [redact(c) for c in self.retrieved_contexts],
            "ground_truth": redact(self.ground_truth) if self.ground_truth else None,
            "metadata": redact(self.metadata),
        }


# ── Parsers ───────────────────────────────────────────────────────────────────


def _parse_record(record: dict[str, Any]) -> EvalSample | None:
    """Parse one raw record dict into an EvalSample.

    Understands two layouts:
      1. LangSmith export: {"inputs": {...}, "outputs": {...}, "metadata": {...}}
      2. Flat layout:      {"question": ..., "answer": ..., ...}
    """
    try:
        if "inputs" in record and "outputs" in record:
            # LangSmith export format (from DatasetBuilder.to_jsonl)
            inputs = record.get("inputs") or {}
            outputs = record.get("outputs") or {}
            meta = record.get("metadata") or {}

            question = inputs.get("question") or ""
            contexts_raw = (
                inputs.get("context") or inputs.get("retrieved_contexts") or []
            )
            answer = outputs.get("answer") or ""
            ground_truth = (
                outputs.get("expected") or outputs.get("ground_truth") or None
            )
        else:
            # Flat layout
            question = record.get("question") or ""
            answer = (
                record.get("answer")
                or record.get("actual_answer")
                or record.get("response")
                or ""
            )
            contexts_raw = (
                record.get("retrieved_contexts")
                or record.get("contexts")
                or record.get("context")
                or []
            )
            ground_truth = (
                record.get("ground_truth")
                or record.get("expected_answer")
                or record.get("reference")
                or None
            )
            meta = record.get("metadata") or {}

        # contexts_raw can be a list or a single string
        if isinstance(contexts_raw, str):
            contexts = [contexts_raw] if contexts_raw.strip() else []
        elif isinstance(contexts_raw, list):
            contexts = [str(c) for c in contexts_raw if c]
        else:
            contexts = []

        sample = EvalSample(
            question=str(question),
            answer=str(answer),
            retrieved_contexts=contexts,
            ground_truth=str(ground_truth) if ground_truth else None,
            metadata=dict(meta) if isinstance(meta, dict) else {},
        )
        return sample if sample.is_valid() else None
    except Exception:
        LOGGER.debug("parse_record_failed", exc_info=True)
        return None


def _load_jsonl(path: Path) -> list[EvalSample]:
    """Load samples from a JSONL file (one JSON object per line)."""
    samples: list[EvalSample] = []
    with path.open(encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, start=1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                LOGGER.warning("jsonl_parse_error at line %d in %s", lineno, path)
                continue
            sample = _parse_record(record)
            if sample:
                samples.append(sample)
    return samples


def _load_json(path: Path) -> list[EvalSample]:
    """Load samples from a JSON file (array or {"samples": [...]} object)."""
    with path.open(encoding="utf-8") as fh:
        data = json.load(fh)

    if isinstance(data, list):
        records = data
    elif isinstance(data, dict):
        records = data.get("samples") or data.get("examples") or data.get("data") or []
    else:
        LOGGER.warning("json_unexpected_root_type: %s in %s", type(data).__name__, path)
        return []

    samples: list[EvalSample] = []
    for record in records:
        sample = _parse_record(record)
        if sample:
            samples.append(sample)
    return samples


def _load_csv(path: Path) -> list[EvalSample]:
    """Load samples from a CSV file.

    Required columns: ``question``, ``answer``
    Optional columns: ``retrieved_contexts``, ``ground_truth``, ``metadata``

    ``retrieved_contexts`` may be a JSON-encoded list or a pipe-separated string.
    """
    samples: list[EvalSample] = []
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for rownum, row in enumerate(reader, start=2):  # 2 = first data row
            question = row.get("question", "").strip()
            answer = (
                row.get("answer")
                or row.get("actual_answer")
                or row.get("response")
                or ""
            ).strip()

            if not question or not answer:
                LOGGER.debug("csv_skip_row %d: missing question or answer", rownum)
                continue

            # Parse retrieved_contexts — accept JSON list or pipe-separated string
            raw_ctx = row.get("retrieved_contexts") or row.get("contexts") or ""
            if raw_ctx.startswith("["):
                try:
                    contexts = json.loads(raw_ctx)
                except json.JSONDecodeError:
                    contexts = [c.strip() for c in raw_ctx.split("|") if c.strip()]
            else:
                contexts = [c.strip() for c in raw_ctx.split("|") if c.strip()]

            ground_truth = row.get("ground_truth") or row.get("expected_answer") or None

            raw_meta = row.get("metadata") or ""
            try:
                meta = json.loads(raw_meta) if raw_meta.strip().startswith("{") else {}
            except json.JSONDecodeError:
                meta = {}

            samples.append(
                EvalSample(
                    question=question,
                    answer=answer,
                    retrieved_contexts=contexts,
                    ground_truth=ground_truth.strip() if ground_truth else None,
                    metadata=meta,
                )
            )
    return samples


# ── Public API ────────────────────────────────────────────────────────────────

_LOADERS = {
    ".jsonl": _load_jsonl,
    ".ndjson": _load_jsonl,
    ".json": _load_json,
    ".csv": _load_csv,
}


def load_dataset(path: str | Path) -> list[EvalSample]:
    """Load an evaluation dataset from a JSONL, JSON, or CSV file.

    The file format is inferred from the extension.  Both the flat and
    LangSmith export layouts are accepted for JSONL and JSON files.

    Sensitive data in every sample is redacted before the sample is returned.

    Args:
        path: Path to the dataset file.

    Returns:
        List of valid ``EvalSample`` objects.  Invalid or unparseable records
        are skipped with a DEBUG-level log entry.

    Raises:
        FileNotFoundError: if *path* does not exist.
        ValueError:        if the file extension is not supported.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Evaluation dataset not found: {p}")

    suffix = p.suffix.lower()
    loader = _LOADERS.get(suffix)
    if loader is None:
        raise ValueError(
            f"Unsupported file extension {p.suffix!r}. "
            f"Supported: {', '.join(_LOADERS)}"
        )

    samples = loader(p)
    LOGGER.info(
        "eval_dataset_loaded",
        extra={"path": str(p), "samples": len(samples), "format": suffix},
    )
    return samples


def load_from_langsmith(dataset_name: str) -> list[EvalSample]:
    """Pull examples from a named LangSmith dataset.

    Requires LangSmith tracing to be configured (LANGSMITH_API_KEY set).
    Returns an empty list if LangSmith is unavailable or the dataset is empty.

    Args:
        dataset_name: Name of the LangSmith dataset to load.

    Returns:
        List of ``EvalSample`` objects.
    """
    try:
        from langsmith import Client

        client = Client()
        examples = list(client.list_examples(dataset_name=dataset_name))
        if not examples:
            LOGGER.info("langsmith_dataset_empty: %s", dataset_name)
            return []

        samples: list[EvalSample] = []
        for ex in examples:
            record = {
                "inputs": ex.inputs or {},
                "outputs": ex.outputs or {},
                "metadata": {},
            }
            sample = _parse_record(record)
            if sample:
                samples.append(sample)

        LOGGER.info(
            "langsmith_dataset_loaded",
            extra={"dataset_name": dataset_name, "samples": len(samples)},
        )
        return samples
    except ImportError:
        LOGGER.warning("langsmith_not_installed: cannot load dataset %s", dataset_name)
        return []
    except Exception:
        LOGGER.exception("langsmith_dataset_load_failed: %s", dataset_name)
        return []
