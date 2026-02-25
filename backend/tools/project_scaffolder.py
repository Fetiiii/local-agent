import os
from typing import Dict, Any

class ProjectScaffolderTool:
    name = "project_scaffolder"
    description = """
    Creates a complete project structure (files and directories) from a JSON object.
    Keys are file paths (relative to export dir), values are file contents.
    Example: {"src/main.py": "print('hello')", "README.md": "# My Project"}
    """
    
    EXPORT_DIR = os.path.join(os.getcwd(), "data", "exports")

    def __init__(self):
        os.makedirs(self.EXPORT_DIR, exist_ok=True)

    def run(self, files: Dict[str, str], **kwargs) -> Dict[str, Any]:
        """
        Creates multiple files at once.
        """
        created_files = []
        errors = []

        try:
            for rel_path, content in files.items():
                # Security: prevent path traversal
                if ".." in rel_path or rel_path.startswith("/"):
                    errors.append(f"Skipped unsafe path: {rel_path}")
                    continue
                
                full_path = os.path.join(self.EXPORT_DIR, rel_path)
                
                # Ensure directory exists
                os.makedirs(os.path.dirname(full_path), exist_ok=True)
                
                # Write file
                with open(full_path, "w", encoding="utf-8") as f:
                    f.write(content)
                
                created_files.append(rel_path)
            
            summary = f"✅ Created {len(created_files)} files."
            if errors:
                summary += f"⚠️ Errors: {', '.join(errors)}"

            return {
                "text": summary,
                "artifacts": created_files
            }

        except Exception as e:
            return {
                "text": f"❌ Scaffolding Error: {str(e)}",
                "artifacts": []
            }
