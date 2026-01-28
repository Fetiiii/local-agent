from __future__ import annotations
from typing import Any, Dict
from backend.tools import register_tool
from backend.ingestion.ingestor import UniversalIngestor

class FileLoaderTool:
    name = "file_loader"
    description = "Load and process local files (pdf, docx, xlsx) into markdown text."

    def __init__(self):
        # Ingestor motorunu başlat
        self.ingestor = UniversalIngestor()

    def run(self, path: str, **kwargs: Any) -> Dict[str, Any]:
        target = kwargs.get("path") or kwargs.get("query") or path
        
        if not target:
             return {"status": "error", "message": "No file path provided."}

        try:
            markdown_content = self.ingestor.ingest_file(target)
            
            if markdown_content:
                return {
                    "status": "ok", 
                    "path": target, 
                    "content": markdown_content[:5000] + "...(truncated)" if len(markdown_content) > 5000 else markdown_content,
                    "length": len(markdown_content)
                }
            else:
                return {"status": "error", "message": "File format not supported or file not found."}
                
        except Exception as e:
            return {"status": "error", "message": f"Failed to load file: {str(e)}"}

# Tool'u kaydet
register_tool(FileLoaderTool())