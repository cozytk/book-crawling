"""AladinCrawler 테스트"""

import json
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from crawlers.aladin import AladinCrawler


class TestAladinApiRequest:
    """API 요청 테스트"""

    def test_api_request_success(self, load_fixture, mock_aladin_key):
        """API 호출 성공"""
        response_json = load_fixture("aladin_search_response.json")
        crawler = AladinCrawler()

        with patch("urllib.request.build_opener") as mock_build_opener:
            mock_response = MagicMock()
            mock_response.read.return_value = response_json.encode("utf-8")
            mock_opener = MagicMock()
            mock_opener.open.return_value = mock_response
            mock_build_opener.return_value = mock_opener

            result = crawler._api_request("ItemSearch.aspx", {"Query": "클린 코드"})

        assert result is not None
        assert "item" in result
        assert len(result["item"]) == 1

    def test_api_request_no_key(self, monkeypatch):
        """API 키 없으면 None 반환"""
        monkeypatch.delenv("ALADIN_TTB_KEY", raising=False)

        # .env 파일도 없는 상황 모킹
        with patch("os.path.exists", return_value=False):
            crawler = AladinCrawler()

        # ttb_key가 없으면 search_book에서 None 반환
        assert crawler.ttb_key == ""


class TestAladinSearchBook:
    """책 검색 테스트"""

    @pytest.mark.asyncio
    async def test_search_book_success(self, load_fixture, mock_aladin_key):
        """검색 성공"""
        response_json = load_fixture("aladin_search_response.json")
        crawler = AladinCrawler()

        with patch.object(crawler, "_api_request", return_value=json.loads(response_json)):
            url, title = await crawler.search_book("클린 코드")

        assert url is not None
        assert "aladin.co.kr" in url
        assert "클린 코드" in title
        assert crawler._current_item_id == 123456789

    @pytest.mark.asyncio
    async def test_search_book_no_results(self, mock_aladin_key):
        """검색 결과 없음"""
        crawler = AladinCrawler()

        with patch.object(crawler, "_api_request", return_value={"item": []}):
            url, title = await crawler.search_book("xyznonexistent")

        assert url is None
        assert title == ""

    @pytest.mark.asyncio
    async def test_search_book_no_api_key(self, monkeypatch):
        """API 키 없음"""
        monkeypatch.delenv("ALADIN_TTB_KEY", raising=False)

        with patch("os.path.exists", return_value=False):
            crawler = AladinCrawler()

        url, title = await crawler.search_book("클린 코드")

        assert url is None
        assert title == ""


class TestAladinGetRating:
    """평점 조회 테스트"""

    @pytest.mark.asyncio
    async def test_get_rating_success(self, load_fixture, mock_aladin_key):
        """평점/리뷰 조회 성공"""
        response_json = load_fixture("aladin_lookup_response.json")
        crawler = AladinCrawler()
        crawler._current_item_id = 123456789

        with patch.object(crawler, "_api_request", return_value=json.loads(response_json)):
            rating, review_count = await crawler.get_rating("https://aladin.co.kr/product/123")

        assert rating == 9.6
        assert review_count == 234

    @pytest.mark.asyncio
    async def test_get_rating_no_item_id(self, mock_aladin_key):
        """item_id 없음"""
        crawler = AladinCrawler()
        # _current_item_id가 설정되지 않음

        rating, review_count = await crawler.get_rating("https://example.com")

        assert rating is None
        assert review_count == 0

    @pytest.mark.asyncio
    async def test_get_rating_fallback_to_customer_review_rank(self, mock_aladin_key):
        """ratingInfo 없으면 customerReviewRank 사용"""
        response = {
            "item": [{
                "itemId": 123,
                "customerReviewRank": 9.2
            }]
        }
        crawler = AladinCrawler()
        crawler._current_item_id = 123

        with patch.object(crawler, "_api_request", return_value=response):
            rating, review_count = await crawler.get_rating("https://example.com")

        assert rating == 9.2
        assert review_count == 0


