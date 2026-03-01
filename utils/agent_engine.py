# utils/agent_engine.py
import json
import asyncio
import chainlit as cl
from typing import List, Dict, Any

import config
from prompts import SYSTEM_PROMPT
from utils.helpers import extract_json
from utils.tool_manager import run_tool
from utils.memory_manager import MemoryManager
from backend.core.model_client import ModelClient

async def run_agent_loop(
    user_query: str, 
    context_str: str, 
    file_hint: str,
    thread_id: str
):
    """
    Main Agent Loop: Supports Parallel Tool Calling & Planning.
    """
    model: ModelClient = cl.user_session.get("model")
    registry = cl.user_session.get("tool_registry")
    memory_manager: MemoryManager = cl.user_session.get("memory_manager")

    # Initial Messages
    current_messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    if memory_manager:
        formatted_history = await memory_manager.get_formatted_history()
        current_messages.extend(formatted_history)
    
    user_content = f"User Query: {user_query}{file_hint}\n\nContext from Files (RAG):\n{context_str}"
    current_messages.append({"role": "user", "content": user_content})

    cur_step = 0
    while cur_step < config.MAX_STEPS:
        cur_step += 1
        
        async with cl.Step(name="Thinking", type="process") as thinking_step:
            decision = None
            response_str = ""
            
            # 1. Model Generation with Retry
            for attempt in range(config.RETRY_COUNT):
                try:
                    generator = await model.generate(current_messages, stream=True, json_mode=(attempt == 0))
                    
                    response_str = ""
                    if isinstance(generator, str):
                        response_str = generator
                        await thinking_step.stream_token(response_str)
                    else:
                        async for chunk in generator:
                            response_str += chunk
                            await thinking_step.stream_token(chunk)
                    
                    decision = extract_json(response_str)
                    if decision:
                        break
                except Exception as e:
                    print(f"Generation Error (Attempt {attempt+1}): {e}")
                    continue
            
            if not decision:
                await cl.Message(content="❌ Model failed to provide a valid JSON decision.").send()
                break

            # 2. Extract Plan & Thought
            thought = decision.get("thought", "Thinking...")
            plan = decision.get("plan", [])
            tool_calls = decision.get("tool_calls", [])
            final_answer = decision.get("final_answer")
            
            # Show plan in UI if it exists
            plan_str = "\n".join([f"- {s}" for s in plan]) if plan else ""
            thinking_step.output = f"**THOUGHT:** {thought}\n\n**PLAN:**\n{plan_str}" if plan_str else thought

        # 3. Handle Parallel Tool Execution
        if tool_calls:
            # Create a list of async tool execution tasks
            tasks = []
            
            # Each tool execution gets its own UI step
            async def execute_and_report(t_call):
                t_name = t_call.get("name")
                t_args = t_call.get("args", {})
                
                async with cl.Step(name=f"Tool: {t_name}", type="tool") as tool_step:
                    tool_step.input = json.dumps(t_args, indent=2)
                    result = await run_tool(t_name, t_args, registry)
                    tool_step.output = result
                    return f"### Tool '{t_name}' Result:\n{result}"

            # Run all tools in parallel using asyncio.gather
            # We wrap them in tasks to execute them concurrently
            tasks = [execute_and_report(t) for t in tool_calls]
            combined_results = await asyncio.gather(*tasks)
            
            all_observations = "\n\n---\n\n".join(combined_results)
            
            # Add to conversation history
            # We record what the assistant said (the JSON decision) and what happened (tool outputs)
            current_messages.append({"role": "assistant", "content": json.dumps(decision)})
            current_messages.append({"role": "user", "content": f"OBSERVATION (Tool Results):\n{all_observations}"})
        
        # 4. Handle Final Answer
        elif final_answer:
            await cl.Message(content=final_answer).send()
            
            # Update Memory (RAM) for next user message
            if memory_manager:
                memory_manager.add_message("assistant", final_answer)
            
            break # Exit loop
        
        else:
            # If model produced no tool calls and no final answer
            break
