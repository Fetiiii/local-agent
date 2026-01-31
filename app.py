import json
import chainlit as cl
from typing import Dict, Any, List, Optional
import traceback
import re

# Backend Imports
from backend.core.model_client import ModelClient
from backend.core.rag import RAGManager
from backend.ingestion.ingestor import UniversalIngestor
from backend.database.db import Database

# Tools Imports
from backend.tools.web_search import WebSearchTool
from backend.tools.data_analyst import DataAnalystTool
from backend.tools.file_writer import FileWriterTool
from backend.tools.image_analysis import ImageAnalysisTool

# --- Configuration ---
MODEL_NAME = "glm4.7-flash:latest"  
VISION_MODEL = "qwen3-vl:2b" 
RETRY_COUNT = 3

# --- System Prompt (GÜÇLENDİRİLMİŞ) ---
SYSTEM_PROMPT = """You are a capable AI assistant with access to tools.
You MUST output strictly in JSON format.

CONTEXT:
- You have a RAG system that AUTOMATICALLY reads uploaded files. DO NOT write code to read PDFs/DOCX. Use the provided context.

TOOL DEFINITIONS & ARGUMENTS:
1. 'data_analyst': Use ONLY for analyzing data, calculating stats, or PLOTTING graphs.
   Args: {"code": "python_code_here"}
2. 'file_writer': Use to save reports, code, or texts to a permanent file.
   Args: {"filename": "example.txt", "content": "text_content_here"}
3. 'web_search': Search the internet for real-time information.
   Args: {"query": "search_term_here"}
4. 'image_analysis': Use to analyze uploaded images (photos, charts, screenshots).
   Args: {"image_path": "path_to_image", "prompt": "question_about_image"}

OUTPUT FORMAT (Strict JSON):
{
    "thought": "Reasoning about why you are using a tool or how you answer.",
    "tool_name": "data_analyst" OR "web_search" OR "file_writer" OR "image_analysis" OR null,
    "tool_args": { ... },
    "final_answer": "Answer to user (MUST BE NULL IF TOOL_NAME IS USED)"
}
"""

# --- Tools Helper ---
def run_tool(name: str, args: Dict, session_tools: Dict) -> str:
    if name == "web_search":
        tool = WebSearchTool()
        return str(tool.run(query=args.get("query", "")))
    
    elif name == "file_writer":
        tool = FileWriterTool()
        return tool.run(filename=args.get("filename"), content=args.get("content"))
    
    elif name == "image_analysis":
        tool = ImageAnalysisTool(model_name=VISION_MODEL)
        # Model 'image_path' veya sadece 'path' göndermiş olabilir
        img_path = args.get("image_path") or args.get("path")
        
        # --- UUID Hallucination Fix ---
        # Eğer modelin verdiği yol bulunamazsa ama hafızada taze bir resim varsa onu kullan
        import os
        if (not img_path or not os.path.exists(img_path)) and cl.user_session.get("last_image_path"):
            img_path = cl.user_session.get("last_image_path")
            
        return tool.run(image_path=img_path, prompt=args.get("prompt", "Describe this image."))
    
    elif name == "data_analyst":
        tool = session_tools.get("data_analyst")
        if tool:
            return tool.run(code=args.get("code", ""))
        else:
            return "Error: Data Analyst tool not initialized."
            
    return "Tool not found."

def extract_json(text: str) -> Optional[Dict]:
    """JSON veya Python Code Block yakalar."""
    text = text.strip()
    
    # 1. Temiz JSON
    try: return json.loads(text)
    except: pass

    # 2. Markdown JSON
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        try: return json.loads(match.group(1))
        except: pass
    
    # 3. Fallback: Eğer model direkt Python kodu yazdıysa, onu tool call'a çevir
    # Örn: ```python ... ```
    code_match = re.search(r"```(?:python)?\s*(.*?)\s*```", text, re.DOTALL)
    if code_match:
        code = code_match.group(1)
        # Eğer kod çok kısaysa (örn: "json") yoksay
        if len(code) > 20 and ("import" in code or "print" in code or "plt." in code):
            return {
                "thought": "Model generated code directly. Auto-wrapping in data_analyst.",
                "tool_name": "data_analyst",
                "tool_args": {"code": code},
                "final_answer": None
            }

    # 4. Süslü parantez aralığı
    match = re.search(r"(\{.*\})", text, re.DOTALL)
    if match:
        try: return json.loads(match.group(1))
        except: pass
        
    return None

# --- App Lifecycle ---

@cl.on_chat_start
async def start():
    model = ModelClient(model_name=MODEL_NAME)
    rag = RAGManager()
    ingestor = UniversalIngestor()
    db = Database()
    data_analyst = DataAnalystTool() 

    cl.user_session.set("model", model)
    cl.user_session.set("rag", rag)
    cl.user_session.set("ingestor", ingestor)
    cl.user_session.set("db", db)
    cl.user_session.set("tools", {"data_analyst": data_analyst})
    
    try:
        conv_id = db.create_conversation(title="New Chat")
        cl.user_session.set("conversation_id", conv_id)
    except Exception as e:
        print(f"DB Init Error: {e}")
        cl.user_session.set("conversation_id", 0)
    
    cl.user_session.set("history", [])
    rag.clear_memory()

    await cl.Message(content=f"👋 **Lokal Agent Hazır!**\nModel: `{MODEL_NAME}`\nToollar: `Data Analyst`, `File Writer`, `Web Search`").send()

