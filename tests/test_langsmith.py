"""
Tests for LangSmith observability integration.

These tests NEVER make real LangSmith API calls — LangSmith is always
disabled in this suite (either via the default disabled state or explicit
monkeypatching).  Tests verify:

  1. LangSmith disabled mode (default)
  2. LangSmith enabled mode (mocked)
  3. Tracing wrappers (trace_node, trace_tool, trace_rag, trace_llm)
  4. Metadata builders
  5. Prompt registry (versioning, retrieval, listing)
  6. Sensitive data redaction
  7. Dataset builder (to_dict, to_jsonl, to_langsmith disabled, to_langsmith enabled)
  8. Configuration loading (env vars, validation)
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure project root is on the path.
sys.path.insert(0, str(Path(__file__).parent.parent))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _clear_langsmith_state():
    """Reset config module state between tests."""
    import observability.langsmith_config as cfg_mod

    cfg_mod.reset_for_testing()


# ---------------------------------------------------------------------------
# 1. Configuration loading
# ---------------------------------------------------------------------------


class TestLangSmithConfig:
    """Tests for observability.langsmith_config."""

    def setup_method(self):
        _clear_langsmith_state()

    def teardown_method(self):
        _clear_langsmith_state()
        # Clean up env vars that tests might have set.
        for var in (
            "LANGSMITH_TRACING",
            "LANGSMITH_API_KEY",
            "LANGSMITH_PROJECT",
            "LANGSMITH_ENDPOINT",
            "LANGCHAIN_TRACING_V2",
            "LANGCHAIN_API_KEY",
            "LANGCHAIN_PROJECT",
        ):
            os.environ.pop(var, None)

    def test_tracing_disabled_by_default(self, monkeypatch):
        monkeypatch.delenv("LANGSMITH_TRACING", raising=False)
        from observability.langsmith_config import get_langsmith_config

        cfg = get_langsmith_config()
        assert cfg.enabled is False

    def test_tracing_enabled_with_key(self, monkeypatch):
        monkeypatch.setenv("LANGSMITH_TRACING", "true")
        monkeypatch.setenv("LANGSMITH_API_KEY", "ls-testkey")
        from observability.langsmith_config import get_langsmith_config

        cfg = get_langsmith_config()
        assert cfg.enabled is True
        assert cfg.api_key == "ls-testkey"

    def test_tracing_disabled_when_key_missing(self, monkeypatch):
        monkeypatch.setenv("LANGSMITH_TRACING", "true")
        monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)
        from observability.langsmith_config import get_langsmith_config

        cfg = get_langsmith_config()
        # Should disable itself when key is missing.
        assert cfg.enabled is False

    def test_default_project_name(self, monkeypatch):
        monkeypatch.delenv("LANGSMITH_PROJECT", raising=False)
        from observability.langsmith_config import get_langsmith_config

        cfg = get_langsmith_config()
        assert cfg.project == "bank-assistant"

    def test_custom_project_name(self, monkeypatch):
        monkeypatch.setenv("LANGSMITH_PROJECT", "my-custom-project")
        from observability.langsmith_config import get_langsmith_config

        cfg = get_langsmith_config()
        assert cfg.project == "my-custom-project"

    def test_bool_parsing_variants(self, monkeypatch):
        """'1', 'yes', 'true' should all enable tracing (with a key)."""
        from observability.langsmith_config import _parse_bool

        for truthy in ("true", "True", "TRUE", "1", "yes", "YES"):
            assert _parse_bool(truthy) is True

        for falsy in ("false", "0", "no", "", None, "maybe"):
            assert _parse_bool(falsy) is False

    def test_is_tracing_enabled_starts_false(self):
        from observability.langsmith_config import is_tracing_enabled

        assert is_tracing_enabled() is False

    def test_configure_langsmith_no_package(self, monkeypatch):
        """configure_langsmith must not raise when langsmith is not installed."""
        monkeypatch.setenv("LANGSMITH_TRACING", "true")
        monkeypatch.setenv("LANGSMITH_API_KEY", "ls-testkey")

        with patch.dict("sys.modules", {"langsmith": None}):
            from observability.langsmith_config import configure_langsmith

            result = configure_langsmith()
        assert result is False

    def test_configure_langsmith_disabled(self, monkeypatch):
        monkeypatch.delenv("LANGSMITH_TRACING", raising=False)
        from observability.langsmith_config import (
            configure_langsmith,
            is_tracing_enabled,
        )

        result = configure_langsmith()
        assert result is False
        assert is_tracing_enabled() is False

    def test_configure_langsmith_idempotent(self, monkeypatch):
        """Calling configure_langsmith() twice should not raise."""
        monkeypatch.delenv("LANGSMITH_TRACING", raising=False)
        from observability.langsmith_config import configure_langsmith

        r1 = configure_langsmith()
        r2 = configure_langsmith()
        assert r1 == r2


# ---------------------------------------------------------------------------
# 2. Sensitive data redaction
# ---------------------------------------------------------------------------


class TestRedaction:
    """Tests for observability.redaction."""

    def test_pin_masked_inline(self):
        from observability.redaction import redact

        result = redact("My PIN is 1234 please help")
        assert "1234" not in result
        assert "[REDACTED]" in result

    def test_sha256_hash_masked(self):
        from observability.redaction import redact

        sha256 = "a" * 64
        result = redact(f"hash={sha256}")
        assert sha256 not in result
        assert "[REDACTED]" in result

    def test_dict_sensitive_key_masked(self):
        from observability.redaction import redact

        result = redact({"pin": "1234", "username": "alice"})
        assert result["pin"] == "[REDACTED]"
        assert result["username"] == "alice"

    def test_dict_pin_hash_masked(self):
        from observability.redaction import redact

        result = redact({"pin_hash": "abc123", "user_id": "U1002"})
        assert result["pin_hash"] == "[REDACTED]"
        assert result["user_id"] == "U1002"

    def test_list_walked_recursively(self):
        from observability.redaction import redact

        result = redact([{"pin": "9999"}, {"user": "U1002"}])
        assert result[0]["pin"] == "[REDACTED]"
        assert result[1]["user"] == "U1002"

    def test_nested_dict_walked(self):
        from observability.redaction import redact

        result = redact({"outer": {"pin": "5678", "safe": "value"}})
        assert result["outer"]["pin"] == "[REDACTED]"
        assert result["outer"]["safe"] == "value"

    def test_non_string_scalars_unchanged(self):
        from observability.redaction import redact

        assert redact(42) == 42
        assert redact(3.14) == 3.14
        assert redact(True) is True
        assert redact(None) is None

    def test_redact_tool_args_verify_identity(self):
        from observability.redaction import redact_tool_args

        result = redact_tool_args(
            "verify_identity", {"user_id": "U1002", "pin": "1234"}
        )
        assert result["pin"] == "[REDACTED]"
        assert result["user_id"] == "U1002"

    def test_redact_tool_args_safe_tool(self):
        from observability.redaction import redact_tool_args

        result = redact_tool_args(
            "get_balance", {"user_id": "U1002", "account_id": "A2001"}
        )
        # No sensitive fields in this call — values should be returned as-is
        # (user_id passes through; it is not in _SENSITIVE_KEYS).
        assert result["user_id"] == "U1002"
        assert result["account_id"] == "A2001"

    def test_argon2_hash_masked(self):
        from observability.redaction import redact

        argon2_hash = "$argon2id$v=19$m=65536,t=3,p=4$some_salt$some_hash"
        result = redact(f"stored={argon2_hash}")
        assert argon2_hash not in result

    def test_idempotent(self):
        from observability.redaction import redact

        original = {"user": "alice", "pin": "1234"}
        once = redact(original)
        twice = redact(once)
        assert once == twice


# ---------------------------------------------------------------------------
# 3. Tracing wrappers (disabled mode)
# ---------------------------------------------------------------------------


class TestTracingDisabled:
    """Tracing wrappers must be zero-overhead pass-throughs when disabled."""

    def setup_method(self):
        _clear_langsmith_state()

    def teardown_method(self):
        _clear_langsmith_state()

    def test_trace_node_passthrough(self):
        from observability.tracing import trace_node

        ran = []
        with trace_node("supervisor"):
            ran.append(True)
        assert ran == [True]

    def test_trace_tool_passthrough(self):
        from observability.tracing import trace_tool

        with trace_tool(
            "get_balance", agent="account_agent", args={"user_id": "U1"}
        ) as ctx:
            ctx["result"] = {"accounts": []}
        assert ctx["result"] == {"accounts": []}

    def test_trace_rag_passthrough(self):
        from observability.tracing import trace_rag

        with trace_rag("lost card policy") as ctx:
            ctx["results"] = [{"source": "card_lost_stolen", "text": "..."}]
        assert len(ctx["results"]) == 1

    def test_trace_llm_passthrough(self):
        from observability.tracing import trace_llm

        with trace_llm("supervisor", model="claude-sonnet-4-5") as ctx:
            ctx["completion"] = "intent: search"
        assert ctx["completion"] == "intent: search"

    def test_traced_tool_decorator_passthrough(self):
        from observability.tracing import traced_tool

        @traced_tool("my_tool", agent="test_agent")
        def my_tool(x: int) -> dict:
            return {"value": x * 2}

        result = my_tool(21)
        assert result == {"value": 42}


# ---------------------------------------------------------------------------
# 4. Tracing wrappers (enabled mode — mocked langsmith)
# ---------------------------------------------------------------------------


class TestTracingEnabled:
    """Tracing wrappers should call langsmith.trace when enabled."""

    def setup_method(self):
        _clear_langsmith_state()

    def teardown_method(self):
        _clear_langsmith_state()

    def _enable_tracing(self, monkeypatch):
        """Force tracing on without a real API key."""
        import observability.langsmith_config as cfg_mod

        monkeypatch.setattr(cfg_mod, "_tracing_enabled", True)
        monkeypatch.setattr(cfg_mod, "_configured", True)

    def test_trace_node_calls_langsmith(self, monkeypatch):
        self._enable_tracing(monkeypatch)
        mock_trace = MagicMock()
        mock_ctx = MagicMock()
        mock_trace.return_value.__enter__ = MagicMock(return_value=mock_ctx)
        mock_trace.return_value.__exit__ = MagicMock(return_value=False)

        with patch.dict("sys.modules", {"langsmith": MagicMock(trace=mock_trace)}):
            from observability.tracing import trace_node

            with trace_node("supervisor", metadata={"session_id": "s1"}):
                pass

        mock_trace.assert_called_once()
        call_kwargs = mock_trace.call_args.kwargs
        assert call_kwargs["name"] == "node:supervisor"
        assert call_kwargs["run_type"] == "chain"

    def test_trace_tool_calls_langsmith(self, monkeypatch):
        self._enable_tracing(monkeypatch)
        mock_trace = MagicMock()
        mock_ctx = MagicMock()
        mock_ctx.end = MagicMock()
        mock_trace.return_value.__enter__ = MagicMock(return_value=mock_ctx)
        mock_trace.return_value.__exit__ = MagicMock(return_value=False)

        with patch.dict("sys.modules", {"langsmith": MagicMock(trace=mock_trace)}):
            from observability.tracing import trace_tool

            with trace_tool(
                "get_balance", agent="account_agent", args={"user_id": "U1"}
            ) as ctx:
                ctx["result"] = {"accounts": []}

        mock_trace.assert_called_once()
        call_kwargs = mock_trace.call_args.kwargs
        assert call_kwargs["name"] == "tool:get_balance"
        assert call_kwargs["run_type"] == "tool"

    def test_trace_tool_pin_redacted(self, monkeypatch):
        """PIN must not appear in LangSmith inputs even when tracing is enabled."""
        self._enable_tracing(monkeypatch)
        captured_inputs = {}

        mock_trace = MagicMock()
        mock_ctx = MagicMock()
        mock_ctx.end = MagicMock()
        mock_trace.return_value.__enter__ = MagicMock(return_value=mock_ctx)
        mock_trace.return_value.__exit__ = MagicMock(return_value=False)

        def _capture_trace(**kwargs):
            captured_inputs.update(kwargs.get("inputs", {}))
            return mock_trace.return_value

        mock_trace.side_effect = _capture_trace

        with patch.dict("sys.modules", {"langsmith": MagicMock(trace=mock_trace)}):
            from observability.tracing import trace_tool

            with trace_tool(
                "verify_identity",
                agent="verify_gate",
                args={"user_id": "U1002", "pin": "1234"},
            ) as ctx:
                ctx["result"] = {"verified": True}

        assert "1234" not in str(captured_inputs)


# ---------------------------------------------------------------------------
# 5. Metadata builders
# ---------------------------------------------------------------------------


class TestMetadata:
    """Tests for observability.metadata."""

    def test_build_conversation_metadata_keys(self):
        from observability.metadata import build_conversation_metadata

        meta = build_conversation_metadata(
            session_id="s123",
            channel="cli",
            turn=3,
            intent="account",
            agent="account_agent",
        )
        assert meta["session_id"] == "s123"
        assert meta["channel"] == "cli"
        assert meta["turn"] == 3
        assert meta["intent"] == "account"
        assert meta["agent"] == "account_agent"
        assert "timestamp" in meta

    def test_build_rag_metadata_keys(self):
        from observability.metadata import build_rag_metadata

        meta = build_rag_metadata(
            query="lost card",
            normalized_query="lost card",
            num_results=3,
            sources=["card_lost_stolen"],
        )
        assert meta["num_results"] == 3
        assert meta["retrieval_method"] == "hybrid_rrf_mmr"
        assert "card_lost_stolen" in meta["sources"]

    def test_build_tool_metadata_keys(self):
        from observability.metadata import build_tool_metadata

        meta = build_tool_metadata(
            tool_name="lock_card",
            agent="fraud_agent",
            turn=2,
            session_id="s456",
        )
        assert meta["tool_name"] == "lock_card"
        assert meta["agent"] == "fraud_agent"
        assert meta["turn"] == 2
        assert meta["session_id"] == "s456"

    def test_build_llm_metadata_keys(self):
        from observability.metadata import build_llm_metadata

        meta = build_llm_metadata(
            model="claude-sonnet-4-5",
            agent="supervisor",
            turn=1,
        )
        assert meta["model"] == "claude-sonnet-4-5"
        assert meta["agent"] == "supervisor"
        assert meta["turn"] == 1

    def test_build_node_metadata_keys(self):
        from observability.metadata import build_node_metadata

        meta = build_node_metadata(
            node_name="search_agent",
            session_id="s789",
            intent="search",
            turn=1,
        )
        assert meta["node_name"] == "search_agent"
        assert meta["session_id"] == "s789"
        assert meta["intent"] == "search"

    def test_metadata_optional_fields_omitted(self):
        from observability.metadata import build_conversation_metadata

        meta = build_conversation_metadata(channel="streamlit", turn=0)
        assert "session_id" not in meta
        assert "intent" not in meta
        assert "agent" not in meta


# ---------------------------------------------------------------------------
# 6. Prompt registry
# ---------------------------------------------------------------------------


class TestPromptRegistry:
    """Tests for observability.prompt_registry."""

    def test_all_agents_have_registered_prompts(self):
        from observability.prompt_registry import list_prompts

        prompts = list_prompts()
        for name in ("supervisor", "search_agent", "account_agent", "fraud_agent"):
            assert name in prompts, f"Prompt '{name}' not registered"

    def test_get_prompt_returns_non_empty_string(self):
        from observability.prompt_registry import get_prompt

        for name in ("supervisor", "search_agent", "account_agent", "fraud_agent"):
            text = get_prompt(name)
            assert isinstance(text, str)
            assert len(text) > 10

    def test_get_prompt_version_format(self):
        from observability.prompt_registry import get_prompt_version

        version = get_prompt_version("supervisor")
        assert version.startswith("v")
        parts = version[1:].split(".")
        assert len(parts) == 3

    def test_get_prompt_metadata_keys(self):
        from observability.prompt_registry import get_prompt_metadata

        meta = get_prompt_metadata("search_agent")
        assert "prompt_name" in meta
        assert "prompt_version" in meta
        assert meta["prompt_name"] == "search_agent"

    def test_unknown_prompt_raises_key_error(self):
        from observability.prompt_registry import get_prompt

        with pytest.raises(KeyError):
            get_prompt("nonexistent_agent")

    def test_register_prompt_custom(self):
        from observability.prompt_registry import get_prompt, register_prompt

        register_prompt("test_agent", "v9.0.0", "Test prompt content", "for tests")
        assert get_prompt("test_agent") == "Test prompt content"

    def test_supervisor_prompt_text_unchanged(self):
        """The registered supervisor prompt must match the original in agents/supervisor.py."""
        from observability.prompt_registry import get_prompt

        prompt = get_prompt("supervisor")
        # Key phrases that were in the original SYSTEM_PROMPT.
        assert "routing classifier" in prompt
        assert '"intent"' in prompt
        assert "search" in prompt
        assert "account" in prompt
        assert "fraud" in prompt
        assert "unclear" in prompt


# ---------------------------------------------------------------------------
# 7. Dataset builder
# ---------------------------------------------------------------------------


class TestDatasetBuilder:
    """Tests for observability.dataset.DatasetBuilder."""

    def setup_method(self):
        _clear_langsmith_state()

    def teardown_method(self):
        _clear_langsmith_state()

    def test_add_example_and_len(self):
        from observability.dataset import DatasetBuilder

        builder = DatasetBuilder()
        builder.add_example("What is my balance?", "Your balance is $500.")
        assert len(builder) == 1

    def test_fluent_interface(self):
        from observability.dataset import DatasetBuilder

        builder = DatasetBuilder()
        result = builder.add_example("Q1", "A1").add_example("Q2", "A2")
        assert result is builder
        assert len(builder) == 2

    def test_to_dict_redacts_sensitive_data(self):
        from observability.dataset import DatasetBuilder

        builder = DatasetBuilder()
        builder.add_example(
            "My PIN is 1234, what is my balance?",
            "Balance is $100",
            metadata={"pin": "1234"},
        )
        example = builder.examples[0]
        d = example.to_dict()
        assert "1234" not in d["question"]
        assert d["metadata"]["pin"] == "[REDACTED]"

    def test_to_langsmith_format_keys(self):
        from observability.dataset import DatasetBuilder

        builder = DatasetBuilder()
        builder.add_example("Q", "A", expected_answer="expected A")
        ls_fmt = builder.examples[0].to_langsmith_format()
        assert "inputs" in ls_fmt
        assert "outputs" in ls_fmt
        assert "question" in ls_fmt["inputs"]
        assert "answer" in ls_fmt["outputs"]

    def test_to_jsonl_creates_file(self, tmp_path):
        from observability.dataset import DatasetBuilder

        builder = DatasetBuilder()
        builder.add_example("Q1", "A1")
        builder.add_example("Q2", "A2", retrieved_context=["ctx1"])

        out = builder.to_jsonl(tmp_path / "eval.jsonl")
        assert out.exists()
        lines = out.read_text().strip().split("\n")
        assert len(lines) == 2
        first = json.loads(lines[0])
        assert "inputs" in first
        assert "outputs" in first

    def test_to_langsmith_disabled_returns_none(self):
        """When tracing is disabled, to_langsmith() must return None without error."""
        from observability.dataset import DatasetBuilder

        builder = DatasetBuilder()
        builder.add_example("Q", "A")
        result = builder.to_langsmith()
        assert result is None

    def test_to_langsmith_no_examples_returns_none(self):
        from observability.dataset import DatasetBuilder

        builder = DatasetBuilder()
        assert builder.to_langsmith() is None

    def test_clear_removes_examples(self):
        from observability.dataset import DatasetBuilder

        builder = DatasetBuilder()
        builder.add_example("Q", "A")
        builder.clear()
        assert len(builder) == 0

    def test_to_langsmith_enabled_mocked(self, monkeypatch):
        """to_langsmith() should call langsmith.Client when tracing is enabled."""
        import observability.langsmith_config as cfg_mod

        monkeypatch.setattr(cfg_mod, "_tracing_enabled", True)
        monkeypatch.setattr(cfg_mod, "_configured", True)

        mock_dataset = MagicMock()
        mock_dataset.id = "dataset-123"
        mock_client = MagicMock()
        mock_client.list_datasets.return_value = iter([])
        mock_client.create_dataset.return_value = mock_dataset
        mock_client.create_examples.return_value = None

        mock_langsmith = MagicMock()
        mock_langsmith.Client.return_value = mock_client

        with patch.dict("sys.modules", {"langsmith": mock_langsmith}):
            from observability.dataset import DatasetBuilder

            builder = DatasetBuilder(dataset_name="test-dataset")
            builder.add_example("Q1", "A1")
            result = builder.to_langsmith()

        assert result == "dataset-123"
        mock_client.create_dataset.assert_called_once()
        mock_client.create_examples.assert_called_once()


# ---------------------------------------------------------------------------
# 8. Graph import does not require API key
# ---------------------------------------------------------------------------


class TestGraphObservabilityImports:
    """LangSmith imports must not break graph imports when tracing is off."""

    def test_graph_imports_with_observability(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("LANGSMITH_TRACING", raising=False)
        _clear_langsmith_state()

        from graph import build_graph

        g = build_graph()
        assert g is not None

    def test_config_validate_startup_includes_langsmith_detail(self, monkeypatch):
        monkeypatch.delenv("LANGSMITH_TRACING", raising=False)
        _clear_langsmith_state()

        # Reset the global flag so validate_startup re-runs the LangSmith init.
        import config as cfg_mod

        monkeypatch.setattr(cfg_mod, "_langsmith_initialized", False)
        monkeypatch.setattr(cfg_mod, "REQUIRED_DIRECTORIES", ())

        from config import validate_startup

        status = validate_startup(require_llm=False, initialize=False)
        # "langsmith" key must appear in details after validate_startup.
        assert "langsmith" in status.details
        assert status.details["langsmith"] in ("enabled", "disabled")
