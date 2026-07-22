# Evaluation Results

## What has actually been run and verified

`tests/test_tools.py` — 11/11 tests passing. These test the tool layer
directly against the real seeded SQLite database (`db/bank.db`), with no
mocking and no LLM involved:

```
tests/test_tools.py::test_verify_identity_success PASSED
tests/test_tools.py::test_verify_identity_wrong_pin PASSED
tests/test_tools.py::test_verify_identity_unknown_user PASSED
tests/test_tools.py::test_get_balance_returns_accounts PASSED
tests/test_tools.py::test_get_balance_unknown_user PASSED
tests/test_tools.py::test_get_transaction_history_limit PASSED
tests/test_tools.py::test_lock_and_unlock_card_roundtrip PASSED
tests/test_tools.py::test_cannot_lock_another_users_card PASSED
tests/test_tools.py::test_report_fraud_transaction_requires_ownership PASSED
tests/test_tools.py::test_mask_account_number PASSED
tests/test_tools.py::test_get_flagged_transactions_structure PASSED

11 passed in 0.04s
```

Notably, `test_cannot_lock_another_users_card` and
`test_report_fraud_transaction_requires_ownership` confirm the cross-user
ownership check works: a verified user cannot act on another user's card or
transactions, even if they somehow obtained the ID.

The LangGraph state machine also compiles and its node structure was
confirmed directly:

```
Graph compiled OK
Nodes: ['__start__', 'supervisor', 'verify_gate', 'search_agent',
         'account_agent', 'fraud_agent', 'clarify', 'await_credentials',
         'human_handoff', '__end__']
```

The FAQ vector search tool (`tools/faq_search.py`) was run end-to-end with
the local fallback embedding provider and correctly retrieved the "lost or
stolen card" document as the top hit for the query "what happens if I lose
my card" — confirming the Chroma indexing/retrieval pipeline works, though
see the note below on embedding quality.

## What's implemented but NOT yet run

`tests/test_conversations.py` defines 7 scripted conversations covering FAQ
lookup, balance checks with and without credentials, card locking, wrong-PIN
rejection, and greeting/clarification handling. Each case checks:

- **Task Success Rate** — did the final reply and state match expectations
- **Tool-Use Accuracy** — was the expected tool (or no tool, for
  missing-credential cases) actually invoked
- **Latency** — wall-clock time per conversation, with p50/mean/max reported

This harness makes real calls to the Anthropic API (`claude-sonnet-4-5`) and
**was not run in this build environment**, because no `ANTHROPIC_API_KEY` was
available in the sandbox used to build this project. Running it before a
demo or interview is a five-minute step:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
python tests/test_conversations.py
```

I'm noting this explicitly rather than fabricating numbers — the honest
status is "harness built and ready, not yet executed against a live model."

## Known limitation: embedding quality

The FAQ search tool defaults to `LocalHashEmbeddingProvider` (see
`tools/embeddings.py`) unless `VOYAGE_API_KEY` is set, because Voyage AI's
embedding API wasn't reachable from this build sandbox either. The local
provider is a deterministic hashing-trick bag-of-words projection — it
captures lexical overlap, not real semantic similarity. It correctly
retrieved the lost-card doc for a query that shared several literal words
with the doc's content ("lose my card" vs "Lost or Stolen Card"), but it
would likely fail on paraphrases with little lexical overlap (e.g. "someone
took my wallet" without the word "card"). Swapping in
`VoyageEmbeddingProvider` with a real `VOYAGE_API_KEY` is a one-line change
in `get_default_provider()` — no other code needs to change — and should be
done before treating this as a real semantic-search deliverable.

## Suggested next steps to fill in real numbers

1. Run `tests/test_conversations.py` with a live API key; record the
   printed Task Success Rate / Tool-Use Accuracy / latency numbers here.
2. Set `VOYAGE_API_KEY` and rebuild the FAQ index
   (`python -c "from tools.faq_search import build_index; build_index()"`),
   then re-run a handful of paraphrased FAQ queries to compare retrieval
   quality against the local fallback.
3. Expand `CASES` in `test_conversations.py` beyond 7 scenarios for a more
   statistically meaningful success-rate number before quoting it in an
   interview or on a resume.
