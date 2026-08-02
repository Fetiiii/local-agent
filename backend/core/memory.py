"""
Headless 3-tier memory for the agent core:
  • short-term  → ctx.history (trimmed to MAX_RECENT in the prompt)
  • mid-term    → rolling summary (ctx.state["summary"]) + episodic store (RAG)
  • long-term   → user profile (ReflectionAgent), injected into the system prompt

Summarization runs in the background (see run_agent) so it never blocks a turn.
"""

from __future__ import annotations

from datetime import datetime

from backend.core.reflection_agent import ReflectionAgent

MAX_RECENT = 10          # raw messages kept in the prompt
SUMMARIZE_THRESHOLD = 16  # summarize once history grows past this


def system_prompt_with_memory(base: str, summary: str) -> str:
    """Augment the base system prompt with the long-term profile and rolling summary."""
    parts = [base]
    profile = ReflectionAgent().format_profile_for_prompt()
    if profile:
        parts.append(profile)
    if summary:
        parts.append(f"📝 ÖNCEKİ KONUŞMA ÖZETİ:\n{summary}\n--- Özet sonu ---")
    return "\n\n".join(parts)


async def summarize_if_needed(ctx):
    """Condense old history into the rolling summary + episodic memory + profile."""
    if len(ctx.history) <= SUMMARIZE_THRESHOLD:
        return
    n = len(ctx.history) - MAX_RECENT
    old = ctx.history[:n]
    convo = "\n".join(f"{m.get('role', '?').upper()}: {m.get('content', '')}" for m in old)
    current = ctx.state.get("summary", "")
    prompt = (
        "You are a memory manager. Merge the current summary with the new lines into a "
        "single concise updated summary. Keep key facts, names, file names, decisions and "
        "user preferences. Output ONLY the summary text.\n\n"
        f"Current summary:\n{current or '(none)'}\n\nNew lines:\n{convo}"
    )
    try:
        new_summary = await ctx.model.generate(
            [{"role": "user", "content": prompt}], stream=False, json_mode=False)
        ctx.state["summary"] = (new_summary or "").strip()
        # Race-safe: drop exactly the n messages we summarized (history may have grown).
        del ctx.history[:n]
    except Exception as e:  # noqa: BLE001
        print(f"Summarization error: {e}")
        return

    if ctx.rag is not None:
        try:
            ctx.rag.add_episodic_memory(convo, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        except Exception as e:  # noqa: BLE001
            print(f"Episodic memory error: {e}")
    try:
        await ReflectionAgent().extract_and_update(convo, model=ctx.model)
    except Exception as e:  # noqa: BLE001
        print(f"Reflection error: {e}")
