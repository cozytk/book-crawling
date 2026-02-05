"""Yes24Crawler 테스트"""

import pytest
from unittest.mock import patch

from crawlers.yes24 import Yes24Crawler


class TestYes24SearchByKeyword:
    """키워드 검색 테스트"""

    def test_search_by_keyword_success(self, load_fixture):
        """검색 성공"""
        html = load_fixture("yes24_search.html")
        crawler = Yes24Crawler()

        with patch.object(crawler, "_fetch_html", return_value=html):
            url, title = crawler.search_by_keyword("Clean Code")

        assert url is not None
        assert "123456789" in url
        assert "Clean Code" in title

    def test_search_by_keyword_excludes_used_shop(self, load_fixture):
        """중고서점 제외"""
        html = load_fixture("yes24_search.html")
        crawler = Yes24Crawler()

        with patch.object(crawler, "_fetch_html", return_value=html):
            url, title = crawler.search_by_keyword("클린 코드")

        # UsedShopHub 링크가 아닌 상품 선택
        assert "UsedShopHub" not in url

    def test_search_by_keyword_no_results(self):
        """검색 결과 없음"""
        crawler = Yes24Crawler()

        with patch.object(crawler, "_fetch_html", return_value="<html></html>"):
            url, title = crawler.search_by_keyword("xyznonexistent")

        assert url is None
        assert title == ""

    def test_search_by_keyword_normalizes_url(self, load_fixture):
        """상대 URL을 절대 URL로 변환"""
        html = load_fixture("yes24_search.html")
        crawler = Yes24Crawler()

        with patch.object(crawler, "_fetch_html", return_value=html):
            url, title = crawler.search_by_keyword("Clean Code")

        assert url.startswith("https://www.yes24.com")


class TestYes24GetRating:
    """평점 조회 테스트"""

    @pytest.mark.asyncio
    async def test_get_rating_success(self, load_fixture):
        """평점/리뷰 추출 성공"""
        html = load_fixture("yes24_detail.html")
        crawler = Yes24Crawler()

        with patch.object(crawler, "_fetch_html", return_value=html):
            rating, review_count = await crawler.get_rating("https://www.yes24.com/Product/Goods/123")

        assert rating == 9.5
        assert review_count == 101

    @pytest.mark.asyncio
    async def test_get_rating_alternative_selector(self):
        """대체 셀렉터로 평점 추출"""
        html = """
        <html>
        <span class="yes_b">9.2</span>
        <div>회원리뷰(50건)</div>
        </html>
        """
        crawler = Yes24Crawler()

        with patch.object(crawler, "_fetch_html", return_value=html):
            rating, review_count = await crawler.get_rating("https://example.com")

        assert rating == 9.2
        assert review_count == 50

    @pytest.mark.asyncio
    async def test_get_rating_with_comma_in_count(self):
        """리뷰 수에 쉼표 포함"""
        html = """
        <html>
        <span class="gd_rating"><em>9.0</em></span>
        <div>회원리뷰(1,234건)</div>
        </html>
        """
        crawler = Yes24Crawler()

        with patch.object(crawler, "_fetch_html", return_value=html):
            rating, review_count = await crawler.get_rating("https://example.com")

        assert review_count == 1234

    @pytest.mark.asyncio
    async def test_get_rating_no_rating(self):
        """평점 없음"""
        html = "<html><body>No rating</body></html>"
        crawler = Yes24Crawler()

        with patch.object(crawler, "_fetch_html", return_value=html):
            rating, review_count = await crawler.get_rating("https://example.com")

        assert rating is None
        assert review_count == 0


class TestYes24Crawl:
    """전체 크롤링 플로우 테스트"""

    @pytest.mark.asyncio
    async def test_crawl_success(self, load_fixture):
        """크롤링 성공"""
        search_html = load_fixture("yes24_search.html")
        detail_html = load_fixture("yes24_detail.html")

        async with Yes24Crawler() as crawler:
            with patch.object(crawler, "_fetch_html") as mock_fetch:
                mock_fetch.side_effect = [search_html, detail_html]
                with patch.object(crawler, "delay"):
                    result = await crawler.crawl("Clean Code")

        assert result is not None
        assert result.platform == "yes24"
        assert result.rating == 9.5
        assert result.rating_scale == 10
        assert result.review_count == 101

    @pytest.mark.asyncio
    async def test_crawl_not_found(self):
        """검색 결과 없음"""
        async with Yes24Crawler() as crawler:
            with patch.object(crawler, "_fetch_html", return_value="<html></html>"):
                result = await crawler.crawl("xyznonexistent")

        assert result is None


class TestYes24ReviewPatterns:
    """리뷰 수 패턴 테스트"""

    @pytest.mark.asyncio
    async def test_review_pattern_gumaepyeong(self):
        """구매평(N) 패턴"""
        html = """
        <html>
        <span class="gd_rating"><em>9.0</em></span>
        <div>구매평(200)</div>
        </html>
        """
        crawler = Yes24Crawler()

        with patch.object(crawler, "_fetch_html", return_value=html):
            rating, review_count = await crawler.get_rating("https://example.com")

        assert review_count == 200

    @pytest.mark.asyncio
    async def test_review_pattern_review_n_geon(self):
        """리뷰 N건 패턴"""
        html = """
        <html>
        <span class="gd_rating"><em>9.0</em></span>
        <div>리뷰 300건</div>
        </html>
        """
        crawler = Yes24Crawler()

        with patch.object(crawler, "_fetch_html", return_value=html):
            rating, review_count = await crawler.get_rating("https://example.com")

        assert review_count == 300
