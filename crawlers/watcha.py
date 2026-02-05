"""왓챠피디아 HTTP 기반 크롤러"""

import re
import urllib.parse

from bs4 import BeautifulSoup

from .base_http import BaseHttpCrawler


class WatchaCrawler(BaseHttpCrawler):
    """
    왓챠피디아 크롤러 (HTTP 기반 - 브라우저 불필요)

    SSR 렌더링된 검색 결과와 상세 페이지에서 평점/리뷰 수 추출.
    5점 만점 스케일.
    """

    name = "watcha"
    base_url = "https://pedia.watcha.com"
    rating_scale = 5
    user_agent = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"

    def search_by_keyword(self, keyword: str) -> tuple[str | None, str]:
        """책 검색 후 가장 관련 있는 결과의 상세 페이지 URL 반환"""
        encoded_query = urllib.parse.quote(keyword)
        search_url = f"{self.base_url}/ko-KR/searches/books?query={encoded_query}"

        try:
            html = self._fetch_html(search_url)
        except Exception:
            return None, ""

        soup = BeautifulSoup(html, "html.parser")

        # /ko-KR/contents/{ID} 패턴의 링크 찾기
        book_links = soup.find_all("a", href=re.compile(r"/ko-KR/contents/[a-zA-Z0-9]+"))

        if not book_links:
            return None, ""

        first_link = book_links[0]
        href = first_link.get("href")

        if not href:
            return None, ""

        # 링크 텍스트에서 제목 추출 (연도・저자 정보 제거)
        title_text = first_link.get_text(strip=True)
        title = re.sub(r"\s*\d{4}\s*・.*$", "", title_text).strip()

        book_url = f"{self.base_url}{href}" if href.startswith("/") else href

        self.logger.parse_result("search", f"Found: {title} at {book_url}")
        return book_url, title

    async def get_rating(self, url: str) -> tuple[float | None, int]:
        """상세 페이지에서 평점/리뷰수 추출"""
        try:
            html = self._fetch_html(url)
        except Exception:
            self.logger.rating_complete(None, 0, method="html", rating_scale=self.rating_scale)
            return None, 0

        soup = BeautifulSoup(html, "html.parser")

        rating = None
        review_count = 0

        text_content = soup.get_text()

        # 평점 추출: "평균 4.0" 패턴
        rating_match = re.search(r"평균\s+([\d.]+)", text_content)
        if rating_match:
            try:
                value = float(rating_match.group(1))
                if 0 < value <= 5:
                    rating = value
                    self.logger.parse_result("rating", rating)
            except ValueError:
                pass

        # 리뷰 수 추출: "(3.2만명)", "(500명)", "(3만명)" 패턴
        review_match = re.search(r"\(([\d.]+)만명\)", text_content)
        if review_match:
            try:
                review_count = int(float(review_match.group(1)) * 10000)
                self.logger.parse_result("review_count", review_count)
            except ValueError:
                pass
        else:
            # "만" 없이 "(500명)" 패턴
            review_match = re.search(r"\(([\d,]+)명\)", text_content)
            if review_match:
                try:
                    review_count = int(review_match.group(1).replace(",", ""))
                    self.logger.parse_result("review_count", review_count)
                except ValueError:
                    pass

        self.logger.rating_complete(rating, review_count, method="html", rating_scale=self.rating_scale)
        return rating, review_count
