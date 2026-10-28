import re
from crawlers.transport import active_transport
import urllib.parse

from bs4 import BeautifulSoup

from .base_http import BaseHttpCrawler
from .utils import title_score, is_isbn, clean_isbn, structured_isbns, isbn_matches, count_number, book_node, author_matches, candidate_score, edition_preference


def original_author_for_isbn(isbn, expected_author=None):
    """Resolve a romanized author only from the verified edition's author box."""
    if not isbn or not is_isbn(isbn):
        return None
    crawler = Yes24Crawler()
    url, _ = crawler.search_by_keyword(isbn)
    if not url:
        return None
    soup = BeautifulSoup(crawler._fetch_html(url), "html.parser")
    for area in soup.select("#infoset_authorGrp .author_name"):
        if not re.match(r"\s*저\s*:", area.get_text(" ", strip=True)):
            continue
        name = area.select_one(".lnk_author")
        alias = area.select_one(".name_other")
        if name and alias:
            return alias.get_text(" ", strip=True).strip("() ") or None
    return None


class Yes24Crawler(BaseHttpCrawler):
    """Yes24 크롤러 (HTTP 기반 - 브라우저 불필요)"""

    name = "yes24"
    base_url = "https://www.yes24.com"
    rating_scale = 10

    def search_by_keyword(self, keyword: str) -> tuple[str | None, str]:
        """책 검색 후 가장 관련 있는 결과의 상세 페이지 URL 반환"""
        encoded_query = urllib.parse.quote(keyword)
        search_url = f"https://www.yes24.com/Product/Search?domain=ALL&query={encoded_query}"
        if not is_isbn(keyword):
            search_url += '&order=REVIEW_CNT'

        def identify():
            self._candidate_products=[]
            try:
                html = self._fetch_html(search_url)
            except Exception:
                return None, "", None, None, []
            url, title = self._select_product(keyword, html)
            if url:
                try:
                    detail_url=urllib.parse.urljoin(self.base_url,url)
                    detail_html=self._fetch_html(detail_url)
                    self._selected_detail=(detail_url,detail_html)
                    detail=BeautifulSoup(detail_html, 'html.parser')
                    node=book_node(detail,title)
                    product=re.search(r'/goods/(\d+)',url,re.I)
                    if node:
                        if product and str(node.get('sku',product.group(1)))!=product.group(1):
                            self.failure_status='identity_mismatch'
                            return None,'',None,None,[]
                        if not self.verify_detail(detail,str(node.get('name','')),keyword if is_isbn(keyword) else None):
                            return None,'',None,None,[]
                except Exception:
                    # The rating lookup retries the same verified product;
                    # transport failure remains distinguishable from no match.
                    pass
            return url, title, self.book_isbn, self.book_author, self._candidate_products
        transport = active_transport()
        result = transport.memo(("yes24-product", keyword, self._expected_author), identify) if transport else identify()
        url, title, self.book_isbn, self.book_author, self._candidate_products = result
        self._selected_title = title or None
        self._selected_product = re.search(r"/goods/(\d+)", url or "", re.I).group(1) if url else None
        return url, title

    def _select_product(self, keyword, html):
        self._candidate_products=[]
        soup = BeautifulSoup(html, "html.parser")

        # a.gd_name 클래스로 검색 결과 링크 찾기
        keyword_lower = keyword.lower()
        best_url = None
        best_title = ""
        best_score = 0.0
        best_rank = (0, 0, 0)

        for link in soup.select("a.gd_name"):
            href = link.get("href", "")
            text = link.get_text(strip=True)
            container = link.find_parent("li") or link.parent
            format_node = container.select_one(".info_name .gd_res")
            if not is_isbn(keyword) and format_node and format_node.get_text(strip=True) not in {"[도서]", "[eBook]", "[직수입양서]", "[직수입일서]", "[직수입중서]", "[외서]"}:
                continue
            if format_node and format_node.get_text(strip=True) == "[eBook]" and not is_isbn(keyword):
                continue
            author_node = container.select_one(".info_auth, .authPub .auth, .gd_auth")
            candidate_author = author_node.get_text(" ", strip=True) if author_node else ""
            if not is_isbn(keyword) and self._expected_author and (not candidate_author or not author_matches(self._expected_author, candidate_author)):
                continue
            if not is_isbn(keyword) and re.search(r"원저|원작|각색|편역", candidate_author):
                continue
            if not is_isbn(keyword) and re.search(r'세트|\bset\b',text,re.I) and not re.search(r'세트|\bset\b',keyword,re.I):
                continue

            # 중고서점 제외
            if "UsedShopHub" in href:
                continue

            # /product/goods/ 형식만 허용
            if "/product/goods/" not in href.lower():
                continue

            score = candidate_score(keyword, text, candidate_author, self._expected_author)
            if score:
                score += edition_preference(keyword, text) / 10000
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
            # Native search's member-review total combines written reviews,
            # one-line comments and Sarak stars. Prefer its explicit written
            # subtotals; a combined total is only a fallback ranking hint.
            written=[]
            for row in container.select('.moreRatingLi li'):
                match=re.fullmatch(r'\s*(?:종이책|eBook)\s+리뷰\s*\(([\d,]+)건\)\s*',row.get_text(' ',strip=True))
                if match:
                    written.append(count_number(match.group(1)))
            counter=container.select_one('.rating_rvCount .txC_blue')
            support=sum(n for n in written if n is not None) if written else count_number(counter.get_text()) if counter else 0
            rank=(bool(score),0 if is_isbn(keyword) else support or 0,score)
            if score:
                self._candidate_products.append({'url':urllib.parse.urljoin(self.base_url,href),'title':text,
                    'author':candidate_author,'support':support or 0})
            if score and rank > best_rank:
                best_rank = rank
                best_score = score
                best_url = href
                best_title = text
                self.book_isbn = next(iter(identifiers), None)
                self.book_author = candidate_author or None

        if not best_url:
            return None, ""

        # URL 정규화
        if best_url.startswith("/"):
            best_url = f"https://www.yes24.com{best_url}"

        return best_url, best_title

    async def get_rating(self, url: str) -> tuple[float | None, int]:
        """상세 페이지에서 평점/리뷰수 추출"""
        try:
            cached=getattr(self,'_selected_detail',None)
            html = cached[1] if cached and cached[0]==url else self._fetch_html(url)
        except Exception:
            self.logger.rating_complete(None, 0, method="html")
            return None, 0

        soup = BeautifulSoup(html, "html.parser")

        # 평점 추출 (Yes24는 10점 만점)
        actual = soup.select_one(".gd_titArea .gd_name, h2.gd_name")
        if actual and getattr(self,'_selected_title',None) and not title_score(self._selected_title, actual.get_text(strip=True)):
            self.failure_status = "identity_mismatch"
            return None, 0
        node=book_node(soup,actual.get_text(strip=True) if actual else getattr(self,'_selected_title',None))
        if node:
            selected_product=getattr(self,'_selected_product',None)
            if selected_product and str(node.get('sku',selected_product))!=selected_product:
                self.failure_status='identity_mismatch'
                return None,0
            query=self._original_query if is_isbn(self._original_query or '') else None
            if not self.verify_detail(soup,str(node.get('name','')),query):
                return None,0
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
            self.short_review_count=count_number(counter.get('data-onecomment-count'))
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
