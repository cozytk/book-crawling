import asyncio
import json
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest
from bs4 import BeautifulSoup

from crawlers.utils import title_score, author_matches
from crawlers.librarything import LibraryThingCrawler
from crawlers.goodreads import GoodreadsCrawler
from crawlers.amazon import AmazonCrawler
from crawlers.yes24 import Yes24Crawler
from crawlers.kyobo import KyoboCrawler
from crawlers.watcha import WatchaCrawler
from crawlers.transport import SearchTransport, fetch_sync, run_parser
from crawlers.aladin import AladinCrawler
from crawlers.foreign_resolver import resolve_foreign_query
from api import platform_cache
from api.local_store import LocalStore
from api.services import crawler_service
from models.book import PlatformRating

GOLDEN = json.loads((Path(__file__).parent / "fixtures/search-golden.json").read_text())


@pytest.mark.parametrize("case", GOLDEN, ids=[c["query"] + "→" + c["title"] for c in GOLDEN])
def test_title_identity_corpus(case):
    assert bool(title_score(case["query"], case["title"])) == case["match"]


def test_author_surname_alone_does_not_override_conflicting_full_name():
    assert not author_matches("Robert Martin", "George Martin")
    assert author_matches("Robert C. Martin", "Robert Martin")


def test_librarything_unrelated_search_and_unscoped_decimal_are_rejected():
    crawler = LibraryThingCrawler()
    links = BeautifulSoup('<p class="item"><a href="/work/1">Wrong Book</a></p>', "html.parser").select("a")
    assert crawler._select_best_link(links, "Clean Code") is None
    assert crawler._parse_work_page('<h1>Clean Code</h1><p>Price (2.99)</p>')[1] is None
    assert crawler._normalize_work_url("https://evil.example/work/12") is None


def test_librarything_wrong_redirect_is_rejected():
    crawler = LibraryThingCrawler()
    with patch.object(crawler, "_fetch_with_scraper", return_value=("<h1>Wrong Book</h1>", "https://www.librarything.com/work/1")), patch.object(crawler, "_search_via_search_page", return_value=(None, "")):
        assert crawler.search_by_keyword("Clean Code") == (None, "")


def detail(kind="Book", score=4.3, isbn="9780132350884", name="Clean Code"):
    node = {"@type": kind, "name": name, "isbn": isbn, "aggregateRating": {"ratingValue": score, "ratingCount": 23, "reviewCount": 7}}
    return '<h1 data-testid="bookTitle">Clean Code</h1><script type="application/ld+json">' + json.dumps(node) + '</script>'


def test_goodreads_checks_book_node_scale_and_isbn():
    crawler = GoodreadsCrawler()
    assert crawler._parse_detail_page(detail(score=8))[1] is None
    assert crawler._parse_detail_page(detail(kind="Movie"))[1] is None
    assert crawler._parse_detail_page(detail(name="Wrong Book"))[1] is None
    assert crawler._parse_detail_page(detail())[1:] == (4.3, 23)
    assert crawler.rating_count == 23 and crawler.text_review_count == 7
    with patch.object(crawler, "_fetch_with_redirect", return_value=(detail(isbn="9781594205071"), "https://www.goodreads.com/book/show/1")):
        assert crawler.search_by_identifier("9780132350884") == (None, "")


async def test_yes24_generic_number_is_not_a_rating_or_known_zero():
    crawler = Yes24Crawler()
    with patch.object(crawler, "_fetch_html", return_value='<span class="yes_b">5</span>'):
        rating, count = await crawler.get_rating("https://example.com")
    record = crawler.result_record("Clean Code", "https://example.com", "Clean Code", rating, count)
    assert record.rating is None and record.review_count is None
    assert record.rating_count is None and record.text_review_count is None
    with patch.object(crawler, "_fetch_html", return_value='<span class="gd_rating"><em>9.3</em></span><em id="scroll_bar_count" data-review-count="566">(566/709)</em>'):
        assert await crawler.get_rating("https://example.com") == (9.3, 566)
        assert crawler.text_review_count == 566 and crawler.rating_count is None


