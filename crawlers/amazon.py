from crawlers.transport import fetch_sync
"""Amazon Books HTTP 기반 크롤러"""

import json
import re
import urllib.parse
import urllib.request

from bs4 import BeautifulSoup

from .base_http import BaseHttpCrawler
from .utils import is_isbn, title_score, book_node, valid_rating, count_number, isbn13, author_matches


class AmazonCrawler(BaseHttpCrawler):
    """
    Amazon Books 크롤러 (HTTP 기반)

    상세 페이지의 JSON-LD 또는 HTML에서 평점/리뷰 수 추출.
    ASIN과 ISBN으로 직접 접근 또는 키워드 검색 지원.
    """

    name = "amazon"
    base_url = "https://www.amazon.com"
    rating_scale = 5  # Amazon은 5점 만점
    user_agent = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )

    def __init__(self):
        super().__init__()
        self._cached_rating: float | None = None
        self._cached_review_count: int = 0

    def _fetch_with_headers(self, url: str) -> str:
        """
        Amazon 페이지 가져오기 (브라우저와 유사한 헤더 포함)
        """
        response = fetch_sync(url, {"User-Agent": self.user_agent, "Accept-Language": "en-US,en;q=0.9"})
        if response is not None:
            return response.text
        req = urllib.request.Request(url)
        headers = {
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Cache-Control": "max-age=0",
            "sec-ch-ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"macOS"',
        }
        for k, v in headers.items():
            req.add_header(k, v)

        with urllib.request.urlopen(req, timeout=15) as resp:
            content = resp.read()
            # gzip 처리
            encoding = resp.info().get("Content-Encoding", "")
            if "gzip" in encoding:
                import gzip
                content = gzip.decompress(content)
            elif "br" in encoding:
                try:
                    import brotli
                    content = brotli.decompress(content)
                except ImportError:
                    pass  # brotli 미설치시 무시
            try:
                return content.decode("utf-8")
            except UnicodeDecodeError:
                return content.decode("latin-1", errors="replace")

    def is_identifier(self, query: str) -> bool:
        """ASIN 또는 ISBN 형식인지 확인"""
        if is_isbn(query):
            return True

        # ASIN: 10자리 영숫자, B로 시작하고 숫자 포함 필수
        # (순수 알파벳은 ASIN이 아님 - "Siddhartha" 같은 제목 제외)
        clean = query.replace("-", "").replace(" ", "")
        if len(clean) == 10 and clean.isalnum():
            has_digit = any(c.isdigit() for c in clean)
            starts_with_b = clean[0].upper() == 'B'
            if has_digit and starts_with_b:
                return True

        return False

    def search_by_identifier(self, identifier: str) -> tuple[str | None, str]:
        """
        ASIN 또는 ISBN으로 직접 상세 페이지 접근

        https://www.amazon.com/dp/{ASIN} 형식으로 직접 접근.
        """
        clean = identifier.replace("-", "").replace(" ", "")
        if len(clean) == 13:
            if not clean.startswith("978"):
                return self.search_by_keyword(identifier)
            core = clean[3:12]
            check = (11 - sum((10 - i) * int(n) for i, n in enumerate(core)) % 11) % 11
            clean = core + ("X" if check == 10 else str(check))
        url = f"https://www.amazon.com/dp/{clean}"

        try:
            html = self._fetch_with_headers(url)
        except Exception:
            return None, ""

        title, rating, review_count = self._parse_detail_page(html)
        if title and self.verify_detail(BeautifulSoup(html, "html.parser"), title, identifier, allow_product=True):
            if not is_isbn(identifier):
                product = BeautifulSoup(html, "html.parser").select_one('input#ASIN, input[name="ASIN"]')
                if not product or product.get("value", "").upper() != clean.upper():
                    return None, ""
            self._rating_loaded = True
            self._cached_rating = rating
            self._cached_review_count = review_count
            return url, title

        return None, ""

    def search_by_keyword(self, keyword: str) -> tuple[str | None, str]:
        """
        키워드로 Amazon Books 검색

        https://www.amazon.com/s?k={keyword}&i=stripbooks-intl-ship 형식으로 검색.
        """
        encoded = urllib.parse.quote(keyword)
        search_url = f"https://www.amazon.com/s?k={encoded}&i=stripbooks"

        try:
            html = self._fetch_with_headers(search_url)
        except Exception:
            return None, ""

        soup = BeautifulSoup(html, "html.parser")

        # 검색 결과에서 첫 번째 책 찾기
        # 방법 1: data-asin 속성이 있는 검색 결과
        candidates = soup.select('[data-component-type="s-search-result"]')
        candidates.sort(key=lambda result: title_score(keyword, result.select_one("h2").get_text(strip=True) if result.select_one("h2") else ""), reverse=True)
        for result in candidates:
            asin = result.get("data-asin", "")
            if not asin:
                continue

            # 제목 추출
            title_elem = result.select_one("h2 a span")
            if not title_elem:
                title_elem = result.select_one("h2 span")
            if not title_elem:
                continue

            title = title_elem.get_text(strip=True)
            text = result.get_text(" ", strip=True)
            if not is_isbn(keyword) and re.search(r"Audiobook|Audible", text, re.I) and not re.search(r"audio|audible", keyword, re.I):
                continue
            # Explicit byline on modern search cards; detail is still verified.
            byline = result.select_one('[data-cy="title-recipe"] .a-row:not(.a-size-medium), .a-row.a-size-base.a-color-secondary')
            if self._expected_author and byline and not author_matches(self._expected_author, byline.get_text(" ", strip=True)):
                continue
            if is_isbn(keyword):
                if not (asin.isdigit() and isbn13(asin) == isbn13(keyword)):
                    if str(keyword).startswith("979"):
                        try:
                            detail_html = self._fetch_with_headers(f"https://www.amazon.com/dp/{asin}")
                            detail_title, detail_rating, detail_count = self._parse_detail_page(detail_html)
                            if self.verify_detail(BeautifulSoup(detail_html, "html.parser"), detail_title, keyword, allow_product=True):
                                self._cached_rating, self._cached_review_count = detail_rating, detail_count
                                self._rating_loaded = True
                                return f"https://www.amazon.com/dp/{asin}", detail_title
                        except Exception:
                            pass
                    continue
            elif not title_score(keyword, title):
                continue
            book_url = f"https://www.amazon.com/dp/{asin}"

            # 검색 결과에서 평점 미리 추출 (가능한 경우)
            rating_elem = result.select_one('span[aria-label*="out of 5 stars"]')
            if rating_elem:
                aria = rating_elem.get("aria-label", "")
                match = re.search(r"([\d.]+)\s*out of\s*5", aria)
                if match:
                    self._cached_rating = valid_rating(match.group(1), 5)

            review_elem = result.select_one('a[href*="product-reviews"] span, a[href*="customerReviews"] span')
            if not review_elem:
                review_elem = result.select_one('a[href*="customerReviews"] span')
            if review_elem:
                text = review_elem.get_text(strip=True)
                match = re.search(r"([\d,]+)", text)
                if match:
                    self._cached_review_count = int(match.group(1).replace(",", ""))
                    self.rating_count = self._cached_review_count

            if self._expected_author:
                self._cached_rating = None  # Fetch detail to verify the known author.
            self._rating_loaded = self._cached_rating is not None
            self._selected_title = title
            return book_url, title

        # Do not reintroduce filtered audio/other-author cards through a generic
        # link fallback on the same structured results page.
        if candidates:
            return None, ""
        # 방법 2: 일반 링크에서 /dp/ 패턴 찾기
        for link in soup.select('a[href*="/dp/"]'):
            href = link.get("href", "")
            match = re.search(r"/dp/([A-Z0-9]{10})", href)
            if match:
                asin = match.group(1)
                title = link.get_text(strip=True)
                if title_score(keyword, title):
                    return f"https://www.amazon.com/dp/{asin}", title

        return None, ""

    def _parse_detail_page(self, html: str) -> tuple[str, float | None, int]:
        """
        상세 페이지에서 제목, 평점, 리뷰 수 추출
        """
        soup = BeautifulSoup(html, "html.parser")

        # 제목 추출
        title = ""
        title_elem = soup.select_one("#productTitle")
        if title_elem:
            title = title_elem.get_text(strip=True)
        else:
            # 대체 셀렉터
            title_elem = soup.select_one("#btAsinTitle")
            if title_elem:
                title = title_elem.get_text(strip=True)

        rating = None
        review_count = 0

        node = book_node(soup, title, allow_product=True) or {}
        aggregate = node.get("aggregateRating", {})
        rating = valid_rating(aggregate.get("ratingValue"), 5, aggregate.get("bestRating"))
        self.rating_count = count_number(aggregate.get("ratingCount"))
        self.text_review_count = count_number(aggregate.get("reviewCount"))
        element = soup.select_one('#acrPopover .a-icon-alt, #averageCustomerReviews .a-icon-alt, #averageCustomerReviews_feature_div .a-icon-alt')
        if rating is None and element:
            match = re.search(r"([\d.]+)\s*out of\s*5", element.get_text())
            rating = valid_rating(match.group(1), 5) if match else None
        element = soup.select_one('#acrCustomerReviewText, #averageCustomerReviews [data-hook="total-review-count"]')
        if element:
            match = re.search(r"([\d,]+)", element.get_text())
            if match and self.rating_count is None:
                self.rating_count = count_number(match.group(1))
        return title, rating, self.rating_count if self.rating_count is not None else self.text_review_count or 0

    async def get_rating(self, url: str) -> tuple[float | None, int]:
        """
        상세 페이지에서 평점/리뷰 수 추출

        search_book에서 이미 추출했으면 캐시 반환.
        """
        # 캐시된 값이 있으면 반환
        if self._rating_loaded or self._cached_rating is not None:
            self.logger.debug("캐시된 평점 사용", rating=self._cached_rating)
            self.logger.rating_complete(
                self._cached_rating, self._cached_review_count, method="json-ld",
                rating_scale=self.rating_scale
            )
            return self._cached_rating, self._cached_review_count

        # 상세 페이지 접근
        try:
            html = self._fetch_with_headers(url)
        except Exception:
            self.logger.rating_complete(None, 0, method="json-ld", rating_scale=self.rating_scale)
            return None, 0

        title, rating, review_count = self._parse_detail_page(html)
        expected = self._expected_title or getattr(self, "_selected_title", None)
        if not self.verify_detail(BeautifulSoup(html, "html.parser"), title, expected, allow_product=True):
            return None, 0
        self._rating_loaded = True
        self.logger.rating_complete(rating, review_count, method="json-ld", rating_scale=self.rating_scale)
        return rating, review_count
