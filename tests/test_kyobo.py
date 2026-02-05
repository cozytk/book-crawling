"""KyoboCrawler 테스트"""

import json
import pytest
from unittest.mock import patch, MagicMock

from crawlers.kyobo import KyoboCrawler


class TestKyoboSearchByKeyword:
    """키워드 검색 테스트"""

    def test_search_by_keyword_success(self, load_fixture):
        """검색 성공"""
        html = load_fixture("kyobo_search.html")
        crawler = KyoboCrawler()

        with patch.object(crawler, "_fetch_html", return_value=html):
            url, title = crawler.search_by_keyword("Clean Code")

        assert url is not None
        assert "S000001032980" in url
        assert "Clean Code" in title

    def test_search_by_keyword_excludes_set_products(self, load_fixture):
        """세트 상품 제외"""
        html = load_fixture("kyobo_search.html")
        crawler = KyoboCrawler()

        with patch.object(crawler, "_fetch_html", return_value=html):
            url, title = crawler.search_by_keyword("클린 코드")

        # 세트 상품(S000001234567)이 아닌 개별 상품 선택
        assert "S000001234567" not in url
        assert "세트" not in title

    def test_search_by_keyword_no_results(self):
        """검색 결과 없음"""
        crawler = KyoboCrawler()

        with patch.object(crawler, "_fetch_html", return_value="<html></html>"):
            url, title = crawler.search_by_keyword("xyznonexistent")

        assert url is None
        assert title == ""

    def test_search_by_keyword_removes_prefix(self, load_fixture):
        """[국내도서] 접두사 제거"""
        html = load_fixture("kyobo_search.html")
        crawler = KyoboCrawler()

        with patch.object(crawler, "_fetch_html", return_value=html):
            url, title = crawler.search_by_keyword("Clean Code")

        assert not title.startswith("[국내도서]")


class TestKyoboGetRating:
    """평점 조회 테스트 (API 기반)"""

    @pytest.mark.asyncio
    async def test_get_rating_from_api(self):
        """API에서 평점 추출 (dual API)"""
        # 1. 평점 API 응답 (statistics)
        stats_response = json.dumps({
            "data": {
                "saleCmdtid": "S000001032980",
                "revwRvgrAvg": 9.8,
            },
            "resultCode": "000000"
        })
        # 2. 리뷰 수 API 응답 (status-count)
        count_response = json.dumps({
            "data": [
                {"revwPatrCode": "000", "count": 127},  # 전체
                {"revwPatrCode": "001", "count": 100},  # 한줄평
                {"revwPatrCode": "002", "count": 27},   # 일반리뷰
            ],
            "resultCode": "000000"
        })

        crawler = KyoboCrawler()

        def mock_urlopen_side_effect(req, timeout=None):
            mock_response = MagicMock()
            url = req.full_url if hasattr(req, 'full_url') else str(req)
            if "statistics" in url:
                mock_response.read.return_value = stats_response.encode("utf-8")
            else:
                mock_response.read.return_value = count_response.encode("utf-8")
            mock_response.__enter__ = MagicMock(return_value=mock_response)
            mock_response.__exit__ = MagicMock(return_value=False)
            return mock_response

        with patch("urllib.request.urlopen", side_effect=mock_urlopen_side_effect):
            rating, review_count = await crawler.get_rating(
                "https://product.kyobobook.co.kr/detail/S000001032980"
            )

        assert rating == 9.8
        assert review_count == 127

    @pytest.mark.asyncio
    async def test_get_rating_invalid_url(self):
        """잘못된 URL - 상품 ID 추출 실패"""
        crawler = KyoboCrawler()
        rating, review_count = await crawler.get_rating("https://invalid.url")

        assert rating is None
        assert review_count == 0

    @pytest.mark.asyncio
    async def test_get_rating_api_error(self):
        """API 오류 처리"""
        crawler = KyoboCrawler()

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = Exception("API Error")

            rating, review_count = await crawler.get_rating(
                "https://product.kyobobook.co.kr/detail/S000001032980"
            )

        assert rating is None
        assert review_count == 0


