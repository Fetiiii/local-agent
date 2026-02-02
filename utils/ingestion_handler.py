# utils/ingestion_handler.py
import chainlit as cl
from backend.ingestion.ingestor import UniversalIngestor
from backend.core.rag import RAGManager
from backend.database.db import Database

async def handle_uploads(message: cl.Message, conv_id: int) -> str:
    """Paylaşılan çalışan kod mantığına birebir sadık kalınmıştır."""
    ingestor: UniversalIngestor = cl.user_session.get("ingestor")
    rag: RAGManager = cl.user_session.get("rag")
    db: Database = cl.user_session.get("db")

    # Ingestion Kısmı (Birebir kopyalandı)
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

    # Hint Kısmı (Orijinal app.py'dan birebir kopyalandı)
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
    
    return file_hint
