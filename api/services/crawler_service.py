"""기존 크롤러를 래핑하는 서비스 레이어"""

import asyncio
import uuid
import sys
import os

# 프로젝트 루트를 Python 경로에 추가 (api/ 하위에서 crawlers/ 접근)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from crawler_logging import CrawlerLogger
from crawlers import (
    AladinCrawler,
    KyoboCrawler,
    Yes24Crawler,
    SarakCrawler,
    WatchaCrawler,
    GoodreadsCrawler,
    AmazonCrawler,
    LibraryThingCrawler,
)
from crawlers.base import BaseCrawler
from crawlers.foreign_resolver import resolve_foreign_query, ForeignQuery
from models.book import BookSearchResult, PlatformRating

# 크롤러 레지스트리
CRAWLERS: dict[str, type[BaseCrawler]] = {
    "aladin": AladinCrawler,
    "kyobo": KyoboCrawler,
    "yes24": Yes24Crawler,
    "sarak": SarakCrawler,
    "watcha": WatchaCrawler,
    "goodreads": GoodreadsCrawler,
    "amazon": AmazonCrawler,
    "librarything": LibraryThingCrawler,
}

FOREIGN_PLATFORMS = {"goodreads", "amazon", "librarything"}

logger = CrawlerLogger("api")


async def crawl_platform(
    crawler_cls: type[BaseCrawler],
    query: str,
    fallback_query: str | None = None,
    original_query: str | None = None,
    execution_id: str | None = None,
) -> PlatformRating | None:
    """단일 플랫폼 크롤링 (스레드 기반 병렬 실행)"""
    session_id = uuid.uuid4().hex[:8]
    orig = original_query or query

    async def _execute():
        async with crawler_cls() as crawler:
            crawler.set_session(session_id, orig, execution_id=execution_id)
            result = await crawler.crawl(query, attempt=1)
            if result is None and fallback_query and fallback_query != query:
                result = await crawler.crawl(fallback_query, attempt=2)
            return result

    return await asyncio.to_thread(lambda: asyncio.run(_execute()))


async def crawl_all(
    query: str, platforms: list[str] | None = None
) -> BookSearchResult:
    """
    여러 플랫폼에서 병렬 크롤링

    main.py의 crawl_all_platforms()와 동일한 로직.
    """
    execution_id = uuid.uuid4().hex[:8]
    logger.set_execution_id(execution_id)

    if platforms is None:
        platforms = list(CRAWLERS.keys())

    valid_platforms = [p for p in platforms if p in CRAWLERS]
    if not valid_platforms:
        return BookSearchResult(query=query)

    # 해외 플랫폼 검색어 해석
    foreign = ForeignQuery()
    has_foreign = any(p in FOREIGN_PLATFORMS for p in valid_platforms)
    if has_foreign:
        foreign = await resolve_foreign_query(query)

    # 태스크 생성
    tasks = []
    task_platforms = []
    for p in valid_platforms:
        if p in FOREIGN_PLATFORMS:
            if foreign.isbn:
                tasks.append(crawl_platform(
                    CRAWLERS[p], foreign.isbn, foreign.query,
                    original_query=query, execution_id=execution_id
                ))
                task_platforms.append(p)
            elif foreign.query:
                tasks.append(crawl_platform(
                    CRAWLERS[p], foreign.query,
                    original_query=query, execution_id=execution_id
                ))
                task_platforms.append(p)
        else:
            tasks.append(crawl_platform(
                CRAWLERS[p], query,
                original_query=query, execution_id=execution_id
            ))
            task_platforms.append(p)

    results = await asyncio.gather(*tasks, return_exceptions=True)

    search_result = BookSearchResult(query=query)
    for platform, result in zip(task_platforms, results):
        if isinstance(result, Exception):
            logger.error("crawl_failed", str(result), {"platform": platform})
        elif result is not None:
            search_result.add_result(result)

    return search_result


async def crawl_all_stream(
    query: str, platforms: list[str] | None = None
):
    """
    여러 플랫폼에서 병렬 크롤링 - 결과를 하나씩 yield

    Yields:
        dict: 각 플랫폼 결과 (PlatformRating.to_dict() 형태)
    """
    execution_id = uuid.uuid4().hex[:8]
    logger.set_execution_id(execution_id)

    if platforms is None:
        platforms = list(CRAWLERS.keys())

    valid_platforms = [p for p in platforms if p in CRAWLERS]
    if not valid_platforms:
        return

    # 해외 플랫폼 검색어 해석
    foreign = ForeignQuery()
    has_foreign = any(p in FOREIGN_PLATFORMS for p in valid_platforms)
    if has_foreign:
        foreign = await resolve_foreign_query(query)

    # 태스크 생성 (platform name -> task mapping)
    tasks = {}
    for p in valid_platforms:
        if p in FOREIGN_PLATFORMS:
            if foreign.isbn:
                task = asyncio.ensure_future(crawl_platform(
                    CRAWLERS[p], foreign.isbn, foreign.query,
                    original_query=query, execution_id=execution_id
                ))
                tasks[task] = p
            elif foreign.query:
                task = asyncio.ensure_future(crawl_platform(
                    CRAWLERS[p], foreign.query,
                    original_query=query, execution_id=execution_id
                ))
                tasks[task] = p
        else:
            task = asyncio.ensure_future(crawl_platform(
                CRAWLERS[p], query,
                original_query=query, execution_id=execution_id
            ))
            tasks[task] = p

    # 결과를 하나씩 yield
    for coro in asyncio.as_completed(list(tasks.keys())):
        try:
            result = await coro
            if result is not None:
                yield result.to_dict()
        except Exception as e:
            logger.error("crawl_failed", str(e))


def get_available_platforms() -> list[dict]:
    """사용 가능한 플랫폼 목록"""
    return [
        {"name": name, "type": "foreign" if name in FOREIGN_PLATFORMS else "domestic"}
        for name in CRAWLERS
    ]
