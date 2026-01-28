from pathlib import Path
from docling.document_converter import DocumentConverter

class DocxParser:
    def __init__(self):
        # Word için ekstra ayara gerek yok, Docling varsayılanı harika.
        self.converter = DocumentConverter()

    def parse(self, file_path: Path) -> str:
        """DOCX'i Markdown'a çevirir."""
        try:
            print(f"📝 Word İşleniyor (Docling): {file_path.name}")
            result = self.converter.convert(file_path)
            return result.document.export_to_markdown()
        except Exception as e:
            return f"Error processing DOCX: {e}"
