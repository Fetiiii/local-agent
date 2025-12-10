import backend.tools.web_search as ws


def test_web_search_requires_query(monkeypatch):
    tool = ws.WebSearchTool()
    monkeypatch.delenv("WEB_SEARCH_API", raising=False)
    res = tool.run("")
    assert res["status"] == "error"
    assert "empty" in res["message"].lower()


def test_web_search_normalizes_results(monkeypatch):
    tool = ws.WebSearchTool()
    monkeypatch.setenv("WEB_SEARCH_API", "https://example.com/api")
    monkeypatch.setenv("WEB_SEARCH_API_KEY", "dummy")

    def fake_get(url, params=None, headers=None, timeout=None):
        class Resp:
            def raise_for_status(self):
                return None

            def json(self):
                return {"items": [{"name": "Title", "url": "https://t", "description": "Desc"}]}

        return Resp()

    monkeypatch.setattr(ws.requests, "get", fake_get)
    res = tool.run("test", num_results=1)
    assert res["status"] == "ok"
    assert res["results"][0]["title"] == "Title"
    assert res["results"][0]["link"] == "https://t"
