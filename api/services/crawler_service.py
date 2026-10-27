"""Concurrent platform searches shared by JSON and SSE endpoints."""
import asyncio
import uuid
from crawler_logging import CrawlerLogger
from crawlers import AladinCrawler, KyoboCrawler, Yes24Crawler, SarakCrawler, WatchaCrawler, GoodreadsCrawler, AmazonCrawler, LibraryThingCrawler
from crawlers.foreign_resolver import resolve_foreign_query
from models.book import BookSearchResult

CRAWLERS = {"aladin": AladinCrawler, "kyobo": KyoboCrawler, "yes24": Yes24Crawler, "sarak": SarakCrawler, "watcha": WatchaCrawler, "goodreads": GoodreadsCrawler, "amazon": AmazonCrawler, "librarything": LibraryThingCrawler}
FOREIGN_PLATFORMS = {"goodreads", "amazon", "librarything"}
logger = CrawlerLogger("api")


async def crawl_platform(crawler_cls, query, fallback_query=None, original_query=None, execution_id=None):
    async def execute():
        async with crawler_cls() as crawler:
            crawler.set_session(uuid.uuid4().hex[:8], original_query or query, execution_id=execution_id)
            result = await crawler.crawl(query, attempt=1)
            if result is None and fallback_query and fallback_query != query:
                result = await crawler.crawl(fallback_query, attempt=2)
            return result
    return await asyncio.to_thread(lambda: asyncio.run(execute()))


async def _platform_results(query, platforms=None):
    selected = list(dict.fromkeys(platforms if platforms is not None else CRAWLERS))
    execution_id = uuid.uuid4().hex[:8]
    foreign_task = asyncio.create_task(resolve_foreign_query(query)) if any(p in FOREIGN_PLATFORMS for p in selected) else None

    async def run(platform):
        try:
            if platform in FOREIGN_PLATFORMS:
                foreign = await foreign_task
                if not foreign.available and not foreign.isbn:
                    return None
                return await crawl_platform(CRAWLERS[platform], foreign.isbn or foreign.query, foreign.query if foreign.isbn else None, original_query=query, execution_id=execution_id)
            return await crawl_platform(CRAWLERS[platform], query, original_query=query, execution_id=execution_id)
        except Exception as exc:
            logger.error("crawl_failed", str(exc), {"platform": platform})
            return None

    tasks = [asyncio.create_task(run(p)) for p in selected if p in CRAWLERS]
    try:
        for task in asyncio.as_completed(tasks):
            result = await task
            if result is not None:
                yield result
    finally:
        pending = tasks + ([foreign_task] if foreign_task else [])
        for task in pending:
            if not task.done():
                task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)


async def crawl_all(query, platforms=None):
    result = BookSearchResult(query=query)
    async for rating in _platform_results(query, platforms):
        result.add_result(rating)
    return result


async def crawl_all_stream(query, platforms=None):
    async for rating in _platform_results(query, platforms):
        yield BookSearchResult(query=query, results=[rating]).to_dict()["results"][0]


def get_available_platforms():
    return [{"name": name, "type": "foreign" if name in FOREIGN_PLATFORMS else "domestic"} for name in CRAWLERS]
