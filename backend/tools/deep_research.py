"""
DeepResearchTool — multi-step "deep search" web research.

Given a question it: (1) generates focused sub-questions, (2) searches + scrapes
several sources in parallel, (3) synthesizes a cited report. Heavier than a
single web_search (many model calls + scrapes), so it's meant for capable models
and thorough research questions.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, List

from utils.helpers import extract_json
from backend.core.model_client import ModelClient
from backend.tools.web_search import WebSearchTool
from backend.tools.web_scraper import WebScraperTool

MAX_SUBQUERIES = 4
RESULTS_PER_SUBQUERY = 2
MAX_SOURCE_CHARS = 3500      # per scraped source fed into synthesis
MAX_TOTAL_SOURCES = 8


class DeepResearchTool:
    name = "deep_research"
    description = (
        "Perform DEEP multi-step web research: breaks the question into sub-questions, "
        "searches and reads several sources, then returns a synthesized, cited report. "
        "Use for thorough research (not quick lookups). Args: {\"query\": \"...\"}"
    )

    def __init__(self):
        self._search = WebSearchTool()
        self._scraper = WebScraperTool()

    async def run(self, query: str, **kwargs: Any) -> Dict[str, Any]:
        query = (query or kwargs.get("query") or "").strip()
        if not query:
            return {"text": "❌ deep_research requires a 'query'.", "artifacts": []}

        model = ModelClient()
        try:
            subqueries = await self._subqueries(model, query)
            sources = await self._gather(subqueries)
            if not sources:
                return {"text": f"❌ Deep research found no readable sources for: {query}",
                        "artifacts": []}
            report = await self._synthesize(model, query, sources)
        except Exception as e:  # noqa: BLE001
            return {"text": f"❌ Deep research error: {e}", "artifacts": []}

        artifacts = [{"title": s["title"], "link": s["url"], "snippet": ""} for s in sources]
        header = f"🔎 Deep research — {len(subqueries)} sub-questions, {len(sources)} sources.\n\n"
        return {"text": header + report, "artifacts": artifacts}

    # ── steps ────────────────────────────────────────────────────────────────

    async def _subqueries(self, model: ModelClient, query: str) -> List[str]:
        prompt = (
            f"Break this research question into up to {MAX_SUBQUERIES} focused, distinct "
            f"web-search sub-questions that together cover it well.\n\nQuestion: {query}\n\n"
            'Reply with JSON only: {"subqueries": ["...", "..."]}'
        )
        raw = await model.generate([{"role": "user", "content": prompt}],
                                   stream=False, json_mode=True)
        data = extract_json(raw, schema_cls=_SubqSchemaProxy) or {}
        subs = data.get("subqueries") if isinstance(data, dict) else None
        subs = [s for s in (subs or []) if isinstance(s, str) and s.strip()][:MAX_SUBQUERIES]
        return subs or [query]

    async def _gather(self, subqueries: List[str]) -> List[Dict]:
        # Search each sub-question, collect candidate URLs (deduped).
        seen_urls, candidates = set(), []
        for sq in subqueries:
            res = await asyncio.to_thread(self._search.run, sq)
            for item in (res.get("artifacts") or [])[:RESULTS_PER_SUBQUERY]:
                url = item.get("link")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    candidates.append({"title": item.get("title", url), "url": url})
        candidates = candidates[:MAX_TOTAL_SOURCES]

        async def _scrape(c):
            res = await asyncio.to_thread(self._scraper.run, c["url"])
            text = res.get("text", "") if isinstance(res, dict) else ""
            if text.startswith("❌") or text.startswith("⚠️"):
                return None
            c["content"] = text[:MAX_SOURCE_CHARS]
            return c

        scraped = await asyncio.gather(*[_scrape(c) for c in candidates])
        return [s for s in scraped if s]

    async def _synthesize(self, model: ModelClient, query: str, sources: List[Dict]) -> str:
        blocks = []
        for i, s in enumerate(sources, 1):
            blocks.append(f"[{i}] {s['title']} — {s['url']}\n{s.get('content','')}")
        context = "\n\n".join(blocks)
        prompt = (
            "You are a research assistant. Using ONLY the sources below, write a clear, "
            "well-structured answer to the question in the user's language. Cite sources "
            "inline as [1], [2], etc. End with a 'Kaynaklar' list mapping numbers to URLs.\n\n"
            f"Question: {query}\n\nSources:\n{context}"
        )
        out = await model.generate([{"role": "user", "content": prompt}],
                                   stream=False, json_mode=False)
        return (out or "").strip() or "(rapor üretilemedi)"


class _SubqSchemaProxy:
    """Minimal shim so extract_json returns the parsed dict for subqueries."""
    def __init__(self, **data):
        self._data = data

    def model_dump(self):
        return self._data
