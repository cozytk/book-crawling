"""Source-shaped regressions for discovery, identity and current HTTP contracts."""
import asyncio
import gzip
import json
from types import SimpleNamespace
from unittest.mock import patch, AsyncMock

import httpx
import pytest
from bs4 import BeautifulSoup

from crawlers.utils import title_score, candidate_score, author_matches
from crawlers.yes24 import Yes24Crawler, original_author_for_isbn
from crawlers.sarak import SarakCrawler
from crawlers.kyobo import KyoboCrawler
from crawlers.watcha import WatchaCrawler
from crawlers.goodreads import GoodreadsCrawler
from crawlers.librarything import LibraryThingCrawler
from crawlers.isbn_lookup import OpenLibraryProvider
from crawlers.transport import SearchTransport
from crawlers.aladin import AladinCrawler
from crawlers.amazon import AmazonCrawler


@pytest.mark.parametrize("query,title", [
    ("인간의 굴레에서", "인간의 굴레에서 1"),
    ("전쟁과 평화", "전쟁과 평화 4 (무선)"),
    ("죄와 벌", "죄와 벌 2"),
    ("레 미제라블", "레 미제라블 5"),
])
def test_work_query_can_discover_split_volumes(query, title):
    assert title_score(query, title)
    assert not title_score(query + " 1", title.replace(" 1", " 2"))


@pytest.mark.parametrize("query", ["톨스토이 전쟁과 평화", "전쟁과 평화 톨스토이"])
def test_author_words_in_query_require_real_candidate_metadata(query):
    assert candidate_score(query, "전쟁과 평화 1", "레프 톨스토이 저")
    assert not candidate_score(query, "전쟁과 평화", "아자 가트 저")


def yes_result(product, title, author, kind="[도서]"):
    return f'<li><div class="info_name"><span class="gd_res">{kind}</span><a class="gd_name" href="/product/goods/{product}">{title}</a></div><span class="info_auth">{author}</span></li>'


@pytest.mark.parametrize("cls", [Yes24Crawler, SarakCrawler])
def test_shared_yes24_discovery_rejects_other_author_adaptation_and_audio(cls):
    crawler = cls()
    crawler.expected_identity("전쟁과 평화", "레프 니콜라예비치 톨스토이")
    html = (yes_result(1, "전쟁과 평화", "아자 가트 저")
            + yes_result(2, "전쟁과 평화", "레프 톨스토이 원저")
            + yes_result(3, "전쟁과 평화", "레프 톨스토이", "[CD]")
            + yes_result(4, "전쟁과 평화 2", "레프 톨스토이 저")
            + yes_result(5, "전쟁과 평화 1", "레프 톨스토이 저"))
    with patch.object(crawler, "_fetch_html", return_value=html):
        url, title = crawler.search_by_keyword("전쟁과 평화")
    assert url.endswith("/5") and title == "전쟁과 평화 1"


def test_kyobo_uses_current_representative_author_and_isbn():
    crawler = KyoboCrawler()
    crawler.expected_identity("전쟁과 평화", "레프 니콜라예비치 톨스토이")
    def item(code, author):
        return f'<div class="prod_item" data-isbn="9788932404806"><a class="prod_info" href="/detail/{code}">전쟁과 평화(상)</a><div class="prod_author_group"><a class="author rep">{author}</a></div><span class="review_klover_text">10.0</span><span class="review_desc">(24)</span></div>'
    with patch.object(crawler, "_fetch_html", return_value=item("wrong", "아자 가트") + item("correct", "레프 톨스토이")):
        assert crawler.search_by_keyword("전쟁과 평화")[0].endswith("/correct")
    assert crawler.book_author == "레프 톨스토이" and crawler.book_isbn == "9788932404806"


async def test_watcha_real_search_shape_ignores_movies_and_preserves_clean_book_url():
    crawler = WatchaCrawler()
    crawler.expected_identity("전쟁과 평화", "레프 니콜라예비치 톨스토이")
    html = ('<a href="/ko/contents/md123">전쟁과 평화 1956 · 이탈리아/미국 영화</a>'
            '<a href="/ko/contents/boBad">전쟁과 평화 2020 · 아자 가트 책</a>'
            '<a href="/ko/contents/bo3QYJY?search_id=temporary">전쟁과 평화 2018 · 레프 톨스토이 책</a>')
    with patch.object(crawler, "_fetch_html", return_value=html) as fetch:
        assert crawler.search_by_keyword("전쟁과 평화") == ("https://pedia.watcha.com/ko/contents/bo3QYJY", "전쟁과 평화")
    assert "/ko/search?query=" in fetch.call_args.args[0]


def test_observed_author_variants_do_not_relax_unrelated_author_matching():
    assert author_matches("서머싯 몸", "W. 서머셋 모옴")
    assert author_matches("레프 니콜라예비치 톨스토이", "Leo Tolstoy")
    assert not author_matches("레프 톨스토이", "Azar Gat")
    assert not author_matches("Robert Martin", "George Martin")
    assert author_matches(["Fiódor Dostoievski", "Fyodor Dostoevsky"], "Fyodor Dostoevsky")
    assert not author_matches(["도스토옙스키", "Fyodor Dostoevsky"], "Azar Gat")


