"""
RAGAS evaluation runner.

Evaluates one sample, a batch, or an entire dataset using the RAGAS
framework and returns an ``EvaluationReport``.

The runner is completely stateless — it reads configuration from
``EvalConfig``, runs RAGAS, and returns results.  It never writes to any
database or modifies application state.

Usage::

    from evaluation import get_eval_config
    from evaluation.dataset_loader import load_dataset
    from evaluation.ragas_runner import RagasRunner

    config = get_eval_config()
    runner = RagasRunner(config)
    samples = load_dataset("eval_data.jsonl")
    report = runner.evaluate(samples)
    print(report.summary())
"""

from __future__ import annotations

import logging
import time
from typing import Any

from evaluation import EvalConfig, ragas_available
from evaluation.dataset_loader import EvalSample
from evaluation.report import EvaluationReport, SampleResult

LOGGER = logging.getLogger(__name__)


def _require_ragas() -> None:
    """Raise a clear ImportError when ragas is not installed."""
    if not ragas_available():
        raise ImportError(
            "RAGAS is not installed. Run:\n"
            "  pip install ragas langchain-anthropic\n\n"
            "Then set ANTHROPIC_API_KEY and optionally EVAL_MODEL."
        )


def _samples_to_ragas_dataset(samples: list[EvalSample]) -> Any:
    """Convert EvalSample list to a RAGAS EvaluationDataset (v0.2+ API).

    Falls back to a HuggingFace ``datasets.Dataset`` for RAGAS v0.1.x.
    """
    try:
        # RAGAS 0.2+ API
        from ragas import EvaluationDataset, SingleTurnSample

        ragas_samples = []
        for s in samples:
            ragas_samples.append(
                SingleTurnSample(
                    user_input=s.question,
                    response=s.answer,
                    retrieved_contexts=s.retrieved_contexts or [],
                    reference=s.ground_truth or "",
                )
            )
        return EvaluationDataset(samples=ragas_samples)
    except ImportError:
        pass

    try:
        # RAGAS 0.1.x fallback — uses HuggingFace datasets
        from datasets import Dataset as HFDataset

        data = {
            "question": [s.question for s in samples],
            "answer": [s.answer for s in samples],
            "contexts": [s.retrieved_contexts or [] for s in samples],
            "ground_truth": [s.ground_truth or "" for s in samples],
        }
        return HFDataset.from_dict(data)
    except ImportError as exc:
        raise ImportError(
            "Neither RAGAS 0.2+ EvaluationDataset nor HuggingFace datasets "
            "is available. Run: pip install ragas"
        ) from exc


def _extract_scores(result: Any, metric_names: list[str]) -> dict[str, float]:
    """Extract per-metric scores from a RAGAS result object.

    Handles both RAGAS 0.2+ (Result object) and 0.1.x (dict-like) APIs.
    """
    scores: dict[str, float] = {}

    # RAGAS 0.2+ returns a Result with a .to_pandas() or .__getitem__ interface
    try:
        import pandas as pd  # noqa: F401

        df = result.to_pandas()
        for name in metric_names:
            col = name
            if col in df.columns:
                val = df[col].mean()
                scores[name] = float(val) if not __import__("math").isnan(val) else 0.0
        return scores
    except (AttributeError, Exception):
        LOGGER.debug("ragas_scores_pandas_fallback", exc_info=True)

    # RAGAS 0.1.x — result behaves like a dict
    try:
        for name in metric_names:
            if name in result:
                scores[name] = float(result[name])
        return scores
    except (TypeError, Exception):
        LOGGER.debug("ragas_scores_dict_fallback", exc_info=True)

    return scores


def _extract_per_sample_scores(
    result: Any, samples: list[EvalSample], metric_names: list[str]
) -> list[SampleResult]:
    """Extract per-sample scores from a RAGAS result."""
    sample_results: list[SampleResult] = []

    try:
        df = result.to_pandas()
        for i, sample in enumerate(samples):
            per_metric: dict[str, float] = {}
            for name in metric_names:
                if name in df.columns:
                    val = df[name].iloc[i]
                    import math

                    per_metric[name] = float(val) if not math.isnan(val) else 0.0
            sample_results.append(
                SampleResult(
                    question=sample.question,
                    answer=sample.answer,
                    ground_truth=sample.ground_truth,
                    retrieved_contexts=sample.retrieved_contexts,
                    scores=per_metric,
                    metadata=sample.metadata,
                )
            )
        return sample_results
    except (AttributeError, Exception):  # noqa: BLE001
        # Fall back: no per-sample breakdown available
        return [
            SampleResult(
                question=s.question,
                answer=s.answer,
                ground_truth=s.ground_truth,
                retrieved_contexts=s.retrieved_contexts,
                scores={},
                metadata=s.metadata,
            )
            for s in samples
        ]


