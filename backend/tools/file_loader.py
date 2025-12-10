"""Load local files (PDF, Word, Excel, text) and return summaries/previews."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from backend.tools import BaseTool, register_tool
from backend.parsing import parse_pdf, parse_excel, parse_word, clean_text, excerpt
from backend.utils.validators import validate_extension, ensure_file_exists


class FileLoaderTool:
    name = "file_loader"
    description = "Load and summarize local files (pdf, docx, xlsx, txt)."
    MAX_PREVIEW_CHARS = 4000  # allow larger previews for PDFs while keeping memory bounded
    DEFAULT_PDF_PAGES = 5
    DEFAULT_EXCEL_ROWS = 50
    DEFAULT_EXCEL_COLS = 30
    DEFAULT_WORD_PARAGRAPHS = 200
    DEFAULT_WORD_CHARS = 8000

    def run(self, path: str, **kwargs: Any) -> Dict[str, Any]:
        target = kwargs.get("path") or kwargs.get("query") or path
        allowed = {".pdf", ".docx", ".xlsx", ".xlsm", ".xls", ".txt"}
        try:
            validate_extension(target, allowed)
            file_path = ensure_file_exists(target)
        except Exception as e:
            return {"status": "error", "message": str(e)}

        ext = Path(file_path).suffix.lower()
        max_preview = int(kwargs.get("max_preview_chars", self.MAX_PREVIEW_CHARS))

        try:
            if ext == ".pdf":
                parsed = parse_pdf(
                    file_path,
                    max_pages=int(kwargs.get("max_pages", self.DEFAULT_PDF_PAGES)),
                )
                raw_content = parsed.get("content", "")
            elif ext in {".xlsx", ".xlsm", ".xls"}:
                parsed = parse_excel(
                    file_path,
                    sheet=kwargs.get("sheet", 0),
                    max_rows=int(kwargs.get("max_rows", self.DEFAULT_EXCEL_ROWS)),
                    max_cols=int(kwargs.get("max_cols", self.DEFAULT_EXCEL_COLS)),
                )
                raw_content = parsed.get("preview_csv", "")
            elif ext == ".docx":
                parsed = parse_word(
                    file_path,
                    max_paragraphs=int(kwargs.get("max_paragraphs", self.DEFAULT_WORD_PARAGRAPHS)),
                    max_chars=int(kwargs.get("max_chars", self.DEFAULT_WORD_CHARS)),
                )
                raw_content = parsed.get("content", "")
            elif ext == ".txt":
                raw_content = Path(file_path).read_text(encoding="utf-8", errors="ignore")
                parsed = {"path": str(file_path)}
            else:
                return {"status": "error", "message": f"Unsupported extension: {ext}"}

            cleaned = clean_text(raw_content)
            content = cleaned[:max_preview] if len(cleaned) > max_preview else cleaned
            preview = parsed.get("preview") or excerpt(cleaned, max_chars=max_preview)

            result = {
                "status": "ok",
                "path": str(file_path),
                "ext": ext,
                **parsed,
            }
            result.update(
                {
                    "content": content,
                    "content_preview": preview,
                    "char_count": len(cleaned),
                }
            )
            return result
        except Exception as e:
            return {"status": "error", "message": f"Failed to parse {file_path}: {e}"}


register_tool(FileLoaderTool())
