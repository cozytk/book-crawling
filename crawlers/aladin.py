"""알라딘 API 기반 크롤러"""

import html
import json
import os
import time
import urllib.parse
import urllib.request

from .base_http import BaseHttpCrawler
from models.book import PlatformRating


class AladinCrawler(BaseHttpCrawler):
    """알라딘 크롤러 (API 기반 - 브라우저 불필요)"""

    name = "aladin"
    base_url = "https://www.aladin.co.kr"
    rating_scale = 10

    def __init__(self):
        super().__init__()
        self.ttb_key = os.environ.get("ALADIN_TTB_KEY", "")
        if not self.ttb_key:
            # .env 파일에서 직접 읽기 시도
            env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
            if os.path.exists(env_path):
                with open(env_path) as f:
                    for line in f:
                        if line.startswith("ALADIN_TTB_KEY="):
                            self.ttb_key = line.strip().split("=", 1)[1]
                            break

    def _api_request(self, endpoint: str, params: dict) -> dict | None:
        """알라딘 API 호출"""
        params["ttbkey"] = self.ttb_key
        params["output"] = "js"  # JSON
        params["Version"] = "20131101"

        query_string = urllib.parse.urlencode(params)
        url = f"http://www.aladin.co.kr/ttb/api/{endpoint}?{query_string}"

        start = time.perf_counter()
        try:
            opener = urllib.request.build_opener()
            opener.addheaders = [("User-Agent", self.user_agent)]
            response = opener.open(url, timeout=10)
            content = response.read().decode("utf-8")
            elapsed_ms = (time.perf_counter() - start) * 1000

            data = json.loads(content)
            self.logger.http_request(
                method="GET",
                url=url.replace(self.ttb_key, "***"),  # API 키 마스킹
                status=response.status,
                elapsed_ms=elapsed_ms,
                size=len(content),
                response_body=content,
            )
            return data
        except Exception as e:
            elapsed_ms = (time.perf_counter() - start) * 1000
            self.logger.http_error("GET", url.replace(self.ttb_key, "***"), str(e), elapsed_ms)
            return None

    async def search_book(self, query: str) -> tuple[str | None, str]:
        """책 검색 후 상세 페이지 URL과 itemId 반환"""
        self.logger.search_start(
            query,
            session_id=self._session_id,
            original_query=self._original_query,
            attempt=self._current_attempt,
        )

        if not self.ttb_key:
            self.logger.error("config_error", "TTB Key가 설정되지 않았습니다.")
            return None, ""

        params = {
            "Query": query,
            "QueryType": "Keyword",
            "MaxResults": 10,
            "SearchTarget": "Book",
        }

        result = self._api_request("ItemSearch.aspx", params)
        if not result or not result.get("item"):
            self.logger.search_complete(
                query, found=False, method="api",
                session_id=self._session_id,
                original_query=self._original_query,
                attempt=self._current_attempt,
            )
            return None, ""

        # 검색어와 가장 잘 맞는 결과 선택 로직 개선
        import re
        import difflib

        def normalize(text):
            return re.sub(r"[\s\-_,\.\(\)\[\]]", "", text).lower()

        query_norm = normalize(query)
        best_item = None
        best_score = -1.0

        for item in result["item"]:
            title = item.get("title", "")
            title_norm = normalize(title)
            sales_point = float(item.get("salesPoint", 0))

            # 1. 제목 유사도 점수 (0~1)
            similarity = difflib.SequenceMatcher(None, query_norm, title_norm).ratio()
            score = similarity * 100

            # 2. 완전 일치 / 주제목 일치 / 권수 매칭 보너스
            # 주제목 추출 (콜론이나 대시 앞부분)
            primary_title = re.split(r"[:\-]", title)[0].strip()
            primary_norm = normalize(primary_title)
            
            # [검색어] + [숫자/상/하] 형식 매칭 (예: "데미안" -> "데미안 1")
            volume_pattern = rf"^{query_norm}[\d상하 ]+" # 공백 허용
            
            if query_norm == title_norm:
                score += 50
            elif query_norm == primary_norm:
                score += 50  # 주제목이 일치하면 완전 일치로 간주
            elif re.match(volume_pattern, title_norm):
                score += 50  # 완전 일치와 동일한 보너스 부여 (SP로 결정되도록)
            elif query_norm in title_norm:
                score += 20

            # 3. 판매 지수 반영 (가중치 상향)
            import math
            if sales_point > 0:
                score += math.log10(sales_point) * 15

            # 4. 제외 키워드 감점 (학습서, 중고 등)
            penalties = ["중학생", "초등", "어린이", "청소년", "워크북", "중고", "만화", "코믹스"]
            for p in penalties:
                if p in title:
                    score -= 30

            # 디버그 로그용
            self.logger.debug(f"Search match check: {title} (ID: {item.get('itemId')}, SP: {sales_point}) | score: {score:.2f}")

            if score > best_score:
                best_score = score
                best_item = item

        if not best_item or best_score < 30:  # 최소 점수 기준
            self.logger.search_complete(
                query, found=False, method="api",
                session_id=self._session_id,
                original_query=self._original_query,
                attempt=self._current_attempt,
            )
            return None, ""

        book_url = best_item.get("link", "")
        publisher = best_item.get("publisher", "")
        book_title = best_item.get("title", "")
        if publisher:
            book_title = f"{book_title} ({publisher})"
        
        # itemId와 isbn13 저장 (get_rating, get_original_title_info에서 사용)
        self._current_item_id = best_item.get("itemId")
        self._current_isbn13 = best_item.get("isbn13")

        self.logger.search_complete(
            query, found=True, title=book_title,
            product_id=str(self._current_item_id), method="api",
            session_id=self._session_id,
            original_query=self._original_query,
            attempt=self._current_attempt,
        )
        return book_url, book_title

    @staticmethod
    def _parse_author(author_str: str) -> tuple[str | None, bool]:
        """
        알라딘 저자 문자열에서 저자명과 번역서 여부 추출

        Args:
            author_str: "키코 야네라스 (지은이), 이소영 (옮긴이)" 형식

        Returns:
            (저자명, 번역서 여부) - 예: ("키코 야네라스", True)
        """
        import re
        is_translated = "옮긴이" in author_str
        match = re.match(r"(.+?)\s*\(지은이\)", author_str)
        if match:
            return match.group(1).strip(), is_translated
        return None, is_translated

    def _search_foreign_edition(self, author_korean: str) -> dict | None:
        """
        한국어 저자명으로 알라딘 해외도서 카탈로그에서 원서 검색

        Args:
            author_korean: 저자의 한국어 이름 (예: "키코 야네라스")

        Returns:
            {"title": str, "isbn13": str|None} 또는 None
        """
        params = {
            "Query": author_korean,
            "QueryType": "Author",
            "MaxResults": 5,
            "SearchTarget": "Foreign",
        }

        result = self._api_request("ItemSearch.aspx", params)
        if not result or not result.get("item"):
            return None

        item = result["item"][0]
        title = item.get("title", "")
        isbn13 = item.get("isbn13")
        self.logger.debug(f"해외도서 검색 결과: {title} (ISBN: {isbn13})")
        return {"title": title, "isbn13": isbn13} if title else None

    async def get_original_title_info(self, item_id: int | str | None = None) -> dict | None:
        """
        원서 제목, 저자, ISBN13 정보 조회

        조회 순서:
        1. ItemLookUp API의 originalTitle 필드
        2. 번역서인 경우: 알라딘 해외도서 카탈로그에서 저자명으로 원서 검색

        Args:
            item_id: 알라딘 상품 ID (None이면 마지막 검색 결과 사용)

        Returns:
            {"title": str|None, "author": str, "isbn13": str|None} 또는 None
        """
        if item_id is None:
            item_id = getattr(self, "_current_item_id", None)
        if not item_id:
            return None

        params = {
            "itemIdType": "ItemId",
            "ItemId": item_id,
        }

        result = self._api_request("ItemLookUp.aspx", params)
        if not result or not result.get("item"):
            self.logger.debug("original_title_not_found", reason="no_item_in_response")
            return None

        item = result["item"][0]
        sub_info = item.get("subInfo", {})
        original_title = sub_info.get("originalTitle") or None
        author = item.get("author", "")
        isbn13 = item.get("isbn13") or getattr(self, "_current_isbn13", None)

        self.logger.api_response("ItemLookUp.details", {"subInfo": sub_info, "author": author})

        if original_title:
            # HTML 엔티티 디코딩 (예: &#x00C9; -> É)
            original_title = html.unescape(original_title)
            # "(2009년)" 같은 연도 정보 제거
            import re
            original_title = re.sub(r"\s*\(\d{4}년?\)$", "", original_title).strip()
            self.logger.debug(f"원서 제목 추출: {original_title}")

        # 원서 제목이 없는 경우
        if not original_title:
            author_name, is_translated = self._parse_author(author)
            if not is_translated:
                # 번역서가 아닌 한국 원서 → 해외 플랫폼 검색 불필요
                return None
            # 번역서인 경우 → 알라딘 해외도서에서 저자명으로 원서 검색
            if author_name:
                self.logger.debug(f"번역서 감지: {author_name} → 해외도서 검색")
                foreign = self._search_foreign_edition(author_name)
                if foreign:
                    original_title = foreign["title"]
                    isbn13 = foreign.get("isbn13") or isbn13

        if not original_title and not isbn13:
            return None

        return {
            "title": original_title,
            "author": author,
            "isbn13": isbn13,
        }

    def get_original_title(self, item_id: int | str | None = None) -> str | None:
        """호환성을 위한 기존 메서드 (비동기 아님)"""
        # Note: 실제 정보는 crawl_all_platforms에서 비동기로 호출됨
        return None

    async def get_rating(self, url: str) -> tuple[float | None, int]:
        """ItemLookUp API로 평점/리뷰수 추출"""
        if not hasattr(self, "_current_item_id") or not self._current_item_id:
            self.logger.rating_complete(None, 0, method="api")
            return None, 0

        params = {
            "itemIdType": "ItemId",
            "ItemId": self._current_item_id,
            "OptResult": "ratingInfo",
        }

        result = self._api_request("ItemLookUp.aspx", params)
        if not result or not result.get("item"):
            self.logger.rating_complete(None, 0, method="api")
            return None, 0

        item = result["item"][0]
        sub_info = item.get("subInfo", {})
        rating_info = sub_info.get("ratingInfo", {})

        self.logger.api_response("ratingInfo", rating_info)

        rating = rating_info.get("ratingScore")
        # ratingCount: 별점 참여자 수 (commentReviewCount는 100자평 개수)
        review_count = rating_info.get("ratingCount", 0)

        # API에서 ratingInfo가 없는 경우 customerReviewRank 사용
        if rating is None:
            rating = item.get("customerReviewRank")
            if rating is not None:
                rating = float(rating)

        self.logger.rating_complete(rating, review_count, method="api")
        return rating, review_count

    async def crawl(self, query: str, attempt: int = 1) -> PlatformRating | None:
        """
        책 검색부터 평점 추출까지 전체 플로우

        API 기반이므로 별도의 delay 불필요
        """
        self._current_attempt = attempt
        start = time.perf_counter()
        try:
            book_url, book_title = await self.search_book(query)

            if not book_url:
                elapsed_ms = (time.perf_counter() - start) * 1000
                self.logger.crawl_complete(
                    query, success=False, elapsed_ms=elapsed_ms,
                    session_id=self._session_id,
                    original_query=self._original_query,
                    attempt=attempt,
                )
                return None

            rating, review_count = await self.get_rating(book_url)

            elapsed_ms = (time.perf_counter() - start) * 1000
            self.logger.crawl_complete(
                query,
                success=True,
                elapsed_ms=elapsed_ms,
                title=book_title,
                rating=rating,
                review_count=review_count,
                session_id=self._session_id,
                original_query=self._original_query,
                attempt=attempt,
            )

            return PlatformRating(
                platform=self.name,
                rating=rating,
                rating_scale=self.rating_scale,
                review_count=review_count,
                url=book_url,
                book_title=book_title,
            )
        except Exception as e:
            elapsed_ms = (time.perf_counter() - start) * 1000
            self.logger.error("crawl_failed", str(e), {"query": query})
            self.logger.crawl_complete(
                query, success=False, elapsed_ms=elapsed_ms,
                session_id=self._session_id,
                original_query=self._original_query,
                attempt=attempt,
            )
            return None
