import os
from typing import Dict, Any

class FileWriterTool:
    name = "file_writer"
    description = "Write content to a file. Useful for creating reports, code files, or summaries."
    
    # Güvenlik: Dosyalar sadece bu klasöre yazılır
    EXPORT_DIR = os.path.join(os.getcwd(), "data", "exports")

    def __init__(self):
        os.makedirs(self.EXPORT_DIR, exist_ok=True)

    def run(self, filename: str, content: str, **kwargs) -> str:
        try:
            # Dosya adını temizle (Path Traversal saldırısını önle)
            safe_filename = os.path.basename(filename)
            file_path = os.path.join(self.EXPORT_DIR, safe_filename)
            
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
                
            return f"✅ File created successfully at: {file_path}"
        except Exception as e:
            return f"❌ Error writing file: {str(e)}"
