"""
backend/tools/file_editing
--------------------------
Safe agent file-editing system.

Re-exports the three core tool classes so callers can do:
    from backend.tools.file_editing import FileReaderTool, FileArchitectTool, FileSurgeonTool
"""

from backend.tools.file_editing.file_reader import FileReaderTool
from backend.tools.file_editing.file_architect import FileArchitectTool
from backend.tools.file_editing.file_surgeon import FileSurgeonTool

__all__ = ["FileReaderTool", "FileArchitectTool", "FileSurgeonTool"]
