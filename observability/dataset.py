"""
LangSmith evaluation dataset builder.

This module lets you create LangSmith datasets from real conversation traces
for offline evaluation and regression testing.

Features:
  - ``DatasetBuilder`` accumulates examples in memory.
  - ``DatasetBuilder.to_langsmith()`` pushes them to LangSmith (when enabled).
  - ``DatasetBuilder.to_jsonl()`` writes a local JSONL file (always available).
  - Each example carries: question, expected_answer, actual_answer,
    retrieved_context, metadata.
  - Sensitive data is redacted before examples are stored or transmitted.

Usage::

    from observability.dataset import DatasetBuilder

    builder = DatasetBuilder(dataset_name="banking-faq-eval")
    builder.add_example(
        question="What happens if I lose my card?",
        actual_answer=state["reply"],
        retrieved_context=[hit["text"] for hit in hits],
        metadata={"session_id": sid, "intent": "search"},
    )
    builder.to_jsonl("eval_dataset.jsonl")
    builder.to_langsmith()   # no-op if tracing is disabled
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from observability.redaction import redact

LOGGER = logging.getLogger(__name__)


@dataclass
class DatasetExample:
    """A single question-answer pair for LangSmith evaluation."""

    question: str
    actual_answer: str
    expected_answer: str | None = None
    retrieved_context: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
    )

    def to_dict(self) -> dict:
        """Return a JSON-serialisable dict with all sensitive data redacted."""
        return {
            "question": redact(self.question),
            "actual_answer": redact(self.actual_answer),
            "expected_answer": (
                redact(self.expected_answer) if self.expected_answer else None
            ),
            "retrieved_context": [redact(c) for c in self.retrieved_context],
            "metadata": redact(self.metadata),
            "created_at": self.created_at,
        }

    def to_langsmith_format(self) -> dict:
        """Return the LangSmith dataset example format.

        LangSmith expects::
            {"inputs": {"question": "..."}, "outputs": {"answer": "..."}}
        """
        d = self.to_dict()
        return {
            "inputs": {
                "question": d["question"],
                "context": d["retrieved_context"],
            },
            "outputs": {
                "answer": d["actual_answer"],
                "expected": d["expected_answer"],
            },
            "metadata": d["metadata"],
        }


class DatasetBuilder:
    """Accumulates evaluation examples and pushes them to LangSmith or JSONL.

    Args:
        dataset_name: Human-readable name for the LangSmith dataset.
        description:  Optional description shown in the LangSmith UI.
    """

    def __init__(
        self,
        dataset_name: str = "bank-assistant-eval",
        description: str = "Evaluation dataset for the Autonomous Bank Assistant.",
    ) -> None:
        self.dataset_name = dataset_name
        self.description = description
        self._examples: list[DatasetExample] = []

    def add_example(
        self,
        question: str,
        actual_answer: str,
        *,
        expected_answer: str | None = None,
        retrieved_context: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> DatasetBuilder:
        """Append a new example.

        Args:
            question:          The user's question or input.
            actual_answer:     The assistant's actual reply.
            expected_answer:   Gold-standard answer for evaluation (optional).
            retrieved_context: RAG chunks that informed the answer (optional).
            metadata:          Arbitrary key-value metadata (will be redacted).

        Returns:
            self  (fluent interface)
        """
        example = DatasetExample(
            question=question,
            actual_answer=actual_answer,
            expected_answer=expected_answer,
            retrieved_context=retrieved_context or [],
            metadata=metadata or {},
        )
        self._examples.append(example)
        LOGGER.debug("dataset_example_added", extra={"total": len(self._examples)})
        return self

    @property
    def examples(self) -> list[DatasetExample]:
        """Read-only view of accumulated examples."""
        return list(self._examples)

    def __len__(self) -> int:
        return len(self._examples)

    def to_jsonl(self, path: str | Path) -> Path:
        """Write examples to a local JSONL file.

        Each line is a JSON object in LangSmith input/output format.
        Sensitive data is redacted.

        Args:
            path: File path (will be created/overwritten).

        Returns:
            Resolved Path of the written file.
        """
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("w", encoding="utf-8") as fh:
            for ex in self._examples:
                fh.write(json.dumps(ex.to_langsmith_format(), ensure_ascii=False))
                fh.write("\n")
        LOGGER.info(
            "dataset_written_to_jsonl",
            extra={"path": str(out), "examples": len(self._examples)},
        )
        return out

    def to_langsmith(self, *, overwrite: bool = False) -> str | None:
        """Push examples to LangSmith as a named dataset.

        This is a no-op (returns None) when:
          - LangSmith tracing is disabled.
          - The langsmith package is not installed.
          - No examples have been added.

        Args:
            overwrite: If True, delete and recreate the dataset. Otherwise,
                       append to an existing dataset of the same name.

        Returns:
            The LangSmith dataset ID string, or None on failure/disabled.
        """
        from observability.langsmith_config import is_tracing_enabled

        if not is_tracing_enabled():
            LOGGER.debug("dataset_push_skipped: tracing disabled")
            return None

        if not self._examples:
            LOGGER.debug("dataset_push_skipped: no examples")
            return None

        try:
            from langsmith import Client

            client = Client()

            # Get or create the dataset.
            existing = list(client.list_datasets(dataset_name=self.dataset_name))
            if existing and overwrite:
                client.delete_dataset(dataset_id=existing[0].id)
                existing = []

            if existing:
                dataset = existing[0]
            else:
                dataset = client.create_dataset(
                    self.dataset_name,
                    description=self.description,
                )

            # Push examples.
            ls_examples = [ex.to_langsmith_format() for ex in self._examples]
            client.create_examples(
                inputs=[e["inputs"] for e in ls_examples],
                outputs=[e["outputs"] for e in ls_examples],
                metadata=[e["metadata"] for e in ls_examples],
                dataset_id=dataset.id,
            )

            LOGGER.info(
                "dataset_pushed_to_langsmith",
                extra={
                    "dataset": self.dataset_name,
                    "id": str(dataset.id),
                    "examples": len(self._examples),
                },
            )
            return str(dataset.id)
        except ImportError:
            LOGGER.warning("dataset_push_failed: langsmith not installed")
            return None
        except Exception:
            LOGGER.exception("dataset_push_failed")
            return None

    def clear(self) -> None:
        """Remove all accumulated examples."""
        self._examples.clear()
