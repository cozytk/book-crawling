"""Validated concurrent search with source caches and shared in-flight jobs."""
import asyncio
import uuid
from dataclasses import dataclass, fields
from datetime import datetime

from crawler_logging import CrawlerLogger
from crawlers import AladinCrawler, KyoboCrawler, Yes24Crawler, SarakCrawler, WatchaCrawler, GoodreadsCrawler, AmazonCrawler, LibraryThingCrawler
from crawlers.foreign_resolver import resolve_foreign_query
from crawlers.work_identity import resolve_work_identity, WorkIdentity
from crawlers.transport import SearchTransport, run_parser
from crawlers.utils import is_isbn
from models.book import BookSearchResult, PlatformRating
from api import platform_cache

CRAWLERS = {"aladin": AladinCrawler, "kyobo": KyoboCrawler, "yes24": Yes24Crawler, "sarak": SarakCrawler, "watcha": WatchaCrawler, "goodreads": GoodreadsCrawler, "amazon": AmazonCrawler, "librarything": LibraryThingCrawler}
FOREIGN_PLATFORMS = {"goodreads", "amazon", "librarything"}
logger = CrawlerLogger("api")
PLATFORM_TIMEOUT = 18
RESOLVE_TIMEOUT = 12
REASONS = {"not_found": "일치하는 책을 찾지 못했습니다", "identity_mismatch": "상품·제목·ISBN이 일치하지 않습니다",
           "blocked": "사이트에서 수집을 차단하거나 요청을 제한했습니다", "timeout": "응답 대기 시간을 초과했습니다",
           "parse_error": "상품은 찾았지만 점수 또는 평가 수를 모두 확인하지 못했습니다", "network_error": "사이트 연결에 실패했습니다",
           "unavailable": "원서 정보를 확인하지 못했습니다"}


async def crawl_platform(crawler_cls, query, fallback_query=None, original_query=None, execution_id=None,
                         expected_author=None, on_failure=None, identity_title=None, identity_isbn=None):
    async def execute():
        async with crawler_cls() as crawler:
            crawler.set_session(uuid.uuid4().hex[:8], original_query or query, execution_id=execution_id)
            expected_title = identity_title or (fallback_query if fallback_query and not is_isbn(fallback_query) else (query if not is_isbn(query) else None))
            crawler.expected_identity(expected_title, expected_author, strict_isbn=is_isbn(original_query or query))
            crawler._preferred_isbn = identity_isbn
            result = await crawler.crawl(query, attempt=1)
            if result is None and fallback_query and fallback_query != query and not is_isbn(original_query or ""):
                crawler.failure_status = None
                result = await crawler.crawl(fallback_query, attempt=2)
            return result, crawler.failure_status
    (result, failure), network_failure = await run_parser(lambda: asyncio.run(execute()))
    failure = failure if failure == "identity_mismatch" else network_failure or failure
    if on_failure and failure:
        on_failure(failure)
    return result


def rating_dict(rating):
    return BookSearchResult(query="", results=[rating]).to_dict()["results"][0]


def rating_from_dict(value):
    allowed = {f.name for f in fields(PlatformRating)}
    payload = {key: item for key, item in value.items() if key in allowed}
    if isinstance(payload.get("crawled_at"), str):
        payload["crawled_at"] = datetime.fromisoformat(payload["crawled_at"])
    return PlatformRating(**payload)


