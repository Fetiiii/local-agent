"""
Conversation persistence — one JSON file per conversation under data/conversations/.

Dead simple and hackable (no DB, no migrations): each file holds the message
history + rolling summary + title, so chats survive restarts and can be resumed.
"""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Dict, List, Optional

CONV_DIR = Path("data/conversations")


def _path(tid: str) -> Path:
    return CONV_DIR / f"{tid}.json"


def new_id() -> str:
    return uuid.uuid4().hex


def _derive_title(history: List[Dict]) -> str:
    for m in history:
        if m.get("role") == "user" and m.get("content"):
            t = m["content"].strip().replace("\n", " ")
            return t[:50] + ("…" if len(t) > 50 else "")
    return "(başlıksız)"


def save(tid: str, history: List[Dict], summary: str = "", title: Optional[str] = None) -> None:
    if not history:
        return
    CONV_DIR.mkdir(parents=True, exist_ok=True)
    p = _path(tid)
    now = time.time()
    created = now
    if p.exists():
        try:
            created = json.loads(p.read_text(encoding="utf-8")).get("created", now)
        except Exception:
            pass
    data = {
        "id": tid,
        "title": title or _derive_title(history),
        "summary": summary,
        "messages": history,
        "created": created,
        "updated": now,
    }
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load(tid: str) -> Optional[Dict]:
    p = _path(tid)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def list_all() -> List[Dict]:
    CONV_DIR.mkdir(parents=True, exist_ok=True)
    out = []
    for p in CONV_DIR.glob("*.json"):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            out.append({"id": d["id"], "title": d.get("title", "(başlıksız)"),
                        "updated": d.get("updated", 0)})
        except Exception:
            continue
    return sorted(out, key=lambda x: x["updated"], reverse=True)


def delete(tid: str) -> bool:
    p = _path(tid)
    if p.exists():
        p.unlink()
        return True
    return False
