import re
from crawlers.transport import active_transport
import urllib.parse

from bs4 import BeautifulSoup

from .base_http import BaseHttpCrawler
from .utils import title_score, is_isbn, clean_isbn, structured_isbns, isbn_matches, count_number, book_node


class Yes24Crawler(BaseHttpCrawler):
    """Yes24 크롤러 (HTTP 기반 - 브라우저 불필요)"""

    name = "yes24"
    base_url = "https://www.yes24.com"
    rating_scale = 10

    def search_by_keyword(self, keyword: str) -> tuple[str | None, str]:
        """책 검색 후 가장 관련 있는 결과의 상세 페이지 URL 반환"""
        encoded_query = urllib.parse.quote(keyword)
        search_url = f"https://www.yes24.com/Product/Search?domain=ALL&query={encoded_query}"

        def identify():
            try:
                html = self._fetch_html(search_url)
            except Exception:
                return None, "", None, None
            url, title = self._select_product(keyword, html)
            return url, title, self.book_isbn, self.book_author
        transport = active_transport()
        result = transport.memo(("yes24-product", keyword), identify) if transport else identify()
        url, title, self.book_isbn, self.book_author = result
        self._selected_title = title or None
        self._selected_product = re.search(r"/goods/(\d+)", url or "", re.I).group(1) if url else None
        return url, title

    def _select_product(self, keyword, html):
        soup = BeautifulSoup(html, "html.parser")

        # a.gd_name 클래스로 검색 결과 링크 찾기
        keyword_lower = keyword.lower()
        best_url = None
        best_title = ""
        best_score = 0.0

        for link in soup.select("a.gd_name"):
            href = link.get("href", "")
            text = link.get_text(strip=True)

            # 중고서점 제외
            if "UsedShopHub" in href:
                continue

            # /product/goods/ 형식만 허용
            if "/product/goods/" not in href.lower():
                continue

            score = title_score(keyword, text)
            identifiers = structured_isbns(link.parent)
            if is_isbn(keyword):
                if not isbn_matches(keyword, identifiers):
                    # Click tracking repeats the search term, not the product
                    # ISBN. Verify the real Book metadata on the goods page.
                    candidate_url = urllib.parse.urljoin(self.base_url, href)
                    try:
                        detail = BeautifulSoup(self._fetch_html(candidate_url), "html.parser")
                        node = book_node(detail, text)
                        product = re.search(r"/goods/(\d+)", href, re.I)
                        if node and product and str(node.get("sku", product.group(1))) == product.group(1):
                            actual_isbn = node.get("isbn")
                            if actual_isbn:
                                identifiers.append(str(actual_isbn))
                            if isbn_matches(keyword, identifiers):
                                self.book_author = str(node.get("author", "")) or None
                    except Exception:
                        pass
                score = 1.0 if isbn_matches(keyword, identifiers) else 0.0
            if score > best_score:
                best_score = score
                best_url = href
                best_title = text
                container = link.find_parent("li") or link.parent
                self.book_isbn = next(iter(identifiers), None)
                author = container.select_one(".info_auth, .authPub .auth, .gd_auth")
                self.book_author = author.get_text(" ", strip=True) if author else None

        if not best_url:
            return None, ""

        # URL 정규화
        if best_url.startswith("/"):
            best_url = f"https://www.yes24.com{best_url}"

        return best_url, best_title

    async def get_rating(self, url: str) -> tuple[float | None, int]:
        """상세 페이지에서 평점/리뷰수 추출"""
        try:
            html = self._fetch_html(url)
        except Exception:
            self.logger.rating_complete(None, 0, method="html")
            return None, 0

        soup = BeautifulSoup(html, "html.parser")

        # 평점 추출 (Yes24는 10점 만점)
        actual = soup.select_one(".gd_titArea .gd_name, h2.gd_name")
        if actual and self._selected_title and not title_score(self._selected_title, actual.get_text(strip=True)):
            self.failure_status = "identity_mismatch"
            return None, 0
        final = getattr(self, "_last_url", "")
        selected_product = getattr(self, "_selected_product", None)
        if final and selected_product and not re.search(rf"/goods/{selected_product}(?:[/?#]|$)", final, re.I):
            self.failure_status = "identity_mismatch"
            return None, 0
        rating = None
        rating_selectors = [
            ".gd_rating em",
            ".gd_rating .yes_b",
            "span.gd_rating em",
        ]

        for selector in rating_selectors:
            rating_elem = soup.select_one(selector)
            if rating_elem:
                rating_text = rating_elem.get_text(strip=True)
                try:
                    value = float(rating_text)
                    if not 0 <= value <= self.rating_scale:
                        continue
                    rating = value
                    self.logger.parse_result(selector, rating)
                    break
                except ValueError:
                    continue

        # 리뷰 수 추출 - "회원리뷰(N건)" 패턴에서 추출
        review_count = 0
        counter = soup.select_one("#scroll_bar_count[data-review-count], #emReviewCountText")
        if counter:
            raw_count = counter.get("data-review-count")
            if raw_count is None:
                match = re.search(r"[\d,]+", counter.get_text())
                raw_count = match.group() if match else None
            self.text_review_count = count_number(raw_count)
            if self.text_review_count is not None:
                review_count = self.text_review_count
        areas = soup.select(".gd_reviewArea, .gd_infoTop, #spanGdReview, #infoset_reivew .tit_txt")
        text = " ".join(area.get_text(" ", strip=True) for area in areas)

        patterns = [
            r"회원리뷰\s*\(\s*(\d[\d,]*)\s*건?\s*\)",
            r"구매평\s*\(\s*(\d[\d,]*)\s*\)",
            r"리뷰\s*(\d[\d,]*)\s*건",
        ]

        for pattern in patterns:
            if self.text_review_count is not None:
                break
            match = re.search(pattern, text)
            if match:
                review_count = int(match.group(1).replace(",", ""))
                self.text_review_count = review_count
                self.logger.parse_result(pattern, review_count)
                break

        self.logger.rating_complete(rating, review_count, method="html")
        return rating, review_count
