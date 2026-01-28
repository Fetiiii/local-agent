import os
import uuid
from typing import List, Dict, Any
import chromadb
from chromadb.utils import embedding_functions
from sentence_transformers import SentenceTransformer

# ChromaDB ve Model Ayarları
VECTOR_DB_PATH = os.path.join(os.getcwd(), "data", "vector_store")
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
        results = self.collection.query(
            query_texts=[query],
            n_results=n_results
        )
        
        # ChromaDB sonucu karmaşık bir dict döner, biz sadece textleri alalım
        # results['documents'] -> [[doc1, doc2, ...]]
        if results and results['documents']:
            return results['documents'][0]
        return []

    def _split_text(self, text: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]:
        """
        Basit ama etkili bir chunking (parçalama) algoritması.
        RecursiveCharacterTextSplitter mantığına benzer.
        """
        if not text:
            return []
            
        chunks = []
        start = 0
        text_len = len(text)
        
        while start < text_len:
            end = start + chunk_size
            
            # Eğer sona gelmediysek ve kelime ortasındaysak, en yakın boşluğa geri git
            if end < text_len:
                # Geriye doğru boşluk ara
                while end > start and text[end] not in [' ', '\n', '.', ',']:
                    end -= 1
                # Eğer hiç boşluk bulamazsa mecburen chunk_size kadar kes (kelime çok uzunsa)
                if end == start:
                    end = start + chunk_size
            
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            
            # Overlap (örtüşme) payı ile bir sonraki parçaya geç
            start = end - overlap
            
        return chunks

    def clear_memory(self):
        """Hafızayı temizler (Yeni sohbet için opsiyonel)."""
        self.client.delete_collection("local_knowledge")
        self.collection = self.client.get_or_create_collection(
            name="local_knowledge",
            embedding_function=self.ef
        )