async def _platform_results(query, platforms=None, on_status=None, force_refresh=False, cache=None):
    selected = list(dict.fromkeys(platforms if platforms is not None else CRAWLERS))
    execution_id = uuid.uuid4().hex[:8]
    foreign_task = None
    identity_task = None
    cache_writes = []

    async def run(platform):
        nonlocal foreign_task, identity_task
        failure = []
        result = None
        status = "not_found"
        if cache and not force_refresh:
            cached = await platform_cache.read(cache, query, platform)
            if cached:
                if on_status:
                    on_status({"platform": platform, "status": cached["status"], "reason": cached["reason"], "source": "cache"})
                return rating_from_dict(cached["rating"]) if cached.get("rating") else None
        try:
            if platform in FOREIGN_PLATFORMS:
                if foreign_task is None:
                    foreign_task = asyncio.create_task(resolve_foreign_query(query))
                foreign = await asyncio.wait_for(asyncio.shield(foreign_task), RESOLVE_TIMEOUT)
                if not foreign.available and not foreign.isbn:
                    status = "unavailable"
                else:
                    source_query = (foreign.query or foreign.isbn) if not is_isbn(query) else foreign.isbn or foreign.query
                    fallback = foreign.isbn if source_query == foreign.query else foreign.query
                    result = await asyncio.wait_for(crawl_platform(CRAWLERS[platform], source_query,
                        fallback, original_query=query, execution_id=execution_id,
                        expected_author=foreign.author, on_failure=failure.append), PLATFORM_TIMEOUT)
            else:
                if identity_task is None:
                    identity_task = asyncio.create_task(resolve_work_identity(query))
                try:
                    identity = await asyncio.wait_for(asyncio.shield(identity_task), 3)
                except Exception:
                    identity = WorkIdentity()
                # Reuse the catalog's edition identifier where supported. If
                # that edition is unavailable, retry the title under the same
                # author constraint. Watcha uses a title-based book catalog.
                if not is_isbn(query) and not identity.isbn and not identity.author:
                    reason="비교할 작품의 저자·판본을 확인하지 못했습니다"
                    if on_status:
                        on_status({"platform":platform,"status":"unavailable","reason":reason,"source":"crawl"})
                    if cache:
                        cache_writes.append(asyncio.create_task(platform_cache.write(cache,query,platform,"unavailable",None,reason)))
                    return None
                source_query = query if platform in {"kyobo", "watcha"} else identity.isbn or query
                if platform == "watcha":
                    source_query = identity.title or query
                result = await asyncio.wait_for(crawl_platform(CRAWLERS[platform], source_query,
                    fallback_query=query if source_query != query and platform != "watcha" else None, original_query=query,
                    execution_id=execution_id, expected_author=identity.author, identity_title=identity.title,
                    identity_isbn=identity.isbn,
                    on_failure=failure.append), PLATFORM_TIMEOUT)
            if result and ((result.rating is not None and result.review_count is not None) or result.rating_count == 0 or result.text_review_count == 0):
                status = "done"
            elif failure:
                status = failure[-1]
            elif result:
                status = "parse_error"
        except asyncio.TimeoutError:
            status = "timeout"
        except Exception:
            logger.error("crawl_failed", "Platform lookup failed", {"platform": platform})
            status = "network_error"
        reason = REASONS.get(status)
        if on_status:
            on_status({"platform": platform, "status": status, "reason": reason, "source": "crawl"})
        if cache:
            cache_writes.append(asyncio.create_task(platform_cache.write(cache, query, platform, status,
                                rating_dict(result) if result else None, reason)))
        return result

    tasks = [asyncio.create_task(run(p)) for p in selected if p in CRAWLERS]
    try:
        for task in asyncio.as_completed(tasks):
            result = await task
            if result is not None:
                yield result
        if cache_writes:
            await asyncio.gather(*cache_writes, return_exceptions=True)
    finally:
        pending = tasks + ([foreign_task] if foreign_task else []) + ([identity_task] if identity_task else []) + cache_writes
        for task in pending:
            if not task.done():
                task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)


@dataclass
class SearchJob:
    task: asyncio.Task | None
    events: list
    listeners: set


_jobs = {}


async def _subscribe(query, platforms=None, force_refresh=False, cache=None):
    selected = tuple(sorted(platforms if platforms is not None else CRAWLERS))
    key = (query.casefold(), selected, force_refresh)
    loop = asyncio.get_running_loop()
    job = _jobs.get(key)
    if job and job.task.get_loop() is not loop:
        job = None
    if job is None:
        job = SearchJob(None, [], set())
        _jobs[key] = job

        def emit(event, data):
            item = (event, data)
            job.events.append(item)
            for queue in list(job.listeners):
                queue.put_nowait(item)

        async def collect():
            try:
                async with SearchTransport() as transport:
                    async for rating in _platform_results(query, selected, lambda value: emit("status", value), force_refresh, cache):
                        emit("rating", rating)
                    emit("metrics", {"http_requests": sum(transport.counts.values()), "requests_by_domain": dict(transport.counts),
                                     "diagnostics": transport.diagnostics})
            except Exception:
                emit("error", "검색 중 오류가 발생했습니다")
            finally:
                emit("done", None)
                if _jobs.get(key) is job:
                    _jobs.pop(key, None)
        job.task = asyncio.create_task(collect())
    queue = asyncio.Queue()
    for item in job.events:
        queue.put_nowait(item)
    job.listeners.add(queue)
    try:
        while True:
            event, data = await queue.get()
            if event == "done":
                return
            if event == "error":
                raise RuntimeError(data)
            yield event, data
    finally:
        job.listeners.discard(queue)
        if not job.listeners and not job.task.done():
            job.task.cancel()
            await asyncio.gather(job.task, return_exceptions=True)


async def crawl_all(query, platforms=None, force_refresh=False, cache=None):
    result = BookSearchResult(query=query)
    subscription = _subscribe(query, platforms, force_refresh, cache)
    try:
        async for event, data in subscription:
            if event == "rating":
                result.add_result(data)
    finally:
        await subscription.aclose()
    return result


async def crawl_all_stream(query, platforms=None, on_status=None, force_refresh=False, cache=None, on_metrics=None):
    subscription = _subscribe(query, platforms, force_refresh, cache)
    try:
        async for event, data in subscription:
            if event == "rating":
                yield rating_dict(data)
            elif event == "status" and on_status:
                on_status(data)
            elif event == "metrics" and on_metrics:
                on_metrics(data)
    finally:
        await subscription.aclose()


def get_available_platforms():
    return [{"name": name, "type": "foreign" if name in FOREIGN_PLATFORMS else "domestic"} for name in CRAWLERS]
