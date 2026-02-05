
import os
import json
import urllib.parse
import urllib.request

def test_google_books(query):
    api_key = os.environ.get("GOOGLE_BOOKS_API_KEY", "")
    if not api_key:
        with open(".env") as f:
            for line in f:
                if line.startswith("GOOGLE_BOOKS_API_KEY="):
                    api_key = line.strip().split("=", 1)[1]
                    break
    
    encoded = urllib.parse.quote(query)
    url = f"https://www.googleapis.com/books/v1/volumes?q={encoded}&key={api_key}"
    
    print(f"Query: {query}")
    req = urllib.request.Request(url)
    req.add_header("User-Agent", "Mozilla/5.0")

    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        
    print(f"Total items: {data.get('totalItems')}")
    for i, item in enumerate(data.get('items', [])[:3]):
        info = item.get('volumeInfo', {})
        print(f"[{i}] Title: {info.get('title')}")
        print(f"    Authors: {info.get('authors')}")
        print(f"    ISBNs: {info.get('industryIdentifiers')}")

if __name__ == "__main__":
    test_google_books("Noces suivi de L'Été 알베르 카뮈")