def test_kyobo_isbn_in_unrelated_text_cannot_identify_a_product():
    crawler = KyoboCrawler()
    html = '<div class="prod_item"><a class="prod_info" href="/detail/S1">Wrong Book</a><p>추천 ISBN 9788937460449</p></div>'
    with patch.object(crawler, "_fetch_html", return_value=html):
        assert crawler.search_by_keyword("9788937460449") == (None, "")
    html = '<div class="prod_item" data-isbn="9788937460449"><a class="prod_info" href="/detail/S1">데미안 리커버 에디션</a></div>'
    with patch.object(crawler, "_fetch_html", return_value=html):
        assert crawler.search_by_keyword("9788937460449")[0].endswith("/detail/S1")


def test_yes24_tracking_query_is_not_isbn_evidence():
    crawler = Yes24Crawler()
    search = '<a class="gd_name" href="/product/goods/176787" onclick="setGoodsClickExtraCodeHub(\'032\', \'9788937460449\', \'176787\', \'0\',this)">데미안</a>'
    with patch.object(crawler, "_fetch_html", return_value=search):
        assert crawler.search_by_keyword("9788937460449") == (None, "")
    page = '<script type="application/ld+json">' + json.dumps({"@type":"Book", "name":"데미안", "isbn":"9788937460449", "sku":"176787"}) + '</script>'
    with patch.object(crawler, "_fetch_html", side_effect=[search, page]):
        assert crawler.search_by_keyword("9788937460449")[1] == "데미안"
    with patch.object(crawler, "_fetch_html", side_effect=[search, page.replace("9788937460449", "9780132350884")]):
        assert crawler.search_by_keyword("9788937460449") == (None, "")


def test_amazon_isbn13_maps_to_isbn10_and_ignores_individual_review():
    crawler = AmazonCrawler()
    html = '<span id="productTitle">Clean Code</span><script type="application/ld+json">' + json.dumps({"@type": "Book", "name": "Clean Code", "isbn": "9780132350884"}) + '</script><span class="a-icon-alt">4.9 out of 5 stars</span>'
    with patch.object(crawler, "_fetch_with_headers", return_value=html) as fetch:
        assert crawler.search_by_identifier("9780132350884")[0].endswith("/dp/0132350882")
    assert fetch.call_args.args[0].endswith("/dp/0132350882")
    assert crawler._cached_rating is None


async def test_watcha_title_metadata_and_book_type_are_checked():
    crawler = WatchaCrawler()
    html = '<a href="/ko/contents/bo12">데미안 2020 ・ 헤르만 헤세 책</a>'
    with patch.object(crawler, "_fetch_html", return_value=html):
        assert crawler.search_by_keyword("데미안")[1] == "데미안"
    with patch.object(crawler, "_fetch_html", return_value=detail(kind="Movie", name="데미안")):
        assert await crawler.get_rating("https://pedia.watcha.com/ko/contents/bo12") == (None, 0)


async def test_async_http_deduplicates_and_limits_domain_concurrency():
    active = 0
    maximum = 0
    calls = 0
    async def handler(request):
        nonlocal active, maximum, calls
        calls += 1; active += 1; maximum = max(maximum, active)
        await asyncio.sleep(.01)
        active -= 1
        return httpx.Response(200, text="ok")
    async with SearchTransport(httpx.AsyncClient(transport=httpx.MockTransport(handler))) as transport:
        await asyncio.gather(*(transport.get(f"https://example.com/{i % 5}") for i in range(20)))
        assert calls == 5 and maximum <= 3
        assert sum(transport.counts.values()) == 5


async def test_canceling_parser_cancels_inflight_http():
    started = asyncio.Event(); canceled = asyncio.Event()
    async def handler(request):
        started.set()
        try:
            await asyncio.sleep(30)
        finally:
            canceled.set()
    async with SearchTransport(httpx.AsyncClient(transport=httpx.MockTransport(handler))):
        worker = asyncio.create_task(run_parser(lambda: fetch_sync("https://example.com/slow")))
        await started.wait()
        worker.cancel()
        await asyncio.gather(worker, return_exceptions=True)
        await asyncio.wait_for(canceled.wait(), 1)


