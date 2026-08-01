"""
Lazily-created, shared docling DocumentConverter.

docling loads heavy layout/table (and optionally OCR) models. Building it eagerly
at every chat start — even when no document is uploaded — is wasteful on modest
hardware. This module builds ONE converter on first use and reuses it for both
PDF and DOCX, with OCR gated behind the INGEST_OCR setting.
"""

from __future__ import annotations

from threading import Lock

from backend.core.settings import settings

_converter = None
_lock = Lock()


def get_converter():
    """Return the shared docling DocumentConverter, building it on first use."""
    global _converter
    if _converter is not None:
        return _converter
    with _lock:
        if _converter is None:
            from docling.document_converter import DocumentConverter, PdfFormatOption
            from docling.datamodel.pipeline_options import PdfPipelineOptions, TableFormerMode
            from docling.datamodel.base_models import InputFormat

            print(f"🔧 Docling motoru yükleniyor (ilk kullanım, OCR={settings.ingest_ocr})...")
            opts = PdfPipelineOptions()
            opts.do_ocr = settings.ingest_ocr
            opts.do_table_structure = True
            opts.table_structure_options.mode = TableFormerMode.ACCURATE
            _converter = DocumentConverter(
                format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=opts)}
            )
    return _converter
