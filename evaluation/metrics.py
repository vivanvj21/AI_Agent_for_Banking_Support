"""
RAGAS metric registry and LLM/embedding configuration.

This module provides:
  - ``SUPPORTED_METRICS``    — frozenset of valid metric names.
  - ``get_metrics()``        — instantiate requested RAGAS metric objects.
  - ``build_ragas_llm()``    — create a RAGAS-compatible LLM wrapper for Anthropic.
  - ``build_ragas_embeddings()`` — create RAGAS-compatible embeddings.

Design decisions:
  - All RAGAS imports are lazy (inside functions) so the evaluation package
    can be imported even when ragas is not installed — only calling the
    functions raises ImportError.
  - We use LangChain's Anthropic integration (langchain_anthropic) wrapped
    with RAGAS's LangchainLLMWrapper, which avoids introducing a new LLM
    client into the codebase.
  - Embeddings fall back to RAGAS's built-in HuggingFace embeddings when
    Voyage AI is not configured, so evaluation works offline.

Usage::

    from evaluation.metrics import get_metrics, build_ragas_llm

    llm = build_ragas_llm(model="claude-sonnet-4-5", api_key="sk-ant-...")
    metrics = get_metrics(["faithfulness", "answer_relevancy"], llm=llm)
"""

from __future__ import annotations

import logging
import os
from typing import Any

LOGGER = logging.getLogger(__name__)

# All metrics supported by this pipeline
SUPPORTED_METRICS: frozenset[str] = frozenset(
    {
        "faithfulness",
        "answer_relevancy",
        "context_precision",
        "context_recall",
    }
)


def build_ragas_llm(
    model: str | None = None,
    api_key: str | None = None,
) -> Any:
    """Build a RAGAS-compatible LLM wrapper using Anthropic via LangChain.

    Args:
        model:   Anthropic model name (e.g. "claude-sonnet-4-5").
                 Falls back to EVAL_MODEL → ANTHROPIC_MODEL → claude-sonnet-4-5.
        api_key: Anthropic API key. Falls back to ANTHROPIC_API_KEY env var.

    Returns:
        A ``ragas.llms.LangchainLLMWrapper`` instance.

    Raises:
        ImportError: if ragas or langchain_anthropic is not installed.
        ValueError:  if no API key is available.
    """
    try:
        from langchain_anthropic import ChatAnthropic
        from ragas.llms import LangchainLLMWrapper
    except ImportError as exc:
        raise ImportError(
            "RAGAS evaluation requires additional packages. "
            "Run: pip install ragas langchain-anthropic"
        ) from exc

    resolved_model = (
        model
        or os.environ.get("EVAL_MODEL")
        or os.environ.get("ANTHROPIC_MODEL")
        or "claude-sonnet-4-5"
    )
    resolved_key = api_key or os.environ.get("ANTHROPIC_API_KEY") or ""
    if not resolved_key:
        raise ValueError(
            "ANTHROPIC_API_KEY is required for RAGAS evaluation. "
            "Set it in the environment or pass api_key= explicitly."
        )

    chat_model = ChatAnthropic(
        model=resolved_model,
        anthropic_api_key=resolved_key,  # type: ignore[arg-type]
        temperature=0,  # deterministic for evaluation
        max_tokens=4096,
    )
    return LangchainLLMWrapper(chat_model)


def build_ragas_embeddings(api_key: str | None = None) -> Any:
    """Build RAGAS-compatible embeddings.

    Prefers Voyage AI when VOYAGE_API_KEY is set (same provider as the
    application's RAG pipeline).  Falls back to a lightweight sentence-
    transformers model when Voyage is not available.

    Args:
        api_key: Voyage API key. Falls back to VOYAGE_API_KEY env var.

    Returns:
        A RAGAS-compatible embeddings object.

    Raises:
        ImportError: if ragas is not installed.
    """
    try:
        from ragas.embeddings import LangchainEmbeddingsWrapper
    except ImportError as exc:
        raise ImportError("RAGAS evaluation requires: pip install ragas") from exc

    voyage_key = api_key or os.environ.get("VOYAGE_API_KEY") or ""
    if voyage_key:
        try:
            from langchain_voyageai import VoyageAIEmbeddings

            emb = VoyageAIEmbeddings(
                voyage_api_key=voyage_key,
                model="voyage-3",
            )
            LOGGER.debug("ragas_embeddings: using voyage-3")
            return LangchainEmbeddingsWrapper(emb)
        except ImportError:
            LOGGER.debug("langchain_voyageai not installed, falling back")

    # Fall back to OpenAI-compatible text-embedding-3-small via langchain if
    # the openai key is present, otherwise use the RAGAS default which uses
    # a local sentence-transformers model (no API key needed).
    try:
        # Use the default RAGAS embeddings (HuggingFace sentence-transformers)
        # which require no API key and work fully offline.
        from ragas.embeddings import (
            BaseRagasEmbeddings,  # noqa: F401
            HuggingfaceEmbeddings,
        )

        LOGGER.debug("ragas_embeddings: using HuggingfaceEmbeddings (offline)")
        return HuggingfaceEmbeddings()
    except (ImportError, AttributeError):
        # Very old or unusual ragas build — return None and let RAGAS use its
        # own default.
        LOGGER.debug("ragas_embeddings: using ragas built-in default")
        return None


def get_metrics(
    metric_names: list[str],
    llm: Any = None,
    embeddings: Any = None,
) -> list[Any]:
    """Instantiate RAGAS metric objects for the requested metric names.

    Args:
        metric_names: Names from ``SUPPORTED_METRICS``.
        llm:          Optional pre-built RAGAS LLM wrapper.  If None, metrics
                      will use RAGAS's own default LLM (not recommended for
                      Anthropic-only setups).
        embeddings:   Optional pre-built RAGAS embeddings wrapper.

    Returns:
        List of instantiated RAGAS metric objects.

    Raises:
        ImportError: if ragas is not installed.
        ValueError:  if any requested metric name is not in SUPPORTED_METRICS.
    """
    unknown = set(metric_names) - SUPPORTED_METRICS
    if unknown:
        raise ValueError(
            f"Unknown metrics: {sorted(unknown)}. "
            f"Supported: {sorted(SUPPORTED_METRICS)}"
        )

    try:
        from ragas.metrics import (
            AnswerRelevancy,
            ContextPrecision,
            ContextRecall,
            Faithfulness,
        )
    except ImportError as exc:
        raise ImportError("RAGAS evaluation requires: pip install ragas") from exc

    _metric_classes = {
        "faithfulness": Faithfulness,
        "answer_relevancy": AnswerRelevancy,
        "context_precision": ContextPrecision,
        "context_recall": ContextRecall,
    }

    instantiated: list[Any] = []
    for name in metric_names:
        cls = _metric_classes[name]
        # Inject the LLM and embeddings if provided, otherwise use RAGAS defaults
        try:
            kwargs: dict[str, Any] = {}
            if llm is not None:
                kwargs["llm"] = llm
            if embeddings is not None and name in ("answer_relevancy",):
                kwargs["embeddings"] = embeddings
            metric = cls(**kwargs)  # type: ignore[call-arg]
        except TypeError:
            # Some metric constructors don't accept all kwargs — fall back
            metric = cls()  # type: ignore[call-arg]
        instantiated.append(metric)

    return instantiated
