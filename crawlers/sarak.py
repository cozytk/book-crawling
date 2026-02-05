"""사락 (Yes24 독서 플랫폼) 크롤러"""

import json
import re
import urllib.parse

from bs4 import BeautifulSoup

from .base_http import BaseHttpCrawler


class SarakCrawler(BaseHttpCrawler):
    """
    사락 크롤러 (HTTP 기반 + API)

    사락은 Yes24의 독서 커뮤니티 플랫폼.
    Yes24 검색으로 상품 ID를 찾은 후 사락 API에서 평점/리뷰 추출.

    URL 패턴:
    - 상세: https://sarak.yes24.com/reading-note/book/{product_id}

    API:
    - 통계: https://sarak-api.yes24.com/api24/v1/reading-note/book/{id}/book-statistics-summary
    """

    name = "sarak"
    base_url = "https://sarak.yes24.com"
    api_url = "https://sarak-api.yes24.com/api24/v1/reading-note/book"
    yes24_url = "https://www.yes24.com"
    rating_scale = 10  # 사락은 10점 만점

    def _extract_product_id(self, url: str) -> str | None:
        """Yes24 URL에서 상품 ID 추출"""
        # /product/goods/102687133 형식
        match = re.search(r"/(?:product/)?goods/(\d+)", url, re.IGNORECASE)
        if match:
            return match.group(1)
        return None

    def search_by_keyword(self, keyword: str) -> tuple[str | None, str]:
        """
        Yes24에서 검색 후 사락 URL 반환

        1. Yes24 검색으로 상품 ID 획득
        2. 사락 URL 구성: /reading-note/book/{product_id}
        """
        encoded_query = urllib.parse.quote(keyword)
        search_url = f"{self.yes24_url}/Product/Search?domain=ALL&query={encoded_query}"

        try:
            html = self._fetch_html(search_url)
        except Exception:
            return None, ""

        soup = BeautifulSoup(html, "html.parser")

        # Yes24 검색 결과에서 첫 번째 책 찾기
        keyword_lower = keyword.lower()
        best_product_id = None
        best_title = ""

        for link in soup.select("a.gd_name"):
            href = link.get("href", "")
            text = link.get_text(strip=True)

            # 중고서점 제외
            if "UsedShopHub" in href:
                continue

            # /product/goods/ 형식만 허용
            if "/product/goods/" not in href.lower():
                continue

            product_id = self._extract_product_id(href)
            if not product_id:
                continue

            # 첫 번째 유효한 결과 저장
            if best_product_id is None:
                best_product_id = product_id
                best_title = text

            # 검색어가 제목에 포함된 경우 우선
            if keyword_lower in text.lower():
                best_product_id = product_id
                best_title = text
                break

        if not best_product_id:
            return None, ""

        # 사락 URL 구성
        sarak_url = f"{self.base_url}/reading-note/book/{best_product_id}"
        return sarak_url, best_title

    def _extract_goods_no(self, url: str) -> str | None:
        """사락 URL에서 상품 번호 추출"""
        match = re.search(r"/book/(\d+)", url)
        return match.group(1) if match else None

    async def get_rating(self, url: str) -> tuple[float | None, int]:
        """
        사락 API에서 평점/평가 참여자 수 추출

        API: /book-statistics-summary
        - starPointAverageForBookInfo: 평점 (10점 만점)
        - userWhoDidVoteThisBookCount: 평가 참여자 수
        """
        goods_no = self._extract_goods_no(url)
        if not goods_no:
            self.logger.error("extract_goods_no_failed", f"URL: {url}")
            return None, 0

        api_url = f"{self.api_url}/{goods_no}/book-statistics-summary"

        try:
            response = self._fetch_html(api_url)
            data = json.loads(response)

            self.logger.api_response("book-statistics-summary", data)

            rating = data.get("starPointAverageForBookInfo")
            review_count = data.get("userWhoDidVoteThisBookCount", 0)

            # 유효성 검사
            if rating is not None and (rating <= 0 or rating > 10):
                rating = None

            self.logger.rating_complete(rating, review_count, method="api")
            return rating, review_count

        except json.JSONDecodeError:
            self.logger.error("json_decode_error", "API 응답 파싱 실패")
            self.logger.rating_complete(None, 0, method="api")
            return None, 0
        except Exception as e:
            self.logger.error("api_error", str(e))
            self.logger.rating_complete(None, 0, method="api")
            return None, 0
