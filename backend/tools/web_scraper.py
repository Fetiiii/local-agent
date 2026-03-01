import requests
import trafilatura
from typing import Dict, Any

class WebScraperTool:
    name = "web_scraper"
    description = "Downloads and extracts clean text content from a given URL. Use this to READ a webpage."
    
    # Context window protection: Limit characters returned
    MAX_CHARS = 8000 

    def run(self, url: str, **kwargs) -> Dict[str, Any]:
        """
        Fetches the URL and returns the main text content.
        """
        try:
            # 1. Fetch HTML
            downloaded = trafilatura.fetch_url(url)
            
            # 1.a Fallback to requests if trafilatura fetch fails (e.g. 403 with default headers)
            if not downloaded:
                headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
                try:
                    resp = requests.get(url, headers=headers, timeout=10)
                    resp.raise_for_status()
                    downloaded = resp.text
                except Exception as req_err:
                    print(f"Fallback request failed: {req_err}")
            
            if not downloaded:
                return {
                    "text": f"❌ Failed to download content from: {url} (Possible 403/404 or Timeout)...",
                    "artifacts": []
                }
            
            # 2. Extract Text
            text = trafilatura.extract(
                downloaded, 
                include_comments=False, 
                include_tables=True, 
                no_fallback=False
            )
            
            if not text:
                return {
                    "text": f"⚠️ Downloaded {url} but could not extract valid text. It might be a JS-heavy app or empty.",
                    "artifacts": []
                }

            # 3. Truncate if too long
            original_len = len(text)
            if original_len > self.MAX_CHARS:
                text = text[:self.MAX_CHARS] + f"[...Content Truncated. Original length: {original_len} chars...]"

            return {
                "text": f"✅ Content from {url}:{text}",
                "artifacts": []
            }

        except Exception as e:
            return {
                "text": f"❌ Scraper Error: {str(e)}",
                "artifacts": []
            }
