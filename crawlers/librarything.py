"""LibraryThing HTTP 기반 크롤러 (cloudscraper 사용)"""

import base64
import json
import os
import random
import re
import time
import urllib.parse
import urllib.request
import cloudscraper
from bs4 import BeautifulSoup, Tag

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
                'platform': 'linux',
                'desktop': True
            }
        )
        # 세션 유지를 위해 홈 페이지 방문 시도 (쿠키 획득)
        try:
            self._scraper.get(self.base_url, timeout=5)
        except: pass
        
        self._cached_rating: float | None = None
        self._cached_review_count: int = 0

    def _fetch_with_scraper(
        self,
        url: str,
        referer: str | None = None,
        is_xhr: bool = False,
    ) -> tuple[str, str]:
        """cloudscraper로 페이지 가져오기"""
        headers: dict[str, str] = {}
        if referer:
            headers["Referer"] = referer
        if is_xhr:
            headers["X-Requested-With"] = "XMLHttpRequest"

        last_error: Exception | None = None
        for attempt in range(3):
            try:
                response = self._scraper.get(
                    url,
                    timeout=15,
                    allow_redirects=True,
                    headers=headers or None,
                )
                if response.status_code in {429, 503} and attempt < 2:
                    time.sleep(0.8 * (attempt + 1))
                    continue
                response.raise_for_status()
                return response.text, response.url
            except Exception as e:
                last_error = e
                if attempt < 2:
                    time.sleep(0.8 * (attempt + 1))
                    continue
                raise

        if last_error is not None:
            raise last_error
        raise RuntimeError("LibraryThing 요청 실패")

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
        return self._search_via_brave(identifier)

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

    def _get_input_value(self, soup: BeautifulSoup, name: str, default: str = "") -> str:
        """검색 페이지 hidden input 값 추출"""
        input_tag = soup.select_one(f'input[name="{name}"]')
        if input_tag and input_tag.get("value") is not None:
            return str(input_tag.get("value"))
        return default

    def _fetch_ajax_search_results(
        self, keyword: str, search_html: str | None, referer: str
    ) -> str | None:
        """ajax_newsearch.php를 호출해 검색 결과 HTML 조각 반환"""
        if not search_html:
            return None

        try:
            soup = BeautifulSoup(search_html, "html.parser")
            params = {
                "search": keyword,
                "searchtype": "newwork_titles",
                "page": "1",
                "sortchoice": self._get_input_value(soup, "sortchoice", "0"),
                "optionidpotential": self._get_input_value(soup, "optionidpotential", "0"),
                "optionidreal": self._get_input_value(soup, "optionidreal", "0"),
                "randomnumber": str(random.randint(1000, 9999)),
            }
            combinewith = self._get_input_value(soup, "combinewith", "")
            if combinewith:
                params["combinewith"] = combinewith

            ajax_url = f"{self.base_url}/ajax_newsearch.php?{urllib.parse.urlencode(params)}"
            payload_text, _ = self._fetch_with_scraper(
                ajax_url,
                referer=referer,
                is_xhr=True,
            )
            payload = json.loads(payload_text)
            encoded_html = payload.get("text", "")
            if not encoded_html:
                return None
            return base64.b64decode(encoded_html).decode("utf-8", errors="replace")
        except Exception:
            return None

    def _extract_rating_from_search_link(self, link: Tag) -> tuple[float | None, int]:
        """검색 결과 row에서 평점/리뷰 수 추출"""
        container = link.find_parent("tr")
        if container is None:
            container = link.parent
        text = container.get_text(" ", strip=True) if container else ""

        rating = None
        review_count = 0

        rating_match = re.search(r'(\d+(?:\.\d+)?)\s*stars?', text, re.IGNORECASE)
        if rating_match:
            try:
                rating = float(rating_match.group(1))
            except Exception:
                pass

        review_match = re.search(r'([\d,]+)\s*reviews?', text, re.IGNORECASE)
        if review_match:
            review_count = int(review_match.group(1).replace(",", ""))

        return rating, review_count

    def _select_best_link(self, links: list[Tag], query: str) -> Tag | None:
        """제목 매칭 + 리뷰 수 기준으로 최적 링크 선택"""
        if not links:
            return None

        matched = [
            link for link in links
            if self._is_title_match(query, link.get_text(strip=True))
        ]
        pool = matched or links
        return max(pool, key=lambda link: self._extract_rating_from_search_link(link)[1])

    def _search_via_search_page(self, keyword: str) -> tuple[str | None, str]:
        """검색 페이지를 통한 검색 및 폴백"""
        encoded = urllib.parse.quote(keyword)
        search_url = f"{self.base_url}/search.php?term={encoded}&searchtype=newwork_titles&sortchoice=0"
        
        html = self._fetch_search_results(search_url)
        link = self._find_link_in_html(html, keyword)
        if not link:
            ajax_html = self._fetch_ajax_search_results(keyword, html, search_url)
            link = self._find_link_in_html(ajax_html, keyword)

        # 결과가 없으면 부제로 재시도
        if not link:
            primary = keyword.split(":")[0].strip()
            if primary != keyword:
                self.logger.debug(f"주제목으로 재시도: {primary}")
                encoded_primary = urllib.parse.quote(primary)
                search_url = f"{self.base_url}/search.php?term={encoded_primary}&searchtype=newwork_titles&sortchoice=0"
                html = self._fetch_search_results(search_url)
                link = self._find_link_in_html(html, primary)
                if not link:
                    ajax_html = self._fetch_ajax_search_results(primary, html, search_url)
                    link = self._find_link_in_html(ajax_html, primary)

        if link:
            href = link.get("href", "")
            if not href.startswith("http"):
                href = f"{self.base_url}{href}"
            title = link.get_text(strip=True) or keyword
            rating, review_count = self._extract_rating_from_search_link(link)
            self._cached_rating = rating
            self._cached_review_count = review_count
            return href, title

        # Cloudflare 등으로 직접 크롤링이 막히는 환경(Railway)에서 Brave Search 결과 URL로 우회
        return self._search_via_brave(keyword)

    def _search_via_brave(self, keyword: str) -> tuple[str | None, str]:
        """Brave Search API로 LibraryThing work URL 우회 검색"""
        api_key = os.getenv("BRAVE_SEARCH_API_KEY")
        if not api_key:
            return None, ""

        try:
            query = f'site:librarything.com/work "{keyword}"'
            params = urllib.parse.urlencode({"q": query, "count": 5})
            url = f"https://api.search.brave.com/res/v1/web/search?{params}"

            req = urllib.request.Request(url)
            req.add_header("X-Subscription-Token", api_key)
            req.add_header("Accept", "application/json")
            req.add_header("User-Agent", self.user_agent)

            with urllib.request.urlopen(req, timeout=10) as resp:
                payload = json.loads(resp.read().decode("utf-8"))

            results = payload.get("web", {}).get("results", [])
            for item in results:
                work_url = str(item.get("url", ""))
                if "librarything.com/work/" not in work_url:
                    continue

                # /t/ 이하가 붙어도 get_rating에서 다시 fetch 가능한 형태로 정규화
                work_id_match = re.search(r"/work/\d+", work_url)
                if work_id_match:
                    work_url = f"{self.base_url}{work_id_match.group(0)}"

                title = str(item.get("title", "")).replace(" | LibraryThing", "").strip()
                if not title:
                    title = keyword
                return work_url, title
        except Exception:
            return None, ""

        return None, ""

    def _find_link_in_html(self, html: str | None, query: str) -> Tag | None:
        """HTML에서 작품 링크 찾기"""
        if not html:
            return None
        soup = BeautifulSoup(html, "html.parser")

        raw_links = soup.select(
            'p.item a[href*="/work/"], td.worktitle a[href*="/work/"], a[href*="/work/"][data-workid]'
        )
        deduped: list[Tag] = []
        seen_work_ids: set[str] = set()

        for link in raw_links:
            href = str(link.get("href", ""))
            if not href:
                continue
            if any(suffix in href for suffix in ("/members", "/reviews", "/editions")):
                continue

            # 이미지 링크면 같은 row의 제목 링크로 교체
            if not link.get_text(strip=True):
                row = link.find_parent("tr")
                if row:
                    title_link = row.select_one('p.item a[href*="/work/"]')
                    if title_link and title_link.get_text(strip=True):
                        link = title_link
                        href = str(link.get("href", ""))

            work_id_match = re.search(r"/work/\d+", href)
            dedupe_key = work_id_match.group(0) if work_id_match else href
            if dedupe_key in seen_work_ids:
                continue
            seen_work_ids.add(dedupe_key)
            deduped.append(link)

        return self._select_best_link(deduped, query)

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