def test_open_library_requires_matched_edition_before_using_another_script_title():
    crawler = OpenLibraryProvider()
    canonical = {"title":"War and Peace", "author_name":["Лев Толстой"], "edition_count":647,
                 "editions":{"docs":[{"title":"War and Peace - Война и мир", "isbn":["9781909115033"]}]}}
    unrelated = {"title":"Another Novel", "author_name":["Лев Толстой"], "isbn":["9780000000001"], "edition_count":9999}
    with patch.object(crawler, "_api_get", return_value={"docs":[unrelated, canonical]}) as fetch:
        result = crawler.search("Война и мир", "레프 톨스토이")
    assert result.title == "War and Peace" and result.isbn == "9781909115033"
    assert "editions.key" in fetch.call_args.args[0]
    assert "%EB%A0%88%ED%94%84" not in fetch.call_args.args[0]
    with patch.object(crawler, "_api_get", return_value={"docs":[unrelated]}):
        assert crawler.search("Война и мир", "레프 톨스토이") is None


def test_goodreads_current_book_cards_filter_author_before_selecting():
    crawler = GoodreadsCrawler()
    crawler.expected_identity("War and Peace", "Leo Tolstoy")
    def item(code, author):
        return f'<div class="Book"><span data-testid="book-item-title"><a href="/book/show/{code}">War and Peace</a></span><a href="/author/show/1">{author}</a></div>'
    with patch.object(crawler, "_fetch_with_redirect", return_value=(item("wrong", "Azar Gat") + item("correct", "Leo Tolstoy"), "https://www.goodreads.com/search?q=War")):
        assert crawler.search_by_keyword("War and Peace")[0].endswith("/correct")


def test_librarything_current_header_never_uses_members_or_arbitrary_decimals():
    crawler = LibraryThingCrawler()
    html = '<div class="pagecard"><div><h1>War and Peace</h1><h3 class="h3_work_author">by Leo Tolstoy</h3></div><div class="lt_scoreboard"><span class="scoreboard_item">34,333 Members</span><span class="scoreboard_item"><a>520 Reviews</a></span><span class="scoreboard_item"><span class="rating" title="4.3 Stars">½</span> (4.26)</span></div></div><div>Price (2.99) 8,888 reviews</div>'
    title, rating, count = crawler._parse_work_page(html)
    assert (title, rating, count) == ("War and Peace", 4.26, 520)
    assert crawler.rating_count is None and crawler.text_review_count == 520
    crawler.expected_identity(title, "Leo Tolstoy")
    assert crawler.verify_detail(BeautifulSoup(html,"html.parser"), title, title)


async def test_browser_compatible_http_retains_cancel_and_decoded_body_contract():
    started, canceled = asyncio.Event(), asyncio.Event()
    async def fetch(url, **kwargs):
        if "slow" in url:
            started.set()
            try:
                await asyncio.sleep(30)
            finally:
                canceled.set()
        return SimpleNamespace(status_code=200, content=b"<h1>Book</h1>", headers={"content-encoding":"gzip"}, url=url)
    browser = SimpleNamespace(get=fetch, close=AsyncMock())
    async with SearchTransport(httpx.AsyncClient(), browser_client=browser) as transport:
        page = await transport.get("https://pedia.watcha.com/book")
        assert page.text == "<h1>Book</h1>"
        task = asyncio.create_task(transport.get("https://pedia.watcha.com/slow"))
        await started.wait()
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        await asyncio.wait_for(canceled.wait(), 1)
    browser.close.assert_awaited_once()


def test_roman_author_comes_from_verified_isbn_and_writer_box_not_translator():
    html = '<div id="infoset_authorGrp"><div class="author_name">역 : <a class="lnk_author">번역자</a><span class="name_other">(Wrong Translator)</span></div><div class="author_name">저 : <a class="lnk_author">조지 오웰</a><span class="name_other">(George Orwell)</span></div></div>'
    with patch.object(Yes24Crawler,"search_by_keyword",return_value=("https://www.yes24.com/product/goods/1","1984")) as search, patch.object(Yes24Crawler,"_fetch_html",return_value=html):
        assert original_author_for_isbn("9788937460777","조지 오웰") == "George Orwell"
        assert original_author_for_isbn("1984","조지 오웰") is None
    search.assert_called_once_with("9788937460777")


