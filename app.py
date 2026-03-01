# app.py
import json
import sqlite3
import os
import chainlit as cl
from chainlit.input_widget import Select, Switch, Slider
from typing import List, Dict
from dotenv import load_dotenv

load_dotenv()

# Config & Modüller
import config
from utils.helpers import safe_db_call
from utils.ingestion_handler import handle_uploads
from utils.agent_engine import run_agent_loop
from utils.memory_manager import MemoryManager

# Backend & Tools
from backend.core.model_client import ModelClient
from backend.core.rag import RAGManager
from backend.ingestion.ingestor import UniversalIngestor
from backend.database.db import Database

# Tools & Registry
from backend.tools import ToolRegistry
from backend.tools.data_analyst import DataAnalystTool
from backend.tools.web_search import WebSearchTool
from backend.tools.web_scraper import WebScraperTool
from backend.tools.file_writer import FileWriterTool
from backend.tools.image_analysis import ImageAnalysisTool
from backend.tools.project_scaffolder import ProjectScaffolderTool

from chainlit.data.sql_alchemy import SQLAlchemyDataLayer

# .env'den URL'yi alıyoruz
db_url = os.getenv("CHAINLIT_DATABASE_URL")

@cl.data_layer
def setup_data_layer():
    db_url = os.getenv("CHAINLIT_DATABASE_URL")
    if db_url:
        print(f"🔌 Connecting to database: {db_url}")        
        return SQLAlchemyDataLayer(conninfo=db_url)
    return None


@cl.password_auth_callback
def auth(username, password):
    # Username boş gelirse hata almamak için kontrol
    if not username:
        return None
    # identifier olarak direkt girilen username'i veriyoruz
    return cl.User(identifier=username, name=username)

@cl.on_chat_start
async def start():
    """Uygulama başlangıcında servisleri ve session'ı ilklendirir."""
    # --- ChatSettings Tanımlama ---
    settings = await cl.ChatSettings([
        Select(
            id="Model",
            label="🤖 LLM Modeli (Ollama)",
            values=["gpt-oss:20b", "glmtest"],
            initial_value=config.MODEL_NAME,
        ),
        Switch(
            id="MultiAgent",
            label="🤝 Multi-Agent Modu",
            initial=False
        ),
        Slider(
            id="Temperature",
            label="Yaratıcılık (Temperature)",
            initial=0.7,
            min=0,
            max=1,
            step=0.1,
        ),
    ]).send()
    
    cl.user_session.set("settings", settings)
    # ------------------------------
    
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
        registry.register(WebScraperTool())
        registry.register(FileWriterTool())
        registry.register(ProjectScaffolderTool())
        registry.register(ImageAnalysisTool(model_name=config.VISION_MODEL))
        # ---------------------------

        # Session Storage
        cl.user_session.set("model", model)
        cl.user_session.set("rag", rag)
        cl.user_session.set("ingestor", ingestor)
        cl.user_session.set("db", db)
        cl.user_session.set("tool_registry", registry)
        cl.user_session.set("memory_manager", MemoryManager(max_recent_messages=10))
        cl.user_session.set("history", [])
        
        # Sidebar Geçmişi (Append özelliği için)
        cl.user_session.set("sidebar_history", [])

        # RAG Memory Reset
        rag.clear_memory()

        await cl.Message(
            content=f"👋 **Lokal Agent Hazır!**\nModel: `{config.MODEL_NAME}`\nToollar aktif: {', '.join(registry.list_tools())}"
        ).send()
        print("✅ Chat initialization complete.")
    except Exception as e:
        print(f"❌ Error during start: {e}")
        await cl.Message(content=f"⚠️ Başlatma Hatası: {str(e)}").send()

@cl.on_settings_update
async def setup_agent(settings):
    """Ayarlar güncellendiğinde servisleri yeniden yapılandırır."""
    print(f"⚙️ Ayarlar Güncellendi: {settings}")
    
    # 1. Yeni modeli session'a set et
    new_model_name = settings["Model"]
    model = ModelClient(model_name=new_model_name)
    cl.user_session.set("model", model)
    
    # 2. Ayarları session'da güncelle
    cl.user_session.set("settings", settings)
    
    await cl.Message(content=f"✅ Ayarlar güncellendi: `{new_model_name}` aktif.").send()

@cl.on_message
async def main(message: cl.Message):
    """Her yeni mesajda iş akışını koordine eder."""
    # DB instance (dosya ekleme vs için gerekebilir)
    db = cl.user_session.get("db")
    if db is None:
        db = Database()
        cl.user_session.set("db", db)

    rag = cl.user_session.get("rag")
    memory = cl.user_session.get("memory_manager")
    
    # Thread ID Chainlit'ten gelir
    thread_id = message.thread_id

    # 1. Kullanıcı mesajını hafızaya ekle (DB'ye Chainlit otomatik ekler)
    if memory:
        memory.add_message("user", message.content) 

    # 2. Dosya yüklemelerini işle
    file_hint = await handle_uploads(message, thread_id)

    # 3. RAG üzerinden ilgili dökümanları ara
    context_chunks = await cl.make_async(rag.search)(message.content, n_results=3)
    context_str = "\n---\n".join(context_chunks)
    
    # 4. Agent döngüsünü çalıştır (Düşünme -> Tool -> Yanıt)
    await run_agent_loop(
        user_query=message.content,
        context_str=context_str,
        file_hint=file_hint,
        thread_id=thread_id
    )


@cl.on_chat_resume
async def on_chat_resume(thread):
    """Sidebar'dan eski bir sohbete tıklandığında çalışır."""
    print(f"♻️ Resuming conversation: {thread['id']}")
    
    # 1. Servisleri tekrar ayağa kaldır    
    model = ModelClient(model_name=config.MODEL_NAME)
    rag = RAGManager()
    db = Database() 
    memory = MemoryManager(max_recent_messages=10)
    registry = ToolRegistry()
    
    # Toolları tekrar register et
    registry.register(DataAnalystTool())
    registry.register(WebSearchTool())
    registry.register(WebScraperTool())
    registry.register(FileWriterTool())
    registry.register(ProjectScaffolderTool())
    registry.register(ImageAnalysisTool(model_name=config.VISION_MODEL))

    # 2. Session'ı güncelle
    cl.user_session.set("model", model)
    cl.user_session.set("rag", rag)
    cl.user_session.set("db", db)
    cl.user_session.set("tool_registry", registry)
    cl.user_session.set("memory_manager", memory)
    # Thread ID session'da tutmaya gerek kalmadı, message.thread_id kullanıyoruz ama 
    # memory manager veya başka yerler için gerekirse:
    cl.user_session.set("conversation_id", thread["id"])

    # 3. Geçmişi Dönüştür ve Hafızaya Al
    history = MemoryManager.convert_thread_to_history(thread["steps"])
    cl.user_session.set("history", history)

    await cl.Message(content="📜 Sohbet geçmişini hatırladım. Devam edebiliriz!").send()