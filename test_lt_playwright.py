import asyncio
from crawlers.librarything import LibraryThingCrawler

async def test():
    crawler = LibraryThingCrawler()
    async with crawler:
        url, title = await crawler.search_book("Material World")
        print(f"Result: {url}, {title}")
        if url:
            rating = await crawler.get_rating(url)
            print(f"Rating: {rating}")

if __name__ == "__main__":
    asyncio.run(test())
