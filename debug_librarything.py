import asyncio
import urllib.parse
import re
from crawlers.librarything import LibraryThingCrawler

async def debug_lt():
    crawler = LibraryThingCrawler()
    query = "Material World: A Substantial Story of Our Past and Future"
    print(f"Searching for: {query}")
    
    # Try with term parameter and primary title
    # primary = "Material World"
    primary = "Demian"
    term_encoded = urllib.parse.quote(primary)
    search_url = f"{crawler.base_url}/search.php?term={term_encoded}&searchtype=newwork_titles"
    print(f"URL: {search_url}")
    html, _ = crawler._fetch_with_scraper(search_url)
    
    # Find results section (second or later occurrence)
    pattern = re.compile("Material World", re.IGNORECASE)
    matches = list(pattern.finditer(html))
    print(f"Occurrences found: {len(matches)}")
    
    for i, m in enumerate(matches):
        start = m.start()
        print(f"\n--- Occurrence {i+1} at {start} ---")
        print(html[start-50:start+250])
        if i > 5: break

if __name__ == "__main__":
    asyncio.run(debug_lt())