@cl.on_message
async def main(message: cl.Message):
    model: ModelClient = cl.user_session.get("model")
    rag: RAGManager = cl.user_session.get("rag")
    ingestor: UniversalIngestor = cl.user_session.get("ingestor")
    db: Database = cl.user_session.get("db")
    tools_map = cl.user_session.get("tools")
    conv_id = cl.user_session.get("conversation_id")
    history: List[Dict] = cl.user_session.get("history")

    try: db.add_message(conv_id, "user", message.content)
    except: pass

    # Ingestion
    if message.elements:
        processing_msg = cl.Message(content="📂 Dosyalar işleniyor...", author="System")
        await processing_msg.send()
        count = 0
        for element in message.elements:
            path = element.path
            if path:
                # Resim dosyalarını RAG'e (ingestor) sokma
                ext = path.lower().split('.')[-1]
                if ext in ['png', 'jpg', 'jpeg', 'webp']:
                    continue

                markdown_text = ingestor.ingest_file(path)
                if markdown_text:
                    chunks = await cl.make_async(rag.add_document)(markdown_text, source=element.name)
                    count += chunks
                    try: db.add_file(conv_id, path, ftype="file", summary=f"Imported {element.name}")
                    except: pass
        processing_msg.content = f"✅ {len(message.elements)} dosya okundu. (Analiz için: `{message.elements[0].path}`)"
        await processing_msg.update()

    # RAG Context
    context_chunks = await cl.make_async(rag.search)(message.content, n_results=3)
    context_str = "\n---\n".join(context_chunks)
    
    current_messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    current_messages.extend(history[-5:])
    
    file_hint = ""
    if message.elements:
        element = message.elements[0]
        ext = element.name.lower().split('.')[-1]
        if ext in ['png', 'jpg', 'jpeg', 'webp']:
             # UUID hatasını (hallucination) önlemek için session'a kaydet
             cl.user_session.set("last_image_path", element.path)
             file_hint = f"\n[SYSTEM HINT]: An image was uploaded at '{element.path}'. Use 'image_analysis' tool to understand it."
        else:
             file_hint = f"\n[SYSTEM HINT]: Last uploaded file path is: '{element.path}'. Use this path for tools if needed."

    user_content = f"User Query: {message.content}{file_hint}\n\nContext from Files (RAG):\n{context_str}"
    current_messages.append({"role": "user", "content": user_content})

    MAX_STEPS = 5
    cur_step = 0
    
    while cur_step < MAX_STEPS:
        cur_step += 1
        
        async with cl.Step(name="Thinking", type="process") as step:
            step.input = "Reasoning..."
            
            decision = None
            response_str = ""
            
            for attempt in range(RETRY_COUNT):
                use_json_mode = (attempt == 0)
                mode_str = "JSON" if use_json_mode else "TEXT"
                print(f"🔄 Attempt {attempt+1} ({mode_str})...")

                response_str = ""
                generator = await model.generate(
                    current_messages, 
                    stream=True, 
                    json_mode=use_json_mode
                )
                
                if isinstance(generator, str):
                    response_str = generator
                    await step.stream_token(response_str)
                else:
                    async for chunk in generator:
                        response_str += chunk
                        await step.stream_token(chunk)
                
                print(f"DEBUG Output: {response_str[:100]}...")
                
                if not response_str:
                    continue
                
                decision = extract_json(response_str)
                if decision:
                    break
            
            if not decision:
                step.output = "Failed to parse model decision."
                await cl.Message(content=f"❌ Model karar veremedi (JSON parse hatası).").send()
                break

            thought = decision.get("thought", "")
            tool_name = decision.get("tool_name")
            tool_args = decision.get("tool_args", {})
            final_answer = decision.get("final_answer")

            # Step çıktısını sadece thought ile güncelle (temizlik için)
            step.output = thought or "Decision made."

        # Action Handling
        if tool_name:
            async with cl.Step(name=f"Tool: {tool_name}", type="tool") as tool_step:
                tool_step.input = str(tool_args)
                result = run_tool(tool_name, tool_args, tools_map)
                
                if "[IMAGE_GENERATED]:" in result:
                    text_part, img_path = result.split("[IMAGE_GENERATED]:")
                    img_path = img_path.strip()
                    image = cl.Image(path=img_path, name="analysis_plot", display="inline")
                    await cl.Message(content="📊 Grafik oluşturuldu:", elements=[image]).send()
                    tool_step.output = text_part
                else:
                    tool_step.output = result
            
            current_messages.append({"role": "assistant", "content": json.dumps(decision)})
            current_messages.append({"role": "user", "content": f"Tool Output: {result}"})
        
        elif final_answer:
            await cl.Message(content=final_answer).send()
            
            history.append({"role": "user", "content": message.content})
            history.append({"role": "assistant", "content": final_answer})
            cl.user_session.set("history", history)
            
            try: db.add_message(conv_id, "assistant", final_answer, meta={"thought": thought})
            except: pass
            break
        
        else:
            await cl.Message(content="Model bir karar veremedi.").send()
            break
