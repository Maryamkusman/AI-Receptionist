"""Runs one agent turn: history in, reply text out, with every step traced."""
import logging
import time
from typing import Any, Dict, List

import anthropic
from sqlalchemy.orm import Session

from .. import config
from ..integrations import messaging
from ..models import AITrace, Client, Conversation, Salon
from .prompt import dynamic_context, stable_system_prompt
from .tools import TOOL_SCHEMAS, ToolContext, ToolError, as_tool_result_text, execute_tool

log = logging.getLogger("fullchair.agent")

FALLBACK_REPLY = ("Thanks for reaching out! I've passed your message to the team and someone will get back "
                  "to you shortly.")
HISTORY_LIMIT = 30

_client = None


def _anthropic() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY, max_retries=2, timeout=60)
    return _client


def _history(conversation: Conversation) -> List[Dict[str, Any]]:
    msgs: List[Dict[str, Any]] = []
    for m in conversation.messages[-HISTORY_LIMIT:]:
        if m.sender == "system":
            continue
        role = "user" if m.direction == "in" else "assistant"
        text = m.text if m.sender != "staff" else f"[Salon staff wrote] {m.text}"
        if msgs and msgs[-1]["role"] == role:
            msgs[-1]["content"] += "\n" + text
        else:
            msgs.append({"role": role, "content": text})
    if msgs and msgs[0]["role"] == "assistant":
        msgs.insert(0, {"role": "user", "content": "[The salon messaged this client first.]"})
    return msgs


def run_claude_agent(db: Session, salon: Salon, client: Client, conversation: Conversation) -> str:
    ctx = ToolContext(db=db, salon=salon, client=client, conversation=conversation)
    stable = stable_system_prompt(db, salon)
    dynamic = dynamic_context(db, salon, client, conversation)
    system = [
        {"type": "text", "text": stable, "cache_control": {"type": "ephemeral"}},
        {"type": "text", "text": dynamic},
    ]
    messages = _history(conversation)
    trace = AITrace(salon_id=salon.id, conversation_id=conversation.id, model=config.MODEL,
                    prompt=dynamic, retrieved_context="", tool_calls=[], input_tokens=0, output_tokens=0,
                    error="")
    started = time.monotonic()
    reply = ""
    try:
        for _ in range(config.MAX_AGENT_TOOL_ROUNDS):
            response = _anthropic().beta.messages.create(
                model=config.MODEL,
                max_tokens=4000,
                system=system,
                tools=TOOL_SCHEMAS,
                messages=messages,
                output_config={"effort": "low"},
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
            )
            trace.input_tokens += response.usage.input_tokens or 0
            trace.output_tokens += response.usage.output_tokens or 0
            trace.model = response.model

            if response.stop_reason == "refusal":
                handoff = execute_tool(ctx, "handoff_to_human", {"summary": "The assistant couldn't handle this message.",
                                                                 "reason": "refusal"})
                trace.tool_calls.append({"name": "handoff_to_human", "input": {"reason": "refusal"}, "result": handoff})
                reply = FALLBACK_REPLY
                break

            text = "".join(b.text for b in response.content if b.type == "text").strip()
            tool_uses = [b for b in response.content if b.type == "tool_use"]
            if response.stop_reason != "tool_use" or not tool_uses:
                reply = text
                break

            messages.append({"role": "assistant", "content": response.content})
            results = []
            for tu in tool_uses:
                try:
                    out = execute_tool(ctx, tu.name, tu.input)
                    results.append({"type": "tool_result", "tool_use_id": tu.id, "content": as_tool_result_text(out)})
                    trace.tool_calls.append({"name": tu.name, "input": tu.input, "result": out})
                    if tu.name == "lookup_service_info":
                        trace.retrieved_context += "\n".join(out.get("results", [])) + "\n"
                except ToolError as e:
                    results.append({"type": "tool_result", "tool_use_id": tu.id, "content": str(e), "is_error": True})
                    trace.tool_calls.append({"name": tu.name, "input": tu.input, "error": str(e)})
            messages.append({"role": "user", "content": results})
        else:
            reply = reply or FALLBACK_REPLY
    except (anthropic.APIConnectionError, anthropic.RateLimitError, anthropic.APIStatusError) as e:
        # Model is down or erroring: take a message and alert the salon rather than guess.
        log.exception("agent call failed")
        trace.error = f"{type(e).__name__}: {e}"[:2000]
        conversation.handoff_flag = True
        conversation.status = "handoff"
        conversation.handoff_summary = "Assistant was unavailable — please reply to this client."
        messaging.notify_staff(db, salon, f"FullChair couldn't answer a {conversation.channel} message from "
                                          f"{client.name or client.phone or 'a client'}. Please follow up.")
        reply = FALLBACK_REPLY
    finally:
        trace.latency_ms = int((time.monotonic() - started) * 1000)
        db.add(trace)
        db.flush()

    return reply or FALLBACK_REPLY
