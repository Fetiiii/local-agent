import json
import asyncio
import chainlit as cl
from typing import List, Dict, Any, Optional

import config
from prompts import SYSTEM_PROMPT, PROMPT_SUPERVISOR, PROMPT_CODER, PROMPT_RESEARCHER
from utils.helpers import extract_json
from utils.tool_manager import run_tool
from utils.memory_manager import MemoryManager
from backend.core.model_client import ModelClient
from backend.core.reflection_agent import ReflectionAgent
from backend.core.schemas import AgentAction

# Structured-output schema: forces the model to emit valid AgentAction JSON.
# Computed once; passed to the model on the first attempt of each step.
AGENT_SCHEMA = AgentAction.model_json_schema()

# Defensive limits — weak models can emit a runaway `tool_calls` array (dozens of
# duplicates), which floods the sandbox and blows the context window. Bound both
# the number of calls and the size of each observation fed back to the model.
MAX_TOOL_CALLS = 8
MAX_OBS_CHARS = 8000


def _sanitize_tool_calls(tool_calls: List[Dict]) -> List[Dict]:
    """Drop duplicate/identical calls (repetition loops) and cap the count."""
    seen = set()
    clean = []
    for tc in tool_calls:
        if not isinstance(tc, dict) or not tc.get("name"):
            continue
        key = (tc.get("name"), json.dumps(tc.get("args", {}), sort_keys=True, ensure_ascii=False))
        if key in seen:
            continue
        seen.add(key)
        clean.append(tc)
        if len(clean) >= MAX_TOOL_CALLS:
            break
    return clean

# Instruction used to compose the final, user-facing answer as plain prose.
_COMPOSE_INSTRUCTION = (
    "Based on everything above, write your final answer to the user now. "
    "Reply in the user's language as clear, well-formatted prose (Markdown allowed). "
    "Do NOT output JSON and do NOT call any tools — just the answer."
)


# ── Shared helpers ───────────────────────────────────────────────────────────

async def _decide(model: ModelClient, messages: List[Dict]) -> Optional[Dict]:
    """
    Ask the model for its next AgentAction decision (non-streamed, schema-forced).

    The raw JSON is never surfaced to the UI — only the parsed thought/plan are.
    Retries without the schema if the first structured attempt fails to parse.
    """
    for attempt in range(config.RETRY_COUNT):
        try:
            raw = await model.generate(
                messages,
                stream=False,
                json_mode=(attempt == 0),
                schema=AGENT_SCHEMA if attempt == 0 else None,
            )
            decision = extract_json(raw)
            if decision:
                return decision
        except Exception as e:
            print(f"Decision generation error (attempt {attempt + 1}): {e}")
    return None


def _format_thought_plan(decision: Dict, extra: str = "") -> str:
    """Render a clean, human-readable step body from a decision (no raw JSON)."""
    parts = []
    thought = decision.get("thought")
    if thought:
        parts.append(f"**💭 Düşünce:** {thought}")
    plan = decision.get("plan") or []
    if plan:
        parts.append("**📋 Plan:**\n" + "\n".join(f"- {s}" for s in plan))
    if extra:
        parts.append(extra)
    return "\n\n".join(parts) if parts else "…"


async def _run_tool_calls(tool_calls: List[Dict], registry, label: str = "") -> str:
    """Execute tool calls in parallel and return the combined observation text."""
    prefix = f"[{label}] " if label else ""
    tool_calls = _sanitize_tool_calls(tool_calls)

    async def _exec(t_call):
        t_name = t_call.get("name")
        t_args = t_call.get("args", {}) or {}
        async with cl.Step(name=f"{prefix}🔧 {t_name}", type="tool") as t_step:
            t_step.input = json.dumps(t_args, indent=2, ensure_ascii=False)
            result = await run_tool(t_name, t_args, registry)
            t_step.output = result
            # Cap what we feed back to the model so one big result can't blow context.
            if len(result) > MAX_OBS_CHARS:
                result = result[:MAX_OBS_CHARS] + "\n… [truncated]"
            return f"### Tool '{t_name}' Result:\n{result}"

    combined = await asyncio.gather(*[_exec(t) for t in tool_calls])
    return "\n\n---\n\n".join(combined)


