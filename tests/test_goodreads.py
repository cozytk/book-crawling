"""GoodreadsCrawler 테스트"""

import pytest
from unittest.mock import patch, MagicMock

from crawlers.goodreads import GoodreadsCrawler


class TestGoodreadsIsIdentifier:
    """ISBN 판별 테스트"""

    def test_is_identifier_isbn13(self):
        """ISBN-13 인식"""
        crawler = GoodreadsCrawler()
        assert crawler.is_identifier("9781594205071") is True

    def test_is_identifier_isbn10(self):
        """ISBN-10 인식"""
        crawler = GoodreadsCrawler()
        assert crawler.is_identifier("1594205078") is True

    def test_is_identifier_isbn_with_hyphens(self):
        """하이픈 포함 ISBN 인식"""
        crawler = GoodreadsCrawler()
        assert crawler.is_identifier("978-1-59420-507-1") is True
        assert crawler.is_identifier("1-59420-507-8") is True

    def test_is_identifier_isbn_with_spaces(self):
        """공백 포함 ISBN 인식"""
        crawler = GoodreadsCrawler()
        assert crawler.is_identifier("978 1 59420 5071") is True

    def test_is_identifier_title_returns_false(self):
        """제목은 ISBN이 아님"""
        crawler = GoodreadsCrawler()
        assert crawler.is_identifier("Clean Code") is False
        assert crawler.is_identifier("Behave") is False

    def test_is_identifier_short_number_returns_false(self):
        """짧은 숫자는 ISBN이 아님"""
        crawler = GoodreadsCrawler()
        assert crawler.is_identifier("12345") is False
        assert crawler.is_identifier("123456789") is False  # 9자리

    def test_is_identifier_long_number_returns_false(self):
        """긴 숫자는 ISBN이 아님"""
        crawler = GoodreadsCrawler()
        assert crawler.is_identifier("12345678901234") is False  # 14자리


class TestGoodreadsParseDetailPage:
    """상세 페이지 파싱 테스트"""

    def test_parse_detail_page_json_ld(self, load_fixture):
        """JSON-LD에서 평점/리뷰 추출"""
        html = load_fixture("goodreads_detail.html")
        crawler = GoodreadsCrawler()

        title, rating, review_count = crawler._parse_detail_page(html)

        assert title == "Clean Code: A Handbook of Agile Software Craftsmanship"
        assert rating == 4.35
        assert review_count == 32072  # ratingCount (별점 참여자 수)

    def test_parse_detail_page_empty_html(self):
        """빈 HTML 처리"""
        crawler = GoodreadsCrawler()

        title, rating, review_count = crawler._parse_detail_page("<html></html>")

        assert title == ""
        assert rating is None
        assert review_count == 0


class TestGoodreadsSearchByIdentifier:
    """ISBN 검색 테스트"""

    def test_search_by_identifier_success(self, load_fixture):
        """ISBN으로 직접 검색 성공"""
        html = load_fixture("goodreads_detail.html")
        crawler = GoodreadsCrawler()

        with patch.object(crawler, "_fetch_with_redirect") as mock_fetch:
            mock_fetch.return_value = (html, "https://goodreads.com/book/show/123")

            url, title = crawler.search_by_identifier("9781594205071")

        assert url == "https://goodreads.com/book/show/123"
        assert "Clean Code" in title
        # 캐시 확인
        assert crawler._cached_rating == 4.35
        assert crawler._cached_review_count == 32072

    def test_search_by_identifier_not_found(self):
        """ISBN 검색 실패"""
        crawler = GoodreadsCrawler()

        with patch.object(crawler, "_fetch_with_redirect") as mock_fetch:
            mock_fetch.return_value = ("<html></html>", "https://goodreads.com/404")

            url, title = crawler.search_by_identifier("0000000000")

        assert url is None
        assert title == ""


