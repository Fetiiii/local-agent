from pathlib import Path

from backend.ingestion.docling_engine import get_converter


class DocxParser:
    """Converts DOCX to Markdown via the shared (lazily-loaded) docling engine."""

    def parse(self, file_path: Path) -> str:
        try:
            print(f"📝 Word İşleniyor (Docling): {file_path.name}")
            result = get_converter().convert(file_path)
            return result.document.export_to_markdown()
        except Exception as e:
            return f"Error processing DOCX: {e}"