class TestKyoboCrawl:
    """전체 크롤링 플로우 테스트"""

    @pytest.mark.asyncio
    async def test_crawl_success(self, load_fixture):
        """크롤링 성공"""
        html = load_fixture("kyobo_search.html")
        stats_response = json.dumps({
            "data": {"revwRvgrAvg": 9.8},
            "resultCode": "000000"
        })
        count_response = json.dumps({
            "data": [
                {"revwPatrCode": "000", "count": 127},
            ],
            "resultCode": "000000"
        })

        def mock_urlopen_side_effect(req, timeout=None):
            mock_response = MagicMock()
            url = req.full_url if hasattr(req, 'full_url') else str(req)
            if "statistics" in url:
                mock_response.read.return_value = stats_response.encode("utf-8")
            else:
                mock_response.read.return_value = count_response.encode("utf-8")
            mock_response.__enter__ = MagicMock(return_value=mock_response)
            mock_response.__exit__ = MagicMock(return_value=False)
            return mock_response

        async with KyoboCrawler() as crawler:
            with patch.object(crawler, "_fetch_html", return_value=html):
                with patch("urllib.request.urlopen", side_effect=mock_urlopen_side_effect):
                    with patch.object(crawler, "delay"):
                        result = await crawler.crawl("Clean Code")

        assert result is not None
        assert result.platform == "kyobo"
        assert result.rating == 9.8
        assert result.rating_scale == 10
        assert result.review_count == 127
        assert "Clean Code" in result.book_title

    @pytest.mark.asyncio
    async def test_crawl_not_found(self):
        """검색 결과 없음"""
        async with KyoboCrawler() as crawler:
            with patch.object(crawler, "_fetch_html", return_value="<html></html>"):
                result = await crawler.crawl("xyznonexistent")

        assert result is None


class TestKyoboKeywordMatching:
    """키워드 매칭 로직 테스트"""

    def test_exact_match_preferred(self):
        """정확한 매칭 우선"""
        html = """
        <html>
        <div class="prod_item">
            <a class="prod_info" href="/detail/S000002">클린 아키텍처</a>
            <span class="review_klover_text">9.0</span>
            <span class="review_desc">(50건)</span>
        </div>
        <div class="prod_item">
            <a class="prod_info" href="/detail/S000001">클린 코드</a>
            <span class="review_klover_text">9.8</span>
            <span class="review_desc">(127건)</span>
        </div>
        </html>
        """
        crawler = KyoboCrawler()

        with patch.object(crawler, "_fetch_html", return_value=html):
            url, title = crawler.search_by_keyword("클린 코드")

        # "클린 코드"가 정확히 매칭되는 두 번째 상품 선택
        assert "S000001" in url
        assert "클린 코드" in title

    def test_all_words_match(self):
        """모든 단어가 포함된 경우 매칭"""
        html = """
        <html>
        <div class="prod_item">
            <a class="prod_info" href="/detail/S000001">Clean Code 클린 코드</a>
            <span class="review_klover_text">9.8</span>
            <span class="review_desc">(127건)</span>
        </div>
        </html>
        """
        crawler = KyoboCrawler()

        with patch.object(crawler, "_fetch_html", return_value=html):
            url, title = crawler.search_by_keyword("클린 코드")

        assert url is not None
        assert "클린 코드" in title


class TestKyoboProductIdExtraction:
    """상품 ID 추출 테스트"""

    def test_extract_product_id_success(self):
        """상품 ID 추출 성공"""
        crawler = KyoboCrawler()
        product_id = crawler._extract_product_id(
            "https://product.kyobobook.co.kr/detail/S000001032980"
        )
        assert product_id == "S000001032980"

    def test_extract_product_id_invalid(self):
        """잘못된 URL"""
        crawler = KyoboCrawler()
        product_id = crawler._extract_product_id("https://invalid.url")
        assert product_id is None
