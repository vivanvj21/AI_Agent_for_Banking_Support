"""
RAGAS evaluation package for the Autonomous Bank Assistant.

This package provides automated evaluation of the RAG retrieval and answer
quality using the RAGAS framework.  It is completely independent of the
runtime inference path — evaluating a dataset never invokes the live LangGraph
agents or writes to any production database.

Public surface::

    from evaluation import EvalConfig, get_eval_config
    from evaluation.dataset_loader import load_dataset, EvalSample
    from evaluation.ragas_runner import RagasRunner
    from evaluation.report import EvaluationReport

RAGAS is an optional dependency.  If it is not installed, every function in
this package raises a clear ``ImportError`` with installation instructions
rather than crashing with an opaque traceback.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class EvalConfig:
    """Immutable evaluation configuration sourced from environment variables.

    All values are optional — sensible defaults allow the pipeline to run
    without any extra configuration beyond what the application already needs.
    """

    # LLM used by RAGAS metrics (faithfulness, answer_relevancy, …)
    eval_model: str
    # Anthropic API key (reused from application config)
    anthropic_api_key: str | None
    # How many samples to send to the LLM in one RAGAS batch
    batch_size: int
    # Where to write JSON / Markdown evaluation reports
    output_dir: Path
    # Which metrics to run  (subset of: faithfulness, answer_relevancy,
    # context_precision, context_recall)
    metrics: list[str] = field(default_factory=list)


def get_eval_config() -> EvalConfig:
    """Read evaluation configuration from environment variables.

    Environment variables:
        EVAL_MODEL       – Anthropic model for RAGAS LLM calls.
                           Defaults to ANTHROPIC_MODEL or claude-sonnet-4-5.
        EVAL_BATCH_SIZE  – Number of samples per RAGAS batch. Default 10.
        EVAL_OUTPUT_DIR  – Directory for report files. Default "evaluation_reports".
        EVAL_METRICS     – Comma-separated metric names. Default: all four.
        ANTHROPIC_API_KEY – Reused from application environment.
    """
    model = (
        os.environ.get("EVAL_MODEL")
        or os.environ.get("ANTHROPIC_MODEL")
        or "claude-sonnet-4-5"
    )
    api_key = os.environ.get("ANTHROPIC_API_KEY") or None
    batch_size = int(os.environ.get("EVAL_BATCH_SIZE") or "10")
    output_dir = Path(os.environ.get("EVAL_OUTPUT_DIR") or "evaluation_reports")

    default_metrics = [
        "faithfulness",
        "answer_relevancy",
        "context_precision",
        "context_recall",
    ]
    metrics_env = os.environ.get("EVAL_METRICS", "").strip()
    metrics = [
        m.strip() for m in metrics_env.split(",") if m.strip()
    ] or default_metrics

    return EvalConfig(
        eval_model=model,
        anthropic_api_key=api_key,
        batch_size=batch_size,
        output_dir=output_dir,
        metrics=metrics,
    )


def ragas_available() -> bool:
    """Return True if the ragas package is importable."""
    import importlib.util

    return importlib.util.find_spec("ragas") is not None


__all__ = ["EvalConfig", "get_eval_config", "ragas_available"]
