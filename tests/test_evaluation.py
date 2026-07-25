"""
Tests for the RAGAS evaluation package (evaluation/).

These tests NEVER call real RAGAS or Anthropic APIs.  All RAGAS / LangChain
imports are mocked so the suite runs in any environment — including CI
where ragas is not installed.

Tests cover:
  1. EvalConfig and get_eval_config()
  2. ragas_available() graceful degradation
  3. EvalSample data model and validation
  4. Dataset loading — JSONL, JSON, CSV, LangSmith
  5. Metrics registry and builders (mocked)
  6. RagasRunner (mocked evaluate)
  7. EvaluationReport serialisation — JSON, Markdown, save()
  8. SampleResult scoring and failure detection
  9. CLI --evaluate-rag argument parsing
  10. Redaction integration in reports / samples
"""

from __future__ import annotations

import csv
import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure project root is on the path.
sys.path.insert(0, str(Path(__file__).parent.parent))


# ---------------------------------------------------------------------------
# 1. EvalConfig and get_eval_config()
# ---------------------------------------------------------------------------


class TestEvalConfig:
    """Tests for evaluation.__init__.EvalConfig and get_eval_config()."""

    def teardown_method(self):
        for var in (
            "EVAL_MODEL",
            "EVAL_BATCH_SIZE",
            "EVAL_OUTPUT_DIR",
            "EVAL_METRICS",
            "ANTHROPIC_API_KEY",
            "ANTHROPIC_MODEL",
        ):
            os.environ.pop(var, None)

    def test_default_config(self, monkeypatch):
        monkeypatch.delenv("EVAL_MODEL", raising=False)
        monkeypatch.delenv("EVAL_BATCH_SIZE", raising=False)
        monkeypatch.delenv("EVAL_OUTPUT_DIR", raising=False)
        monkeypatch.delenv("EVAL_METRICS", raising=False)
        monkeypatch.delenv("ANTHROPIC_MODEL", raising=False)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        from evaluation import get_eval_config

        cfg = get_eval_config()
        assert cfg.eval_model == "claude-sonnet-4-5"
        assert cfg.batch_size == 10
        assert cfg.output_dir == Path("evaluation_reports")
        assert cfg.anthropic_api_key is None
        assert len(cfg.metrics) == 4
        assert "faithfulness" in cfg.metrics
        assert "answer_relevancy" in cfg.metrics
        assert "context_precision" in cfg.metrics
        assert "context_recall" in cfg.metrics

    def test_custom_model_from_env(self, monkeypatch):
        monkeypatch.setenv("EVAL_MODEL", "claude-haiku-3")
        from evaluation import get_eval_config

        cfg = get_eval_config()
        assert cfg.eval_model == "claude-haiku-3"

    def test_custom_model_falls_back_to_anthropic_model(self, monkeypatch):
        monkeypatch.delenv("EVAL_MODEL", raising=False)
        monkeypatch.setenv("ANTHROPIC_MODEL", "claude-opus-4")
        from evaluation import get_eval_config

        cfg = get_eval_config()
        assert cfg.eval_model == "claude-opus-4"

    def test_custom_batch_size(self, monkeypatch):
        monkeypatch.setenv("EVAL_BATCH_SIZE", "25")
        from evaluation import get_eval_config

        cfg = get_eval_config()
        assert cfg.batch_size == 25

    def test_custom_output_dir(self, monkeypatch):
        monkeypatch.setenv("EVAL_OUTPUT_DIR", "/tmp/my_reports")
        from evaluation import get_eval_config

        cfg = get_eval_config()
        assert cfg.output_dir == Path("/tmp/my_reports")

    def test_custom_metrics(self, monkeypatch):
        monkeypatch.setenv("EVAL_METRICS", "faithfulness, context_recall")
        from evaluation import get_eval_config

        cfg = get_eval_config()
        assert cfg.metrics == ["faithfulness", "context_recall"]

    def test_api_key_from_env(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-key")
        from evaluation import get_eval_config

        cfg = get_eval_config()
        assert cfg.anthropic_api_key == "sk-ant-test-key"

    def test_config_is_frozen(self, monkeypatch):
        monkeypatch.delenv("EVAL_MODEL", raising=False)
        from evaluation import get_eval_config

        cfg = get_eval_config()
        with pytest.raises(AttributeError):
            cfg.eval_model = "should-not-work"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# 2. ragas_available()
# ---------------------------------------------------------------------------


class TestRagasAvailable:
    """Tests for evaluation.ragas_available()."""

    def test_ragas_available_returns_bool(self):
        from evaluation import ragas_available

        result = ragas_available()
        assert isinstance(result, bool)

    def test_ragas_available_false_when_missing(self, monkeypatch):
        """When ragas is not importable, ragas_available() returns False."""
        import importlib.util

        original_find_spec = importlib.util.find_spec

        def _fake_find_spec(name, *args, **kwargs):
            if name == "ragas":
                return None
            return original_find_spec(name, *args, **kwargs)

        monkeypatch.setattr(importlib.util, "find_spec", _fake_find_spec)
        from evaluation import ragas_available

        assert ragas_available() is False


# ---------------------------------------------------------------------------
# 3. EvalSample data model
# ---------------------------------------------------------------------------


class TestEvalSample:
    """Tests for evaluation.dataset_loader.EvalSample."""

    def test_valid_sample(self):
        from evaluation.dataset_loader import EvalSample

        s = EvalSample(question="Q?", answer="A.")
        assert s.is_valid()

    def test_invalid_sample_empty_question(self):
        from evaluation.dataset_loader import EvalSample

        s = EvalSample(question="", answer="A.")
        assert not s.is_valid()

    def test_invalid_sample_empty_answer(self):
        from evaluation.dataset_loader import EvalSample

        s = EvalSample(question="Q?", answer="  ")
        assert not s.is_valid()

    def test_sample_with_full_fields(self):
        from evaluation.dataset_loader import EvalSample

        s = EvalSample(
            question="What is my balance?",
            answer="Your balance is $500.",
            retrieved_contexts=["Account A2001 has balance $500."],
            ground_truth="The balance for A2001 is $500.",
            metadata={"session_id": "s123"},
        )
        assert s.is_valid()
        assert len(s.retrieved_contexts) == 1
        assert s.ground_truth is not None
        assert s.metadata["session_id"] == "s123"

    def test_to_dict_redacts_sensitive_data(self):
        from evaluation.dataset_loader import EvalSample

        s = EvalSample(
            question="My PIN is 1234, what is my balance?",
            answer="Balance is $100",
            metadata={"pin": "5678"},
        )
        d = s.to_dict()
        assert "1234" not in d["question"]
        assert d["metadata"]["pin"] == "[REDACTED]"

    def test_to_dict_with_none_ground_truth(self):
        from evaluation.dataset_loader import EvalSample

        s = EvalSample(question="Q?", answer="A.")
        d = s.to_dict()
        assert d["ground_truth"] is None

    def test_defaults(self):
        from evaluation.dataset_loader import EvalSample

        s = EvalSample(question="Q", answer="A")
        assert s.retrieved_contexts == []
        assert s.ground_truth is None
        assert s.metadata == {}


# ---------------------------------------------------------------------------
# 4. Dataset loading — JSONL, JSON, CSV
# ---------------------------------------------------------------------------


class TestDatasetLoaderFile:
    """Tests for evaluation.dataset_loader.load_dataset()."""

    def test_load_jsonl_flat_layout(self, tmp_path):
        from evaluation.dataset_loader import load_dataset

        p = tmp_path / "data.jsonl"
        records = [
            {"question": "Q1?", "answer": "A1."},
            {"question": "Q2?", "answer": "A2.", "ground_truth": "ref2"},
        ]
        p.write_text("\n".join(json.dumps(r) for r in records), encoding="utf-8")

        samples = load_dataset(str(p))
        assert len(samples) == 2
        assert samples[0].question == "Q1?"
        assert samples[1].ground_truth == "ref2"

    def test_load_jsonl_langsmith_layout(self, tmp_path):
        from evaluation.dataset_loader import load_dataset

        p = tmp_path / "data.jsonl"
        record = {
            "inputs": {"question": "What is my balance?", "context": ["ctx1"]},
            "outputs": {"answer": "Your balance is $500.", "expected": "Balance: $500"},
            "metadata": {"intent": "account"},
        }
        p.write_text(json.dumps(record), encoding="utf-8")

        samples = load_dataset(str(p))
        assert len(samples) == 1
        assert samples[0].question == "What is my balance?"
        assert samples[0].retrieved_contexts == ["ctx1"]
        assert samples[0].ground_truth == "Balance: $500"

    def test_load_jsonl_skips_invalid_lines(self, tmp_path):
        from evaluation.dataset_loader import load_dataset

        p = tmp_path / "data.jsonl"
        lines = [
            json.dumps({"question": "Q?", "answer": "A."}),
            "NOT VALID JSON",
            json.dumps({"question": "", "answer": "missing Q"}),
            "# comment line",
            json.dumps({"question": "Q2?", "answer": "A2."}),
        ]
        p.write_text("\n".join(lines), encoding="utf-8")

        samples = load_dataset(str(p))
        assert len(samples) == 2

    def test_load_json_array(self, tmp_path):
        from evaluation.dataset_loader import load_dataset

        p = tmp_path / "data.json"
        data = [
            {"question": "Q1?", "answer": "A1."},
            {"question": "Q2?", "answer": "A2.", "retrieved_contexts": ["c1", "c2"]},
        ]
        p.write_text(json.dumps(data), encoding="utf-8")

        samples = load_dataset(str(p))
        assert len(samples) == 2
        assert len(samples[1].retrieved_contexts) == 2

    def test_load_json_object_with_samples_key(self, tmp_path):
        from evaluation.dataset_loader import load_dataset

        p = tmp_path / "data.json"
        data = {"samples": [{"question": "Q?", "answer": "A."}]}
        p.write_text(json.dumps(data), encoding="utf-8")

        samples = load_dataset(str(p))
        assert len(samples) == 1

    def test_load_json_object_with_examples_key(self, tmp_path):
        from evaluation.dataset_loader import load_dataset

        p = tmp_path / "data.json"
        data = {"examples": [{"question": "Q?", "answer": "A."}]}
        p.write_text(json.dumps(data), encoding="utf-8")

        samples = load_dataset(str(p))
        assert len(samples) == 1

    def test_load_csv(self, tmp_path):
        from evaluation.dataset_loader import load_dataset

        p = tmp_path / "data.csv"
        with p.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(
                fh, fieldnames=["question", "answer", "ground_truth"]
            )
            writer.writeheader()
            writer.writerow(
                {"question": "Q1?", "answer": "A1.", "ground_truth": "ref1"}
            )
            writer.writerow({"question": "Q2?", "answer": "A2.", "ground_truth": ""})

        samples = load_dataset(str(p))
        assert len(samples) == 2
        assert samples[0].ground_truth == "ref1"

    def test_load_csv_pipe_separated_contexts(self, tmp_path):
        from evaluation.dataset_loader import load_dataset

        p = tmp_path / "data.csv"
        with p.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(
                fh, fieldnames=["question", "answer", "retrieved_contexts"]
            )
            writer.writeheader()
            writer.writerow(
                {
                    "question": "Q?",
                    "answer": "A.",
                    "retrieved_contexts": "ctx1|ctx2|ctx3",
                }
            )

        samples = load_dataset(str(p))
        assert len(samples) == 1
        assert samples[0].retrieved_contexts == ["ctx1", "ctx2", "ctx3"]

    def test_load_csv_json_contexts(self, tmp_path):
        from evaluation.dataset_loader import load_dataset

        p = tmp_path / "data.csv"
        with p.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(
                fh, fieldnames=["question", "answer", "retrieved_contexts"]
            )
            writer.writeheader()
            writer.writerow(
                {
                    "question": "Q?",
                    "answer": "A.",
                    "retrieved_contexts": json.dumps(["c1", "c2"]),
                }
            )

        samples = load_dataset(str(p))
        assert len(samples) == 1
        assert samples[0].retrieved_contexts == ["c1", "c2"]

    def test_file_not_found_raises(self):
        from evaluation.dataset_loader import load_dataset

        with pytest.raises(FileNotFoundError):
            load_dataset("/nonexistent/path/data.jsonl")

    def test_unsupported_extension_raises(self, tmp_path):
        from evaluation.dataset_loader import load_dataset

        p = tmp_path / "data.parquet"
        p.write_text("dummy", encoding="utf-8")

        with pytest.raises(ValueError, match="Unsupported file extension"):
            load_dataset(str(p))

    def test_load_ndjson_alias(self, tmp_path):
        """'.ndjson' extension should work as a JSONL alias."""
        from evaluation.dataset_loader import load_dataset

        p = tmp_path / "data.ndjson"
        p.write_text(json.dumps({"question": "Q?", "answer": "A."}), encoding="utf-8")

        samples = load_dataset(str(p))
        assert len(samples) == 1

    def test_alternative_field_names(self, tmp_path):
        """Test alternative field names: actual_answer, response, contexts, reference."""
        from evaluation.dataset_loader import load_dataset

        p = tmp_path / "data.jsonl"
        record = {
            "question": "Q?",
            "response": "A.",
            "contexts": ["c1"],
            "reference": "ref",
        }
        p.write_text(json.dumps(record), encoding="utf-8")

        samples = load_dataset(str(p))
        assert len(samples) == 1
        assert samples[0].answer == "A."
        assert samples[0].retrieved_contexts == ["c1"]
        assert samples[0].ground_truth == "ref"

    def test_string_context_becomes_list(self, tmp_path):
        """A single string context should become a one-element list."""
        from evaluation.dataset_loader import load_dataset

        p = tmp_path / "data.jsonl"
        record = {"question": "Q?", "answer": "A.", "context": "single context"}
        p.write_text(json.dumps(record), encoding="utf-8")

        samples = load_dataset(str(p))
        assert samples[0].retrieved_contexts == ["single context"]


# ---------------------------------------------------------------------------
# 5. Dataset loading — LangSmith
# ---------------------------------------------------------------------------


class TestDatasetLoaderLangSmith:
    """Tests for evaluation.dataset_loader.load_from_langsmith()."""

    def test_langsmith_not_installed_returns_empty(self):
        from evaluation.dataset_loader import load_from_langsmith

        with patch.dict("sys.modules", {"langsmith": None}):
            result = load_from_langsmith("test-dataset")
        assert result == []

    def test_langsmith_empty_dataset_returns_empty(self):
        mock_client = MagicMock()
        mock_client.list_examples.return_value = []

        mock_langsmith = MagicMock()
        mock_langsmith.Client.return_value = mock_client

        with patch.dict("sys.modules", {"langsmith": mock_langsmith}):
            from evaluation.dataset_loader import load_from_langsmith

            result = load_from_langsmith("empty-dataset")
        assert result == []

    def test_langsmith_loads_examples(self):
        mock_example = MagicMock()
        mock_example.inputs = {"question": "Q?", "context": ["ctx"]}
        mock_example.outputs = {"answer": "A.", "expected": "ref"}

        mock_client = MagicMock()
        mock_client.list_examples.return_value = [mock_example]

        mock_langsmith = MagicMock()
        mock_langsmith.Client.return_value = mock_client

        with patch.dict("sys.modules", {"langsmith": mock_langsmith}):
            from evaluation.dataset_loader import load_from_langsmith

            result = load_from_langsmith("test-dataset")

        assert len(result) == 1
        assert result[0].question == "Q?"
        assert result[0].retrieved_contexts == ["ctx"]

    def test_langsmith_api_error_returns_empty(self):
        mock_langsmith = MagicMock()
        mock_langsmith.Client.side_effect = RuntimeError("API error")

        with patch.dict("sys.modules", {"langsmith": mock_langsmith}):
            from evaluation.dataset_loader import load_from_langsmith

            result = load_from_langsmith("broken-dataset")
        assert result == []


# ---------------------------------------------------------------------------
# 6. Metrics registry (mocked)
# ---------------------------------------------------------------------------


class TestMetrics:
    """Tests for evaluation.metrics (with mocked RAGAS imports)."""

    def test_supported_metrics_is_frozenset(self):
        from evaluation.metrics import SUPPORTED_METRICS

        assert isinstance(SUPPORTED_METRICS, frozenset)
        assert "faithfulness" in SUPPORTED_METRICS
        assert "answer_relevancy" in SUPPORTED_METRICS
        assert "context_precision" in SUPPORTED_METRICS
        assert "context_recall" in SUPPORTED_METRICS

    def test_unknown_metric_raises_value_error(self):
        from evaluation.metrics import get_metrics

        # Mock the ragas import inside get_metrics so it doesn't fail
        mock_ragas_metrics = MagicMock()
        with patch.dict(
            "sys.modules",
            {
                "ragas": MagicMock(),
                "ragas.metrics": mock_ragas_metrics,
            },
        ), pytest.raises(ValueError, match="Unknown metrics"):
            get_metrics(["nonexistent_metric"])

    def test_build_ragas_llm_missing_key_raises(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

        mock_chat = MagicMock()
        mock_wrapper = MagicMock()

        with patch.dict(
            "sys.modules",
            {
                "langchain_anthropic": MagicMock(ChatAnthropic=mock_chat),
                "ragas": MagicMock(),
                "ragas.llms": MagicMock(LangchainLLMWrapper=mock_wrapper),
            },
        ):
            from evaluation.metrics import build_ragas_llm

            with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
                build_ragas_llm(api_key="")

    def test_build_ragas_llm_success(self, monkeypatch):
        mock_chat_cls = MagicMock()
        mock_chat_instance = MagicMock()
        mock_chat_cls.return_value = mock_chat_instance
        mock_wrapper_cls = MagicMock()
        mock_wrapper_instance = MagicMock()
        mock_wrapper_cls.return_value = mock_wrapper_instance

        with patch.dict(
            "sys.modules",
            {
                "langchain_anthropic": MagicMock(ChatAnthropic=mock_chat_cls),
                "ragas": MagicMock(),
                "ragas.llms": MagicMock(LangchainLLMWrapper=mock_wrapper_cls),
            },
        ):
            from evaluation.metrics import build_ragas_llm

            result = build_ragas_llm(model="claude-sonnet-4-5", api_key="sk-ant-test")

        assert result is mock_wrapper_instance
        mock_chat_cls.assert_called_once()
        mock_wrapper_cls.assert_called_once_with(mock_chat_instance)

    def test_build_ragas_llm_missing_packages_raises(self):
        with patch.dict(
            "sys.modules",
            {
                "langchain_anthropic": None,
                "ragas": MagicMock(),
                "ragas.llms": None,
            },
        ):
            from evaluation.metrics import build_ragas_llm

            with pytest.raises(ImportError, match="pip install ragas"):
                build_ragas_llm(api_key="sk-ant-test")

    def test_get_metrics_with_mocked_ragas(self):
        mock_faithfulness = MagicMock()
        mock_answer_rel = MagicMock()
        mock_ctx_prec = MagicMock()
        mock_ctx_recall = MagicMock()

        mock_ragas_metrics = MagicMock()
        mock_ragas_metrics.Faithfulness = MagicMock(return_value=mock_faithfulness)
        mock_ragas_metrics.AnswerRelevancy = MagicMock(return_value=mock_answer_rel)
        mock_ragas_metrics.ContextPrecision = MagicMock(return_value=mock_ctx_prec)
        mock_ragas_metrics.ContextRecall = MagicMock(return_value=mock_ctx_recall)

        with patch.dict(
            "sys.modules",
            {
                "ragas": MagicMock(),
                "ragas.metrics": mock_ragas_metrics,
            },
        ):
            from evaluation.metrics import get_metrics

            metrics = get_metrics(
                ["faithfulness", "context_precision"],
                llm=MagicMock(),
            )

        assert len(metrics) == 2


# ---------------------------------------------------------------------------
# 7. SampleResult
# ---------------------------------------------------------------------------


class TestSampleResult:
    """Tests for evaluation.report.SampleResult."""

    def test_mean_score_with_scores(self):
        from evaluation.report import SampleResult

        sr = SampleResult(
            question="Q?",
            answer="A.",
            scores={"faithfulness": 0.8, "context_precision": 0.6},
        )
        assert sr.mean_score == pytest.approx(0.7)

    def test_mean_score_empty(self):
        from evaluation.report import SampleResult

        sr = SampleResult(question="Q?", answer="A.", scores={})
        assert sr.mean_score == 0.0

    def test_is_failed_when_below_threshold(self):
        from evaluation.report import SampleResult

        sr = SampleResult(
            question="Q?",
            answer="A.",
            scores={"faithfulness": 0.3, "context_precision": 0.9},
        )
        assert sr.is_failed is True

    def test_is_not_failed_when_all_above_threshold(self):
        from evaluation.report import SampleResult

        sr = SampleResult(
            question="Q?",
            answer="A.",
            scores={"faithfulness": 0.8, "context_precision": 0.9},
        )
        assert sr.is_failed is False

    def test_to_dict_redacts_sensitive_data(self):
        from evaluation.report import SampleResult

        sr = SampleResult(
            question="My PIN is 1234",
            answer="Balance is $100",
            scores={"faithfulness": 0.9},
            metadata={"pin": "5678"},
        )
        d = sr.to_dict()
        assert "1234" not in d["question"]
        assert d["metadata"]["pin"] == "[REDACTED]"
        assert d["scores"]["faithfulness"] == 0.9
        assert "mean_score" in d
        assert "failed" in d


# ---------------------------------------------------------------------------
# 8. EvaluationReport
# ---------------------------------------------------------------------------


class TestEvaluationReport:
    """Tests for evaluation.report.EvaluationReport."""

    def _make_report(self, **overrides):
        from evaluation.report import EvaluationReport, SampleResult

        defaults = {
            "dataset_name": "test-dataset",
            "metric_names": ["faithfulness", "answer_relevancy"],
            "aggregate_scores": {"faithfulness": 0.85, "answer_relevancy": 0.78},
            "sample_results": [
                SampleResult(
                    question="Q1?",
                    answer="A1.",
                    scores={"faithfulness": 0.9, "answer_relevancy": 0.8},
                    ground_truth="ref1",
                    retrieved_contexts=["ctx1", "ctx2"],
                ),
                SampleResult(
                    question="Q2?",
                    answer="A2.",
                    scores={"faithfulness": 0.8, "answer_relevancy": 0.76},
                    retrieved_contexts=["ctx3"],
                ),
            ],
            "total_samples": 3,
            "failed_samples": 1,
            "elapsed_seconds": 12.345,
        }
        defaults.update(overrides)
        return EvaluationReport(**defaults)

    def test_evaluated_samples(self):
        report = self._make_report()
        assert report.evaluated_samples == 2

    def test_mean_overall_score(self):
        report = self._make_report()
        expected = (0.85 + 0.78) / 2
        assert report.mean_overall_score == pytest.approx(expected)

    def test_mean_overall_score_empty(self):
        report = self._make_report(aggregate_scores={})
        assert report.mean_overall_score == 0.0

    def test_failed_sample_results(self):
        from evaluation.report import SampleResult

        failed_sr = SampleResult(
            question="Q?",
            answer="A.",
            scores={"faithfulness": 0.3},
        )
        report = self._make_report(
            sample_results=[failed_sr],
        )
        assert len(report.failed_sample_results) == 1

    def test_retrieval_stats(self):
        report = self._make_report()
        stats = report.retrieval_stats
        assert stats["avg_contexts"] == 1.5
        assert stats["min_contexts"] == 1
        assert stats["max_contexts"] == 2
        assert stats["samples_with_no_context"] == 0

    def test_retrieval_stats_empty(self):
        report = self._make_report(sample_results=[])
        stats = report.retrieval_stats
        assert stats["avg_contexts"] == 0.0

    def test_summary_format(self):
        report = self._make_report()
        s = report.summary()
        assert "test-dataset" in s
        assert "2/3" in s
        assert "faithfulness" in s

    def test_to_dict_keys(self):
        report = self._make_report()
        d = report.to_dict()
        expected_keys = {
            "dataset_name",
            "evaluated_at",
            "total_samples",
            "evaluated_samples",
            "failed_samples",
            "elapsed_seconds",
            "metric_names",
            "aggregate_scores",
            "mean_overall_score",
            "retrieval_stats",
            "failed_sample_count",
            "sample_results",
        }
        assert set(d.keys()) == expected_keys

    def test_to_dict_scores_rounded(self):
        report = self._make_report()
        d = report.to_dict()
        for score in d["aggregate_scores"].values():
            # Should be rounded to 4 decimal places
            assert score == round(score, 4)

    def test_to_json_valid(self):
        report = self._make_report()
        j = report.to_json()
        parsed = json.loads(j)
        assert parsed["dataset_name"] == "test-dataset"
        assert len(parsed["sample_results"]) == 2

    def test_to_markdown_sections(self):
        report = self._make_report()
        md = report.to_markdown()
        assert "# RAGAS Evaluation Report" in md
        assert "## Overall Scores" in md
        assert "## Retrieval Statistics" in md
        assert "## Per-Question Scores" in md
        assert "faithfulness" in md

    def test_to_markdown_no_scores(self):
        report = self._make_report(aggregate_scores={}, sample_results=[])
        md = report.to_markdown()
        assert "_No scores computed._" in md

    def test_to_markdown_with_failures(self):
        from evaluation.report import SampleResult

        failed = SampleResult(question="Q?", answer="A.", scores={"faithfulness": 0.2})
        report = self._make_report(sample_results=[failed])
        md = report.to_markdown()
        assert "## Failed Samples" in md

    def test_save_json(self, tmp_path):
        report = self._make_report()
        written = report.save(output_dir=tmp_path, fmt="json")
        assert "json" in written
        assert written["json"].exists()
        assert written["json"].suffix == ".json"
        content = json.loads(written["json"].read_text(encoding="utf-8"))
        assert content["dataset_name"] == "test-dataset"

    def test_save_markdown(self, tmp_path):
        report = self._make_report()
        written = report.save(output_dir=tmp_path, fmt="markdown")
        assert "markdown" in written
        assert written["markdown"].exists()
        assert written["markdown"].suffix == ".md"

    def test_save_both(self, tmp_path):
        report = self._make_report()
        written = report.save(output_dir=tmp_path, fmt="both")
        assert "json" in written
        assert "markdown" in written
        assert len(written) == 2

    def test_save_custom_stem(self, tmp_path):
        report = self._make_report()
        written = report.save(output_dir=tmp_path, fmt="json", stem="custom_name")
        assert "custom_name" in written["json"].name

    def test_save_creates_output_directory(self, tmp_path):
        report = self._make_report()
        nested = tmp_path / "deep" / "nested" / "dir"
        written = report.save(output_dir=nested, fmt="json")
        assert nested.exists()
        assert written["json"].exists()

    def test_evaluated_at_is_populated(self):
        report = self._make_report()
        assert report.evaluated_at is not None
        assert "T" in report.evaluated_at  # ISO-8601 format


# ---------------------------------------------------------------------------
# 9. RagasRunner (mocked)
# ---------------------------------------------------------------------------


class TestRagasRunner:
    """Tests for evaluation.ragas_runner.RagasRunner (all RAGAS calls mocked)."""

    def test_evaluate_empty_returns_empty_report(self):
        """When samples is empty, return a report with zero samples."""
        from evaluation import get_eval_config
        from evaluation.ragas_runner import RagasRunner

        config = get_eval_config()
        runner = RagasRunner(config)

        # Mock ragas_available to True so the runner proceeds
        with patch("evaluation.ragas_runner.ragas_available", return_value=True):
            report = runner.evaluate([])

        assert report.total_samples == 0
        assert report.evaluated_samples == 0
        assert report.aggregate_scores == {}

    def test_evaluate_empty_raises_when_requested(self):
        from evaluation import get_eval_config
        from evaluation.ragas_runner import RagasRunner

        config = get_eval_config()
        runner = RagasRunner(config)

        with patch(
            "evaluation.ragas_runner.ragas_available", return_value=True
        ), pytest.raises(ValueError, match="Cannot evaluate an empty"):
            runner.evaluate([], raise_on_empty=True)

    def test_evaluate_raises_when_ragas_not_available(self):
        from evaluation import get_eval_config
        from evaluation.dataset_loader import EvalSample
        from evaluation.ragas_runner import RagasRunner

        config = get_eval_config()
        runner = RagasRunner(config)

        with patch(
            "evaluation.ragas_runner.ragas_available", return_value=False
        ), pytest.raises(ImportError, match="RAGAS is not installed"):
            runner.evaluate([EvalSample(question="Q", answer="A")])

    def test_evaluate_single_delegates(self):
        """evaluate_single should call evaluate with a single-element list."""
        from evaluation import get_eval_config
        from evaluation.dataset_loader import EvalSample
        from evaluation.ragas_runner import RagasRunner

        config = get_eval_config()
        runner = RagasRunner(config)

        mock_report = MagicMock()
        with patch.object(runner, "evaluate", return_value=mock_report) as mock_eval:
            sample = EvalSample(question="Q", answer="A")
            result = runner.evaluate_single(sample)

        assert result is mock_report
        mock_eval.assert_called_once_with([sample])

    def test_dataset_name_stored(self):
        from evaluation import get_eval_config
        from evaluation.ragas_runner import RagasRunner

        config = get_eval_config()
        runner = RagasRunner(config, dataset_name="my-eval")
        assert runner.dataset_name == "my-eval"

    def test_evaluate_skips_invalid_samples(self):
        """Invalid samples should be counted as failures, not sent to RAGAS."""
        import pandas as pd

        from evaluation import get_eval_config
        from evaluation.dataset_loader import EvalSample
        from evaluation.ragas_runner import RagasRunner

        config = get_eval_config()
        runner = RagasRunner(config)

        valid = EvalSample(question="Q?", answer="A.")
        invalid = EvalSample(question="", answer="")

        # Mock the entire RAGAS evaluate chain
        mock_ragas_result = MagicMock()
        mock_df = pd.DataFrame({"faithfulness": [0.9]})
        mock_ragas_result.to_pandas.return_value = mock_df

        mock_ragas_evaluate = MagicMock(return_value=mock_ragas_result)
        mock_single_turn = MagicMock()
        mock_eval_dataset = MagicMock()

        with (
            patch("evaluation.ragas_runner.ragas_available", return_value=True),
            patch.object(runner, "_get_metrics", return_value=[MagicMock()]),
            patch.dict(
                "sys.modules",
                {
                    "ragas": MagicMock(
                        evaluate=mock_ragas_evaluate,
                        EvaluationDataset=mock_eval_dataset,
                        SingleTurnSample=mock_single_turn,
                    ),
                },
            ),
        ):
            report = runner.evaluate([valid, invalid])

        assert report.total_samples == 2
        assert report.failed_samples == 1


# ---------------------------------------------------------------------------
# 10. CLI argument parsing
# ---------------------------------------------------------------------------


class TestCLIEvalArgs:
    """Tests for CLI --evaluate-rag argument integration."""

    def test_parse_evaluate_rag_argument(self):
        """The --evaluate-rag argument should be accepted by the parser."""
        from cli import _parse_args

        with patch("sys.argv", ["cli.py", "--evaluate-rag", "data.jsonl"]):
            args = _parse_args()
        assert args.evaluate_rag == "data.jsonl"

    def test_parse_eval_output_argument(self):
        from cli import _parse_args

        with patch(
            "sys.argv",
            ["cli.py", "--evaluate-rag", "d.json", "--eval-output", "/tmp/out"],
        ):
            args = _parse_args()
        assert args.eval_output == "/tmp/out"

    def test_parse_eval_metrics_argument(self):
        from cli import _parse_args

        with patch(
            "sys.argv",
            [
                "cli.py",
                "--evaluate-rag",
                "d.json",
                "--eval-metrics",
                "faithfulness,context_recall",
            ],
        ):
            args = _parse_args()
        assert args.eval_metrics == "faithfulness,context_recall"

    def test_eval_defaults_are_none(self):
        from cli import _parse_args

        with patch("sys.argv", ["cli.py"]):
            args = _parse_args()
        assert args.evaluate_rag is None
        assert args.eval_output is None
        assert args.eval_metrics is None


# ---------------------------------------------------------------------------
# 11. Score bar helper
# ---------------------------------------------------------------------------


class TestScoreBar:
    """Tests for report._score_bar()."""

    def test_full_bar(self):
        from evaluation.report import _score_bar

        bar = _score_bar(1.0, width=10)
        assert bar == "██████████"

    def test_empty_bar(self):
        from evaluation.report import _score_bar

        bar = _score_bar(0.0, width=10)
        assert bar == "░░░░░░░░░░"

    def test_half_bar(self):
        from evaluation.report import _score_bar

        bar = _score_bar(0.5, width=10)
        assert "█" in bar
        assert "░" in bar
        assert len(bar) == 10
