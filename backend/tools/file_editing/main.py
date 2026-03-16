"""
backend/tools/file_editing/main.py
------------------------------------
End-to-end demonstration of the agent file-editing system.

Run from the project root::

    python -m backend.tools.file_editing.main

Steps demonstrated
------------------
1. List directory tree
2. Read a file with viewport
3. Create files via FileArchitect
4. Modify a file via FileSurgeon
5. Show a unified diff
6. Create a backup, then restore it
"""

from __future__ import annotations

import textwrap
from pathlib import Path

from backend.tools.file_editing.file_reader import FileReaderTool
from backend.tools.file_editing.file_architect import FileArchitectTool
from backend.tools.file_editing.file_surgeon import FileSurgeonTool
from backend.tools.file_editing.hitl.diff_generator import generate_diff
from backend.tools.file_editing.hitl.approval_manager import ApprovalManager, ApprovalStatus
from backend.tools.file_editing.backup.backup_manager import BackupManager
from backend.tools.file_editing.context_manager import FileContextManager
from backend.tools.file_editing.config import DATA_ROOT

# ── Helpers ───────────────────────────────────────────────────────────────────

_SEP = "─" * 60

def section(title: str) -> None:
    print(f"\n{_SEP}\n  {title}\n{_SEP}")


def show(result: dict) -> None:
    text = result.get("text", "")
    print(textwrap.indent(text, "  "))


# ── Demo ──────────────────────────────────────────────────────────────────────

def main() -> None:
    reader    = FileReaderTool()
    architect = FileArchitectTool()
    surgeon   = FileSurgeonTool()
    backup_mgr = BackupManager()
    ctx_mgr   = FileContextManager()

    # ─────────────────────────────────────────────────────────────────────────
    # Step 1: List the project tree
    # ─────────────────────────────────────────────────────────────────────────
    section("Step 1 — list_tree()")
    show(reader.list_tree())

    # ─────────────────────────────────────────────────────────────────────────
    # Step 2: Create demo files via FileArchitect
    # ─────────────────────────────────────────────────────────────────────────
    section("Step 2 — FileArchitect: create demo project files")
    files_to_create = {
        "demo_project/config.json": '{"version": "1.0", "debug": false}',
        "demo_project/app.py": textwrap.dedent("""\
            \"\"\"Demo application entry-point.\"\"\"

            def greet(name: str) -> str:
                return f"Hello, {name}!"


            if __name__ == "__main__":
                print(greet("World"))
        """),
        "demo_project/README.md": textwrap.dedent("""\
            # Demo Project

            A minimal demo created by the FileArchitectTool.
        """),
    }
    show(architect.run(files_to_create))

    # ─────────────────────────────────────────────────────────────────────────
    # Step 3: Read a file with viewport
    # ─────────────────────────────────────────────────────────────────────────
    section("Step 3 — read_lines() with viewport")
    show(reader.read_lines("demo_project/app.py", start_line=1, end_line=5))

    # ─────────────────────────────────────────────────────────────────────────
    # Step 4: Modify a file via FileSurgeon
    # ─────────────────────────────────────────────────────────────────────────
    section("Step 4 — FileSurgeon: replace a block")
    original_path = DATA_ROOT / "demo_project" / "app.py"
    original_content = original_path.read_text(encoding="utf-8")

    search_block  = 'return f"Hello, {name}!"'
    replace_block = 'return f"Greetings, {name}! Welcome to lokal-agent."'

    result = surgeon.run(
        path="demo_project/app.py",
        search_block=search_block,
        replace_block=replace_block,
    )
    show(result)

    # ─────────────────────────────────────────────────────────────────────────
    # Step 5: Show the diff
    # ─────────────────────────────────────────────────────────────────────────
    section("Step 5 — unified diff")
    new_content = original_path.read_text(encoding="utf-8")
    diff = generate_diff(original_content, new_content, filename="demo_project/app.py")
    print(diff if diff else "  (no changes detected)")

    # ─────────────────────────────────────────────────────────────────────────
    # Step 6: File preview / summarize (context manager)
    # ─────────────────────────────────────────────────────────────────────────
    section("Step 6 — FileContextManager: summarize")
    summary = ctx_mgr.summarize("demo_project/app.py")
    print(textwrap.indent(summary, "  "))

    # ─────────────────────────────────────────────────────────────────────────
    # Step 7: Backup and restore
    # ─────────────────────────────────────────────────────────────────────────
    section("Step 7 — BackupManager: backup → modify → restore")

    # Create a backup BEFORE further modification.
    backup_id = backup_mgr.create_backup(
        [original_path],
        action="demo: pre-restore snapshot",
    )
    print(f"  Backup created: {backup_id}")

    # Simulate another (unwanted) edit directly so we have something to undo.
    original_path.write_text(
        new_content.replace(
            "Greetings, {name}! Welcome to lokal-agent.",
            "CORRUPTED CONTENT",
        ),
        encoding="utf-8",
    )
    print("  Simulated accidental corruption of app.py")

    # Restore the backup.
    restore_result = backup_mgr.restore_backup(backup_id)
    show(restore_result)

    restored = original_path.read_text(encoding="utf-8")
    if "Greetings" in restored:
        print("  ✅ Restore verified — file content is correct.")
    else:
        print("  ❌ Restore may have failed — check backup_id.")

    # ─────────────────────────────────────────────────────────────────────────
    # Step 8: HITL approval (auto-approve for demo)
    # ─────────────────────────────────────────────────────────────────────────
    section("Step 8 — ApprovalManager (auto_approve=True for demo)")
    approval_mgr = ApprovalManager(auto_approve=True)
    demo_diff = generate_diff("old line\n", "new line\n", filename="example.py")
    from pathlib import Path as _Path
    result = approval_mgr.request_approval(
        file_path=_Path("example.py"),
        diff=demo_diff,
    )
    print(f"  Decision: {result.status.value}  ({result.reason})")

    section("Demo complete ✅")


if __name__ == "__main__":
    main()
