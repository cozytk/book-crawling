"""통합 테스트"""

import json
import pytest
from unittest.mock import patch, AsyncMock

from main import crawl_all_platforms
from crawlers.foreign_resolver import _is_korean, _get_original_info
from crawlers import KyoboCrawler, Yes24Crawler, AladinCrawler, GoodreadsCrawler


class TestIsKorean:
    """한국어 감지 테스트"""

    def test_is_korean_true(self):
        """한국어 포함"""
        assert _is_korean("클린 코드") is True
        assert _is_korean("한글") is True
        assert _is_korean("Clean Code 클린코드") is True

    def test_is_korean_false(self):
        """한국어 미포함"""
        assert _is_korean("Clean Code") is False
        assert _is_korean("12345") is False
        assert _is_korean("") is False


class TestGetOriginalInfo:
    """원서 정보 조회 테스트"""

    @pytest.mark.asyncio
    async def test_get_original_info_success(self, mock_aladin_key):
        """원서 정보 조회 성공"""
        with patch.object(AladinCrawler, "search_book", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = ("https://aladin.co.kr/123", "클린 코드")

            with patch.object(AladinCrawler, "get_original_title_info", new_callable=AsyncMock) as mock_get:
                mock_get.return_value = {"title": "Clean Code", "author": "Robert C. Martin", "isbn13": "9780132350884"}

                info = await _get_original_info("클린 코드")

        assert info["title"] == "Clean Code"
        assert info["isbn13"] == "9780132350884"


class TestCrawlAllPlatforms:
    """crawl_all_platforms 테스트"""

    @pytest.mark.asyncio
    async def test_crawl_single_platform(self, load_fixture):
        """단일 플랫폼 크롤링"""
        html = load_fixture("kyobo_search.html")

        with patch.object(KyoboCrawler, "_fetch_html", return_value=html):
            with patch.object(KyoboCrawler, "delay", new_callable=AsyncMock):
                result = await crawl_all_platforms("Clean Code", ["kyobo"])

        assert result.query == "Clean Code"
        assert len(result.results) == 1
        assert result.results[0].platform == "kyobo"

    @pytest.mark.asyncio
    async def test_crawl_multiple_platforms(self, load_fixture, mock_aladin_key):
        """복수 플랫폼 크롤링"""
        kyobo_html = load_fixture("kyobo_search.html")
        yes24_search = load_fixture("yes24_search.html")
        yes24_detail = load_fixture("yes24_detail.html")
        aladin_search = json.loads(load_fixture("aladin_search_response.json"))
        aladin_lookup = json.loads(load_fixture("aladin_lookup_response.json"))

        with patch.object(KyoboCrawler, "_fetch_html", return_value=kyobo_html):
            with patch.object(Yes24Crawler, "_fetch_html") as mock_yes24:
                mock_yes24.side_effect = [yes24_search, yes24_detail]
                with patch.object(AladinCrawler, "_api_request") as mock_aladin:
                    mock_aladin.side_effect = [aladin_search, aladin_lookup]
                    with patch.object(KyoboCrawler, "delay", new_callable=AsyncMock):
                        with patch.object(Yes24Crawler, "delay", new_callable=AsyncMock):
                            result = await crawl_all_platforms(
                                "Clean Code",
                                ["kyobo", "yes24", "aladin"]
                            )

        assert result.query == "Clean Code"
        assert len(result.results) == 3

        platforms = {r.platform for r in result.results}
        assert platforms == {"kyobo", "yes24", "aladin"}

    @pytest.mark.asyncio
    async def test_crawl_invalid_platform_filtered(self, load_fixture):
        """유효하지 않은 플랫폼 필터링"""
        html = load_fixture("kyobo_search.html")

        with patch.object(KyoboCrawler, "_fetch_html", return_value=html):
            with patch.object(KyoboCrawler, "delay", new_callable=AsyncMock):
                result = await crawl_all_platforms(
                    "Clean Code",
                    ["kyobo", "invalid_platform"]
                )

        assert len(result.results) == 1
        assert result.results[0].platform == "kyobo"

    @pytest.mark.asyncio
    async def test_crawl_all_invalid_platforms(self):
        """모든 플랫폼이 유효하지 않음"""
        result = await crawl_all_platforms("Clean Code", ["invalid1", "invalid2"])

        assert len(result.results) == 0

    @pytest.mark.asyncio
    async def test_crawl_korean_with_goodreads(self, load_fixture, mock_aladin_key):
        """한국어 검색어로 Goodreads 포함 크롤링 (원서 연결)"""
        aladin_search = json.loads(load_fixture("aladin_search_response.json"))
        aladin_lookup = json.loads(load_fixture("aladin_lookup_response.json"))

        with patch.object(AladinCrawler, "_api_request") as mock_aladin:
            mock_aladin.side_effect = [
                aladin_search,  # _get_original_title의 search
                aladin_lookup,  # get_original_title
                aladin_search,  # crawl의 search
                aladin_lookup,  # crawl의 get_rating
            ]
            # GoodreadsCrawler의 search_by_keyword를 직접 모킹
            with patch.object(GoodreadsCrawler, "search_by_keyword") as mock_search:
                mock_search.return_value = ("https://goodreads.com/book/123", "Clean Code")
                with patch.object(GoodreadsCrawler, "get_rating", new_callable=AsyncMock) as mock_rating:
                    mock_rating.return_value = (4.35, 1471)
                    with patch.object(GoodreadsCrawler, "delay", new_callable=AsyncMock):
                        result = await crawl_all_platforms(
                            "클린 코드",
                            ["aladin", "goodreads"]
                        )

        assert len(result.results) == 2

        goodreads_result = next(r for r in result.results if r.platform == "goodreads")
        assert goodreads_result.rating == 4.35
        assert goodreads_result.rating_scale == 5


class TestCrawlAllPlatformsErrorHandling:
    """에러 처리 테스트"""

    @pytest.mark.asyncio
    async def test_crawl_handles_exception(self, load_fixture):
        """크롤러 예외 처리"""
        html = load_fixture("kyobo_search.html")

        with patch.object(KyoboCrawler, "_fetch_html", return_value=html):
            with patch.object(Yes24Crawler, "_fetch_html", side_effect=Exception("Network error")):
                with patch.object(KyoboCrawler, "delay", new_callable=AsyncMock):
                    result = await crawl_all_platforms(
                        "Clean Code",
                        ["kyobo", "yes24"]
                    )

        # kyobo만 성공
        assert len(result.results) == 1
        assert result.results[0].platform == "kyobo"

    @pytest.mark.asyncio
    async def test_crawl_handles_all_failures(self):
        """모든 크롤러 실패"""
        with patch.object(KyoboCrawler, "_fetch_html", side_effect=Exception("Error")):
            with patch.object(Yes24Crawler, "_fetch_html", side_effect=Exception("Error")):
                result = await crawl_all_platforms(
                    "Clean Code",
                    ["kyobo", "yes24"]
                )

        assert len(result.results) == 0
