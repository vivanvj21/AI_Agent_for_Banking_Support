"""
Search Agent: answers FAQ/policy questions using the vector-backed
search_faq tool. Read-only, no identity verification required — anyone can
ask "what happens if I lose my card" without proving who they are.
"""

from anthropic import Anthropic
from tools.faq_search import search_faq

client = Anthropic()

TOOLS = [
    {
        "name": "search_faq",
        "description": "Search the bank's FAQ and policy documents for information relevant to a general question (not specific to a user's account).",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The user's question, or a short search phrase derived from it."},
                "k": {"type": "integer", "description": "Number of results to retrieve.", "default": 3},
            },
            "required": ["query"],
        },
    }
]

SYSTEM_PROMPT = """You are the Search Agent for a bank's customer support system.
You answer general questions about policies, account types, fraud reporting process,
interest rates, and lost/stolen card procedures using the search_faq tool.

Rules:
- Always call search_faq at least once before answering a factual question.
- Base your answer only on what search_faq returns. If the results don't cover
  the question, say you don't have that information rather than guessing.
- Keep answers concise (2-4 sentences).
- You do not have access to any specific user's account data — if asked about
  "my balance" or "my card", say that's handled by a different part of the
  system and you can only answer general policy questions.
"""


def run_search_agent(user_message: str, tool_log: list, turn: int, max_tool_iters: int = 3) -> str:
    messages = [{"role": "user", "content": user_message}]

    for _ in range(max_tool_iters):
        response = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=500,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        )

        if response.stop_reason != "tool_use":
            text_blocks = [b.text for b in response.content if b.type == "text"]
            return "\n".join(text_blocks).strip() or "I couldn't find an answer to that."

        messages.append({"role": "assistant", "content": response.content})
        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            if block.name == "search_faq":
                result = search_faq(**block.input)
                tool_log.append({
                    "turn": turn, "agent": "search_agent", "tool": "search_faq",
                    "args": block.input,
                    "result_summary": f"{len(result.get('results', []))} chunk(s) retrieved",
                })
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": str(result),
                })
        messages.append({"role": "user", "content": tool_results})

    return "I'm having trouble finding that information right now — please try rephrasing your question."