class TestAladinGetOriginalTitleInfo:
    """원서 정보 조회 테스트"""

    @pytest.mark.asyncio
    async def test_get_original_title_info_success(self, load_fixture, mock_aladin_key):
        """원서 정보 조회 성공"""
        response_json = load_fixture("aladin_lookup_response.json")
        crawler = AladinCrawler()
        crawler._current_item_id = 123456789

        with patch.object(crawler, "_api_request", return_value=json.loads(response_json)):
            info = await crawler.get_original_title_info()

        assert info is not None
        assert info["title"] == "Clean Code: A Handbook Of Agile Software Craftsmanship"

    @pytest.mark.asyncio
    async def test_get_original_title_info_with_year_removed(self, mock_aladin_key):
        """연도 정보 제거"""
        response = {
            "item": [{
                "subInfo": {
                    "originalTitle": "Clean Code (2008년)"
                },
                "isbn13": "9780132350884",
            }]
        }
        crawler = AladinCrawler()
        crawler._current_item_id = 123

        with patch.object(crawler, "_api_request", return_value=response):
            info = await crawler.get_original_title_info()

        assert info is not None
        assert info["title"] == "Clean Code"
        assert "2008" not in info["title"]
        assert info["isbn13"] == "9780132350884"

    @pytest.mark.asyncio
    async def test_get_original_title_info_no_original(self, mock_aladin_key):
        """원서 정보 없음 (isbn13도 없으면 None)"""
        response = {
            "item": [{
                "subInfo": {}
            }]
        }
        crawler = AladinCrawler()
        crawler._current_item_id = 123

        with patch.object(crawler, "_api_request", return_value=response):
            info = await crawler.get_original_title_info()

        assert info is None

    @pytest.mark.asyncio
    async def test_get_original_title_info_isbn_only_not_translated(self, mock_aladin_key):
        """원서 제목 없고 번역서 아님 → None 반환 (한국 원서)"""
        response = {
            "item": [{
                "subInfo": {},
                "isbn13": "9788901234567",
                "author": "홍길동 (지은이)",
            }]
        }
        crawler = AladinCrawler()
        crawler._current_item_id = 123

        with patch.object(crawler, "_api_request", return_value=response):
            info = await crawler.get_original_title_info()

        assert info is None

    @pytest.mark.asyncio
    async def test_get_original_title_info_isbn_only_translated(self, mock_aladin_key):
        """원서 제목 없지만 번역서 + isbn13 있음 → info 반환"""
        response = {
            "item": [{
                "subInfo": {},
                "isbn13": "9788901234567",
                "author": "존 스미스 (지은이), 김철수 (옮긴이)",
            }]
        }
        crawler = AladinCrawler()
        crawler._current_item_id = 123

        with patch.object(crawler, "_api_request", return_value=response):
            with patch.object(crawler, "_search_foreign_edition", return_value=None):
                info = await crawler.get_original_title_info()

        assert info is not None
        assert info["title"] is None
        assert info["isbn13"] == "9788901234567"

    @pytest.mark.asyncio
    async def test_get_original_title_info_no_item_id(self, mock_aladin_key):
        """item_id 없음"""
        crawler = AladinCrawler()

        info = await crawler.get_original_title_info()

        assert info is None


class TestAladinCrawl:
    """전체 크롤링 플로우 테스트"""

    @pytest.mark.asyncio
    async def test_crawl_success(self, load_fixture, mock_aladin_key):
        """크롤링 성공"""
        search_response = json.loads(load_fixture("aladin_search_response.json"))
        lookup_response = json.loads(load_fixture("aladin_lookup_response.json"))

        async with AladinCrawler() as crawler:
            with patch.object(crawler, "_api_request") as mock_api:
                mock_api.side_effect = [search_response, lookup_response]
                result = await crawler.crawl("클린 코드")

        assert result is not None
        assert result.platform == "aladin"
        assert result.rating == 9.6
        assert result.rating_scale == 10
        assert result.review_count == 234

    @pytest.mark.asyncio
    async def test_crawl_not_found(self, mock_aladin_key):
        """검색 결과 없음"""
        async with AladinCrawler() as crawler:
            with patch.object(crawler, "_api_request", return_value={"item": []}):
                result = await crawler.crawl("xyznonexistent")

        assert result is None
