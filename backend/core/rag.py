import os
import uuid
from pathlib import Path
from typing import List, Dict, Any
import chromadb
from chromadb.utils import embedding_functions
from sentence_transformers import SentenceTransformer
from llama_index.core.node_parser import SentenceSplitter

# ChromaDB ve Model Ayarları
BASE_DIR = Path(__file__).parent.parent.parent
VECTOR_DB_PATH = str(BASE_DIR / "data" / "vector_store")
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"

class RAGManager:
    def __init__(self):
        print(f"🧠 RAG Manager Başlatılıyor ({VECTOR_DB_PATH})...")
        
        # Klasör yoksa oluştur
        os.makedirs(VECTOR_DB_PATH, exist_ok=True)
        
        # ChromaDB Client (Persistent)
        self.client = chromadb.PersistentClient(path=VECTOR_DB_PATH)
        
        # Embedding Function (Sentence-Transformers kullanıyoruz, hafif ve hızlı)
        # ChromaDB'nin built-in fonksiyonu yerine manuel yönetmek daha stabil sonuç veriyor bazen,
        # ama burada Chroma'nın utility'sini kullanmak en kolayı.
        self.ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name=EMBEDDING_MODEL_NAME)
        
        # Koleksiyonları al veya yarat
        self.collection = self.client.get_or_create_collection(
            name="local_knowledge",
            embedding_function=self.ef
        )
        self.episodic_collection = self.client.get_or_create_collection(
            name="episodic_memory",
            embedding_function=self.ef
        )

    def add_document(self, text: str, source: str):
        """
        Metni parçalara (chunk) ayırır ve Vektör DB'ye ekler.
        """
        chunks = self._split_text(text)
        
        if not chunks:
            return 0
            
        ids = [str(uuid.uuid4()) for _ in chunks]
        metadatas = [{"source": source} for _ in chunks]
        
        # DB'ye ekle
        self.collection.add(
            documents=chunks,
            metadatas=metadatas,
            ids=ids
        )
        print(f"📚 {len(chunks)} parça hafızaya eklendi: {source}")
        return len(chunks)

    def search(self, query: str, n_results: int = 3) -> List[str]:
        """
        Sorgu ile en alakalı metin parçalarını (local doc) VE eski episodic anıları getirir.
        """
        combined_results = []
        try:
            # 1. Local Knowledge (Docs) Search
            if not hasattr(self, "collection") or self.collection is None:
                self.collection = self.client.get_or_create_collection(
                    name="local_knowledge",
                    embedding_function=self.ef
                )

            doc_results = self.collection.query(
                query_texts=[query],
                n_results=n_results
            )
            if doc_results and doc_results['documents'] and doc_results['documents'][0]:
                combined_results.extend(doc_results['documents'][0])
                
            # 2. Episodic Memory Search
            if not hasattr(self, "episodic_collection") or self.episodic_collection is None:
                self.episodic_collection = self.client.get_or_create_collection(
                    name="episodic_memory",
                    embedding_function=self.ef
                )
                
            epi_results = self.episodic_collection.query(
                query_texts=[query],
                n_results=n_results
            )
            
            if epi_results and epi_results['documents'] and epi_results['documents'][0]:
                for doc, meta in zip(epi_results['documents'][0], epi_results['metadatas'][0]):
                    ts = meta.get("timestamp", "Unknown time")
                    combined_results.append(f"[Past Conversation at {ts}]:\n{doc}")

        except Exception as e:
            print(f"⚠️ RAG Search Hatası: {e}")
            try:
                self.collection = self.client.get_or_create_collection(name="local_knowledge", embedding_function=self.ef)
                self.episodic_collection = self.client.get_or_create_collection(name="episodic_memory", embedding_function=self.ef)
            except Exception as e2:
                print(f"⚠️ RAG Collection Refresh Hatası: {e2}")
                
        return combined_results

    def add_episodic_memory(self, summary_text: str, timestamp: str):
        """Kaydedilen konuşma özetlerini (Medium-Term Memory) Episodic DB'ye ekler."""
        if not summary_text.strip():
            return
            
        doc_id = str(uuid.uuid4())
        self.episodic_collection.add(
            documents=[summary_text],
            metadatas=[{"timestamp": timestamp, "type": "conversation_summary"}],
            ids=[doc_id]
        )
        print(f"📖 Episodic hafızaya yeni anı eklendi: {timestamp}")

    def search_episodic_memory(self, query: str, n_results: int = 3) -> List[str]:
        """Eski konuşma anılarını RAG ile getirir."""
        try:
            results = self.episodic_collection.query(
                query_texts=[query],
                n_results=n_results
            )
            if results and results['documents'] and results['documents'][0]:
                return results['documents'][0]
        except Exception as e:
            print(f"⚠️ Episodic Search Hatası: {e}")
        return []

    def _split_text(self, text: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]:
        """
        LlamaIndex SentenceSplitter kullanarak düzenli ve güvenli parçalama yapar.
        """
        if not text:
            return []
            
        splitter = SentenceSplitter(chunk_size=chunk_size, chunk_overlap=overlap)
        return splitter.split_text(text)

    def clear_memory(self):
        """Hafızayı temizler (Yeni sohbet için opsiyonel)."""
        self.client.delete_collection("local_knowledge")
        self.collection = self.client.get_or_create_collection(
            name="local_knowledge",
            embedding_function=self.ef
        )


# The embedding model + ChromaDB client are expensive to build and the vector
# store is shared across sessions anyway — so reuse a single RAGManager instead
# of reloading the embedding model on every chat start/resume.
_rag_instance = None


def get_rag_manager() -> "RAGManager":
    global _rag_instance
    if _rag_instance is None:
        _rag_instance = RAGManager()
    return _rag_instance
