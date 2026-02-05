"""BaseHttpCrawler 테스트"""

import pytest
from unittest.mock import patch, MagicMock

from crawlers.base_http import BaseHttpCrawler


class ConcreteHttpCrawler(BaseHttpCrawler):
    """테스트용 구체 크롤러"""

    name = "test_crawler"
    base_url = "https://test.com"
    rating_scale = 10

    async def get_rating(self, url: str) -> tuple[float | None, int]:
        return 9.5, 100


class ConcreteHttpCrawlerWithIdentifier(BaseHttpCrawler):
    """식별자 검색을 지원하는 테스트용 크롤러"""

    name = "test_with_id"
    base_url = "https://test.com"
    rating_scale = 10

    def is_identifier(self, query: str) -> bool:
        return query.startswith("ID:")

    def search_by_identifier(self, identifier: str) -> tuple[str | None, str]:
        return f"https://test.com/book/{identifier}", f"Book {identifier}"

    def search_by_keyword(self, keyword: str) -> tuple[str | None, str]:
        return f"https://test.com/search/{keyword}", f"Search: {keyword}"

    async def get_rating(self, url: str) -> tuple[float | None, int]:
        return 9.0, 50


class TestBaseHttpCrawlerDefaults:
    """BaseHttpCrawler 기본 동작 테스트"""

    def test_is_identifier_default_false(self):
        """is_identifier 기본값은 False"""
        crawler = ConcreteHttpCrawler()
        assert crawler.is_identifier("any query") is False
        assert crawler.is_identifier("9781234567890") is False

    def test_search_by_identifier_raises_not_implemented(self):
        """search_by_identifier는 기본적으로 NotImplementedError"""
        crawler = ConcreteHttpCrawler()
        with pytest.raises(NotImplementedError):
            crawler.search_by_identifier("123")

    def test_search_by_keyword_raises_not_implemented(self):
        """search_by_keyword는 기본적으로 NotImplementedError"""
        crawler = ConcreteHttpCrawler()
        with pytest.raises(NotImplementedError):
            crawler.search_by_keyword("test")


class TestBaseHttpCrawlerRouting:
    """search_book 라우팅 테스트"""

    @pytest.mark.asyncio
    async def test_search_book_routes_to_keyword_by_default(self):
        """기본적으로 keyword 검색으로 라우팅"""
        crawler = ConcreteHttpCrawlerWithIdentifier()

        url, title = await crawler.search_book("Clean Code")

        assert "search/Clean Code" in url
        assert "Search:" in title

    @pytest.mark.asyncio
    async def test_search_book_routes_to_identifier_when_detected(self):
        """식별자 감지 시 identifier 검색으로 라우팅"""
        crawler = ConcreteHttpCrawlerWithIdentifier()

        url, title = await crawler.search_book("ID:12345")

        assert "book/ID:12345" in url
        assert "Book ID:12345" in title


class TestBaseHttpCrawlerFetchHtml:
    """_fetch_html 테스트"""

    @patch("urllib.request.build_opener")
    def test_fetch_html_utf8(self, mock_build_opener):
        """UTF-8 인코딩 처리"""
        mock_response = MagicMock()
        mock_response.read.return_value = "<html>테스트</html>".encode("utf-8")
        mock_opener = MagicMock()
        mock_opener.open.return_value = mock_response
        mock_build_opener.return_value = mock_opener

        crawler = ConcreteHttpCrawler()
        html = crawler._fetch_html("https://test.com")

        assert "테스트" in html

    @patch("urllib.request.build_opener")
    def test_fetch_html_euckr_fallback(self, mock_build_opener):
        """EUC-KR 폴백 인코딩"""
        mock_response = MagicMock()
        # UTF-8로 디코딩할 수 없는 EUC-KR 인코딩 바이트
        mock_response.read.return_value = "<html>한글</html>".encode("euc-kr")
        mock_opener = MagicMock()
        mock_opener.open.return_value = mock_response
        mock_build_opener.return_value = mock_opener

        crawler = ConcreteHttpCrawler()
        html = crawler._fetch_html("https://test.com")

        assert "html" in html


class TestBaseHttpCrawlerAsyncContextManager:
    """async context manager 테스트"""

    @pytest.mark.asyncio
    async def test_async_context_manager(self):
        """async with 문 사용 가능"""
        async with ConcreteHttpCrawler() as crawler:
            assert crawler.name == "test_crawler"

    @pytest.mark.asyncio
    async def test_async_context_manager_returns_self(self):
        """__aenter__는 self 반환"""
        crawler = ConcreteHttpCrawler()
        result = await crawler.__aenter__()
        assert result is crawler


class TestBaseHttpCrawlerCrawl:
    """crawl 메서드 테스트"""

    @pytest.mark.asyncio
    async def test_crawl_returns_platform_rating(self):
        """crawl은 PlatformRating 반환"""
        crawler = ConcreteHttpCrawlerWithIdentifier()

        # delay를 모킹하여 테스트 속도 향상
        with patch.object(crawler, "delay"):
            result = await crawler.crawl("test query")

        assert result is not None
        assert result.platform == "test_with_id"
        assert result.rating == 9.0
        assert result.review_count == 50

    @pytest.mark.asyncio
    async def test_crawl_returns_none_on_not_found(self):
        """검색 결과 없으면 None 반환"""

        class NullCrawler(BaseHttpCrawler):
            name = "null"

            def search_by_keyword(self, keyword):
                return None, ""

            async def get_rating(self, url):
                return None, 0

        crawler = NullCrawler()
        result = await crawler.crawl("not found")

        assert result is None
