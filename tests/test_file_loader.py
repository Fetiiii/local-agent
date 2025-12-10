import backend.tools.file_loader as fl


def test_file_loader_respects_pdf_limits(monkeypatch, tmp_path):
    tool = fl.FileLoaderTool()
    p = tmp_path / "sample.pdf"
    p.write_bytes(b"%PDF-1.4")

    called = {}

    def fake_parse_pdf(path, max_pages):
        called["path"] = path
        called["max_pages"] = max_pages
        return {"content": "page1\npage2", "page_count": 2}

    monkeypatch.setattr(fl, "parse_pdf", fake_parse_pdf)

    res = tool.run(str(p), max_pages=1, max_preview_chars=5)
    assert res["status"] == "ok"
    assert called["path"] == p
    assert called["max_pages"] == 1
    assert res["content"] == "page1"
    assert res["content_preview"].startswith("pa")


def test_file_loader_passes_excel_params(monkeypatch, tmp_path):
    tool = fl.FileLoaderTool()
    p = tmp_path / "sample.xlsx"
    p.write_bytes(b"")  # existence is enough; parser is stubbed

    captured = {}

    def fake_parse_excel(path, sheet, max_rows, max_cols):
        captured.update({"path": path, "sheet": sheet, "max_rows": max_rows, "max_cols": max_cols})
        return {
            "preview_csv": "col1\n1",
            "columns": ["col1"],
            "sheet": sheet,
            "preview": "col1",
        }

    monkeypatch.setattr(fl, "parse_excel", fake_parse_excel)

    res = tool.run(str(p), sheet="Data", max_rows=10, max_cols=2)
    assert res["status"] == "ok"
    assert captured["path"] == p
    assert captured["sheet"] == "Data"
    assert captured["max_rows"] == 10
    assert captured["max_cols"] == 2
    assert res["columns"] == ["col1"]
    assert res["content_preview"].startswith("col1")
