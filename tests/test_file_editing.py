"""
tests/test_file_editing.py
---------------------------
Test suite for the agent file-editing system.

Covers all four layers:
  Layer 1 — security utilities (path resolver, syntax validator, atomic write)
  Layer 2 — core tool trio (FileReader, FileArchitect, FileSurgeon)
  Layer 3 — HITL (diff_generator, ApprovalManager)
  Layer 4 — BackupManager

Run::
    python tests/test_file_editing.py

All tests are self-contained and write only to a temporary directory so they
never pollute the real data/exports or data/temp/backups directories.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

# ── Ensure project root is on the path ───────────────────────────────────────
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.tools.file_editing.security.atomic_write import atomic_write, AtomicWriteError
from backend.tools.file_editing.security.syntax_validator import (
    validate_syntax,
    SyntaxValidationError,
)
from backend.tools.file_editing.security.path_resolver import SafePathResolver, PathTraversalError
from backend.tools.file_editing.file_reader import FileReaderTool
from backend.tools.file_editing.file_architect import FileArchitectTool
from backend.tools.file_editing.file_surgeon import FileSurgeonTool
from backend.tools.file_editing.hitl.diff_generator import generate_diff, has_changes
from backend.tools.file_editing.hitl.approval_manager import (
    ApprovalManager,
    ApprovalStatus,
    ApprovalResult,
)
from backend.tools.file_editing.backup.backup_manager import BackupManager

# ── Utility ───────────────────────────────────────────────────────────────────

_PASS = "✅"
_FAIL = "❌"

_results: list[tuple[str, bool]] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    status = _PASS if condition else _FAIL
    msg = f"{status}  {name}"
    if detail:
        msg += f"  ({detail})"
    print(msg)
    _results.append((name, condition))


# ═══════════════════════════════════════════════════════════════════════════════
# Layer 1 — Security Utilities
# ═══════════════════════════════════════════════════════════════════════════════

def test_path_resolver() -> None:
    print("\n── PathResolver ──")
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        resolver = SafePathResolver(root)

        # Valid relative path resolves inside root
        safe = resolver.resolve("subdir/file.txt")
        check("valid relative path", str(safe).startswith(str(root)))

        # Absolute path inside root is allowed
        inside = root / "out.txt"
        safe2 = resolver.resolve(inside)
        check("absolute path inside root", safe2 == inside.resolve())

        # Traversal is blocked
        raised = False
        try:
            resolver.resolve("../../etc/passwd")
        except PathTraversalError:
            raised = True
        check("traversal blocked (../../)", raised)

        # is_safe() convenience method
        check("is_safe returns True for valid path", resolver.is_safe("ok.txt"))
        check("is_safe returns False for traversal", not resolver.is_safe("../../bad"))


def test_syntax_validator() -> None:
    print("\n── SyntaxValidator ──")

    # Valid Python
    raised = False
    try:
        validate_syntax("script.py", "def foo():\n    return 42\n")
    except SyntaxValidationError:
        raised = True
    check("valid Python passes", not raised)

    # Invalid Python
    raised = False
    try:
        validate_syntax("bad.py", "def foo(\n")
    except SyntaxValidationError:
        raised = True
    check("invalid Python raises SyntaxValidationError", raised)

    # Valid JSON
    raised = False
    try:
        validate_syntax("data.json", '{"key": "value"}')
    except SyntaxValidationError:
        raised = True
    check("valid JSON passes", not raised)

    # Invalid JSON
    raised = False
    try:
        validate_syntax("data.json", "{key: value}")
    except SyntaxValidationError:
        raised = True
    check("invalid JSON raises SyntaxValidationError", raised)

    # Unknown extension is silently skipped
    raised = False
    try:
        validate_syntax("notes.txt", "anything goes here !!!")
    except SyntaxValidationError:
        raised = True
    check("unknown extension silently skipped", not raised)


def test_atomic_write() -> None:
    print("\n── AtomicWrite ──")
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / "output.txt"
        atomic_write(target, "hello world")

        check("file exists after write", target.exists())
        check("content is correct", target.read_text() == "hello world")

        # No leftover .tmp file
        tmp_files = list(Path(tmp).glob("*.tmp"))
        check("no leftover .tmp files", len(tmp_files) == 0)

        # Overwrite existing file
        atomic_write(target, "updated content")
        check("overwrite works", target.read_text() == "updated content")


# ═══════════════════════════════════════════════════════════════════════════════
# Layer 2 — Core Tool Trio
# ═══════════════════════════════════════════════════════════════════════════════

def test_file_reader() -> None:
    print("\n── FileReaderTool ──")
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        reader = FileReaderTool(root=root)

        # Create a nested structure
        (root / "sub").mkdir()
        (root / "sub" / "file.py").write_text("line one\nline two\nline three\n")
        (root / "top.txt").write_text("top level")

        # list_tree
        tree_result = reader.list_tree()
        check("list_tree returns text", "text" in tree_result)
        check("list_tree contains file names", "file.py" in tree_result["text"])

        # read_lines — all lines
        r = reader.read_lines("sub/file.py")
        check("read_lines succeeds", "text" in r)
        check("read_lines contains numbered lines", "1: line one" in r["text"])
        check("read_lines has total_lines", r.get("total_lines") == 3)

        # read_lines — viewport
        r2 = reader.read_lines("sub/file.py", start_line=2, end_line=2)
        check("viewport shows only requested line", "2: line two" in r2["text"])
        check("viewport excludes other lines", "1:" not in r2["text"])

        # read_lines — missing file
        r3 = reader.read_lines("does_not_exist.py")
        check("missing file returns error text", "❌" in r3["text"])


def test_file_architect() -> None:
    print("\n── FileArchitectTool ──")
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        architect = FileArchitectTool(root=root)

        # Create multiple files
        files = {
            "pkg/__init__.py": "",
            "pkg/config.json": '{"env": "test"}',
            "pkg/README.md": "# Test",
        }
        result = architect.run(files)
        check("architect creates files", len(result["created"]) == 3)
        check("pkg/__init__.py exists", (root / "pkg/__init__.py").exists())
        check("pkg/config.json valid JSON written", (root / "pkg/config.json").exists())

        # Overwrite protection
        result2 = architect.run({"pkg/README.md": "new content"}, overwrite=False)
        check("overwrite=False produces error", len(result2["errors"]) == 1)

        # Overwrite allowed
        result3 = architect.run({"pkg/README.md": "new content"}, overwrite=True)
        check("overwrite=True replaces file", len(result3["created"]) == 1)

        # Max files limit
        too_many = {f"f{i}.txt": f"content {i}" for i in range(25)}
        result4 = architect.run(too_many)
        check("too many files returns error", "❌" in result4["text"])

        # Syntax validation blocks invalid Python
        result5 = architect.run({"broken.py": "def foo(\n"})
        check("invalid Python blocked", len(result5["errors"]) == 1)

        # Path traversal blocked
        result6 = architect.run({"../../escape.txt": "bad"})
        check("path traversal blocked", len(result6["errors"]) == 1)


def test_file_surgeon() -> None:
    print("\n── FileSurgeonTool ──")
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        surgeon = FileSurgeonTool(root=root)

        # Create a test file
        source = 'def greet():\n    return "Hello"\n\ndef other():\n    pass\n'
        (root / "app.py").write_text(source, encoding="utf-8")

        # Exact match replacement
        result = surgeon.run(
            path="app.py",
            search_block='return "Hello"',
            replace_block='return "Hi there"',
        )
        check("exact match succeeds", "✅" in result["text"])
        updated = (root / "app.py").read_text(encoding="utf-8")
        check("content actually replaced", 'return "Hi there"' in updated)

        # Normalised-whitespace match (extra spaces)
        source2 = 'x  =  1\ny  =  2\n'
        (root / "vars.py").write_text(source2, encoding="utf-8")
        result2 = surgeon.run(
            path="vars.py",
            search_block="x = 1",   # normalised version
            replace_block="x = 99",
        )
        check("whitespace-normalised match works", "✅" in result2["text"])

        # No match → diagnostic
        result3 = surgeon.run(
            path="app.py",
            search_block="this block does not exist in the file at all",
            replace_block="anything",
        )
        check("no match returns diagnostic", "❌" in result3["text"])
        check("no match includes closest score", "closest_score" in result3)

        # Path traversal blocked
        result4 = surgeon.run(
            path="../../etc/danger",
            search_block="a",
            replace_block="b",
        )
        check("traversal blocked by surgeon", "❌" in result4["text"])


# ═══════════════════════════════════════════════════════════════════════════════
# Layer 3 — HITL
# ═══════════════════════════════════════════════════════════════════════════════

def test_diff_generator() -> None:
    print("\n── DiffGenerator ──")
    old = "line 1\nline 2\nline 3\n"
    new = "line 1\nline 2 modified\nline 3\n"

    diff = generate_diff(old, new, filename="test.py")
    check("diff is non-empty for changed content", bool(diff))
    check("diff contains +++ marker", "+++ new/test.py" in diff)
    check("diff shows removed line", "-line 2" in diff)
    check("diff shows added line", "+line 2 modified" in diff)

    # Identical content → empty diff
    no_diff = generate_diff(old, old, filename="test.py")
    check("identical content produces empty diff", no_diff == "")
    check("has_changes is False for identical", not has_changes(old, old))
    check("has_changes is True for different", has_changes(old, new))


def test_approval_manager() -> None:
    print("\n── ApprovalManager ──")

    # Auto-approve mode
    mgr = ApprovalManager(auto_approve=True)
    result = mgr.request_approval(Path("dummy.py"), "some diff")
    check("auto_approve returns APPROVED", result.status == ApprovalStatus.APPROVED)

    # Custom decision function — always reject
    def always_reject(fp: Path, diff: str) -> ApprovalResult:
        return ApprovalResult(status=ApprovalStatus.REJECTED, reason="test rejection")

    mgr2 = ApprovalManager(decision_fn=always_reject)
    result2 = mgr2.request_approval(Path("x.py"), "diff")
    check("custom decision_fn returns REJECTED", result2.status == ApprovalStatus.REJECTED)

    # Custom decision function — edit
    def always_edit(fp: Path, diff: str) -> ApprovalResult:
        return ApprovalResult(
            status=ApprovalStatus.EDITED,
            edited_content="replacement content",
            reason="test edit",
        )

    mgr3 = ApprovalManager(decision_fn=always_edit)
    result3 = mgr3.request_approval(Path("y.py"), "diff")
    check("custom decision_fn returns EDITED", result3.status == ApprovalStatus.EDITED)
    check("EDITED result carries edited_content", result3.edited_content == "replacement content")


# ═══════════════════════════════════════════════════════════════════════════════
# Layer 4 — BackupManager
# ═══════════════════════════════════════════════════════════════════════════════

def test_backup_manager() -> None:
    print("\n── BackupManager ──")
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        backup_dir = tmp_path / "backups"
        source_file = tmp_path / "important.py"
        source_file.write_text("original content", encoding="utf-8")

        mgr = BackupManager(backup_root=backup_dir)

        # Create backup
        backup_id = mgr.create_backup([source_file], action="test backup")
        check("backup_id is a non-empty string", bool(backup_id))

        snapshot_dir = backup_dir / backup_id
        check("snapshot directory created", snapshot_dir.exists())

        meta_path = snapshot_dir / "metadata.json"
        check("metadata.json created", meta_path.exists())

        meta = json.loads(meta_path.read_text())
        check("metadata has 'time' key", "time" in meta)
        check("metadata has 'files' key", "files" in meta)
        check("metadata has 'action' key", meta.get("action") == "test backup")

        saved_copy = snapshot_dir / "files" / "important.py"
        check("file copy saved in backup", saved_copy.exists())
        check("saved copy has correct content", saved_copy.read_text() == "original content")

        # Corrupt source and restore
        source_file.write_text("CORRUPTED", encoding="utf-8")
        restore_result = mgr.restore_backup(backup_id)
        check("restore succeeds", "✅" in restore_result["text"])
        check("file content restored", source_file.read_text() == "original content")

        # list_backups
        listing = mgr.list_backups()
        check("list_backups returns non-empty list", len(listing) >= 1)

        # Unknown backup_id
        bad = mgr.restore_backup("nonexistent_id")
        check("unknown backup_id returns error", "❌" in bad["text"])


# ═══════════════════════════════════════════════════════════════════════════════
# Runner
# ═══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    print("\n" + "═" * 60)
    print("  Agent File-Editing System — Test Suite")
    print("═" * 60)

    # Layer 1
    test_path_resolver()
    test_syntax_validator()
    test_atomic_write()

    # Layer 2
    test_file_reader()
    test_file_architect()
    test_file_surgeon()

    # Layer 3
    test_diff_generator()
    test_approval_manager()

    # Layer 4
    test_backup_manager()

    # Summary
    total  = len(_results)
    passed = sum(1 for _, ok in _results if ok)
    failed = total - passed

    print("\n" + "═" * 60)
    print(f"  Results: {passed}/{total} passed", end="")
    if failed:
        print(f"  |  {failed} FAILED ← see ❌ above")
        failed_names = [name for name, ok in _results if not ok]
        for n in failed_names:
            print(f"    ❌ {n}")
    else:
        print("  — all good! 🎉")
    print("═" * 60 + "\n")

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