async def test_identical_searches_share_one_collection(monkeypatch):
    calls = 0
    async def crawl(cls, query, **kwargs):
        nonlocal calls
        calls += 1
        await asyncio.sleep(.02)
        return PlatformRating(cls.name, 9, 10, 12, "https://example.com", query)
    monkeypatch.setattr(crawler_service, "crawl_platform", crawl)
    async def consume():
        return [r async for r in crawler_service.crawl_all_stream("unique job", ["yes24"])]
    first, second = await asyncio.gather(consume(), consume())
    assert calls == 1 and first == second


async def test_one_disconnected_subscriber_does_not_cancel_the_other(monkeypatch):
    started = asyncio.Event(); release = asyncio.Event()
    calls = 0
    async def crawl(cls, query, **kwargs):
        nonlocal calls
        calls += 1; started.set()
        await release.wait()
        return PlatformRating(cls.name, 9, 10, 12, "https://example.com", query)
    monkeypatch.setattr(crawler_service, "crawl_platform", crawl)
    async def consume():
        return [r async for r in crawler_service.crawl_all_stream("disconnect subscriber", ["yes24"])]
    first, second = asyncio.create_task(consume()), asyncio.create_task(consume())
    await started.wait()
    first.cancel()
    await asyncio.gather(first, return_exceptions=True)
    release.set()
    assert len(await second) == 1 and calls == 1


async def test_detail_block_remains_blocked_instead_of_becoming_a_parse_error():
    async def handler(request):
        if "/Search" in str(request.url):
            return httpx.Response(200, text='<a class="gd_name" href="/product/goods/1">Clean Code</a>')
        return httpx.Response(403)
    failures = []
    async with SearchTransport(httpx.AsyncClient(transport=httpx.MockTransport(handler))):
        result = await crawler_service.crawl_platform(Yes24Crawler, "Clean Code", on_failure=failures.append)
    assert failures == ["blocked"]
    assert result.rating is None and result.review_count is None


async def test_source_failure_expires_without_recrawling_success(tmp_path, monkeypatch):
    platform_cache.clear_memory()
    store = LocalStore(str(tmp_path / "source-cache.sqlite3"))
    calls = {"yes24": 0, "kyobo": 0}
    async def crawl(cls, query, **kwargs):
        calls[cls.name] += 1
        if cls.name == "kyobo":
            kwargs["on_failure"]("blocked")
            return None
        return PlatformRating(cls.name, 9, 10, 12, "https://example.com", query)
    monkeypatch.setattr(crawler_service, "crawl_platform", crawl)
    await crawler_service.crawl_all("source ttl", ["yes24", "kyobo"], cache=store)
    now = platform_cache.time.time()
    monkeypatch.setattr(platform_cache.time, "time", lambda: now + 61)
    await crawler_service.crawl_all("source ttl", ["yes24", "kyobo"], cache=store)
    assert calls == {"yes24": 1, "kyobo": 2}


async def test_aladin_domestic_and_foreign_share_search_and_detail(monkeypatch):
    monkeypatch.setenv("ALADIN_TTB_KEY", "fixture-key")
    async def handler(request):
        item = {"itemId": 1, "title": "데미안", "link": "https://www.aladin.co.kr/shop/wproduct.aspx?ItemId=1",
                "author": "헤르만 헤세 (지은이), 홍길동 (옮긴이)", "isbn13": "9788937460449",
                "subInfo": {"originalTitle": "Demian", "ratingInfo": {"ratingScore": 8.8, "ratingCount": 456}}}
        await asyncio.sleep(.01)
        return httpx.Response(200, json={"item": [item]})
    with patch("crawlers.foreign_resolver.ISBNLookup.search", return_value=None), patch("crawlers.foreign_resolver.original_author_for_isbn", return_value=None):
        async with SearchTransport(httpx.AsyncClient(transport=httpx.MockTransport(handler))) as transport:
            domestic, foreign = await asyncio.gather(crawler_service.crawl_platform(AladinCrawler, "데미안"), resolve_foreign_query("데미안"))
            assert domestic.rating == 8.8 and foreign.query == "Demian"
            assert sum(transport.counts.values()) == 2
