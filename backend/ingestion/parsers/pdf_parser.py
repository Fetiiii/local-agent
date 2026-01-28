from pathlib import Path
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.pipeline_options import PdfPipelineOptions, TableFormerMode
from docling.datamodel.base_models import InputFormat

class PDFParser:
    def __init__(self):
        pipeline_options = PdfPipelineOptions()
        pipeline_options.do_ocr = True
        pipeline_options.do_table_structure = True
        pipeline_options.table_structure_options.mode = TableFormerMode.ACCURATE
        
        self.converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
            }
        )

    def parse(self, file_path: Path) -> str:
        """PDF'i Markdown'a çevirir."""
        try:
            print(f"📄 PDF İşleniyor (Docling): {file_path.name}")
            result = self.converter.convert(file_path)
            # Markdown çıktısını al
            return result.document.export_to_markdown()
        except Exception as e:
            return f"Error processing PDF: {e}"
