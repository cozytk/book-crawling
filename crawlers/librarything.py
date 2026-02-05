"""LibraryThing HTTP 기반 크롤러 (cloudscraper 사용)"""

import re
import urllib.parse
import cloudscraper
from bs4 import BeautifulSoup

from .base_http import BaseHttpCrawler
from .utils import is_isbn


class LibraryThingCrawler(BaseHttpCrawler):
    """
    LibraryThing 크롤러 (HTTP 기반)

    cloudscraper를 사용하여 Cloudflare 우회.
    """

    name = "librarything"
    base_url = "https://www.librarything.com"
    rating_scale = 5  # LibraryThing은 5점 만점

    def __init__(self):
        super().__init__()
        self._scraper = cloudscraper.create_scraper(
            browser={
                'browser': 'chrome',
                'platform': 'darwin',
                'desktop': True
            }
        )
        # 세션 유지를 위해 홈 페이지 방문 시도 (쿠키 획득)
        try:
            self._scraper.get(self.base_url, timeout=5)
        except: pass
        
        self._cached_rating: float | None = None
        self._cached_review_count: int = 0

    def _fetch_with_scraper(self, url: str) -> tuple[str, str]:
        """cloudscraper로 페이지 가져오기"""
        response = self._scraper.get(url, timeout=15, allow_redirects=True)
        response.raise_for_status()
        return response.text, response.url

    def _fetch_search_results(self, url: str) -> str | None:
        """검색 결과 페이지 HTML 가져오기"""
        try:
            html, _ = self._fetch_with_scraper(url)
            return html
        except Exception:
            return None

    def is_identifier(self, query: str) -> bool:
        """ISBN 형식인지 확인"""
        return is_isbn(query)

    def search_by_identifier(self, identifier: str) -> tuple[str | None, str]:
        """ISBN으로 직접 작품 페이지 접근"""
        clean = identifier.replace("-", "").replace(" ", "")
        url = f"{self.base_url}/isbn/{clean}"

        try:
            html, final_url = self._fetch_with_scraper(url)
            if "/work/" not in str(final_url):
                return None, ""
            
            title, rating, review_count = self._parse_work_page(html)
            if title:
                self._cached_rating = rating
                self._cached_review_count = review_count
                return str(final_url), title
        except Exception:
            pass
        return None, ""

    def search_by_keyword(self, keyword: str) -> tuple[str | None, str]:
        """제목으로 검색"""
        encoded = urllib.parse.quote(keyword)
        
        # 방법 1: /title/ 직접 접근
        title_url = f"{self.base_url}/title/{encoded}"
        try:
            html, final_url = self._fetch_with_scraper(title_url)
            if "/work/" in str(final_url):
                title, rating, review_count = self._parse_work_page(html)
                if title:
                    self._cached_rating = rating
                    self._cached_review_count = review_count
                    return str(final_url), title
        except Exception:
            pass

        # 방법 2: 검색 페이지 시도 (term 파라미터 사용)
        return self._search_via_search_page(keyword)

    def _search_via_search_page(self, keyword: str) -> tuple[str | None, str]:
        """검색 페이지를 통한 검색 및 폴백"""
        encoded = urllib.parse.quote(keyword)
        search_url = f"{self.base_url}/search.php?search={encoded}&searchtype=newwork_titles&sortchoice=0"
        
        html = self._fetch_search_results(search_url)
        link = self._find_link_in_html(html)

        # 결과가 없으면 부제로 재시도
        if not link:
            primary = keyword.split(":")[0].strip()
            if primary != keyword:
                self.logger.debug(f"주제목으로 재시도: {primary}")
                encoded_primary = urllib.parse.quote(primary)
                search_url = f"{self.base_url}/search.php?search={encoded_primary}&searchtype=newwork_titles&sortchoice=0"
                html = self._fetch_search_results(search_url)
                link = self._find_link_in_html(html)

        if link:
            href = link.get("href", "")
            if not href.startswith("http"):
                href = f"{self.base_url}{href}"
            
            try:
                work_html, final_work_url = self._fetch_with_scraper(href)
                title, rating, review_count = self._parse_work_page(work_html)

                if title:
                    self._cached_rating = rating
                    self._cached_review_count = review_count
                    return str(final_work_url), title
            except Exception:
                pass
        
        return None, ""

    def _find_link_in_html(self, html: str | None) -> BeautifulSoup | None:
        """HTML에서 작품 링크 찾기"""
        if not html:
            return None
        soup = BeautifulSoup(html, "html.parser")
        return soup.select_one("td.worktitle a") or soup.select_one('a[href*="/work/"]')

    def _is_title_match(self, query: str, result_title: str) -> bool:
        """제목 일치 여부 확인"""
        q = query.lower().strip()
        t = result_title.lower().strip()
        if q == t or q in t or t in q:
            return True
        
        # 특수문자 제거 후 단어 단위 매칭
        q_words = set(re.sub(r'[:\-]', ' ', q).split())
        t_words = set(re.sub(r'[:\-]', ' ', t).split())
        return bool(q_words and q_words.issubset(t_words))

    def _parse_work_page(self, html: str) -> tuple[str, float | None, int]:
        """작품 페이지 파싱"""
        soup = BeautifulSoup(html, "html.parser")
        title = ""
        h1 = soup.select_one("h1")
        if h1:
            title = h1.get_text(strip=True)

        rating = None
        review_count = 0

        # 평점 추출
        rating_match = re.search(r'\((\d+\.\d+)\)', html)
        if rating_match:
            try:
                rating = float(rating_match.group(1))
            except: pass

        # 리뷰 수 추출
        review_match = re.search(r'>(\d[\d,]*)\s*Reviews</a>', html)
        if review_match:
            review_count = int(review_match.group(1).replace(",", ""))
        return title, rating, review_count

    async def get_rating(self, url: str) -> tuple[float | None, int]:
        """평점 반환 (캐시 사용)"""
        if self._cached_rating is not None or self._cached_review_count > 0:
            self.logger.rating_complete(
                self._cached_rating, self._cached_review_count, method="cloudscraper",
                rating_scale=self.rating_scale
            )
            return self._cached_rating, self._cached_review_count

        try:
            html, _ = self._fetch_with_scraper(url)
            _, rating, review_count = self._parse_work_page(html)
            self.logger.rating_complete(rating, review_count, method="cloudscraper", rating_scale=self.rating_scale)
            return rating, review_count
        except Exception:
            self.logger.rating_complete(None, 0, method="cloudscraper", rating_scale=self.rating_scale)
            return None, 0
