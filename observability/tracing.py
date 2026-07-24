"""
LangSmith tracing context managers and decorators.

All helpers are NO-OPs when LangSmith is disabled (``is_tracing_enabled()``
returns False) or when the ``langsmith`` package is not installed.

Usage:
    from observability.tracing import trace_node, trace_tool, trace_llm, trace_rag

    # As a context manager:
    with trace_node("supervisor", metadata={"session_id": sid}):
        ...

    # As a decorator (for functions that return a dict / any value):
    @trace_tool("get_balance", agent="account_agent")
    def get_balance(user_id, account_id=None):
        ...

Design notes:
  - We use ``langsmith.trace()`` as the underlying primitive wherever possible.
  - All inputs/outputs are redacted before being sent.
  - Errors are recorded as ``error`` fields, then re-raised so normal
    exception handling is undisturbed.
  - The helpers import langsmith lazily, so the application starts normally
    even if the package is missing.
"""

from __future__ import annotations

import functools
import logging
import time
from collections.abc import Callable, Generator
from contextlib import contextmanager

from observability.langsmith_config import is_tracing_enabled
from observability.redaction import redact, redact_tool_args

LOGGER = logging.getLogger(__name__)

# ── Low-level helper ──────────────────────────────────────────────────────────


def _get_langsmith_client():
    """Return a langsmith.Client instance, or None if unavailable."""
    try:
        from langsmith import Client

        return Client()
    except Exception:  # noqa: BLE001
        return None


# ── Node tracing ──────────────────────────────────────────────────────────────


@contextmanager
def trace_node(
    node_name: str,
    *,
    metadata: dict | None = None,
    tags: list[str] | None = None,
) -> Generator[None, None, None]:
    """Context manager that traces a LangGraph node execution.

    When tracing is disabled this is a zero-overhead pass-through.

    Args:
        node_name: Name shown in LangSmith (e.g. "supervisor", "search_agent").
        metadata:  Additional metadata dict (will be redacted).
        tags:      List of string tags for filtering in LangSmith.
    """
    if not is_tracing_enabled():
        yield
        return

    try:
        from langsmith import trace

        safe_meta = redact(metadata or {})
        safe_tags = tags or [f"node:{node_name}"]

        with trace(
            name=f"node:{node_name}",
            run_type="chain",
            metadata=safe_meta,
            tags=safe_tags,
        ):
            yield
    except ImportError:
        yield
    except Exception:
        LOGGER.debug("trace_node_failed for %s", node_name, exc_info=True)
        yield


# ── Tool tracing ──────────────────────────────────────────────────────────────


@contextmanager
def trace_tool(
    tool_name: str,
    *,
    agent: str = "unknown",
    args: dict | None = None,
    metadata: dict | None = None,
    tags: list[str] | None = None,
) -> Generator[dict, None, None]:
    """Context manager that traces a tool invocation.

    Yields a mutable dict with a single key ``"result"`` where the caller
    can store the tool's return value — this is then recorded as the
    run's output in LangSmith.

    Example::

        with trace_tool("get_balance", agent="account_agent", args={"user_id": uid}) as ctx:
            ctx["result"] = get_balance(uid)
        return ctx["result"]

    Args:
        tool_name: Tool function name.
        agent:     Agent that invoked the tool.
        args:      Tool arguments dict (will be redacted before sending).
        metadata:  Additional metadata.
        tags:      String tags.
    """
    result_holder: dict = {"result": None, "error": None}
    yield_holder: dict = result_holder

    if not is_tracing_enabled():
        yield yield_holder
        return

    try:
        from langsmith import trace

        safe_args = redact_tool_args(tool_name, args or {})
        safe_meta = redact(metadata or {})
        safe_tags = tags or [f"tool:{tool_name}", f"agent:{agent}"]
        start = time.perf_counter()

        try:
            with trace(
                name=f"tool:{tool_name}",
                run_type="tool",
                inputs={"tool_name": tool_name, "args": safe_args},
                metadata={**safe_meta, "agent": agent},
                tags=safe_tags,
            ) as run_tree:
                yield yield_holder
                elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
                if yield_holder.get("error"):
                    if run_tree:
                        run_tree.end(error=str(yield_holder["error"]))
                else:
                    safe_result = redact(yield_holder.get("result"))
                    if run_tree:
                        run_tree.end(
                            outputs={"result": safe_result, "elapsed_ms": elapsed_ms}
                        )
        except Exception as exc:
            yield_holder["error"] = exc
            raise
    except ImportError:
        yield yield_holder
    except Exception:
        LOGGER.debug("trace_tool_failed for %s", tool_name, exc_info=True)
        yield yield_holder


# ── RAG retrieval tracing ─────────────────────────────────────────────────────


