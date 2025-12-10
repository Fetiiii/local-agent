from __future__ import annotations

import json
import re
import logging
import os
from pathlib import Path

from flask import Flask, request, jsonify
from flask_cors import CORS

# Backend modülleri
import backend.tools 
from backend.core.agent import Agent, AgentConfig
from backend.core.context_manager import ContextManager
from backend.core.model_client import ModelClient
from backend.core.router import Router
from backend.core.memory_manager import MemoryManager
from backend.database.db import init_db_sync
from backend.tools.file_loader import FileLoaderTool

# --- FLASK KURULUMU ---
app = Flask(__name__)
# CORS: Tüm originlere izin ver (PySide ve Browser için)
CORS(app, resources={r"/api/*": {"origins": "*"}}, supports_credentials=False)

# --- YAPILANDIRMA ---
MODES_DIR = Path(__file__).resolve().parent / "backend" / "modes"
model_client = ModelClient(base_url="http://127.0.0.1:8080")
memory = MemoryManager()
context = ContextManager(memory=memory)
router = Router()
db = init_db_sync()
agent = Agent(model_client=model_client, context_manager=context, router=router, db=db, config=AgentConfig())
file_loader = FileLoaderTool()
UPLOAD_DIR = Path(__file__).resolve().parent / "data" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


# --- YARDIMCI: DEBUG LOGGER ---
def log_raw_response(text):
    """
    Modelden gelen ham veriyi senin OneDrive masaüstüne 'debug_log.txt' dosyasına yazar.
    """
    try:
        
        desktop = r"C:/Users/cagri/OneDrive/Desktop"
        
        
        if not os.path.exists(desktop):
            desktop = os.path.join(os.environ['USERPROFILE'], 'Desktop')

        log_file = os.path.join(desktop, "debug_log.txt")
        
        with open(log_file, "a", encoding="utf-8") as f:
            f.write("\n\n================= YENİ CEVAP BAŞLANGICI =================\n")
            f.write(text)
            f.write("\n================= YENİ CEVAP BİTİŞİ =================\n")
    except Exception as e:
        print(f"Loglama yapılamadı: {e}")


# --- KRİTİK FONKSİYON: GÜVENLİ AYRIŞTIRICI ---
def process_model_output(raw_text: str) -> tuple[str, str]:
    """
    Model çıktısını işler. 
    STRATEJİ: Veri kaybetmektense, kirli göstermek iyidir. 
    Bölme işlemi sadece <think> tagleri varsa yapılır.
    """

    log_raw_response(raw_text)

    if not raw_text:
        return "", ""

    thought = ""
    reply = raw_text


    if "<think>" in raw_text:
        think_match = re.search(r"<think>(.*?)</think>", raw_text, re.DOTALL)
        if think_match:
            thought = think_match.group(1).strip()
            reply = re.sub(r"<think>.*?</think>", "", raw_text, flags=re.DOTALL).strip()
            return thought, reply


    if "assistantfinal" in raw_text:
        reply = raw_text.replace("assistantfinal", "")
    
    reply = re.sub(r"^User asks.*?(?:\.|\n)", "", reply, count=1, flags=re.DOTALL | re.IGNORECASE).strip()

    def clean_garbage(t):
        return re.sub(r"<\|.*?\|>", "", t).strip()

    return clean_garbage(thought), clean_garbage(reply)


@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    return response


