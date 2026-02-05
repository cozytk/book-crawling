"""교보문고 HTTP 기반 크롤러"""

import json
import re
import urllib.parse
import urllib.request

from bs4 import BeautifulSoup

from .base_http import BaseHttpCrawler


class KyoboCrawler(BaseHttpCrawler):
    """
    교보문고 크롤러 (HTTP 기반 + API)

    검색: 검색 페이지 HTML 파싱
    평점/리뷰: API 사용

    API:
    - 평점: /api/review/statistics?saleCmdtid={id} → revwRvgrAvg
    - 리뷰 수: /api/gw/pdt/review/status-count?saleCmdtid={id} → revwPatrCode:000
    """

    name = "kyobo"
    base_url = "https://www.kyobobook.co.kr"
    stats_api_url = "https://product.kyobobook.co.kr/api/review/statistics"
    count_api_url = "https://product.kyobobook.co.kr/api/gw/pdt/review/status-count"
    rating_scale = 10
    user_agent = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

    def search_by_keyword(self, keyword: str) -> tuple[str | None, str]:
        """책 검색 - 검색 페이지 HTML 파싱"""
        encoded_query = urllib.parse.quote(keyword)
        search_url = f"https://search.kyobobook.co.kr/search?keyword={encoded_query}&gbCode=TOT&target=total"

        try:
            html = self._fetch_html(search_url)
        except Exception:
            return None, ""

        soup = BeautifulSoup(html, "html.parser")

        # 검색 결과 아이템 찾기
        items = soup.select(".prod_item")
        if not items:
            return None, ""

        keyword_lower = keyword.lower()
        keyword_words = [w for w in keyword_lower.split() if len(w) > 1]
        best_title = ""
        best_url = ""

        for item in items:
            # 책 제목 및 URL 추출
            title_elem = item.select_one("a.prod_info")
            if not title_elem:
                continue

            book_name = title_elem.get_text(strip=True)
            # "[국내도서]" 등의 prefix 제거
            if book_name.startswith("[") and "]" in book_name:
                book_name = book_name.split("]", 1)[1].strip()

            book_url = title_elem.get("href", "")

            if not book_url:
                continue
            if not book_url.startswith("http"):
                book_url = "https://product.kyobobook.co.kr" + book_url

            # ebook 제외 (종이책 우선)
            if "ebook" in book_url.lower():
                continue

            # 세트/에디션 상품 제외
            exclude_keywords = ["세트", "에디션", "3종", "2종", "전집", "박스세트"]
            if any(kw in book_name for kw in exclude_keywords):
                continue

            # 첫 번째 유효한 결과 저장
            if not best_url:
                best_title = book_name
                best_url = book_url

            # 검색어 매칭
            title_lower = book_name.lower().replace(" ", "")
            keyword_normalized = keyword_lower.replace(" ", "")

            if keyword_normalized in title_lower:
                return book_url, book_name

            if all(word in title_lower for word in keyword_words):
                return book_url, book_name

        return (best_url, best_title) if best_url else (None, "")

    def _extract_product_id(self, url: str) -> str | None:
        """URL에서 상품 ID 추출 (예: S000061352497)"""
        match = re.search(r"/detail/(\w+)", url)
        return match.group(1) if match else None

    def _fetch_api(self, url: str) -> dict | None:
        """API 호출 헬퍼"""
        try:
            req = urllib.request.Request(url)
            req.add_header("User-Agent", self.user_agent)
            req.add_header("Referer", "https://product.kyobobook.co.kr/")

            with urllib.request.urlopen(req, timeout=10) as resp:
                response = resp.read().decode("utf-8")

            return json.loads(response)
        except Exception:
            return None

    async def get_rating(self, url: str) -> tuple[float | None, int]:
        """
        API에서 평점/리뷰 수 추출

        - 평점: /api/review/statistics → revwRvgrAvg
        - 리뷰 수: /api/gw/pdt/review/status-count → revwPatrCode:000 (전체)
        """
        product_id = self._extract_product_id(url)
        if not product_id:
            self.logger.error("extract_product_id_failed", f"URL: {url}")
            return None, 0

        rating = None
        review_count = 0

        # 1. 평점 조회 (statistics API)
        stats_data = self._fetch_api(f"{self.stats_api_url}?saleCmdtid={product_id}")
        if stats_data and stats_data.get("resultCode") == "000000":
            stats = stats_data.get("data", {})
            rating = stats.get("revwRvgrAvg")
            self.logger.api_response("statistics", stats)
            if rating is not None and (rating <= 0 or rating > 10):
                rating = None

        # 2. 전체 리뷰 수 조회 (status-count API)
        count_data = self._fetch_api(f"{self.count_api_url}?saleCmdtid={product_id}")
        if count_data and count_data.get("resultCode") == "000000":
            self.logger.api_response("status-count", count_data.get("data", []))
            for item in count_data.get("data", []):
                # revwPatrCode: 000 = 전체 리뷰 수
                if item.get("revwPatrCode") == "000":
                    review_count = item.get("count", 0)
                    break

        self.logger.rating_complete(rating, review_count, method="api")
        return rating, review_count
