import json
from unittest.mock import patch
import pytest
from crawlers.utils import title_score, is_isbn
from crawlers.aladin import AladinCrawler
from crawlers.yes24 import Yes24Crawler
from crawlers.kyobo import KyoboCrawler
from crawlers.sarak import SarakCrawler
from crawlers.isbn_lookup import GoogleBooksProvider, OpenLibraryProvider


@pytest.mark.parametrize("query,title", [("데미안", "데 미 안"), ("Clean Code", "Clean Code: A Handbook of Agile Software Craftsmanship"), ("사피엔스", "사피엔스 - 인류의 역사")])
def test_normalized_title_matches(query, title):
    assert title_score(query, title) > 0


@pytest.mark.parametrize("query,title", [("데미안", "싯다르타"), ("Clean Code", "The Clean Coder"), ("해리 포터 1", "해리 포터 2"), ("데미안 1", "데미안 10"), ("", "anything")])
def test_unrelated_or_wrong_volume_rejected(query, title):
    assert title_score(query, title) == 0


def test_isbn10_check_digit_x():
    assert is_isbn("0-8044-2957-X")


@pytest.mark.parametrize("crawler_type", [Yes24Crawler, SarakCrawler])
def test_yes24_and_sarak_do_not_take_unrelated_first_result(crawler_type):
    crawler = crawler_type()
    html = '<a class="gd_name" href="/product/goods/1">싯다르타</a>'
    with patch.object(crawler, "_fetch_html", return_value=html):
        assert crawler.search_by_keyword("데미안") == (None, "")


@pytest.mark.parametrize("crawler_type", [Yes24Crawler, SarakCrawler])
def test_isbn_search_requires_matching_identifier(crawler_type):
    crawler = crawler_type()
    html = '<div data-isbn="9788937460449"><a class="gd_name" href="/product/goods/176787">데미안</a></div>'
    with patch.object(crawler, "_fetch_html", return_value=html):
        assert crawler.search_by_keyword("9788937460449")[1] == "데미안"
        assert crawler.search_by_keyword("9780132350884") == (None, "")


def test_kyobo_short_query_does_not_match_empty_word_list():
    crawler = KyoboCrawler()
    html = '<div class="prod_item"><a class="prod_info" href="/detail/S1">싯다르타</a></div>'
    with patch.object(crawler, "_fetch_html", return_value=html):
        assert crawler.search_by_keyword("책") == (None, "")


async def test_aladin_popularity_cannot_override_identity(mock_aladin_key):
    crawler = AladinCrawler()
    unrelated = {"title": "싯다르타", "salesPoint": 999999999, "itemId": 1, "link": "https://example.com"}
    with patch.object(crawler, "_api_request", return_value={"item": [unrelated]}):
        assert await crawler.search_book("데미안") == (None, "")


async def test_aladin_translation_does_not_choose_another_book_by_author(mock_aladin_key):
    crawler = AladinCrawler()
    crawler._current_item_id = 1
    data = {"item": [{"author": "헤르만 헤세 (지은이), 홍길동 (옮긴이)", "isbn13": "9788937460449"}]}
    with patch.object(crawler, "_api_request", return_value=data), patch.object(crawler, "_search_foreign_edition") as author_search:
        info = await crawler.get_original_title_info()
    assert info["title"] is None
    author_search.assert_not_called()


def test_google_does_not_resolve_translation_by_author_only():
    provider = GoogleBooksProvider(api_key="test")
    data = {"items": [{"volumeInfo": {"title": "데미안", "language": "ko", "authors": ["Hermann Hesse"]}}]}
    with patch.object(provider, "_api_get", return_value=data), patch.object(provider, "_find_english_edition_by_author") as author_search:
        assert provider.find_original_by_isbn("9788937460449") is None
    author_search.assert_not_called()


def test_open_library_requests_isbn_field_and_checks_title():
    provider = OpenLibraryProvider()
    with patch.object(provider, "_api_get", return_value={"docs": [{"title": "The Clean Coder", "isbn": ["9780137081073"]}]}) as request:
        assert provider.search("Clean Code") is None
    assert "fields=title,author_name,isbn" in request.call_args.args[0]


def test_kyobo_current_search_rating_avoids_dead_statistics_endpoint():
    crawler = KyoboCrawler()
    html = '<div class="prod_item"><a class="prod_info" href="/detail/S1">데미안</a><span class="review_klover_text">9.7</span><span class="review_desc">(2,030)</span></div>'
    with patch.object(crawler, "_fetch_html", return_value=html):
        crawler.search_by_keyword("데미안")
    import asyncio
    with patch.object(crawler, "_fetch_api") as request:
        assert asyncio.run(crawler.get_rating("https://product.kyobobook.co.kr/detail/S1")) == (9.7, 2030)
    request.assert_not_called()
