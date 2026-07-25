"""
Evaluation report data model and serialisation.

An ``EvaluationReport`` is the final output of a RAGAS evaluation run.
It can be serialised to:
  - JSON  — machine-readable, suitable for CI pipelines
  - Markdown — human-readable, suitable for PR comments and dashboards

All text fields in per-sample data are redacted using the shared
redaction utility before being written to any report.

Usage::

    report = runner.evaluate(samples)
    report.save(output_dir="evaluation_reports", fmt="both")
    print(report.to_markdown())
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

# Score below which a sample is flagged as "failed" / needing investigation
_FAILURE_THRESHOLD = 0.5


@dataclass
class SampleResult:
    """Per-sample scores and metadata."""

    question: str
    answer: str
    scores: dict[str, float] = field(default_factory=dict)
    ground_truth: str | None = None
    retrieved_contexts: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def mean_score(self) -> float:
        """Average of all metric scores for this sample."""
        if not self.scores:
            return 0.0
        return sum(self.scores.values()) / len(self.scores)

    @property
    def is_failed(self) -> bool:
        """True if any individual metric is below the failure threshold."""
        return any(v < _FAILURE_THRESHOLD for v in self.scores.values())

    def to_dict(self) -> dict[str, Any]:
        """Return a redacted, JSON-serialisable dict."""
        return {
            "question": redact(self.question),
            "answer": redact(self.answer),
            "ground_truth": redact(self.ground_truth) if self.ground_truth else None,
            "retrieved_contexts": [redact(c) for c in self.retrieved_contexts],
            "scores": self.scores,
            "mean_score": round(self.mean_score, 4),
            "failed": self.is_failed,
            "metadata": redact(self.metadata),
        }


@dataclass
class EvaluationReport:
    """Full evaluation report: aggregate scores + per-sample breakdown.

    Attributes:
        dataset_name:      Name / label of the evaluated dataset.
        metric_names:      Ordered list of metric names that were computed.
        aggregate_scores:  Mean score per metric across all valid samples.
        sample_results:    Per-sample ``SampleResult`` objects.
        total_samples:     Total number of samples attempted.
        failed_samples:    Samples that were skipped / invalid.
        elapsed_seconds:   Wall-clock time for the evaluation run.
        evaluated_at:      ISO-8601 timestamp of when evaluation ran.
    """

    dataset_name: str
    metric_names: list[str]
    aggregate_scores: dict[str, float]
    sample_results: list[SampleResult]
    total_samples: int
    failed_samples: int
    elapsed_seconds: float
    evaluated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
    )

    # ── Derived properties ────────────────────────────────────────────────────

    @property
    def evaluated_samples(self) -> int:
        return self.total_samples - self.failed_samples

    @property
    def failed_sample_results(self) -> list[SampleResult]:
        return [s for s in self.sample_results if s.is_failed]

    @property
    def mean_overall_score(self) -> float:
        if not self.aggregate_scores:
            return 0.0
        return sum(self.aggregate_scores.values()) / len(self.aggregate_scores)

    # ── Retrieval statistics ──────────────────────────────────────────────────

    @property
    def retrieval_stats(self) -> dict[str, Any]:
        """Summary statistics about retrieved contexts across all samples."""
        if not self.sample_results:
            return {"avg_contexts": 0.0, "min_contexts": 0, "max_contexts": 0}
        counts = [len(s.retrieved_contexts) for s in self.sample_results]
        return {
            "avg_contexts": round(sum(counts) / len(counts), 2),
            "min_contexts": min(counts),
            "max_contexts": max(counts),
            "samples_with_no_context": sum(1 for c in counts if c == 0),
        }

    # ── Summary ───────────────────────────────────────────────────────────────

    def summary(self) -> str:
        """Return a compact one-line summary suitable for CLI output."""
        score_str = ", ".join(f"{k}={v:.3f}" for k, v in self.aggregate_scores.items())
        return (
            f"[{self.dataset_name}] "
            f"{self.evaluated_samples}/{self.total_samples} samples | "
            f"{score_str} | "
            f"{self.elapsed_seconds:.1f}s"
        )

    # ── Serialisation ─────────────────────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        """Return a fully redacted, JSON-serialisable dict."""
        return {
            "dataset_name": self.dataset_name,
            "evaluated_at": self.evaluated_at,
            "total_samples": self.total_samples,
            "evaluated_samples": self.evaluated_samples,
            "failed_samples": self.failed_samples,
            "elapsed_seconds": round(self.elapsed_seconds, 3),
            "metric_names": self.metric_names,
            "aggregate_scores": {
                k: round(v, 4) for k, v in self.aggregate_scores.items()
            },
            "mean_overall_score": round(self.mean_overall_score, 4),
            "retrieval_stats": self.retrieval_stats,
            "failed_sample_count": len(self.failed_sample_results),
            "sample_results": [s.to_dict() for s in self.sample_results],
        }

    def to_json(self, indent: int = 2) -> str:
        """Serialise the report to a JSON string (redacted)."""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

    def to_markdown(self) -> str:
        """Serialise the report to a Markdown string (redacted).

        Sections:
          - Header with metadata
          - Overall scores table
          - Retrieval statistics
          - Per-question scores table (top 20)
          - Failed samples (if any)
        """
        lines: list[str] = []

        # ── Header ──────────────────────────────────────────────────────────
        lines += [
            f"# RAGAS Evaluation Report — {self.dataset_name}",
            "",
            f"- **Evaluated at**: {self.evaluated_at}",
            f"- **Total samples**: {self.total_samples}",
            f"- **Evaluated samples**: {self.evaluated_samples}",
            f"- **Failed / skipped samples**: {self.failed_samples}",
            f"- **Elapsed time**: {self.elapsed_seconds:.2f}s",
            "",
        ]

        # ── Overall scores table ─────────────────────────────────────────────
        if self.aggregate_scores:
            lines += [
                "## Overall Scores",
                "",
                "| Metric | Score |",
                "|--------|-------|",
            ]
            for metric, score in self.aggregate_scores.items():
                bar = _score_bar(score)
                lines.append(f"| {metric} | {score:.4f} {bar} |")
            lines += [
                f"| **Mean Overall** | **{self.mean_overall_score:.4f}** |",
                "",
            ]
        else:
            lines += ["## Overall Scores", "", "_No scores computed._", ""]

        # ── Retrieval statistics ─────────────────────────────────────────────
        rs = self.retrieval_stats
        lines += [
            "## Retrieval Statistics",
            "",
            f"- Average contexts per question: **{rs.get('avg_contexts', 0):.2f}**",
            f"- Min contexts: {rs.get('min_contexts', 0)}",
            f"- Max contexts: {rs.get('max_contexts', 0)}",
            f"- Questions with no context: {rs.get('samples_with_no_context', 0)}",
            "",
        ]

        # ── Per-question scores table ────────────────────────────────────────
        if self.sample_results:
            lines += [
                "## Per-Question Scores",
                "",
            ]
            header_cols = ["#", "Question (truncated)"] + self.metric_names + ["Mean"]
            lines.append("| " + " | ".join(header_cols) + " |")
            lines.append("| " + " | ".join(["---"] * len(header_cols)) + " |")
            for idx, sr in enumerate(self.sample_results[:20], start=1):
                question_short = redact(sr.question)[:60].replace("|", "\\|")
                row = [str(idx), question_short]
                for m in self.metric_names:
                    v = sr.scores.get(m)
                    row.append(f"{v:.3f}" if v is not None else "—")
                row.append(f"{sr.mean_score:.3f}")
                lines.append("| " + " | ".join(row) + " |")
            if len(self.sample_results) > 20:
                lines.append(
                    f"| … | _and {len(self.sample_results) - 20} more_ | "
                    + " | ".join([""] * (len(self.metric_names) + 1))
                    + " |"
                )
            lines.append("")

        # ── Failed samples ───────────────────────────────────────────────────
        failed = self.failed_sample_results
        if failed:
            lines += [
                f"## Failed Samples ({len(failed)})",
                "",
                f"> Samples where any metric scored below {_FAILURE_THRESHOLD:.2f}.",
                "",
            ]
            for idx, sr in enumerate(failed[:10], start=1):
                q = redact(sr.question)[:80].replace("|", "\\|")
                score_str = ", ".join(f"{k}={v:.3f}" for k, v in sr.scores.items())
                lines.append(f"{idx}. **Q**: {q}  ")
                lines.append(f"   **Scores**: {score_str}")
                lines.append("")
            if len(failed) > 10:
                lines.append(f"_…and {len(failed) - 10} more failed samples._")
                lines.append("")

        return "\n".join(lines)

    # ── Persistence ───────────────────────────────────────────────────────────

    def save(
        self,
        output_dir: str | Path = "evaluation_reports",
        fmt: str = "both",
        stem: str | None = None,
    ) -> dict[str, Path]:
        """Write the report to disk.

        Args:
            output_dir: Directory to write files into (created if needed).
            fmt:        "json", "markdown", or "both".
            stem:       Filename stem (without extension).
                        Defaults to ``"<dataset_name>_<timestamp>"``.

        Returns:
            Dict mapping format name ("json" / "markdown") to the written Path.
        """
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)

        ts = self.evaluated_at.replace(":", "").replace("-", "").replace("Z", "")
        safe_name = self.dataset_name.replace(" ", "_").replace("/", "-")
        file_stem = stem or f"{safe_name}_{ts}"

        written: dict[str, Path] = {}

        if fmt in ("json", "both"):
            json_path = out / f"{file_stem}.json"
            json_path.write_text(self.to_json(), encoding="utf-8")
            written["json"] = json_path
            LOGGER.info("eval_report_written", extra={"path": str(json_path)})

        if fmt in ("markdown", "both"):
            md_path = out / f"{file_stem}.md"
            md_path.write_text(self.to_markdown(), encoding="utf-8")
            written["markdown"] = md_path
            LOGGER.info("eval_report_written", extra={"path": str(md_path)})

        return written


# ── Internal helpers ──────────────────────────────────────────────────────────


def _score_bar(score: float, width: int = 10) -> str:
    """Return a compact ASCII bar for a 0-1 score."""
    filled = round(score * width)
    return "█" * filled + "░" * (width - filled)
