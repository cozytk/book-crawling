
import os
import asyncio
import json
from crawlers.aladin import AladinCrawler

async def debug_aladin():
    crawler = AladinCrawler()
    query = "노이즈"
    print(f"Searching for: {query}")
    
    params = {
        "Query": query,
        "QueryType": "Keyword",
        "MaxResults": 10,
        "SearchTarget": "Book",
    }
    result = crawler._api_request("ItemSearch.aspx", params)
    
    if result and result.get("item"):
        for i, item in enumerate(result["item"]):
            print(f"[{i}] Title: {item.get('title')}")
            print(f"    Author: {item.get('author')}")
            print(f"    Publisher: {item.get('publisher')}")
            print(f"    SalesPoint: {item.get('salesPoint')}")
            print(f"    ItemId: {item.get('itemId')}")
            print(f"    ISBN: {item.get('isbn13')}")

        
if __name__ == "__main__":
    asyncio.run(debug_aladin())
