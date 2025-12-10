from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Union

import pandas as pd

from backend.utils.validators import ensure_file_exists, validate_extension
from backend.parsing.text_cleaner import normalize_whitespace, excerpt

SheetSelector = Union[str, int, None]


def _resolve_sheet_name(xf: pd.ExcelFile, sheet: SheetSelector) -> str:
    """Map user-provided sheet selector to a concrete sheet name."""
    sheet_names: List[str] = xf.sheet_names
    if sheet is None:
        return sheet_names[0]
    if isinstance(sheet, int):
        if sheet < 0 or sheet >= len(sheet_names):
            raise ValueError(f"Sheet index out of range: {sheet}")
        return sheet_names[sheet]
    if isinstance(sheet, str):
        if sheet not in sheet_names:
            raise ValueError(f"Sheet '{sheet}' not found. Available: {', '.join(sheet_names)}")
        return sheet
    raise TypeError("sheet must be str, int, or None")


def parse_excel(
    path: str | Path,
    sheet: SheetSelector = 0,
    max_rows: int = 50,
    max_cols: int = 30,
) -> Dict[str, Any]:
    """
    Load an Excel file safely and return a CSV-like preview plus metadata.
    - Reads only the requested sheet.
    - Limits rows/cols to avoid huge memory usage.
    """
    if max_rows <= 0:
        raise ValueError("max_rows must be positive")
    if max_cols <= 0:
        raise ValueError("max_cols must be positive")

    validate_extension(path, {".xlsx", ".xlsm", ".xls"})
    excel_path = ensure_file_exists(path)

    with pd.ExcelFile(excel_path) as xf:
        available_sheets = xf.sheet_names
        sheet_name = _resolve_sheet_name(xf, sheet)
        df = xf.parse(sheet_name=sheet_name, nrows=max_rows, header=0)

    df = df.iloc[:, :max_cols]
    df = df.fillna("")

    preview_df = df.head(max_rows)
    preview_csv = preview_df.to_csv(index=False)

    return {
        "path": str(excel_path),
        "sheet": sheet_name,
        "available_sheets": available_sheets,
        "columns": [str(c) for c in preview_df.columns.tolist()],
        "row_count_preview": int(preview_df.shape[0]),
        "col_count_preview": int(preview_df.shape[1]),
        "preview_csv": normalize_whitespace(preview_csv),
        "preview_excerpt": excerpt(preview_csv, max_chars=4000),
    }
