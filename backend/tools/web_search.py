"""Web search tool using Brave Search API."""

from __future__ import annotations

import os
from typing import Any, Dict, List
import time

import requests
from dotenv import load_dotenv

from backend.tools import BaseTool

load_dotenv()


class WebSearchTool:
    name = "web_search"
    description = "Perform web search using Brave Search API and return top results."

    DEFAULT_RESULTS = 5
    MAX_RESULTS = 10
    DEFAULT_TIMEOUT = 10

    brave_endpoint = "https://api.search.brave.com/res/v1/web/search"

    # Rate-limit için (Brave: 1 QPS)
    _last_call_timestamp = 0

    def _prepare_query(self, query: str) -> str:
        return " ".join((query or "").split())

    def _extract_results(self, payload: dict) -> List[Dict[str, Any]]:
        """Extract Brave Search results -> normalized {title, link, snippet}."""
        results = payload.get("web", {}).get("results", [])
        normalized = []

        for item in results:
            title = item.get("title") or ""
            link = item.get("url") or ""
            snippet = item.get("description") or ""
            normalized.append({"title": title, "link": link, "snippet": snippet})

        return normalized

    def _rate_limit(self):
        now = time.time()
        since_last = now - self._last_call_timestamp

        # Brave = 1 QPS -> en az 1 saniye beklemeli
        if since_last < 1.0:
            time.sleep(1.0 - since_last)

        self._last_call_timestamp = time.time()

    def run(self, query: str, **kwargs: Any) -> Dict[str, Any]:
        q = self._prepare_query(kwargs.get("query") or query or "")

        api_key = os.getenv("WEB_SEARCH_API_KEY")
        timeout = float(os.getenv("WEB_SEARCH_TIMEOUT", self.DEFAULT_TIMEOUT))
        num_results = int(kwargs.get("num_results") or self.DEFAULT_RESULTS)
        num_results = max(1, min(num_results, self.MAX_RESULTS))

        if not q:
            return {"status": "error", "message": "Query is empty."}

        if not api_key:
            return {"status": "error", 
                    "message": "WEB_SEARCH_API_KEY missing. Set your Brave API key in .env."}

        # Rate limit (Brave: 1 request per second)
        self._rate_limit()

        try:
            headers = {
                "X-Subscription-Token": api_key,
                "Accept": "application/json"
            }

            params = {
                "q": q,
                "count": num_results
            }

            resp = requests.get(
                self.brave_endpoint,
                params=params,
                headers=headers,
                timeout=timeout
            )
            resp.raise_for_status()

            data = resp.json()
            results = self._extract_results(data)
            limited = results[:num_results]

            return {
                "status": "ok",
                "query": q,
                "results": limited,
                "count": len(limited),
                "provider": "Brave Search API",
            }

        except Exception as e:
            return {"status": "error", "query": q, "message": str(e)}