async def _simulate_stream(msg: "cl.Message", text: str):
    """Stream already-produced text into the message with a light typing effect."""
    # Bound the typing time regardless of length (~150 chunks max).
    chunk_size = max(24, len(text) // 150)
    for i in range(0, len(text), chunk_size):
        await msg.stream_token(text[i:i + chunk_size])
        await asyncio.sleep(0.01)


async def _stream_final_answer(model: ModelClient, messages: List[Dict], final_answer: Optional[str]) -> str:
    """
    Send the user-facing final answer.

    If the agent's decision already produced a usable `final_answer`, stream THAT
    directly — no second model call, so there's no dead-air and no double
    generation. Only when the decision left the answer empty do we compose one
    with a dedicated plain-text pass.
    """
    msg = cl.Message(content="")
    await msg.send()

    answer = (final_answer or "").strip()
    if answer:
        await _simulate_stream(msg, answer)
        await msg.update()
        return answer

    # No answer in the decision → compose one (real streamed generation).
    full = ""
    try:
        compose_messages = messages + [{"role": "user", "content": _COMPOSE_INSTRUCTION}]
        gen = await model.generate(compose_messages, stream=True, json_mode=False)
        if isinstance(gen, str):
            full = gen
            await msg.stream_token(gen)
        else:
            async for chunk in gen:
                full += chunk
                await msg.stream_token(chunk)
    except Exception as e:
        print(f"Final-answer compose error: {e}")

    full = full.strip() or "✅ Tamamlandı."
    if msg.content != full and not msg.content:
        msg.content = full
    await msg.update()
    return full


# ── Sub-agent (multi-agent mode) ─────────────────────────────────────────────

async def run_sub_agent_loop(instruction: str, role_prompt: str, sub_agent_name: str, context_str: str, file_hint: str) -> str:
    """Runs a specialized sub-agent (Coder or Researcher) until completion."""
    model: ModelClient = cl.user_session.get("model")
    registry = cl.user_session.get("tool_registry")

    current_messages = [
        {"role": "system", "content": role_prompt},
        {"role": "user", "content": f"Manager Instructions: {instruction}{file_hint}\n\nContext from Files (RAG):\n{context_str}"},
    ]

    cur_step = 0
    final_output = ""

    while cur_step < config.MAX_STEPS:
        cur_step += 1

        async with cl.Step(name=f"🤖 {sub_agent_name}", type="process") as step:
            decision = await _decide(model, current_messages)
            if not decision:
                step.output = "❌ Geçerli JSON üretemedi."
                return "❌ Sub-agent failed to produce valid JSON."

            tool_calls = decision.get("tool_calls") or []
            final_answer = decision.get("final_answer")
            step.output = _format_thought_plan(decision)

        if tool_calls:
            obs = await _run_tool_calls(tool_calls, registry, label=sub_agent_name)
            current_messages.append({"role": "assistant", "content": json.dumps(decision, ensure_ascii=False)})
            current_messages.append({"role": "user", "content": f"OBSERVATION:\n{obs}"})
        elif final_answer:
            final_output = final_answer
            break
        else:
            break

    return final_output or "❌ Sub-agent finished with no final answer."


# ── Supervisor (multi-agent mode) ────────────────────────────────────────────

async def run_supervisor_loop(user_query: str, context_str: str, file_hint: str, memory_manager: MemoryManager):
    """Multi-Agent Orchestrator Loop"""
    model: ModelClient = cl.user_session.get("model")

    profile_str = ReflectionAgent().format_profile_for_prompt()
    system_content = f"{PROMPT_SUPERVISOR}\n\n{profile_str}" if profile_str else PROMPT_SUPERVISOR

    current_messages = [{"role": "system", "content": system_content}]
    if memory_manager:
        current_messages.extend(await memory_manager.get_formatted_history())

    user_content = f"User Query: {user_query}{file_hint}\n\nContext from Files:\n{context_str}"
    current_messages.append({"role": "user", "content": user_content})

    cur_step = 0
    while cur_step < config.MAX_STEPS:
        cur_step += 1

        async with cl.Step(name="🧭 Supervisor", type="process") as step:
            decision = await _decide(model, current_messages)
            if not decision:
                step.output = "❌ Geçerli JSON üretemedi."
                await cl.Message(content="❌ Supervisor geçerli bir karar üretemedi.").send()
                return

            route_to = decision.get("route_to")
            instruction = decision.get("instruction", "")
            final_answer = decision.get("final_answer")

            extra = f"**➡️ Yönlendiriliyor:** {route_to}\n\n**📌 Görev:** {instruction}" if route_to else ""
            step.output = _format_thought_plan(decision, extra=extra)

        if route_to:
            sub_prompt = PROMPT_CODER if route_to == "CoderAgent" else PROMPT_RESEARCHER
            sub_result = await run_sub_agent_loop(instruction, sub_prompt, route_to, context_str, file_hint)
            current_messages.append({"role": "assistant", "content": json.dumps(decision, ensure_ascii=False)})
            current_messages.append({"role": "user", "content": f"Sub-Agent Observation ({route_to}):\n{sub_result}"})
        else:
            # No routing → the supervisor is done: stream the final answer.
            answer = await _stream_final_answer(model, current_messages, final_answer=final_answer)
            if memory_manager:
                memory_manager.add_message("assistant", answer)
                memory_manager.schedule_summarization()  # background, non-blocking
            break


# ── Main router ──────────────────────────────────────────────────────────────

async def run_agent_loop(user_query: str, context_str: str, file_hint: str, thread_id: str):
    """Main Agent Router: branches to Supervisor or Single-Agent mode."""
    memory_manager: MemoryManager = cl.user_session.get("memory_manager")
    settings = cl.user_session.get("settings", {})

    if settings.get("MultiAgent"):
        await run_supervisor_loop(user_query, context_str, file_hint, memory_manager)
        return

    model: ModelClient = cl.user_session.get("model")
    registry = cl.user_session.get("tool_registry")

    profile_str = ReflectionAgent().format_profile_for_prompt()
    system_content = f"{SYSTEM_PROMPT}\n\n{profile_str}" if profile_str else SYSTEM_PROMPT

    current_messages = [{"role": "system", "content": system_content}]
    if memory_manager:
        current_messages.extend(await memory_manager.get_formatted_history())

    user_content = f"User Query: {user_query}{file_hint}\n\nContext from Files (RAG):\n{context_str}"
    current_messages.append({"role": "user", "content": user_content})

    cur_step = 0
    while cur_step < config.MAX_STEPS:
        cur_step += 1

        async with cl.Step(name="🧠 Düşünüyor", type="process") as thinking_step:
            decision = await _decide(model, current_messages)
            if not decision:
                thinking_step.output = "❌ Geçerli JSON üretemedi."
                await cl.Message(content="❌ Model geçerli bir karar üretemedi. Tekrar dener misin?").send()
                break

            tool_calls = decision.get("tool_calls") or []
            final_answer = decision.get("final_answer")
            thinking_step.output = _format_thought_plan(decision)

        if tool_calls:
            obs = await _run_tool_calls(tool_calls, registry)
            current_messages.append({"role": "assistant", "content": json.dumps(decision, ensure_ascii=False)})
            current_messages.append({"role": "user", "content": f"OBSERVATION (Tool Results):\n{obs}"})
        else:
            # No tools requested → the agent is done: stream the final answer.
            answer = await _stream_final_answer(model, current_messages, final_answer=final_answer)
            if memory_manager:
                memory_manager.add_message("assistant", answer)
                memory_manager.schedule_summarization()  # background, non-blocking
            break
