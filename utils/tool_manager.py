import os
import chainlit as cl
from typing import Dict, Any, Union
from backend.tools import ToolRegistry
from utils.sidebar_helpers import set_sidebar_elements

# HITL & Backups
from backend.tools.file_editing.hitl.approval_manager import ApprovalManager, ApprovalStatus
from backend.tools.file_editing.backup.backup_manager import BackupManager
from backend.tools.file_editing.hitl.diff_generator import generate_diff
from backend.tools.file_editing.config import DATA_ROOT
import json
from pathlib import Path

async def run_tool(name: str, args: Dict[str, Any], registry: ToolRegistry) -> str:
    """
    Registry'den tool'u çeker ve çalıştırır (Async Wrapper).
    Eğer tool 'artifacts' dönerse Sidebar'ı günceller.
    """
    # 1. Tool'u Registry'den iste
    tool = registry.get(name)
    
    if not tool:
        return f"Error: Tool '{name}' not found in registry."

    try:
        # 2. Argüman Hazırlığı
        run_kwargs = {}
        
        if name == "web_search":
            run_kwargs = {"query": args.get("query", "")}
        
        elif name == "data_analyst":
            run_kwargs = {"code": args.get("code", "")}
            
        elif name == "file_writer":
            run_kwargs = {
                "filename": args.get("filename"), 
                "content": args.get("content")
            }

        elif name == "image_analysis":
            img_path = args.get("image_path") or args.get("path")
            
            # --- UUID Hallucination Fix ---
            if (not img_path or not os.path.exists(img_path)):
                last_path = cl.user_session.get("last_image_path")
                if last_path and os.path.exists(last_path):
                    img_path = last_path
                else:
                    return f"Error: Image path '{img_path}' not found and no session image available."
            
            run_kwargs = {
                "image_path": img_path, 
                "prompt": args.get("prompt", "Describe.")
            }
        
        else:
            # Standart dışı bir tool geldiyse, direkt argümanları pasla
            run_kwargs = args

        # 3. Handle File Editing Approvals & Backups
        if name in ["file_surgeon", "file_architect"]:
            # Only intercept if human approval isn't bypassed
            res = await handle_file_editing_approval(name, run_kwargs)
            if res.get("status") == "REJECTED":
                return "❌ User rejected the change."
            elif res.get("status") == "ERROR":
                return f"❌ Approval/Backup Error: {res.get('message')}"

        # 4. Tool'u Thread Pool'da Çalıştır (UI Bloklanmasın)
        # cl.make_async(func) -> async_func
        print(f"🔧 Running tool: {name} with args: {run_kwargs}")
        
        # Tool execution: async tools (e.g. shell_executor) are awaited directly;
        # blocking sync tools are offloaded to a thread pool via cl.make_async.
        import asyncio
        if asyncio.iscoroutinefunction(tool.run):
            result = await tool.run(**run_kwargs)
        else:
            result = await cl.make_async(tool.run)(**run_kwargs)

        # 4. Sonuç İşleme (Sidebar Kontrolü)
        # Yeni Protokol: { "text": "...", "artifacts": [...] }
        if isinstance(result, dict) and ("artifacts" in result or "text" in result):
            text_output = result.get("text", "")
            artifacts = result.get("artifacts", [])
            
            # Eğer artifact varsa sidebar'a bas
            if artifacts:
                await set_sidebar_elements(f"Tool: {name}", artifacts)
                # Yan panele yönlendirme mesajı ekle (opsiyonel)
                # text_output += "\n(Detaylar yan panelde)"
            
            return text_output

        # Legacy Protokol (Sadece string veya düz dict)
        # Web Search dict döner, onu stringe çevirelim mi?
        if isinstance(result, dict) and name == "web_search":
            # Web Search sonucunu da sidebar'a atalım mı? 
            # Şu anki web_search.py dict dönüyor ama 'artifacts' key'i yok.
            # Onu da güncelleyip 'artifacts' yapısına uydurabiliriz.
            return str(result)

        return str(result)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return f"Tool Execution Error ({name}): {str(e)}"

# ── Extension: HITL & Backups ───────────────────────────────────────────────

async def handle_file_editing_approval(name: str, run_kwargs: Dict[str, Any]) -> Dict[str, str]:
    """
    Shows a diff/preview of the proposed change and asks the user for approval via Chainlit.
    If approved, creates a backup.
    Returns: {"status": "APPROVED"|"REJECTED"|"ERROR", "message": "..."}
    """
    backup_mgr = BackupManager()
    
    if name == "file_architect":
        files_dict = run_kwargs.get("files", {})
        if not files_dict:
            return {"status": "APPROVED"}
            
        preview_text = "✨ **FileArchitect is creating/modifying these files:**\n"
        paths_to_backup = []
        for rel_path, content in files_dict.items():
            preview_text += f"- `{rel_path}` ({len(content)} chars)\n"
            target = DATA_ROOT / rel_path
            if target.exists():
                paths_to_backup.append(target)
                
        if not await ask_user_approval("FileArchitect Write Proposal", preview_text):
            return {"status": "REJECTED"}
            
        if paths_to_backup:
            try:
                b_id = backup_mgr.create_backup(paths_to_backup, action="FileArchitect batch write")
                print(f"✅ Created backup {b_id} for FileArchitect")
            except Exception as e:
                return {"status": "ERROR", "message": str(e)}
        return {"status": "APPROVED"}

    elif name == "file_surgeon":
        rel_path = run_kwargs.get("path")
        search_block = run_kwargs.get("search_block", "")
        replace_block = run_kwargs.get("replace_block", "")
        
        target = DATA_ROOT / rel_path
        if not target.exists():
            # Let the tool run to handle the "file not found" error itself
            return {"status": "APPROVED"}
            
        try:
            old_content = target.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            return {"status": "ERROR", "message": f"Cannot read file for diff preview: {e}"}
            
        # VERY simple preview (does not replicate the complex tier-matching logic)
        diff_text = f"✨ **FileSurgeon proposes edits to `{rel_path}`:**\n"
        diff_text += f"**Finding:**\n```\n{search_block}\n```\n**Replacing with:**\n```\n{replace_block}\n```"
        
        if not await ask_user_approval(f"FileSurgeon Edit Proposal for {rel_path}", diff_text):
            return {"status": "REJECTED"}
            
        try:
            b_id = backup_mgr.create_backup([target], action=f"FileSurgeon edit to {rel_path}")
            print(f"✅ Created backup {b_id} for FileSurgeon")
        except Exception as e:
            return {"status": "ERROR", "message": str(e)}
            
        return {"status": "APPROVED"}
        
    return {"status": "APPROVED"}

async def ask_user_approval(title: str, prompt_text: str) -> bool:
    """Asks user to Approve or Reject via AskActionMessage."""
    res = await cl.AskActionMessage(
        content=prompt_text,
        actions=[
            cl.Action(name="approve", payload={"value": "approve"}, label="✅ Approve & Write", tooltip="Execute tool and create backup"),
            cl.Action(name="reject", payload={"value": "reject"}, label="❌ Reject", tooltip="Abort changes"),
        ],
        timeout=300 # Wait 5 minutes for approval
    ).send()

    if res and res.get("payload", {}).get("value") == "approve":
        return True
    return False