@contextmanager
def trace_rag(
    query: str,
    *,
    normalized_query: str = "",
    metadata: dict | None = None,
    tags: list[str] | None = None,
) -> Generator[dict, None, None]:
    """Context manager that traces a RAG retrieval call.

    Yields a mutable dict where the caller stores retrieval details:
      result_holder["results"] = list of hit dicts
      result_holder["scores"]  = list of distances/scores (optional)

    Args:
        query:            Raw user query.
        normalized_query: Query after preprocessing.
        metadata:         Additional metadata.
        tags:             String tags.
    """
    result_holder: dict = {"results": [], "scores": []}

    if not is_tracing_enabled():
        yield result_holder
        return

    try:
        from langsmith import trace

        safe_meta = redact(metadata or {})
        safe_tags = tags or ["rag", "retrieval"]
        start = time.perf_counter()

        with trace(
            name="rag:search_faq",
            run_type="retriever",
            inputs={
                "query": query,
                "normalized_query": normalized_query or query,
            },
            metadata=safe_meta,
            tags=safe_tags,
        ) as run_tree:
            yield result_holder
            elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
            if run_tree:
                run_tree.end(
                    outputs={
                        "num_results": len(result_holder.get("results", [])),
                        "sources": [
                            r.get("source", "unknown")
                            for r in result_holder.get("results", [])
                        ],
                        "elapsed_ms": elapsed_ms,
                    }
                )
    except ImportError:
        yield result_holder
    except Exception:
        LOGGER.debug("trace_rag_failed", exc_info=True)
        yield result_holder


# ── LLM request tracing ───────────────────────────────────────────────────────


@contextmanager
def trace_llm(
    agent: str,
    *,
    model: str,
    messages: list[dict] | None = None,
    system_prompt: str | None = None,
    metadata: dict | None = None,
    tags: list[str] | None = None,
) -> Generator[dict, None, None]:
    """Context manager that traces a single LLM request.

    Yields a mutable dict where the caller stores the response:
      ctx["completion"] = str text response
      ctx["input_tokens"] = int (optional)
      ctx["output_tokens"] = int (optional)

    Args:
        agent:         Agent making the call (e.g. "supervisor").
        model:         Model identifier.
        messages:      Conversation messages list (will be redacted).
        system_prompt: System prompt string (will be redacted).
        metadata:      Additional metadata.
        tags:          String tags.
    """
    result_holder: dict = {
        "completion": None,
        "input_tokens": None,
        "output_tokens": None,
    }

    if not is_tracing_enabled():
        yield result_holder
        return

    try:
        from langsmith import trace

        safe_messages = redact(messages or [])
        safe_system = redact(system_prompt or "")
        safe_meta = redact(metadata or {})
        safe_tags = tags or [f"llm:{model}", f"agent:{agent}"]
        start = time.perf_counter()

        with trace(
            name=f"llm:{agent}",
            run_type="llm",
            inputs={
                "model": model,
                "messages": safe_messages,
                "system": safe_system,
            },
            metadata={**safe_meta, "model": model, "agent": agent},
            tags=safe_tags,
        ) as run_tree:
            yield result_holder
            elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
            if run_tree:
                run_tree.end(
                    outputs={
                        "completion": redact(result_holder.get("completion") or ""),
                        "input_tokens": result_holder.get("input_tokens"),
                        "output_tokens": result_holder.get("output_tokens"),
                        "elapsed_ms": elapsed_ms,
                    }
                )
    except ImportError:
        yield result_holder
    except Exception:
        LOGGER.debug("trace_llm_failed for %s", agent, exc_info=True)
        yield result_holder


# ── Decorator variant ─────────────────────────────────────────────────────────


def traced_tool(tool_name: str, agent: str = "unknown") -> Callable:
    """Decorator that wraps a tool function with LangSmith tracing.

    The wrapped function must return a dict.  Its return value is
    recorded as the run's output after redaction.

    Usage::

        @traced_tool("get_balance", agent="account_agent")
        def get_balance(user_id, account_id=None):
            ...
    """

    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            if not is_tracing_enabled():
                return fn(*args, **kwargs)

            try:
                # Build safe inputs from positional + keyword args.
                import inspect

                from langsmith import trace

                sig = inspect.signature(fn)
                bound = sig.bind(*args, **kwargs)
                bound.apply_defaults()
                raw_args = dict(bound.arguments)
                safe_inputs = redact_tool_args(tool_name, raw_args)

                with trace(
                    name=f"tool:{tool_name}",
                    run_type="tool",
                    inputs={"tool_name": tool_name, "args": safe_inputs},
                    metadata={"agent": agent},
                    tags=[f"tool:{tool_name}", f"agent:{agent}"],
                ) as run_tree:
                    result = fn(*args, **kwargs)
                    if run_tree:
                        run_tree.end(outputs={"result": redact(result)})
                    return result
            except ImportError:
                return fn(*args, **kwargs)
            except Exception:
                LOGGER.debug(
                    "traced_tool_decorator_failed for %s", tool_name, exc_info=True
                )
                return fn(*args, **kwargs)

        return wrapper

    return decorator