class TestGoodreadsSearchByKeyword:
    """제목 검색 테스트"""

    def test_search_by_keyword_redirect_to_detail(self, load_fixture):
        """검색이 상세 페이지로 리다이렉트되는 경우"""
        html = load_fixture("goodreads_detail.html")
        crawler = GoodreadsCrawler()

        with patch.object(crawler, "_fetch_with_redirect") as mock_fetch:
            # 정확한 매칭으로 상세 페이지로 리다이렉트
            mock_fetch.return_value = (html, "https://goodreads.com/book/show/3735293")

            url, title = crawler.search_by_keyword("Clean Code")

        assert "/book/show/" in url
        assert "Clean Code" in title

    def test_search_by_keyword_search_results(self, load_fixture):
        """검색 결과 페이지에서 첫 번째 책 선택"""
        html = load_fixture("goodreads_search.html")
        crawler = GoodreadsCrawler()

        with patch.object(crawler, "_fetch_with_redirect") as mock_fetch:
            mock_fetch.return_value = (html, "https://goodreads.com/search?q=clean")

            url, title = crawler.search_by_keyword("Clean Code")

        assert "/book/show/3735293" in url
        assert "Clean Code" in title

    def test_search_by_keyword_no_results(self):
        """검색 결과 없음"""
        crawler = GoodreadsCrawler()

        with patch.object(crawler, "_fetch_with_redirect") as mock_fetch:
            mock_fetch.return_value = ("<html><body>No results</body></html>", "https://goodreads.com/search")

            url, title = crawler.search_by_keyword("xyznonexistent")

        assert url is None
        assert title == ""


class TestGoodreadsGetRating:
    """평점 조회 테스트"""

    @pytest.mark.asyncio
    async def test_get_rating_from_cache(self):
        """캐시된 평점 반환"""
        crawler = GoodreadsCrawler()
        crawler._cached_rating = 4.5
        crawler._cached_review_count = 1000

        rating, review_count = await crawler.get_rating("https://example.com")

        assert rating == 4.5
        assert review_count == 1000

    @pytest.mark.asyncio
    async def test_get_rating_fetch_if_no_cache(self, load_fixture):
        """캐시 없으면 페이지에서 추출"""
        html = load_fixture("goodreads_detail.html")
        crawler = GoodreadsCrawler()
        # 캐시 없음 (None)

        with patch.object(crawler, "_fetch_with_redirect") as mock_fetch:
            mock_fetch.return_value = (html, "https://goodreads.com/book/123")

            rating, review_count = await crawler.get_rating("https://goodreads.com/book/123")

        assert rating == 4.35
        assert review_count == 32072  # ratingCount (별점 참여자 수)


class TestGoodreadsCrawl:
    """전체 크롤링 플로우 테스트"""

    @pytest.mark.asyncio
    async def test_crawl_by_isbn(self, load_fixture):
        """ISBN으로 크롤링"""
        html = load_fixture("goodreads_detail.html")

        async with GoodreadsCrawler() as crawler:
            with patch.object(crawler, "_fetch_with_redirect") as mock_fetch:
                mock_fetch.return_value = (html, "https://goodreads.com/book/show/123")
                with patch.object(crawler, "delay"):
                    result = await crawler.crawl("9781594205071")

        assert result is not None
        assert result.platform == "goodreads"
        assert result.rating == 4.35
        assert result.rating_scale == 5
        assert result.review_count == 32072

    @pytest.mark.asyncio
    async def test_crawl_by_title(self, load_fixture):
        """제목으로 크롤링"""
        search_html = load_fixture("goodreads_search.html")
        detail_html = load_fixture("goodreads_detail.html")

        async with GoodreadsCrawler() as crawler:
            with patch.object(crawler, "_fetch_with_redirect") as mock_fetch:
                # 첫 번째 호출: 검색
                # 두 번째 호출: 상세 페이지 (get_rating에서)
                mock_fetch.side_effect = [
                    (search_html, "https://goodreads.com/search"),
                    (detail_html, "https://goodreads.com/book/show/123"),
                ]
                with patch.object(crawler, "delay"):
                    result = await crawler.crawl("Clean Code")

        assert result is not None
        assert result.platform == "goodreads"
