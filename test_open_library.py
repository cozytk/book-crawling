
import json
import urllib.parse
import urllib.request

def test_open_library(title):
    encoded = urllib.parse.quote(title)
    url = f"https://openlibrary.org/search.json?q={encoded}&limit=5"
    
    print(f"Requesting: {url}")
    req = urllib.request.Request(url)
    req.add_header("User-Agent", "Mozilla/5.0")

    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        
    print(f"Total items: {data.get('numFound')}")
    for i, doc in enumerate(data.get('docs', [])):
        print(f"[{i}] Title: {doc.get('title')}")
        print(f"    Authors: {doc.get('author_name')}")
        print(f"    ISBNs: {doc.get('isbn')[:5] if doc.get('isbn') else None}")

if __name__ == "__main__":
    test_open_library("Noces suivi de L'Été")
