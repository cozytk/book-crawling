"""왓챠피디아 HTTP 기반 크롤러"""

import re
import urllib.parse

from bs4 import BeautifulSoup

from .base_http import BaseHttpCrawler
from .utils import title_score, book_node, valid_rating, count_number, author_matches, candidate_score
from .transport import active_transport


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

    def _fetch_html(self, url):
        if active_transport():
            return super()._fetch_html(url)
        from curl_cffi.requests import Session
        if not getattr(self, "_browser_session", None):
            self._browser_session = Session(impersonate="chrome")
        response = self._browser_session.get(url, timeout=8)
        response.raise_for_status()
        return response.text

    async def __aexit__(self, *args):
        if getattr(self, "_browser_session", None):
            self._browser_session.close()

    def search_by_keyword(self, keyword: str) -> tuple[str | None, str]:
        """책 검색 후 가장 관련 있는 결과의 상세 페이지 URL 반환"""
        encoded_query = urllib.parse.quote(keyword)
        search_url = f"{self.base_url}/ko/search?query={encoded_query}"

        try:
            html = self._fetch_html(search_url)
        except Exception:
            return None, ""

        soup = BeautifulSoup(html, "html.parser")

        # /ko-KR/contents/{ID} 패턴의 링크 찾기
        book_links = soup.find_all("a", href=re.compile(r"^/(?:ko-KR|ko)/contents/b[a-zA-Z0-9]+"))

        if not book_links:
            return None, ""

        def clean_title(link):
            return re.split(r"\s*\d{4}\s*[・·]|[・·]", link.get_text(" ", strip=True))[0].removesuffix(" 책").strip()
        def author(link):
            text = re.split(r"[・·]", link.get_text(" ", strip=True), maxsplit=1)
            return text[1].removesuffix(" 책").strip() if len(text) == 2 else ""
        book_links = [link for link in book_links if not self._expected_author or
                      (author(link) and author_matches(self._expected_author, author(link)))]
        if not book_links:
            return None, ""
        first_link = max(book_links, key=lambda link: candidate_score(keyword, clean_title(link), author(link), self._expected_author))
        if not candidate_score(keyword, clean_title(first_link), author(first_link), self._expected_author):
            return None, ""
        href = first_link.get("href")

        if not href:
            return None, ""

        # 링크 텍스트에서 제목 추출 (연도・저자 정보 제거)
        title = clean_title(first_link)
        self._selected_title = title

        book_url = urllib.parse.urljoin(self.base_url, urllib.parse.urlsplit(href).path)

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

        node = book_node(soup, getattr(self, "_selected_title", ""))
        if node is None:
            self.failure_status = "parse_error"
            return None, 0
        if not self.verify_detail(soup, str(node.get("name", "")), getattr(self, "_selected_title", None)):
            return None, 0
        aggregate = node.get("aggregateRating", {})
        self.rating_count = count_number(aggregate.get("ratingCount"))
        self.text_review_count = count_number(aggregate.get("reviewCount"))
        rating = valid_rating(aggregate.get("ratingValue"), 5, aggregate.get("bestRating"))
        return rating, self.rating_count if self.rating_count is not None else self.text_review_count or 0
