# utils/agent_engine.py
import json
import chainlit as cl
from typing import List, Dict, Any

import config
from prompts import SYSTEM_PROMPT
from utils.helpers import extract_json, safe_db_call
from utils.tool_manager import run_tool
from backend.core.model_client import ModelClient
from backend.database.db import Database

async def run_agent_loop(
    user_query: str, 
    context_str: str, 
    file_hint: str,
    conv_id: int
):
    """
    Agent'ın ana düşünme ve tool kullanma döngüsünü yönetir.
    UI güncellemelerini ve model etkileşimini koordine eder.
    """
    model: ModelClient = cl.user_session.get("model")
    db: Database = cl.user_session.get("db")
    registry = cl.user_session.get("tool_registry")
    history: List[Dict[str, str]] = cl.user_session.get("history", [])

    # Mesaj setini hazırla
    current_messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    current_messages.extend(history[-5:]) # Son 5 mesajı hafızada tut
    
    user_content = f"User Query: {user_query}{file_hint}\n\nContext from Files (RAG):\n{context_str}"
    print(f"--- DEBUG: USER CONTENT TO MODEL ---\n{user_content}\n-----------------------------------")
    current_messages.append({"role": "user", "content": user_content})

    cur_step = 0
    while cur_step < config.MAX_STEPS:
        cur_step += 1
        
        async with cl.Step(name="Thinking", type="process") as step:
            decision = None
            response_str = ""
            
            # Model Yanıtı ve Retry Mekanizması
            for attempt in range(config.RETRY_COUNT):
                use_json_mode = (attempt == 0)
                
                try:
                    generator = await model.generate(current_messages, stream=True, json_mode=use_json_mode)
                    
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
                    print(f"Generation Error (Attempt {attempt+1}): {e}")
                    continue
            
            if not decision:
                await cl.Message(content="❌ Model geçerli bir karar veremedi (JSON Hatası).").send()
                break

            thought = decision.get("thought", "Düşünülüyor...")
            tool_name = decision.get("tool_name")
            tool_args = decision.get("tool_args", {})
            final_answer = decision.get("final_answer")
            
            step.output = thought

        # Tool Kullanımı
        if tool_name:
            async with cl.Step(name=f"Tool: {tool_name}", type="tool") as tool_step:
                tool_step.input = str(tool_args)
                result = await cl.make_async(run_tool)(tool_name, tool_args, registry)
                
                if "[IMAGE_GENERATED]:" in result:
                    text_part, img_path = result.split("[IMAGE_GENERATED]:")
                    image = cl.Image(path=img_path.strip(), name="analysis_plot", display="inline")
                    await cl.Message(content="📊 Grafik oluşturuldu:", elements=[image]).send()
                    tool_step.output = text_part
                else:
                    tool_step.output = result
            
            # Mesaj geçmişine ekle ve döngüye devam et
            current_messages.append({"role": "assistant", "content": json.dumps(decision)})
            current_messages.append({"role": "user", "content": f"Tool Output: {result}"})
        
        # Final Yanıtı
        elif final_answer:
            await cl.Message(content=final_answer).send()
            
            # Session geçmişini güncelle
            history.append({"role": "user", "content": user_query})
            history.append({"role": "assistant", "content": final_answer})
            cl.user_session.set("history", history)
            
            # DB'ye kaydet
            await safe_db_call(db.add_message, conv_id, "assistant", final_answer, meta={"thought": thought})
            break
        
        else:
            await cl.Message(content="⚠️ Model bir karar veremedi.").send()
            break