class RagasRunner:
    """Runs RAGAS evaluation against a list of EvalSample objects.

    Args:
        config: Evaluation configuration (model, batch_size, metrics, …).
                Use ``get_eval_config()`` to build from environment variables.
        dataset_name: Human-readable label for this evaluation run.
    """

    def __init__(
        self, config: EvalConfig, dataset_name: str = "bank-assistant"
    ) -> None:
        self.config = config
        self.dataset_name = dataset_name
        self._llm: Any = None
        self._embeddings: Any = None
        self._metrics_cache: list[Any] | None = None

    def _get_llm(self) -> Any:
        if self._llm is None:
            from evaluation.metrics import build_ragas_llm

            self._llm = build_ragas_llm(
                model=self.config.eval_model,
                api_key=self.config.anthropic_api_key,
            )
        return self._llm

    def _get_metrics(self) -> list[Any]:
        if self._metrics_cache is None:
            from evaluation.metrics import build_ragas_embeddings, get_metrics

            llm = self._get_llm()
            emb = build_ragas_embeddings()
            self._metrics_cache = get_metrics(
                self.config.metrics, llm=llm, embeddings=emb
            )
        return self._metrics_cache

    def evaluate(
        self,
        samples: list[EvalSample],
        *,
        raise_on_empty: bool = False,
    ) -> EvaluationReport:
        """Evaluate a list of samples and return an EvaluationReport.

        Args:
            samples:        List of ``EvalSample`` objects to evaluate.
            raise_on_empty: If True, raise ValueError when samples is empty.
                            If False (default), return a report with zero samples.

        Returns:
            An ``EvaluationReport`` with aggregate and per-sample scores.

        Raises:
            ImportError: if ragas is not installed.
            ValueError:  if samples is empty and raise_on_empty=True.
        """
        _require_ragas()

        if not samples:
            if raise_on_empty:
                raise ValueError("Cannot evaluate an empty dataset.")
            LOGGER.warning("ragas_runner: no samples to evaluate")
            return EvaluationReport(
                dataset_name=self.dataset_name,
                metric_names=self.config.metrics,
                aggregate_scores={},
                sample_results=[],
                total_samples=0,
                failed_samples=0,
                elapsed_seconds=0.0,
            )

        LOGGER.info(
            "ragas_eval_start",
            extra={"samples": len(samples), "metrics": self.config.metrics},
        )
        start = time.perf_counter()

        # Validate: drop invalid samples but record them as failures
        valid = [s for s in samples if s.is_valid()]
        failed_count = len(samples) - len(valid)
        if failed_count:
            LOGGER.warning("ragas_eval: %d invalid samples skipped", failed_count)

        try:
            from ragas import evaluate as ragas_evaluate

            ragas_dataset = _samples_to_ragas_dataset(valid)
            metrics = self._get_metrics()

            ragas_result = ragas_evaluate(
                dataset=ragas_dataset,
                metrics=metrics,
            )

            elapsed = time.perf_counter() - start
            aggregate = _extract_scores(ragas_result, self.config.metrics)
            per_sample = _extract_per_sample_scores(
                ragas_result, valid, self.config.metrics
            )

            LOGGER.info(
                "ragas_eval_complete",
                extra={"elapsed_s": round(elapsed, 2), "scores": aggregate},
            )
            return EvaluationReport(
                dataset_name=self.dataset_name,
                metric_names=self.config.metrics,
                aggregate_scores=aggregate,
                sample_results=per_sample,
                total_samples=len(samples),
                failed_samples=failed_count,
                elapsed_seconds=elapsed,
            )
        except Exception as exc:
            elapsed = time.perf_counter() - start
            LOGGER.exception("ragas_eval_failed")
            raise RuntimeError(f"RAGAS evaluation failed: {exc}") from exc

    def evaluate_single(self, sample: EvalSample) -> EvaluationReport:
        """Evaluate a single EvalSample.

        Convenience wrapper around ``evaluate([sample])``.
        """
        return self.evaluate([sample])
