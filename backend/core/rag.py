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
        
        # Koleksiyonu al veya yarat
        self.collection = self.client.get_or_create_collection(
            name="local_knowledge",
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
        Sorgu ile en alakalı metin parçalarını getirir.
        """
        try:
            # Koleksiyonun varlığını ve geçerliliğini kontrol et
            if not hasattr(self, "collection") or self.collection is None:
                self.collection = self.client.get_or_create_collection(
                    name="local_knowledge",
                    embedding_function=self.ef
                )

            results = self.collection.query(
                query_texts=[query],
                n_results=n_results
            )
            
            if results and results['documents']:
                return results['documents'][0]
        except Exception as e:
            print(f"⚠️ RAG Search Hatası: {e}")
            # Hata durumunda koleksiyonu yenilemeyi dene
            try:
                self.collection = self.client.get_or_create_collection(
                    name="local_knowledge",
                    embedding_function=self.ef
                )
            except Exception as e2:
                print(f"⚠️ RAG Collection Refresh Hatası: {e2}")
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
