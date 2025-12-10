"""Image analysis stub: returns basic metadata (size, mode, format)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from backend.tools import BaseTool, register_tool
from backend.utils.validators import ensure_file_exists

try:
    from PIL import Image
except ImportError:
    Image = None  # type: ignore


class ImageAnalysisTool:
    name = "image_analysis"
    description = "Analyze images for text/content (OCR/caption)."

    def run(self, image_path: str, **kwargs: Any) -> Dict[str, Any]:
        target = kwargs.get("image_path") or kwargs.get("path") or kwargs.get("query") or image_path
        img_path = ensure_file_exists(target)

        if not Image:
            return {"status": "error", "message": "Pillow not installed", "path": str(img_path)}

        with Image.open(img_path) as img:
            info = {
                "format": img.format,
                "mode": img.mode,
                "size": img.size,
                "palette": bool(img.palette),
            }
            # Simple color histogram summary
            try:
                histogram = img.histogram()
                info["histogram_bins"] = len(histogram)
            except Exception:
                info["histogram_bins"] = None
        return {"status": "ok", "path": str(img_path), "meta": info, "analysis": "TODO: OCR/caption"}


register_tool(ImageAnalysisTool())
