import asyncio
import argparse
import pandas as pd
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

async def crawl_kyobo(keyword, max_pages=1):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        results = []
        
        for current_page in range(1, max_pages + 1):
            print(f"Crawling page {current_page} for keyword: {keyword}...")
            url = f"https://search.kyobobook.co.kr/search?keyword={keyword}&page={current_page}"
            await page.goto(url)
            
            # Wait for the product list to load
            await page.wait_for_selector(".prod_list")
            
            # Get the page content and parse with BeautifulSoup
            content = await page.content()
            soup = BeautifulSoup(content, "html.parser")
            
            # Find all book items
            items = soup.select(".prod_item")
            
            if not items:
                print("No more items found.")
                break
                
            for item in items:
                try:
                    # Title: Combine all spans inside .prod_info (e.g., [국내도서] + Title)
                    title_elem = item.select_one(".prod_info")
                    if title_elem:
                        # Extract all text, which includes both the tag [국내도서] and the actual title
                        title = title_elem.get_text(" ", strip=True)
                    else:
                        title = "N/A"
                    
                    author_elem = item.select_one(".author")
                    author = author_elem.get_text(strip=True) if author_elem else "N/A"
                    
                    # Publisher: Target the 'text' link within the author information area
                    # This avoids picking up the "미리보기" (Preview) button text.
                    publisher_elem = item.select_one(".prod_author_info a.text")
                    if not publisher_elem:
                        # Fallback: try to find a link with class 'text' that is NOT an author
                        publisher_candidates = item.select("a.text")
                        publisher_elem = next((c for c in publisher_candidates if "author" not in c.get("class", [])), None)
                    
                    publisher = publisher_elem.get_text(strip=True) if publisher_elem else "N/A"
                    
                    price_elem = item.select_one(".price .val")
                    price = price_elem.get_text(strip=True) if price_elem else "N/A"
                    
                    results.append({
                        "title": title,
                        "author": author,
                        "publisher": publisher,
                        "price": price
                    })
                except Exception as e:
                    print(f"Error parsing item: {e}")
            
            # Respectful delay (as per robots.txt Crawl-delay suggestion, though simpler here)
            await asyncio.sleep(2) 

        await browser.close()
        return results

def main():
    parser = argparse.ArgumentParser(description="Kyobo Book Crawler")
    parser.add_argument("--keyword", type=str, required=True, help="Keyword to search for")
    parser.add_argument("--pages", type=int, default=1, help="Number of pages to crawl")
    parser.add_argument("--output", type=str, default="results.csv", help="Output CSV file name")
    
    args = parser.parse_args()
    
    print(f"Starting crawl for '{args.keyword}'...")
    data = asyncio.run(crawl_kyobo(args.keyword, args.pages))
    
    if data:
        df = pd.DataFrame(data)
        df.to_csv(args.output, index=False, encoding="utf-8-sig")
        print(f"Successfully saved {len(data)} items to {args.output}")
    else:
        print("No data found.")

if __name__ == "__main__":
    main()
