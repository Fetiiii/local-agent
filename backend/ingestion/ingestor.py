import os
from pathlib import Path
from typing import Optional

# Local imports
from backend.ingestion.parsers.pdf_parser import PDFParser
from backend.ingestion.parsers.docx_parser import DocxParser
from backend.ingestion.parsers.excel_parser import ExcelParser

class UniversalIngestor:
    def __init__(self):
        # Motorları bir kere başlatıyoruz (Performans için)
        print("🔧 Ingestor Motorları Başlatılıyor...")
        self.pdf_engine = PDFParser()
        self.docx_engine = DocxParser()
        self.excel_engine = ExcelParser()

        # Desteklenen formatlar ve ilgili motorlar.
        # NOT: Legacy binary ".doc" docling ile güvenilir okunamaz → desteklenmiyor
        # (kullanıcı .docx'e çevirmeli).
        self.parsers = {
            ".pdf": self.pdf_engine,
            ".docx": self.docx_engine,
            ".xlsx": self.excel_engine,
            ".xls": self.excel_engine,
            ".csv": self.excel_engine
        }

    def ingest_file(self, file_path: str) -> Optional[str]:
        """
        Dosyayı okur ve Markdown string olarak döner.
        Dosya formatı desteklenmiyorsa None döner.
        """
        path = Path(file_path)

        if not path.exists():
            print(f"❌ Dosya bulunamadı: {file_path}")
            return None

        ext = path.suffix.lower()

        if ext == ".doc":
            print("⚠️ Legacy .doc desteklenmiyor — lütfen .docx'e çevirin.")
            return None
        if ext not in self.parsers:
            print(f"⚠️ Desteklenmeyen format: {ext}")
            return None

        # İlgili motoru çağır
        parser = self.parsers[ext]
        markdown_content = parser.parse(path)
        
        return markdown_content
