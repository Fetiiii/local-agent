import asyncio
import os
import sys
from pathlib import Path

# Ensure project root is importable when run directly (python tests/test_all.py)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Test the in-process (local) data_analyst path, not the Docker sandbox.
os.environ.setdefault("SANDBOX_BACKEND", "local")

import pandas as pd
from backend.tools.data_analyst import DataAnalystTool
from backend.tools.web_scraper import WebScraperTool
from utils.helpers import extract_json

async def test_data_analyst_persistence():
    print("\n🧪 Testing Data Analyst Persistence...")
    tool = DataAnalystTool()
    
    # Step 1: Define a variable
    code1 = "df = pd.DataFrame({'a': [1, 2], 'b': [3, 4]})"
    res1 = await tool.run(code1)
    print(f"Step 1 Result: {res1['text']}")

    # Step 2: Use the variable in a new call
    code2 = "print(df.shape)"
    res2 = await tool.run(code2)
    print(f"Step 2 Result: {res2['text']}")
    
    if "(2, 2)" in res2['text']:
        print("✅ Data Analyst Persistence Passed!")
    else:
        print("❌ Data Analyst Persistence Failed!")

def test_web_scraper():
    print("\n🧪 Testing Web Scraper...")
    tool = WebScraperTool()
    url = "https://example.com"
    res = tool.run(url)
    print(f"Scraper Result Length: {len(res['text'])}")

    text = res["text"]
    # trafilatura extracts body text (not the <title>), so assert on successful
    # extraction of the example.com body rather than the page title.
    ok = "❌" not in text and ("documentation" in text.lower() or "example" in text.lower())
    if ok:
        print("✅ Web Scraper Passed!")
    else:
        print(f"❌ Web Scraper Failed (Text: {text[:100]}...)")

def test_json_extraction():
    print("\n🧪 Testing JSON Extraction...")
    
    # Case 1: Legacy Valid JSON
    valid_json = '{"thought": "test", "tool_name": "web_search", "tool_args": {"query": "python"}, "final_answer": null}'
    res1 = extract_json(valid_json)
    if res1 and res1.get('tool_calls', [{}])[0].get('name') == "web_search":
        print("✅ Valid JSON Passed (Legacy Format Remapped)")
    else:
        print("❌ Valid JSON Failed")

    # Case 2: Broken JSON (Missing brace)
    broken_json_2 = '{"thought": "test", "tool_calls": [{"name": "web_search", "args": {"query": "python"'
    
    res2 = extract_json(broken_json_2)
    if res2 and res2.get('tool_calls', [{}])[0].get('name') == "web_search":
        print("✅ Broken JSON Passed (Repaired)")
    else:
        print(f"❌ Broken JSON Failed: {res2}")

async def main():
    await test_data_analyst_persistence()
    test_web_scraper()
    test_json_extraction()

if __name__ == "__main__":
    asyncio.run(main())
