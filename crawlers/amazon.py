from crawlers.transport import fetch_sync, active_transport
"""Amazon Books HTTP 기반 크롤러"""

import json
import re
import urllib.parse
import urllib.request

from bs4 import BeautifulSoup

from .base_http import BaseHttpCrawler
from .utils import is_isbn, title_score, book_node, valid_rating, count_number, isbn13, isbn_matches, author_matches, structured_isbns


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
        self._verified_product = None

    def _fetch_with_headers(self, url: str, extra_headers=None) -> str:
        """
        Amazon 페이지 가져오기 (브라우저와 유사한 헤더 포함)
        """
        response = fetch_sync(url, {"User-Agent": self.user_agent, "Accept-Language": "en-US,en;q=0.9",
            "Accept":"text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8", **(extra_headers or {})})
        if response is not None:
            transport=active_transport()
            if transport:
                soup=BeautifulSoup(response.text,"html.parser")
                transport.diagnostics.setdefault(self.name,{})["page_title"]=soup.title.get_text(strip=True) if soup.title else None
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
        headers.update(extra_headers or {})
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

    @staticmethod
    def _star_value(text):
        match=re.search(r"(\d+(?:\.\d+)?)\s*out of\s*5\s*stars?",text,re.I)
        if not match:
            match=re.search(r"별\s*5개\s*중\s*(\d+(?:\.\d+)?)",text)
        return valid_rating(match.group(1),5) if match else None

    def _card_rating(self, card, asin):
        area=card.select_one('[data-cy="reviews-block"]') or card
        popover=area.select_one('[data-a-popover]')
        if popover:
            try:
                url=json.loads(popover['data-a-popover']).get('url','')
                linked=urllib.parse.parse_qs(urllib.parse.urlsplit(url).query).get('asin',[asin])[0]
                if linked!=asin:
                    return None,None,None,None
            except (ValueError,TypeError):
                return None,None,None,None
        score=next((value for node in area.select('.a-icon-alt, [aria-label]')
                    if (value:=self._star_value(node.get('aria-label','')+' '+node.get_text(' ',strip=True))) is not None),None)
        voters=written=display=None
        for node in area.select('a[aria-label], a[href*="customerReviews"], a[href*="product-reviews"]'):
            label=node.get('aria-label','')
            match=re.fullmatch(r'\s*([\d,]+)\s*(?:global\s+)?(?:ratings?|개\s*평가)\s*',label,re.I)
            if match:
                voters=count_number(match.group(1))
                break
            match=re.fullmatch(r'\s*([\d,]+)\s*(?:customer\s+)?reviews?\s*',label,re.I)
            if match:
                written=count_number(match.group(1))
            text=node.get_text(' ',strip=True).strip('() ')
            if re.fullmatch(r'[\d,]+',text):
                display=count_number(text)
        return score,voters,written,display

    def _verify_product(self, html, title, query):
        soup=BeautifulSoup(html,'html.parser')
        # Native ISBN rows are explicit product fields, not global page text.
        for row in soup.select('#detailBullets_feature_div li, #productDetails_detailBullets_sections1 tr, #productDetailsTable tr'):
            text=row.get_text(' ',strip=True)
            if re.search(r'ISBN\s*[-–]?\s*1[03]',text,re.I):
                text=re.split(r'ISBN\s*[-–]?\s*1[03]',text,maxsplit=1,flags=re.I)[-1]
                match=re.search(r'(?<!\d)(?:97[89][-\d ]{10,16}|[\d-]{9,12}[\dX])(?!\d)',text)
                if match:
                    row['data-isbn']=match.group(0).strip()
        expected=self._expected_title
        if is_isbn(query or '') and isbn_matches(query,structured_isbns(soup)):
            self._expected_title=None  # Explicit product ISBN proves translated titles too.
        try:
            verified=self.verify_detail(soup,title,query,allow_product=True)
        finally:
            self._expected_title=expected
        if verified:
            identifiers=[isbn13(value) for value in structured_isbns(soup) if is_isbn(str(value))]
            self.book_isbn=next((value for value in identifiers if value==isbn13(query)),None) or next(iter(identifiers),None)
        return verified

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

        # The public rating popover omits title/author. Use it only after the
        # service has matched a separately verified product to the current work.
        product_identity = self._verified_product
        if product_identity and product_identity.get('url') == url:
            title = product_identity.get('title', '')
            author = product_identity.get('source_author', '')
            if (title_score(self._expected_title, title)
                    and self._expected_author and author_matches(self._expected_author, author)):
                try:
                    widget = f'{self.base_url}/review/widgets/average-customer-review/popover/ref=acr_search__popover?ie=UTF8&asin={clean}&ref=acr_search__popover&contextId=search'
                    html = self._fetch_with_headers(widget, {'X-Requested-With': 'XMLHttpRequest', 'Referer': url})
                    aggregate = self._parse_verified_popover(html, clean)
                    if aggregate:
                        self._cached_rating, self.rating_count = aggregate
                        self._cached_review_count = self.rating_count
                        self.book_author = author
                        self._rating_loaded = self.count_observed = True
                        transport = active_transport()
                        if transport:
                            transport.diagnostics.setdefault(self.name, {})['method'] = 'verified_product_popover'
                        return url, title
                except Exception:
                    pass

        try:
            html = self._fetch_with_headers(url)
        except Exception:
            return None, ""

        title, rating, review_count = self._parse_detail_page(html)
        product = BeautifulSoup(html,"html.parser").select_one('input#ASIN, input[name="ASIN"]')
        if product and product.get('value','').upper()!=clean.upper():
            # Amazon can render an audiobook/default child while retaining
            # the print ISBN in the edition details. Its stars are not the
            # selected product's aggregate.
            self.failure_status='identity_mismatch'
            return None,''
        if title and self._verify_product(html, title, identifier):
            if not is_isbn(identifier):
                if not product or product.get("value", "").upper() != clean.upper():
                    return None, ""
            self._rating_loaded = True
            self._cached_rating = rating
            self._cached_review_count = review_count
            return url, title

        return None, ""

    @staticmethod
    def _parse_verified_popover(html, asin):
        soup = BeautifulSoup(html, 'html.parser')
        # Bind the aggregate to all of the widget's own product/review links;
        # percentages in its star histogram are not participant counts.
        linked = []
        for anchor in soup.select('a[href]'):
            parsed = urllib.parse.urlsplit(urllib.parse.urljoin('https://www.amazon.com', anchor['href']))
            match = re.search(r'/(?:dp|product-reviews|portal/customer-reviews)/([A-Z0-9]{10})(?:/|$)', parsed.path, re.I)
            if match:
                if parsed.hostname != 'www.amazon.com':
                    return None
                linked.append(match.group(1).upper())
        if not linked or any(value != asin.upper() for value in linked):
            return None
        score_node = soup.select_one('[data-hook="acr-average-stars-rating-text"]')
        count_node = soup.select_one('[data-hook="total-review-count"]')
        score = AmazonCrawler._star_value(score_node.get_text(' ', strip=True)) if score_node else None
        count = re.fullmatch(r'\s*([\d,]+)\s+global\s+ratings?\s*', count_node.get_text(' ', strip=True), re.I) if count_node else None
        if score is None or not count:
            return None
        return score, count_number(count.group(1))

    def search_by_keyword(self, keyword: str) -> tuple[str | None, str]:
        """
        키워드로 Amazon Books 검색

        https://www.amazon.com/s?k={keyword}&i=stripbooks-intl-ship 형식으로 검색.
        """
        encoded = urllib.parse.quote(keyword)
        search_url = f"https://www.amazon.com/s?k={encoded}&i=stripbooks&language=en_US"

        try:
            html = self._fetch_with_headers(search_url)
        except Exception:
            return None, ""

        soup = BeautifulSoup(html, "html.parser")
        transport=active_transport()
        if transport:
            transport.diagnostics.setdefault(self.name,{})['query']=keyword

        # 검색 결과에서 첫 번째 책 찾기
        # 방법 1: data-asin 속성이 있는 검색 결과
        candidates = soup.select('[data-component-type="s-search-result"]')
        if transport:
            transport.diagnostics[self.name]['candidates']=[{'asin':row.get('data-asin'),
                'title':row.select_one('h2').get_text(' ',strip=True) if row.select_one('h2') else '',
                'author':row.select_one('[data-cy="title-recipe"] .a-row, .a-row.a-size-base.a-color-secondary').get_text(' ',strip=True) if row.select_one('[data-cy="title-recipe"] .a-row, .a-row.a-size-base.a-color-secondary') else ''}
                for row in candidates[:6]]
        def rank_card(row):
            heading=row.select_one('h2')
            title_match=title_score(keyword,heading.get_text(' ',strip=True) if heading else '')
            byline=row.select_one('[data-cy="title-recipe"] .a-row:not(.a-size-medium), .a-row.a-size-base.a-color-secondary')
            author_ok=not self._expected_author or bool(byline and author_matches(self._expected_author,byline.get_text(' ',strip=True)))
            if not title_match or not author_ok:
                return (0,0,0,0)
            score,voters,written,display=self._card_rating(row,row.get('data-asin',''))
            return (1,score is not None,voters or written or display or 0,title_match)
        candidates.sort(key=rank_card,reverse=True)
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
            selected_format = re.split(r"Other formats?\s*:", text, maxsplit=1, flags=re.I)[0]
            primary_format=result.select_one('[data-cy="price-recipe"] a.a-text-bold')
            if primary_format:
                selected_format=primary_format.get_text(' ',strip=True)
            if not is_isbn(keyword) and re.search(r"\b(?:Audiobook|Audible)\b|오디오북", selected_format, re.I) and not re.search(r"audio|audible|오디오북", keyword, re.I):
                continue
            # Explicit byline on modern search cards; detail is still verified.
            byline = result.select_one('[data-cy="title-recipe"] .a-row:not(.a-size-medium), .a-row.a-size-base.a-color-secondary')
            if self._expected_author and byline and not author_matches(self._expected_author, byline.get_text(" ", strip=True)):
                continue
            if is_isbn(keyword):
                if not (is_isbn(asin) and isbn13(asin) == isbn13(keyword)):
                    if str(keyword).startswith("979"):
                        try:
                            detail_html = self._fetch_with_headers(f"https://www.amazon.com/dp/{asin}")
                            detail_title, detail_rating, detail_count = self._parse_detail_page(detail_html)
                            if self._verify_product(detail_html, detail_title, keyword):
                                self._cached_rating, self._cached_review_count = detail_rating, detail_count
                                self._rating_loaded = True
                                return f"https://www.amazon.com/dp/{asin}", detail_title
                        except Exception:
                            pass
                    continue
            elif not title_score(keyword, title):
                continue
            book_url = f"https://www.amazon.com/dp/{asin}"

            score,voters,written,display=self._card_rating(result,asin)
            verified=not self._expected_author or bool(byline and author_matches(self._expected_author,byline.get_text(' ',strip=True)))
            self._cached_rating=score if verified else None
            self.rating_count=voters if verified else None
            self.text_review_count=written if verified else None
            self._cached_review_count=voters if voters is not None else written if written is not None else display
            self.count_observed=verified and self._cached_review_count is not None
            if verified and byline:
                self.book_author=byline.get_text(' ',strip=True)
            if is_isbn(asin):
                self.book_isbn=isbn13(asin)
            if transport:
                transport.diagnostics[self.name].update({'asin':asin,'method':'verified_search_card' if verified and score is not None else 'detail_required'})
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
        if not self._verify_product(html, title, expected):
            return None, 0
        self._rating_loaded = True
        self.logger.rating_complete(rating, review_count, method="json-ld", rating_scale=self.rating_scale)
        return rating, review_count