@app.route("/api/chat", methods=["POST", "OPTIONS"])
def chat():
    if request.method == "OPTIONS":
        return ("", 204)
    try:
        data = request.get_json(force=True) or {}
        message = data.get("message", "")
        mode = data.get("mode", "chat")
        conversation_id = data.get("conversation_id")
        
        try:
            conversation_id = int(conversation_id) if conversation_id is not None else None
        except Exception:
            conversation_id = None

        # Sohbet ID Yönetimi
        if conversation_id:
            conv_row = db.get_conversation(conversation_id)
            if not conv_row:
                conversation_id = db.create_conversation(title="API Chat", mode=mode)
        else:
            conversation_id = db.create_conversation(title="API Chat", mode=mode)


        mode_params = _load_mode_params(mode)
        mode_params["n_predict"] = -1      # Sonsuz üretim (Context dolana kadar)
        mode_params["max_tokens"] = 8192   # Yüksek limit
        
        
        model_client.set_mode(mode)
        model_client.update_params(mode_params)

        # Araç izinleri
        allowed_tools = {"file_loader", "web_search", "sql_query", "image_analysis", "planning"}
        if data.get("allow_python"): allowed_tools.add("python_exec")
        if data.get("allow_shell"): allowed_tools.add("shell_exec")
        agent.router.allowed_tools = allowed_tools

        user_meta = {}
        if "file_preview" in data:
            user_meta["file_preview"] = data["file_preview"]

        # 1. AJAN ÇALIŞIYOR (Cevap üretiliyor)
        agent_reply = agent.handle_user_message(message, mode=mode, conversation_id=conversation_id, user_meta=user_meta)
        
        # 2. İŞLEME (Temizlik)
        thought_content, clean_reply = process_model_output(agent_reply.content)
        

        if clean_reply and clean_reply != agent_reply.content and conversation_id:
            try:
                if hasattr(db, 'conn'):
                    cursor = db.conn.cursor()
                    cursor.execute("""
                        UPDATE messages 
                        SET content = ? 
                        WHERE conversation_id = ? AND role = 'assistant' 
                        ORDER BY id DESC LIMIT 1
                    """, (clean_reply, conversation_id))
                    db.conn.commit()
            except Exception as e:
                logging.warning(f"DB Update failed: {e}")

        return jsonify({
            "reply": clean_reply,
            "thought": thought_content,
            "conversation_id": conversation_id,
            "tool": agent_reply.meta.get("tool", {}) if agent_reply.meta else {},
        })

    except Exception as e:
        logging.exception("CHAT error")
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/conversations", methods=["GET"])
def list_conversations():
    rows = db.list_conversations(limit=50)
    return jsonify({"conversations": rows})


@app.route("/api/conversations/<int:conversation_id>/messages", methods=["GET"])
def get_messages(conversation_id: int):
    rows = db.get_messages(conversation_id, limit=100)
    cleaned_rows = []
    for row in rows:
        msg = dict(row)
        if msg.get('role') == 'assistant':
            # Geçmişi yüklerken de temizlik kuralını uygula
            t, r = process_model_output(msg.get('content', ''))
            # Eğer temizlik sonucu boş değilse kullan, boşsa orijinal kalsın
            if r:
                msg['content'] = r
                msg['thought'] = t
            else:
                 msg['content'] = msg.get('content', '')
        cleaned_rows.append(msg)
    return jsonify({"conversation_id": conversation_id, "messages": cleaned_rows})


@app.route("/api/conversations", methods=["POST"])
def create_conversation():
    data = request.get_json(force=True) or {}
    title = data.get("title", "New Chat")
    mode = data.get("mode", "chat")
    conv_id = db.create_conversation(title=title, mode=mode)
    return jsonify({"id": conv_id, "title": title, "mode": mode})


@app.route("/api/conversations/<int:conversation_id>", methods=["PUT"])
def rename_conversation(conversation_id: int):
    data = request.get_json(force=True) or {}
    title = data.get("title")
    if not title:
        return jsonify({"status": "error", "message": "title required"}), 400
    db.rename_conversation(conversation_id, title)
    return jsonify({"status": "ok", "id": conversation_id, "title": title})


@app.route("/api/conversations/<int:conversation_id>", methods=["DELETE"])
def delete_conversation(conversation_id: int):
    db.delete_conversation(conversation_id)
    return jsonify({"status": "ok", "id": conversation_id})


@app.route("/api/upload/file", methods=["POST", "OPTIONS"])
def upload_file():
    if request.method == "OPTIONS":
        return ("", 204)
    conversation_id = request.form.get("conversation_id")
    try:
        conversation_id = int(conversation_id) if conversation_id else None
    except Exception:
        conversation_id = None
    if not conversation_id:
        conversation_id = db.create_conversation(title="API Chat", mode="chat")
    if "file" not in request.files:
        return jsonify({"status": "error", "message": "No file part"}), 400
    file = request.files["file"]
    if file.filename == "":
        return jsonify({"status": "error", "message": "No selected file"}), 400

    safe_name = file.filename.replace("..", "_").replace("/", "_").replace("\\", "_")
    save_path = UPLOAD_DIR / safe_name
    file.save(save_path)

    result = file_loader.run(path=str(save_path))
    summary = ""
    if isinstance(result, dict):
        summary = result.get("content", "")[:200] if result.get("content") else json.dumps(result)[:200]
    db.add_file(conversation_id, str(save_path), Path(save_path).suffix, summary)
    return jsonify({"status": "ok", "path": str(save_path), "preview": result, "conversation_id": conversation_id})


def _load_mode_params(mode: str) -> dict:
    path = MODES_DIR / f"{mode}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    default_path = MODES_DIR / "default.json"
    if default_path.exists():
        return json.loads(default_path.read_text(encoding="utf-8"))
    return {}


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000)