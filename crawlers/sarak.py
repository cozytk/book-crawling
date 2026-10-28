"""사락 (Yes24 독서 플랫폼) 크롤러"""

import json
import re
import urllib.parse

from bs4 import BeautifulSoup

from .base_http import BaseHttpCrawler
from .utils import title_score, is_isbn, clean_isbn, structured_isbns, isbn_matches, count_number, book_node, valid_rating


class SarakCrawler(BaseHttpCrawler):
    """
    사락 크롤러 (HTTP 기반 + API)

    사락은 Yes24의 독서 커뮤니티 플랫폼.
    Yes24 검색으로 상품 ID를 찾은 후 사락 API에서 평점/리뷰 추출.

    URL 패턴:
    - 상세: https://sarak.yes24.com/reading-note/book/{product_id}

    API:
    - 통계: https://sarak-api.yes24.com/api24/v1/reading-note/book/{id}/book-statistics-summary
    """

    name = "sarak"
    base_url = "https://sarak.yes24.com"
    api_url = "https://sarak-api.yes24.com/api24/v1/reading-note/book"
    yes24_url = "https://www.yes24.com"
    rating_scale = 10  # 사락은 10점 만점

    def _extract_product_id(self, url: str) -> str | None:
        """Yes24 URL에서 상품 ID 추출"""
        # /product/goods/102687133 형식
        match = re.search(r"/(?:product/)?goods/(\d+)", url, re.IGNORECASE)
        if match:
            return match.group(1)
        return None

    def search_by_keyword(self, keyword: str) -> tuple[str | None, str]:
        """
        Yes24에서 검색 후 사락 URL 반환

        1. Yes24 검색으로 상품 ID 획득
        2. 사락 URL 구성: /reading-note/book/{product_id}
        """
        from .yes24 import Yes24Crawler
        identifier = Yes24Crawler()
        identifier.expected_identity(self._expected_title, self._expected_author, self._strict_isbn)
        identifier._fetch_html = self._fetch_html
        url, title = identifier.search_by_keyword(keyword)
        product_id = self._extract_product_id(url or "")
        if not product_id:
            return None, ""
        if not is_isbn(keyword) and not is_isbn(self._original_query or ''):
            # The largest Yes24 written-review population can have very few
            # Sarak votes. Reuse its verified search candidates, but compare
            # this source's own aggregates for at most three eligible books.
            candidates=sorted(getattr(identifier,'_candidate_products',[]),key=lambda c:c['support'],reverse=True)
            unique={}
            for candidate in candidates:
                candidate_id=self._extract_product_id(candidate['url'])
                if candidate_id and candidate_id not in unique:
                    unique[candidate_id]=candidate
                if len(unique)==3:
                    break
            aggregates=[]
            for candidate_id,candidate in unique.items():
                try:
                    data=json.loads(self._fetch_html(f'{self.api_url}/{candidate_id}/book-statistics-summary'))
                    if str(data.get('goodsNo'))!=candidate_id:
                        continue
                    voters=count_number(data.get('userWhoDidVoteThisBookCount'))
                    score=valid_rating(data.get('starPointAverageForBookInfo'),10)
                    if voters is None or score is None or score<=0:
                        continue
                    aggregates.append((voters,count_number(data.get('reviewCount')) or 0,candidate_id,candidate,data))
                except Exception:
                    continue
            for _,_,candidate_id,candidate,data in sorted(aggregates,key=lambda x:(x[0],x[1]),reverse=True):
                try:
                    detail=BeautifulSoup(self._fetch_html(candidate['url']),'html.parser')
                    node=book_node(detail,candidate['title'])
                    if not node or str(node.get('sku',''))!=candidate_id or not identifier.verify_detail(detail,str(node.get('name',''))):
                        continue
                except Exception:
                    continue
                self.book_isbn,self.book_author=identifier.book_isbn,identifier.book_author
                self.rating_count=count_number(data.get('userWhoDidVoteThisBookCount'))
                self.text_review_count=count_number(data.get('reviewCount'))
                self._cached_rating=valid_rating(data.get('starPointAverageForBookInfo'),10)
                self._cached_review_count=self.rating_count
                self._rating_loaded=self.count_observed=True
                from .transport import active_transport
                transport=active_transport()
                if transport:
                    transport.diagnostics.setdefault(self.name,{}).update({'method':'verified_candidate_aggregates',
                        'product_id':candidate_id,'candidates':[{'product_id':a[2],'rating_count':a[0],'text_review_count':a[1]} for a in aggregates]})
                return f'{self.base_url}/reading-note/book/{candidate_id}',str(node['name'])
        self.book_isbn, self.book_author = identifier.book_isbn, identifier.book_author
        return f"{self.base_url}/reading-note/book/{product_id}", title

    def _extract_goods_no(self, url: str) -> str | None:
        """사락 URL에서 상품 번호 추출"""
        match = re.search(r"/book/(\d+)", url)
        return match.group(1) if match else None

    async def get_rating(self, url: str) -> tuple[float | None, int]:
        """
        사락 API에서 평점/평가 참여자 수 추출

        API: /book-statistics-summary
        - starPointAverageForBookInfo: 평점 (10점 만점)
        - userWhoDidVoteThisBookCount: 평가 참여자 수
        """
        if self._rating_loaded:
            return self._cached_rating,self._cached_review_count
        goods_no = self._extract_goods_no(url)
        if not goods_no:
            self.logger.error("extract_goods_no_failed", f"URL: {url}")
            return None, 0

        api_url = f"{self.api_url}/{goods_no}/book-statistics-summary"

        try:
            response = self._fetch_html(api_url)
            data = json.loads(response)

            self.logger.api_response("book-statistics-summary", data)

            rating = data.get("starPointAverageForBookInfo")
            self.rating_count = count_number(data.get("userWhoDidVoteThisBookCount"))
            self.text_review_count = count_number(data.get("reviewCount"))
            review_count = self.rating_count or 0

            # 유효성 검사
            if rating is not None and (rating <= 0 or rating > 10):
                rating = None

            self.logger.rating_complete(rating, review_count, method="api")
            return rating, review_count

        except json.JSONDecodeError:
            self.logger.error("json_decode_error", "API 응답 파싱 실패")
            self.logger.rating_complete(None, 0, method="api")
            return None, 0
        except Exception as e:
            self.logger.error("api_error", str(e))
            self.logger.rating_complete(None, 0, method="api")
            return None, 0
