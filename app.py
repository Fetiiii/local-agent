import json
import chainlit as cl
from typing import Dict, Any, List, Optional
import traceback

# Backend Imports
from backend.core.model_client import ModelClient
from backend.core.rag import RAGManager
from backend.ingestion.ingestor import UniversalIngestor
from backend.database.db import Database
from backend.tools.web_search import WebSearchTool

# --- Configuration ---
MODEL_NAME = "gpt-oss:20b"

# --- System Prompt ---
SYSTEM_PROMPT = """You are a smart AI assistant capable of reasoning and using tools.
You have access to a local knowledge base (RAG) containing files uploaded by the user.
Always check the context provided in the prompt for answers from files.

You must reply in valid JSON format ONLY. Do not write anything outside the JSON object.

Structure:
{
    "thought": "Your reasoning process here...",
    "tool_name": "name of the tool to use (or null if replying to user)",
    "tool_args": { "arg_name": "value" },
    "final_answer": "Your response to the user (only if tool_name is null)"
}

Available Tools:
1. web_search: Search the internet. Args: {"query": "string"}
2. calculate: Evaluate mathematical expressions. Args: {"expression": "string"}

If you have enough information (from context or general knowledge), set "tool_name": null and provide "final_answer".
"""

# --- Tools Helper ---
def run_tool(name: str, args: Dict) -> str:
    if name == "web_search":
        tool = WebSearchTool()
        return str(tool.run(query=args.get("query", "")))
    elif name == "calculate":
        try:
            return str(eval(args.get("expression", "0"), {"__builtins__": None}, {{}}))
        except Exception as e:
            return f"Error: {e}"
    return "Tool not found."

# --- App Lifecycle ---

@cl.on_chat_start
async def start():
    # 1. Initialize Components
    model = ModelClient(model_name=MODEL_NAME)
    rag = RAGManager()
    ingestor = UniversalIngestor()
    db = Database() # Veritabanı bağlantısı

    # 2. Store in Session
    cl.user_session.set("model", model)
    cl.user_session.set("rag", rag)
    cl.user_session.set("ingestor", ingestor)
    cl.user_session.set("db", db)
    
    # 3. Create or Resume Conversation
    try:
        conv_id = db.create_conversation(title="New Chat")
        cl.user_session.set("conversation_id", conv_id)
    except Exception as e:
        print(f"DB Init Error: {e}")
        cl.user_session.set("conversation_id", 0)
    
    # 4. Memory (History) & Reset RAG
    cl.user_session.set("history", [])
    rag.clear_memory()

    await cl.Message(content=f"👋 **Lokal Agent Hazır!**\nModel: `{MODEL_NAME}`\nDosyaları sürükleyip bırakabilirsiniz.").send()

@cl.on_message
async def main(message: cl.Message):
    model: ModelClient = cl.user_session.get("model")
    rag: RAGManager = cl.user_session.get("rag")
    ingestor: UniversalIngestor = cl.user_session.get("ingestor")
    db: Database = cl.user_session.get("db")
    conv_id = cl.user_session.get("conversation_id")
    history: List[Dict] = cl.user_session.get("history")

    # --- 0. Save User Message to DB ---
    try:
        db.add_message(conv_id, "user", message.content)
    except Exception as e:
        print(f"❌ DB Save Error (User): {e}")

    # --- 1. File Handling (Ingestion) ---
    if message.elements:
        processing_msg = cl.Message(content="📂 Dosyalar işleniyor...", author="System")
        await processing_msg.send()
        
        count = 0
        for element in message.elements:
            path = element.path
            if path:
                # Parse
                markdown_text = ingestor.ingest_file(path)
                if markdown_text:
                    # RAG Indexing
                    chunks = rag.add_document(markdown_text, source=element.name)
                    count += chunks
                    # DB'ye dosya kaydı
                    try:
                        db.add_file(conv_id, path, ftype="file", summary=f"Imported {element.name}")
                    except: pass
        
        processing_msg.content = f"✅ {len(message.elements)} dosya okundu ve {count} parça hafızaya eklendi."
        await processing_msg.update()

    # --- 2. Context Retrieval (RAG) ---
    context_chunks = rag.search(message.content, n_results=3)
    context_str = "\n---\n".join(context_chunks)
    
    # --- 3. Prompt Construction ---
    current_messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    current_messages.extend(history[-5:])
    
    user_content = f"User Query: {message.content}\n\nContext from Files:\n{context_str}"
    current_messages.append({"role": "user", "content": user_content})

    # --- 4. ReAct Loop ---
    MAX_STEPS = 5
    cur_step = 0
    
    while cur_step < MAX_STEPS:
        cur_step += 1
        print(f"🔄 Step {cur_step} started...")
        
        async with cl.Step(name="Thinking", type="process") as step:
            step.input = "Reasoning..."
            
            # Generate JSON (ASYNC WRAPPER)
            # cl.make_async blocking işlemi ayrı thread'de çalıştırır.
            response_json_str = await cl.make_async(model.generate)(
                current_messages, 
                stream=False, 
                json_mode=True
            )
            
            print(f"DEBUG Raw Output:\n{response_json_str[:100]}...") # İlk 100 karakteri bas
            
            try:
                clean_json = response_json_str.strip()
                if clean_json.startswith("```json"):
                    clean_json = clean_json.split("```json")[1].split("```")[0].strip()
                elif clean_json.startswith("```"):
                     clean_json = clean_json.split("```")[1].split("```")[0].strip()
                
                decision = json.loads(clean_json)
            except json.JSONDecodeError as e:
                print(f"❌ JSON Parse Error: {e}")
                step.output = "JSON Parse Error."
                await cl.Message(content=f"Model error: Invalid JSON.\nRaw: {response_json_str}").send()
                break

            thought = decision.get("thought", "")
            tool_name = decision.get("tool_name")
            tool_args = decision.get("tool_args", {})
            final_answer = decision.get("final_answer")

            step.output = thought or "Done."

        # Action Handling
        if tool_name:
            print(f"🛠 Tool Call: {tool_name}")
            async with cl.Step(name=f"Tool: {tool_name}", type="tool") as tool_step:
                tool_step.input = str(tool_args)
                result = run_tool(tool_name, tool_args)
                tool_step.output = result
            
            current_messages.append({"role": "assistant", "content": response_json_str})
            current_messages.append({"role": "user", "content": f"Tool Output: {result}"})
        
        elif final_answer:
            print(f"✅ Final Answer Reached. Sending to UI...")
            # ÖNCE UI'a gönder
            await cl.Message(content=final_answer).send()
            
            # Update History
            history.append({"role": "user", "content": message.content})
            history.append({"role": "assistant", "content": final_answer})
            cl.user_session.set("history", history)
            
            # SONRA DB'ye kaydet
            try:
                db.add_message(conv_id, "assistant", final_answer, meta={"thought": thought})
                print("💾 Saved to DB.")
            except Exception as e:
                print(f"❌ DB Save Error (Assistant): {e}")
            
            break
        
        else:
            print("⚠️ No decision made.")
            await cl.Message(content="Model bir karar veremedi.").send()
            break