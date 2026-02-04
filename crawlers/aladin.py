"""알라딘 API 기반 크롤러"""

import json
import os
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

        try:
            opener = urllib.request.build_opener()
            opener.addheaders = [("User-Agent", self.user_agent)]
            response = opener.open(url, timeout=10)
            content = response.read().decode("utf-8")
            return json.loads(content)
        except Exception as e:
            print(f"[{self.name}] API 호출 실패: {e}")
            return None

    async def search_book(self, query: str) -> tuple[str | None, str]:
        """책 검색 후 상세 페이지 URL과 itemId 반환"""
        print(f"[{self.name}] 검색 중: {query}")

        if not self.ttb_key:
            print(f"[{self.name}] TTB Key가 설정되지 않았습니다.")
            return None, ""

        params = {
            "Query": query,
            "QueryType": "Keyword",
            "MaxResults": 10,
            "SearchTarget": "Book",
        }

        result = self._api_request("ItemSearch.aspx", params)
        if not result or not result.get("item"):
            return None, ""

        # 검색어와 가장 잘 맞는 결과 선택
        query_lower = query.lower()
        best_item = None

        for item in result["item"]:
            title = item.get("title", "")

            # 첫 번째 유효한 결과 저장
            if best_item is None:
                best_item = item

            # 검색어가 제목에 포함된 경우 우선
            if query_lower in title.lower():
                best_item = item
                break

            # 검색어의 각 단어가 제목에 포함되는지 체크
            query_words = query_lower.split()
            title_lower = title.lower()
            if all(word in title_lower for word in query_words if len(word) > 1):
                best_item = item
                break

        if not best_item:
            return None, ""

        book_url = best_item.get("link", "")
        book_title = best_item.get("title", "")
        # itemId를 URL에 저장 (get_rating에서 사용)
        self._current_item_id = best_item.get("itemId")

        print(f"[{self.name}] 찾은 책: {book_title}")
        return book_url, book_title

    async def get_rating(self, url: str) -> tuple[float | None, int]:
        """ItemLookUp API로 평점/리뷰수 추출"""
        if not hasattr(self, "_current_item_id") or not self._current_item_id:
            return None, 0

        params = {
            "itemIdType": "ItemId",
            "ItemId": self._current_item_id,
            "OptResult": "ratingInfo",
        }

        result = self._api_request("ItemLookUp.aspx", params)
        if not result or not result.get("item"):
            return None, 0

        item = result["item"][0]
        sub_info = item.get("subInfo", {})
        rating_info = sub_info.get("ratingInfo", {})

        rating = rating_info.get("ratingScore")
        review_count = rating_info.get("commentReviewCount", 0)

        # API에서 ratingInfo가 없는 경우 customerReviewRank 사용
        if rating is None:
            rating = item.get("customerReviewRank")
            if rating is not None:
                rating = float(rating)

        return rating, review_count

    async def crawl(self, query: str) -> PlatformRating | None:
        """
        책 검색부터 평점 추출까지 전체 플로우

        API 기반이므 별도의 delay 불필요
        """
        try:
            book_url, book_title = await self.search_book(query)

            if not book_url:
                print(f"[{self.name}] 검색 결과 없음: {query}")
                return None

            rating, review_count = await self.get_rating(book_url)

            return PlatformRating(
                platform=self.name,
                rating=rating,
                rating_scale=self.rating_scale,
                review_count=review_count,
                url=book_url,
                book_title=book_title,
            )
        except Exception as e:
            print(f"[{self.name}] 크롤링 실패: {e}")
            return None
