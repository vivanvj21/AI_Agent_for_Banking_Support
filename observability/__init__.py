"""
LangSmith observability package for the Autonomous Bank Assistant.

Import surface:
    from observability import is_tracing_enabled, get_langsmith_config
    from observability.tracing import trace_node, trace_tool, trace_llm
    from observability.redaction import redact
    from observability.metadata import build_conversation_metadata
    from observability.prompt_registry import get_prompt
    from observability.dataset import DatasetBuilder
"""

from observability.langsmith_config import get_langsmith_config, is_tracing_enabled

__all__ = ["get_langsmith_config", "is_tracing_enabled"]
