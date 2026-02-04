import re
import urllib.parse

from bs4 import BeautifulSoup

from .base_http import BaseHttpCrawler


class Yes24Crawler(BaseHttpCrawler):
    """Yes24 크롤러 (HTTP 기반 - 브라우저 불필요)"""

    name = "yes24"
    base_url = "https://www.yes24.com"
    rating_scale = 10

    async def search_book(self, query: str) -> tuple[str | None, str]:
        """책 검색 후 가장 관련 있는 결과의 상세 페이지 URL 반환"""
        encoded_query = urllib.parse.quote(query)
        search_url = f"https://www.yes24.com/Product/Search?domain=ALL&query={encoded_query}"

        print(f"[{self.name}] 검색 중: {query}")

        try:
            html = self._fetch_html(search_url)
        except Exception as e:
            print(f"[{self.name}] 검색 페이지 로드 실패: {e}")
            return None, ""

        soup = BeautifulSoup(html, "html.parser")

        # a.gd_name 클래스로 검색 결과 링크 찾기
        query_lower = query.lower()
        best_url = None
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

            # 첫 번째 유효한 결과 저장
            if best_url is None:
                best_url = href
                best_title = text

            # 검색어가 제목에 포함된 경우 우선
            if query_lower in text.lower():
                best_url = href
                best_title = text
                break

        if not best_url:
            return None, ""

        # URL 정규화
        if best_url.startswith("/"):
            best_url = f"https://www.yes24.com{best_url}"

        print(f"[{self.name}] 찾은 책: {best_title}")
        return best_url, best_title

    async def get_rating(self, url: str) -> tuple[float | None, int]:
        """상세 페이지에서 평점/리뷰수 추출"""
        try:
            html = self._fetch_html(url)
        except Exception as e:
            print(f"[{self.name}] 상품 페이지 로드 실패: {e}")
            return None, 0

        soup = BeautifulSoup(html, "html.parser")

        # 평점 추출 (Yes24는 10점 만점)
        rating = None
        rating_selectors = [
            ".gd_rating em",
            ".yes_b",
            "span.gd_rating em",
        ]

        for selector in rating_selectors:
            rating_elem = soup.select_one(selector)
            if rating_elem:
                rating_text = rating_elem.get_text(strip=True)
                try:
                    rating = float(rating_text)
                    break
                except ValueError:
                    continue

        # 리뷰 수 추출 - "회원리뷰(N건)" 패턴에서 추출
        review_count = 0
        text = soup.get_text()

        patterns = [
            r"회원리뷰\s*\(\s*(\d[\d,]*)\s*건?\s*\)",
            r"구매평\s*\(\s*(\d[\d,]*)\s*\)",
            r"리뷰\s*(\d[\d,]*)\s*건",
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                review_count = int(match.group(1).replace(",", ""))
                break

        return rating, review_count