async def test_service_uses_shared_isbn_but_preserves_original_work_scope(monkeypatch):
    from crawlers.work_identity import WorkIdentity
    from api.services import crawler_service
    from models.book import PlatformRating
    calls=[]
    async def identity(query):
        return WorkIdentity("헤르만 헤세","데미안","9788937460449")
    async def crawl(cls, query, **kwargs):
        calls.append((cls.name,query,kwargs))
        return PlatformRating(cls.name,9,10,10,"https://example.com","데미안")
    monkeypatch.setattr(crawler_service,"resolve_work_identity",identity)
    monkeypatch.setattr(crawler_service,"crawl_platform",crawl)
    result=await crawler_service.crawl_all("데미안",["yes24","kyobo","watcha"])
    assert len(result.results)==3
    for platform,query,kwargs in calls:
        assert query == ("데미안" if platform in {"watcha","kyobo"} else "9788937460449")
        assert kwargs["original_query"] == "데미안" and kwargs["expected_author"]=="헤르만 헤세"
        assert kwargs["fallback_query"] == (None if platform in {"watcha","kyobo"} else "데미안")


async def test_adaptation_category_does_not_hide_a_general_edition(mock_aladin_key):
    crawler=AladinCrawler()
    items=[{"title":"죄와 벌","author":"표도르 도스토옙스키 (지은이)","categoryName":"국내도서>청소년>소설","salesPoint":10000,"itemId":1,"link":"https://example.com/1"},
           {"title":"죄와 벌 1","author":"표도르 도스토옙스키 (지은이)","categoryName":"국내도서>소설>러시아","salesPoint":1000,"itemId":2,"link":"https://example.com/2"}]
    with patch.object(crawler,"_api_request",return_value={"item":items}):
        assert (await crawler.search_book("죄와 벌"))[0].endswith("/2")


async def test_waf_success_status_is_not_misreported_as_no_search_results():
    from crawlers.transport import FetchFailure
    async def handler(request):
        return httpx.Response(202,headers={"x-amzn-waf-action":"challenge"},text="<script>AwsWafIntegration</script>")
    async with SearchTransport(httpx.AsyncClient(transport=httpx.MockTransport(handler))) as transport:
        with pytest.raises(FetchFailure) as exc:
            await transport.get("https://www.goodreads.com/search?q=book")
        assert exc.value.status == "blocked"


def test_unrated_goodreads_edition_does_not_contribute_zero_stars():
    crawler=GoodreadsCrawler()
    node={"@type":"Book","name":"A Book","aggregateRating":{"ratingValue":0,"ratingCount":0}}
    html='<h1 data-testid="bookTitle">A Book</h1><script type="application/ld+json">'+json.dumps(node)+'</script>'
    assert crawler._parse_detail_page(html)[1:] == (None,0)


def test_amazon_other_audio_formats_do_not_exclude_the_selected_paperback():
    crawler=AmazonCrawler()
    def item(asin,formats):
        return f'<div data-component-type="s-search-result" data-asin="{asin}"><h2><span>Of Human Bondage</span></h2><div>{formats}</div></div>'
    html=item("B004N59WMK","Audiobook Other formats: Paperback")+item("059368768X","Paperback Other formats: Kindle, Audiobook")
    with patch.object(crawler,"_fetch_with_headers",return_value=html):
        assert crawler.search_by_keyword("Of Human Bondage")[0].endswith("059368768X")


async def test_shared_identity_survives_unavailable_aladin():
    from crawlers.work_identity import resolve_work_identity
    html='<div class="prod_item" data-isbn="9788932404806"><a class="prod_info" href="/detail/S1">전쟁과 평화(상)</a><div class="prod_author_group"><a class="author rep">레프 톨스토이</a></div></div>'
    with patch.object(KyoboCrawler,"_fetch_html",return_value=html),patch.object(AladinCrawler,"_api_request",side_effect=TimeoutError) as aladin:
        identity=await resolve_work_identity("전쟁과 평화")
    assert identity.isbn=="9788932404806" and identity.author=="레프 톨스토이"
    aladin.assert_not_called()


async def test_unresolved_identity_cannot_reenable_other_author_first_result(monkeypatch):
    from api.services import crawler_service
    from crawlers.work_identity import WorkIdentity
    monkeypatch.setattr(crawler_service,"resolve_work_identity",AsyncMock(return_value=WorkIdentity()))
    crawl=AsyncMock()
    monkeypatch.setattr(crawler_service,"crawl_platform",crawl)
    statuses=[]
    result=await crawler_service.crawl_all("동명 작품",["yes24","sarak"])
    assert result.results==[]
    crawl.assert_not_awaited()


async def test_foreign_resolution_uses_verified_edition_work_when_ttb_fails():
    from crawlers.work_identity import WorkIdentity
    from crawlers.foreign_resolver import _resolve_foreign_query
    with patch("crawlers.foreign_resolver.work_identity",return_value=WorkIdentity("작가","작품","9788937460449")),patch("crawlers.foreign_resolver._get_original_info",AsyncMock(return_value=None)),patch("crawlers.foreign_resolver.original_author_for_isbn",return_value="A Writer"),patch("crawlers.foreign_resolver.ISBNLookup.find_original",return_value={"title":"Verified Work","isbn":"9780132350884","authors":["A Writer"]}) as lookup:
        result=await _resolve_foreign_query("작품")
    assert result.query=="Verified Work" and result.isbn=="9780132350884"
    lookup.assert_called_once_with(isbn="9788937460449")
