from crawlers.transport import fetch_sync, active_transport
"""교보문고 HTTP 기반 크롤러"""

import json
import re
import urllib.parse
import urllib.request

from bs4 import BeautifulSoup

from .base_http import BaseHttpCrawler
from .utils import title_score, is_isbn, clean_isbn, structured_isbns, isbn_matches, author_matches, candidate_score, edition_preference


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

    @staticmethod
    def _edition_metadata(item):
        publisher=item.select_one('.prod_publish .text')
        translators=[]
        for writer in item.select('.prod_author_group a.author:not(.rep)'):
            kind=writer.find_next('span',class_='type')
            if kind and '번역' in kind.get_text():
                translators.append(writer.get_text(' ',strip=True))
        return publisher.get_text(' ',strip=True) if publisher else '', ', '.join(translators)

    def search_by_keyword(self, keyword: str) -> tuple[str | None, str]:
        """책 검색 - 검색 페이지 HTML 파싱"""
        transport=active_transport()
        if transport and self._preferred_isbn:
            with transport.memo_lock:
                future=transport.memo_values.get(("kyobo-selected",keyword,self._preferred_isbn))
            cached=future.result() if future else None
            if cached and author_matches(self._expected_author,cached["author"]):
                self.book_isbn,self.book_author=cached["isbn"],cached["author"]
                self._search_rating=cached["rating"]
                self._search_review_count=cached["reviews"]
                self.count_observed=cached["count_observed"]
                self._rating_loaded=self._search_rating is not None
                return cached["url"],cached["title"]
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
        best_score = 0.0
        self._search_rating = None
        self._search_review_count = 0
        self.discovery_candidates = []
        self.series_sizes = []

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
            author_node = item.select_one(".prod_author_group .author.rep, .prod_author, .prod_author_info .author")
            candidate_author = author_node.get_text(" ", strip=True) if author_node else ""
            role=author_node.find_next('span',class_='type') if author_node else None
            if not is_isbn(keyword) and role and role.get_text(strip=True) in {'원작','원저'}:
                continue
            if not is_isbn(keyword) and self._expected_author and (not candidate_author or not author_matches(self._expected_author, candidate_author)):
                continue

            if not book_url:
                continue
            if not book_url.startswith("http"):
                book_url = "https://product.kyobobook.co.kr" + book_url

            # ebook 제외 (종이책 우선)
            if "ebook" in book_url.lower():
                continue

            # 세트/에디션 상품 제외
            publisher,translator=self._edition_metadata(item)
            exclude_keywords = ["세트", "3종", "2종", "전집", "박스세트"]
            if not is_isbn(keyword) and any(kw in book_name and kw not in keyword for kw in exclude_keywords):
                size=re.search(r'전\s*(\d{1,2})\s*권',item.get_text(' ',strip=True))
                if size and title_score(keyword,re.sub('박스세트|세트|전집','',book_name).strip()):
                    self.series_sizes.append({'publisher':publisher,'translator':translator,'total':int(size.group(1))})
                continue

            score = candidate_score(keyword, book_name, candidate_author, self._expected_author)
            if score:
                score += edition_preference(keyword, book_name) / 10000
            if is_isbn(keyword):
                score = 1.0 if isbn_matches(keyword, structured_isbns(item)) else 0.0
            elif score and self._preferred_isbn and isbn_matches(self._preferred_isbn,structured_isbns(item)):
                score += 10
            if score:
                rating_node=item.select_one(".review_klover_text, .review_score")
                try:
                    observed_rating=float(rating_node.get_text(strip=True)) if rating_node else None
                except ValueError:
                    observed_rating=None
                if observed_rating is not None and not 0 < observed_rating <= 10:
                    observed_rating=None
                count_node=item.select_one(".review_desc")
                count_match=re.search(r"[\d,]+",count_node.get_text()) if count_node else None
                author_id=re.search(r"goClickSearchPage\('chrc',\s*[\"']([^\"']+)",author_node.get("onclick", "")) if author_node else None
                self.discovery_candidates.append({"title":book_name,"url":book_url,"author":candidate_author,
                    "publisher":publisher,"translator":translator,
                    "author_id":author_id.group(1) if author_id else None,"isbn":next(iter(structured_isbns(item)),None),
                    "reviews":int(count_match.group().replace(",","")) if count_match else 0,"score":score,
                    "rating":observed_rating,"count_observed":count_match is not None})
            if score > best_score:
                best_score = score
                best_title = book_name
                best_url = book_url
                score_elem = item.select_one(".review_klover_text, .review_score")
                count_elem = item.select_one(".review_desc")
                try:
                    self._search_rating = float(score_elem.get_text(strip=True)) if score_elem else None
                except ValueError:
                    self._search_rating = None
                count = re.search(r"[\d,]+", count_elem.get_text()) if count_elem else None
                self._search_review_count = int(count.group().replace(",", "")) if count else 0
                # The list does not identify this count as voters vs written
                # reviews. Preserve it as an observed count without relabeling.
                self.count_observed = count is not None
                self._rating_loaded = self._search_rating is not None
                self.book_isbn = next(iter(structured_isbns(item)), None)
                self.book_author = candidate_author or None

        return (best_url, best_title) if best_url else (None, "")

    def _extract_product_id(self, url: str) -> str | None:
        """URL에서 상품 ID 추출 (예: S000061352497)"""
        match = re.search(r"/detail/(\w+)", url)
        return match.group(1) if match else None

    def _fetch_api(self, url: str) -> dict | None:
        """API 호출 헬퍼"""
        try:
            response = fetch_sync(url, {"User-Agent": self.user_agent})
            if response is not None:
                return json.loads(response.text)
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

        if getattr(self, "_search_rating", None) is not None:
            rating = self._search_rating
            if 0 < rating <= 10:
                return rating, self._search_review_count

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
