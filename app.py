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
from utils.helpers import safe_db_call, get_ollama_models
from utils.ingestion_handler import handle_uploads
from utils.agent_engine import run_agent_loop
from utils.memory_manager import MemoryManager

# Backend & Tools
from backend.core.model_client import ModelClient
from backend.core.rag import RAGManager, get_rag_manager
from backend.ingestion.ingestor import UniversalIngestor
from backend.database.db import Database

# Tools & Registry
from backend.tools import ToolRegistry
from backend.tools.data_analyst import DataAnalystTool
from backend.tools.web_search import WebSearchTool
from backend.tools.web_scraper import WebScraperTool
from backend.tools.image_analysis import ImageAnalysisTool
from backend.tools.shell_executor import ShellExecutorTool

# File-Editing System (Layer 1-4)
from backend.tools.file_editing.file_reader import FileReaderTool
from backend.tools.file_editing.file_architect import FileArchitectTool
from backend.tools.file_editing.file_surgeon import FileSurgeonTool

from chainlit.data.sql_alchemy import SQLAlchemyDataLayer

# .env'den URL'yi alıyoruz
db_url = os.getenv("CHAINLIT_DATABASE_URL")

_LAST_MODEL_PATH = os.path.join("data", "memory", "last_settings.json")

def _save_last_model(thread_id: str, model_name: str):
    import json
    os.makedirs(os.path.dirname(_LAST_MODEL_PATH), exist_ok=True)
    try:
        with open(_LAST_MODEL_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        data = {}
    data[thread_id] = model_name
    with open(_LAST_MODEL_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f)

def _load_last_model(thread_id: str, default: str) -> str:
    import json
    try:
        with open(_LAST_MODEL_PATH, "r", encoding="utf-8") as f:
            return json.load(f).get(thread_id, default)
    except Exception:
        return default

def build_tool_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(DataAnalystTool())
    registry.register(WebSearchTool())
    registry.register(WebScraperTool())
    registry.register(ShellExecutorTool())
    registry.register(ImageAnalysisTool(model_name=config.VISION_MODEL))
    registry.register(FileReaderTool())
    registry.register(FileArchitectTool())
    registry.register(FileSurgeonTool())
    return registry

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
    # Ollama modellerini dinamik olarak çek
    ollama_models = await get_ollama_models()
    
    # Varsayılan model listede yoksa ekle veya listenin ilkini seç
    initial_model = config.MODEL_NAME
    if initial_model not in ollama_models:
        initial_model = ollama_models[0] if ollama_models else "hf.co/unsloth/gpt-oss-20b-GGUF:Q6_K"

    settings = await cl.ChatSettings([
        Select(
            id="Model",
            label="🤖 LLM Modeli (Ollama)",
            values=ollama_models,
            initial_value=initial_model,
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
    # --- Servisleri Başlat ---
    print("🚀 Chat starting...")
    try:
        # Servisleri başlat (seçilen veya belirlenen initial_model ile)
        model = ModelClient(model_name=initial_model)
        rag = get_rag_manager()
        ingestor = UniversalIngestor()
        db = Database()

        registry = build_tool_registry()

        # Session Storage
        cl.user_session.set("model", model)
        cl.user_session.set("rag_manager", rag)
        cl.user_session.set("ingestor", ingestor)
        cl.user_session.set("db", db)
        cl.user_session.set("tool_registry", registry)
        cl.user_session.set("memory_manager", MemoryManager(max_recent_messages=10))
        cl.user_session.set("history", [])
        
        # Sidebar Geçmişi (Append özelliği için)
        cl.user_session.set("sidebar_history", [])


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

    # 3. Seçilen modeli thread bazlı diske kaydet (resume'da geri yüklensin)
    thread_id = cl.context.session.thread_id
    if thread_id:
        _save_last_model(thread_id, new_model_name)

    await cl.Message(content=f"✅ Ayarlar güncellendi: `{new_model_name}` aktif.").send()

@cl.on_message
async def main(message: cl.Message):
    """Her yeni mesajda iş akışını koordine eder."""
    # DB instance (dosya ekleme vs için gerekebilir)
    db = cl.user_session.get("db")
    if db is None:
        db = Database()
        cl.user_session.set("db", db)

    rag = cl.user_session.get("rag_manager")
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
    last_model = _load_last_model(thread_id=thread["id"], default=config.MODEL_NAME)
    model = ModelClient(model_name=last_model)
    rag = get_rag_manager()
    db = Database() 
    memory = MemoryManager(max_recent_messages=10)
    registry = build_tool_registry()

    # 2. Session'ı güncelle
    cl.user_session.set("model", model)
    cl.user_session.set("rag_manager", rag)
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


@cl.on_chat_end
async def on_chat_end():
    """Oturum bitince sandbox konteynerini temizle."""
    try:
        from backend.tools.sandbox import sandbox, current_session_id
        await sandbox.destroy(current_session_id())
    except Exception as e:
        print(f"Sandbox cleanup error: {e}")