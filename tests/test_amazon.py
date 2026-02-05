"""AmazonCrawler 테스트"""

import pytest
from unittest.mock import patch

from crawlers.amazon import AmazonCrawler


class TestAmazonIsIdentifier:
    """식별자 판별 테스트"""

    def test_is_identifier_isbn13(self):
        """ISBN-13 인식"""
        crawler = AmazonCrawler()
        assert crawler.is_identifier("9781594205071") is True

    def test_is_identifier_isbn10(self):
        """ISBN-10 인식"""
        crawler = AmazonCrawler()
        assert crawler.is_identifier("1594205078") is True

    def test_is_identifier_isbn_with_hyphens(self):
        """하이픈 포함 ISBN 인식"""
        crawler = AmazonCrawler()
        assert crawler.is_identifier("978-1-59420-507-1") is True
        assert crawler.is_identifier("1-59420-507-8") is True

    def test_is_identifier_asin(self):
        """ASIN 인식 (10자리 영숫자)"""
        crawler = AmazonCrawler()
        assert crawler.is_identifier("B01A7YX4TW") is True
        assert crawler.is_identifier("B000000001") is True

    def test_is_identifier_title_returns_false(self):
        """제목은 식별자가 아님"""
        crawler = AmazonCrawler()
        assert crawler.is_identifier("Behave") is False
        assert crawler.is_identifier("Clean Code") is False

    def test_is_identifier_short_number_returns_false(self):
        """짧은 숫자는 식별자가 아님"""
        crawler = AmazonCrawler()
        assert crawler.is_identifier("12345") is False
        assert crawler.is_identifier("123456789") is False  # 9자리


class TestAmazonParseDetailPage:
    """상세 페이지 파싱 테스트"""

    def test_parse_detail_page_json_ld(self, load_fixture):
        """JSON-LD에서 평점/리뷰 추출"""
        html = load_fixture("amazon_detail.html")
        crawler = AmazonCrawler()

        title, rating, review_count = crawler._parse_detail_page(html)

        assert title == "Behave: The Biology of Humans at Our Best and Worst"
        assert rating == 4.7
        assert review_count == 5123

    def test_parse_detail_page_html_fallback(self):
        """JSON-LD 없을 때 HTML에서 추출"""
        html = """
        <html>
        <span id="productTitle">Test Book Title</span>
        <span class="a-icon-alt">4.5 out of 5 stars</span>
        <span id="acrCustomerReviewText">1,234 ratings</span>
        </html>
        """
        crawler = AmazonCrawler()

        title, rating, review_count = crawler._parse_detail_page(html)

        assert title == "Test Book Title"
        assert rating == 4.5
        assert review_count == 1234

    def test_parse_detail_page_empty_html(self):
        """빈 HTML 처리"""
        crawler = AmazonCrawler()

        title, rating, review_count = crawler._parse_detail_page("<html></html>")

        assert title == ""
        assert rating is None
        assert review_count == 0


class TestAmazonSearchByIdentifier:
    """식별자 검색 테스트"""

    def test_search_by_identifier_success(self, load_fixture):
        """ASIN/ISBN으로 직접 검색 성공"""
        html = load_fixture("amazon_detail.html")
        crawler = AmazonCrawler()

        with patch.object(crawler, "_fetch_with_headers", return_value=html):
            url, title = crawler.search_by_identifier("1594205078")

        assert url == "https://www.amazon.com/dp/1594205078"
        assert "Behave" in title
        # 캐시 확인
        assert crawler._cached_rating == 4.7
        assert crawler._cached_review_count == 5123

    def test_search_by_identifier_not_found(self):
        """식별자 검색 실패"""
        crawler = AmazonCrawler()

        with patch.object(crawler, "_fetch_with_headers", return_value="<html></html>"):
            url, title = crawler.search_by_identifier("0000000000")

        assert url is None
        assert title == ""


class TestAmazonSearchByKeyword:
    """키워드 검색 테스트"""

    def test_search_by_keyword_success(self, load_fixture):
        """키워드 검색 성공"""
        html = load_fixture("amazon_search.html")
        crawler = AmazonCrawler()

        with patch.object(crawler, "_fetch_with_headers", return_value=html):
            url, title = crawler.search_by_keyword("Behave")

        assert url is not None
        assert "1594205078" in url
        assert "Behave" in title

    def test_search_by_keyword_extracts_rating_from_results(self, load_fixture):
        """검색 결과에서 평점 미리 추출"""
        html = load_fixture("amazon_search.html")
        crawler = AmazonCrawler()

        with patch.object(crawler, "_fetch_with_headers", return_value=html):
            crawler.search_by_keyword("Behave")

        # 검색 결과에서 평점이 캐시되어야 함
        assert crawler._cached_rating == 4.7

    def test_search_by_keyword_no_results(self):
        """검색 결과 없음"""
        crawler = AmazonCrawler()

        with patch.object(crawler, "_fetch_with_headers", return_value="<html></html>"):
            url, title = crawler.search_by_keyword("xyznonexistent")

        assert url is None
        assert title == ""


class TestAmazonGetRating:
    """평점 조회 테스트"""

    @pytest.mark.asyncio
    async def test_get_rating_from_cache(self):
        """캐시된 평점 반환"""
        crawler = AmazonCrawler()
        crawler._cached_rating = 4.5
        crawler._cached_review_count = 1000

        rating, review_count = await crawler.get_rating("https://amazon.com/dp/123")

        assert rating == 4.5
        assert review_count == 1000

    @pytest.mark.asyncio
    async def test_get_rating_fetch_if_no_cache(self, load_fixture):
        """캐시 없으면 페이지에서 추출"""
        html = load_fixture("amazon_detail.html")
        crawler = AmazonCrawler()
        # 캐시 없음 (None)

        with patch.object(crawler, "_fetch_with_headers", return_value=html):
            rating, review_count = await crawler.get_rating("https://amazon.com/dp/123")

        assert rating == 4.7
        assert review_count == 5123


class TestAmazonCrawl:
    """전체 크롤링 플로우 테스트"""

    @pytest.mark.asyncio
    async def test_crawl_by_asin(self, load_fixture):
        """ASIN으로 크롤링"""
        html = load_fixture("amazon_detail.html")

        async with AmazonCrawler() as crawler:
            with patch.object(crawler, "_fetch_with_headers", return_value=html):
                with patch.object(crawler, "delay"):
                    result = await crawler.crawl("1594205078")

        assert result is not None
        assert result.platform == "amazon"
        assert result.rating == 4.7
        assert result.rating_scale == 5
        assert result.review_count == 5123

    @pytest.mark.asyncio
    async def test_crawl_by_keyword(self, load_fixture):
        """제목으로 크롤링"""
        search_html = load_fixture("amazon_search.html")
        detail_html = load_fixture("amazon_detail.html")

        async with AmazonCrawler() as crawler:
            with patch.object(crawler, "_fetch_with_headers") as mock_fetch:
                mock_fetch.side_effect = [search_html, detail_html]
                with patch.object(crawler, "delay"):
                    result = await crawler.crawl("Behave")

        assert result is not None
        assert result.platform == "amazon"
        assert "Behave" in result.book_title

    @pytest.mark.asyncio
    async def test_crawl_not_found(self):
        """검색 결과 없음"""
        async with AmazonCrawler() as crawler:
            with patch.object(crawler, "_fetch_with_headers", return_value="<html></html>"):
                result = await crawler.crawl("xyznonexistent")

        assert result is None
