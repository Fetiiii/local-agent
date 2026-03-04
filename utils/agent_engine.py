import json
import asyncio
import chainlit as cl
from typing import List, Dict, Any

import config
from prompts import SYSTEM_PROMPT, PROMPT_SUPERVISOR, PROMPT_CODER, PROMPT_RESEARCHER
from utils.helpers import extract_json
from utils.tool_manager import run_tool
from utils.memory_manager import MemoryManager
from backend.core.model_client import ModelClient
from backend.core.reflection_agent import ReflectionAgent

async def run_sub_agent_loop(instruction: str, role_prompt: str, sub_agent_name: str, context_str: str, file_hint: str) -> str:
    """Runs a specialized sub-agent (Coder or Researcher) until completion."""
    model: ModelClient = cl.user_session.get("model")
    registry = cl.user_session.get("tool_registry")
    
    current_messages = [
        {"role": "system", "content": role_prompt},
        {"role": "user", "content": f"Manager Instructions: {instruction}{file_hint}\n\nContext from Files (RAG):\n{context_str}"}
    ]
    
    cur_step = 0
    final_output = ""
    
    while cur_step < config.MAX_STEPS:
        cur_step += 1
        
        async with cl.Step(name=f"Sub-Agent: {sub_agent_name}", type="process") as step:
            decision = None
            response_str = ""
            for attempt in range(config.RETRY_COUNT):
                try:
                    generator = await model.generate(current_messages, stream=True, json_mode=(attempt == 0))
                    response_str = ""
                    if isinstance(generator, str):
                        response_str = generator
                        await step.stream_token(response_str)
                    else:
                        async for chunk in generator:
                            response_str += chunk
                            await step.stream_token(chunk)
                    
                    decision = extract_json(response_str)
                    if decision:
                        break
                except Exception as e:
                    print(f"Sub-Agent error (attempt {attempt+1}): {e}")
            
            if not decision:
                return "❌ Sub-agent failed to produce valid JSON."
                
            thought = decision.get("thought", "Thinking...")
            tool_calls = decision.get("tool_calls", [])
            final_answer = decision.get("final_answer")
            
            step.output = f"**THOUGHT:** {thought}\n"

        if tool_calls:
            tasks = []
            async def execute_tool(t_call):
                t_name, t_args = t_call.get("name"), t_call.get("args", {})
                async with cl.Step(name=f"[{sub_agent_name}] Tool: {t_name}", type="tool") as t_step:
                    t_step.input = json.dumps(t_args, indent=2)
                    result = await run_tool(t_name, t_args, registry)
                    t_step.output = result
                    return f"### Tool '{t_name}' Result:\n{result}"

            tasks = [execute_tool(t) for t in tool_calls]
            combined = await asyncio.gather(*tasks)
            obs = "\n\n---\n\n".join(combined)
            
            current_messages.append({"role": "assistant", "content": json.dumps(decision)})
            current_messages.append({"role": "user", "content": f"OBSERVATION:\n{obs}"})
            
        elif final_answer:
            final_output = final_answer
            break
        else:
            break
            
    return final_output or "❌ Sub-agent finished with no final answer."

async def run_supervisor_loop(user_query: str, context_str: str, file_hint: str, memory_manager: MemoryManager):
    """Multi-Agent Orchestrator Loop"""
    model: ModelClient = cl.user_session.get("model")
    
    # Load long-term profile
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
        
        async with cl.Step(name="Supervisor Manager", type="process") as step:
            decision = None
            for attempt in range(config.RETRY_COUNT):
                try:
                    generator = await model.generate(current_messages, stream=True, json_mode=(attempt == 0))
                    response_str = ""
                    if isinstance(generator, str):
                        response_str = generator
                        await step.stream_token(response_str)
                    else:
                        async for chunk in generator:
                            response_str += chunk
                            await step.stream_token(chunk)
                    
                    decision = extract_json(response_str)
                    if decision: break
                except Exception as e:
                    print(f"Supervisor error: {e}")
            
            if not decision:
                await cl.Message(content="❌ Supervisor failed valid JSON.").send()
                break
                
            thought = decision.get("thought", "")
            route_to = decision.get("route_to")
            instruction = decision.get("instruction", "")
            final_answer = decision.get("final_answer")
            
            step.output = f"**THOUGHT:** {thought}\n"
            if route_to:
                step.output += f"**ROUTING TO:** {route_to}\n**INSTRUCTION:** {instruction}"
                
        if route_to:
            sub_prompt = PROMPT_CODER if route_to == "CoderAgent" else PROMPT_RESEARCHER
            sub_result = await run_sub_agent_loop(instruction, sub_prompt, route_to, context_str, file_hint)
            
            current_messages.append({"role": "assistant", "content": json.dumps(decision)})
            current_messages.append({"role": "user", "content": f"Sub-Agent Observation ({route_to}):\n{sub_result}"})
            
        elif final_answer:
            await cl.Message(content=final_answer).send()
            if memory_manager:
                memory_manager.add_message("assistant", final_answer)
            break
        else:
            break

async def run_agent_loop(
    user_query: str, 
    context_str: str, 
    file_hint: str,
    thread_id: str
):
    """
    Main Agent Router: Branches to Supervisor or Single Agent Mode.
    """
    memory_manager: MemoryManager = cl.user_session.get("memory_manager")
    settings = cl.user_session.get("settings", {})
    
    if settings.get("MultiAgent"):
        await run_supervisor_loop(user_query, context_str, file_hint, memory_manager)
        return

    model: ModelClient = cl.user_session.get("model")
    registry = cl.user_session.get("tool_registry")
    
    # --- Original Single Agent Logic Starts Here ---
    # Load long-term profile
    profile_str = ReflectionAgent().format_profile_for_prompt()
    system_content = f"{SYSTEM_PROMPT}\n\n{profile_str}" if profile_str else SYSTEM_PROMPT

    current_messages = [{"role": "system", "content": system_content}]
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
            tasks = []
            
            async def execute_and_report(t_call):
                t_name = t_call.get("name")
                t_args = t_call.get("args", {})
                
                async with cl.Step(name=f"Tool: {t_name}", type="tool") as tool_step:
                    tool_step.input = json.dumps(t_args, indent=2)
                    result = await run_tool(t_name, t_args, registry)
                    tool_step.output = result
                    return f"### Tool '{t_name}' Result:\n{result}"

            tasks = [execute_and_report(t) for t in tool_calls]
            combined_results = await asyncio.gather(*tasks)
            
            all_observations = "\n\n---\n\n".join(combined_results)
            
            current_messages.append({"role": "assistant", "content": json.dumps(decision)})
            current_messages.append({"role": "user", "content": f"OBSERVATION (Tool Results):\n{all_observations}"})
        
        # 4. Handle Final Answer
        elif final_answer:
            await cl.Message(content=final_answer).send()
            
            if memory_manager:
                memory_manager.add_message("assistant", final_answer)
            
            break # Exit loop
        
        else:
            break
