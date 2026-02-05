"""Goodreads HTTP 기반 크롤러"""

import json
import re
import urllib.parse
import urllib.request

from bs4 import BeautifulSoup

from .base_http import BaseHttpCrawler
from .utils import is_isbn


class GoodreadsCrawler(BaseHttpCrawler):
    """
    Goodreads 크롤러 (HTTP 기반 - 브라우저 불필요)

    상세 페이지의 JSON-LD에서 평점/리뷰 수 추출.
    ISBN과 제목 검색을 별도 메서드로 분리하여 인터페이스 명확화.
    """

    name = "goodreads"
    base_url = "https://www.goodreads.com"
    rating_scale = 5  # Goodreads는 5점 만점
    user_agent = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

    def __init__(self):
        super().__init__()
        self._cached_rating: float | None = None
        self._cached_review_count: int = 0

    def _fetch_with_redirect(self, url: str, retries: int = 2) -> tuple[str, str]:
        """
        URL에서 HTML 가져오기 (리다이렉트 추적, 재시도 지원)

        Args:
            url: 요청 URL
            retries: 재시도 횟수 (기본 2회)

        Returns:
            (html, final_url) - 최종 URL과 HTML 내용
        """
        import time

        last_error = None
        for attempt in range(retries + 1):
            try:
                req = urllib.request.Request(url)
                headers = {
                    "User-Agent": self.user_agent,
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.9",
                }
                for k, v in headers.items():
                    req.add_header(k, v)

                with urllib.request.urlopen(req, timeout=30) as resp:
                    final_url = resp.geturl()
                    content = resp.read()
                    try:
                        html = content.decode("utf-8")
                    except UnicodeDecodeError:
                        html = content.decode("latin-1", errors="replace")

                return html, final_url
            except Exception as e:
                last_error = e
                if attempt < retries:
                    time.sleep(1)  # 재시도 전 1초 대기
                    continue
                raise last_error

    def is_identifier(self, query: str) -> bool:
        """ISBN 형식인지 확인"""
        return is_isbn(query)

    def search_by_identifier(self, identifier: str) -> tuple[str | None, str]:
        """
        ISBN으로 직접 조회 (1회 요청)

        https://www.goodreads.com/book/isbn/{isbn} 형식으로 직접 접근.
        상세 페이지로 리다이렉트되어 바로 데이터 추출 가능.

        Args:
            identifier: ISBN-10 또는 ISBN-13

        Returns:
            (book_url, book_title) 또는 (None, "") if not found
        """
        # 하이픈 제거
        isbn_clean = identifier.replace("-", "").replace(" ", "")
        url = f"https://www.goodreads.com/book/isbn/{isbn_clean}"

        try:
            html, final_url = self._fetch_with_redirect(url)
        except Exception:
            return None, ""

        # 상세 페이지에서 제목과 평점 추출
        title, rating, review_count = self._parse_detail_page(html)
        if title:
            self._cached_rating = rating
            self._cached_review_count = review_count
            return final_url, title

        return None, ""

    def search_by_keyword(self, keyword: str) -> tuple[str | None, str]:
        """
        제목으로 검색 (검색 결과 파싱)

        https://www.goodreads.com/search?q={title} 형식으로 검색.
        검색 결과에서 첫 번째 책 URL 추출.

        Args:
            keyword: 책 제목

        Returns:
            (book_url, book_title) 또는 (None, "") if not found
        """
        encoded_title = urllib.parse.quote(keyword)
        search_url = f"https://www.goodreads.com/search?q={encoded_title}"

        try:
            html, final_url = self._fetch_with_redirect(search_url)
        except Exception:
            return None, ""

        # 검색 결과가 상세 페이지로 리다이렉트된 경우 (정확한 매칭)
        if "/book/show/" in final_url:
            book_title, rating, review_count = self._parse_detail_page(html)
            if book_title:
                self._cached_rating = rating
                self._cached_review_count = review_count
                return final_url, book_title
            return None, ""

        # 검색 결과 페이지에서 첫 번째 책 찾기
        soup = BeautifulSoup(html, "html.parser")

        # 검색 결과 테이블에서 책 링크 찾기
        book_link = soup.select_one("a.bookTitle")
        if book_link:
            book_url = book_link.get("href", "")
            if book_url and not book_url.startswith("http"):
                book_url = f"https://www.goodreads.com{book_url}"
            book_title = book_link.get_text(strip=True)
            return book_url, book_title

        # 대체 셀렉터 시도
        book_link = soup.select_one('a[href*="/book/show/"]')
        if book_link:
            book_url = book_link.get("href", "")
            if book_url and not book_url.startswith("http"):
                book_url = f"https://www.goodreads.com{book_url}"
            book_title = book_link.get_text(strip=True)
            if book_title:
                return book_url, book_title

        return None, ""

    def _parse_detail_page(self, html: str) -> tuple[str, float | None, int]:
        """
        상세 페이지에서 제목, 평점, 리뷰 수 추출

        Returns:
            (title, rating, review_count)
        """
        soup = BeautifulSoup(html, "html.parser")

        # 제목 추출
        title = ""
        title_elem = soup.select_one('h1[data-testid="bookTitle"]')
        if title_elem:
            title = title_elem.get_text(strip=True)
        else:
            # 대체 셀렉터
            title_elem = soup.select_one("h1.Text__title1")
            if title_elem:
                title = title_elem.get_text(strip=True)

        # JSON-LD에서 평점/리뷰 추출
        rating = None
        review_count = 0

        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string)
                if isinstance(data, dict) and "aggregateRating" in data:
                    ar = data["aggregateRating"]
                    rating = float(ar.get("ratingValue", 0))
                    # ratingCount: 별점 참여자 수 (reviewCount는 리뷰 작성자 수)
                    review_count = int(ar.get("ratingCount", 0))
                    return title, rating, review_count
            except (json.JSONDecodeError, ValueError, TypeError):
                continue

        # JSON-LD 실패 시 HTML에서 직접 추출
        rating_elem = soup.select_one('div[class*="RatingStatistics"] span[class*="RatingStars"]')
        if rating_elem:
            aria_label = rating_elem.get("aria-label", "")
            match = re.search(r"([\d.]+)\s*out of\s*5", aria_label)
            if match:
                rating = float(match.group(1))

        review_elem = soup.select_one('span[data-testid="reviewsCount"]')
        if review_elem:
            text = review_elem.get_text(strip=True)
            match = re.search(r"([\d,]+)", text)
            if match:
                review_count = int(match.group(1).replace(",", ""))

        return title, rating, review_count

    async def get_rating(self, url: str) -> tuple[float | None, int]:
        """
        상세 페이지에서 평점/리뷰 수 추출

        search_book에서 이미 추출했으면 캐시 반환,
        아니면 상세 페이지 다시 접근.
        """
        # 캐시된 값이 있으면 반환
        if self._cached_rating is not None:
            self.logger.debug("캐시된 평점 사용", rating=self._cached_rating)
            self.logger.rating_complete(
                self._cached_rating, self._cached_review_count, method="json-ld",
                rating_scale=self.rating_scale
            )
            return self._cached_rating, self._cached_review_count

        # 상세 페이지 접근
        try:
            html, _ = self._fetch_with_redirect(url)
        except Exception:
            self.logger.rating_complete(None, 0, method="json-ld", rating_scale=self.rating_scale)
            return None, 0

        _, rating, review_count = self._parse_detail_page(html)
        self.logger.rating_complete(rating, review_count, method="json-ld", rating_scale=self.rating_scale)
        return rating, review_count
