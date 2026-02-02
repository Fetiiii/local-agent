# app.py
import chainlit as cl
from typing import List, Dict

# Config & Modüller
import config
from utils.helpers import safe_db_call
from utils.ingestion_handler import handle_uploads
from utils.agent_engine import run_agent_loop

# Backend & Tools
from backend.core.model_client import ModelClient
from backend.core.rag import RAGManager
from backend.ingestion.ingestor import UniversalIngestor
from backend.database.db import Database

# Tools & Registry
from backend.tools import ToolRegistry
from backend.tools.data_analyst import DataAnalystTool
from backend.tools.web_search import WebSearchTool
from backend.tools.file_writer import FileWriterTool
from backend.tools.image_analysis import ImageAnalysisTool

@cl.on_chat_start
async def start():
    """Uygulama başlangıcında servisleri ve session'ı ilklendirir."""
    print("🚀 Chat starting...")
    try:
        # Servisleri başlat
        model = ModelClient(model_name=config.MODEL_NAME)
        rag = RAGManager()
        ingestor = UniversalIngestor()
        db = Database()

        # --- Tool Registry Setup ---
        registry = ToolRegistry()
        registry.register(DataAnalystTool())
        registry.register(WebSearchTool())
        registry.register(FileWriterTool())
        registry.register(ImageAnalysisTool(model_name=config.VISION_MODEL))
        # ---------------------------

        # Session Storage
        cl.user_session.set("model", model)
        cl.user_session.set("rag", rag)
        cl.user_session.set("ingestor", ingestor)
        cl.user_session.set("db", db)
        cl.user_session.set("tool_registry", registry) # YENİ: Registry kullanımı
        cl.user_session.set("history", [])
        
        # DB Conversation Init
        conv_id = await safe_db_call(db.create_conversation, title="New Chat")
        cl.user_session.set("conversation_id", conv_id or 0)
        
        # RAG Memory Reset
        rag.clear_memory()

        await cl.Message(
            content=f"👋 **Lokal Agent Hazır!**\nModel: `{config.MODEL_NAME}`\nToollar aktif: {', '.join(registry.list_tools())}"
        ).send()
        print("✅ Chat initialization complete.")
    except Exception as e:
        print(f"❌ Error during start: {e}")
        await cl.Message(content=f"⚠️ Başlatma Hatası: {str(e)}").send()

@cl.on_message
async def main(message: cl.Message):
    """Her yeni mesajda iş akışını koordine eder."""
    db = cl.user_session.get("db")
    rag = cl.user_session.get("rag")
    conv_id = cl.user_session.get("conversation_id")

    # 1. Kullanıcı mesajını kaydet
    await safe_db_call(db.add_message, conv_id, "user", message.content)

    # 2. Dosya yüklemelerini işle
    file_hint = await handle_uploads(message, conv_id)

    # 3. RAG üzerinden ilgili dökümanları ara
    context_chunks = await cl.make_async(rag.search)(message.content, n_results=3)
    context_str = "\n---\n".join(context_chunks)
    
    # 4. Agent döngüsünü çalıştır (Düşünme -> Tool -> Yanıt)
    await run_agent_loop(
        user_query=message.content,
        context_str=context_str,
        file_hint=file_hint,
        conv_id=conv_id
    )