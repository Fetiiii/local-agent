import asyncio
import ollama

MODEL = 'gpt-oss:20b'

SHARED_FORMAT = """Reply with JSON containing:
- "thought": your step-by-step reasoning
- "tool_calls": a list of tool calls to execute, each with "name" and "args" keys
- "final_answer": your findings string when fully done, otherwise an empty string

Rules:
- Use tool_calls to call tools by name until the task is complete.
- When done, set tool_calls to [] and put your findings in final_answer."""

MANIFEST = """Available tools (use these exact names in tool_calls):
- Name: search_web | Args: {"query": "<search query>"}
- Name: scrape_url | Args: {"url": "<full URL>"}"""

USER_MSG = f"{MANIFEST}\n\nManager Instructions: Search for the latest Python version.\n\nIMPORTANT: Reply with a single JSON object only."

async def test(label, system):
    print(f"\n{'='*50}\nTEST: {label}")
    r = await ollama.AsyncClient().chat(
        model=MODEL,
        messages=[{'role': 'system', 'content': system}, {'role': 'user', 'content': USER_MSG}]
    )
    s = r['message']['content']
    print(f"LENGTH: {len(s)}")
    print(f"RESPONSE: {repr(s[:200])}")

async def main():
    await test("A. RESEARCHER AGENT",  f"You are the RESEARCHER AGENT. {SHARED_FORMAT}")
    await test("B. CODER AGENT",       f"You are the CODER AGENT. {SHARED_FORMAT}")
    await test("C. DATA AGENT",        f"You are the DATA AGENT. {SHARED_FORMAT}")
    await test("D. ANALYST AGENT",     f"You are the ANALYST AGENT. {SHARED_FORMAT}")
    await test("E. No role label",     f"{SHARED_FORMAT}")

if __name__ == "__main__":
    asyncio.run(main())
