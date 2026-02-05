"""HTTP 전용 크롤러 베이스 클래스 - 브라우저 없음"""

import time
import urllib.request

from crawlers.base import BaseCrawler
from models.book import PlatformRating


class BaseHttpCrawler(BaseCrawler):
    """
    HTTP 전용 크롤러 베이스 클래스

    Playwright 브라우저 없이 순수 HTTP 요청으로 크롤링하는 크롤러의 베이스 클래스.
    Yes24처럼 JavaScript 렌더링이 필요 없는 사이트에 적합.

    검색 패턴:
    - 식별자 검색: ISBN, 상품코드 등으로 직접 상세 페이지 접근
    - 키워드 검색: 검색 페이지에서 결과 파싱 후 상세 페이지 접근

    서브클래스는 search_by_identifier()와 search_by_keyword() 중
    지원하는 메서드만 오버라이드하면 됨.

    장점:
    - 메모리 사용량 최소화 (~20MB vs Playwright ~200MB)
    - 빠른 실행 속도 (브라우저 초기화 불필요)
    - 단순한 구조

    단점:
    - JavaScript로 렌더링되는 컨텐츠 접근 불가
    - 복잡한 상호작용 불가
    """

    user_agent: str = "Mozilla/5.0"

    def __init__(self):
        """로거 초기화"""
        super().__init__()

    async def __aenter__(self):
        """async with 진입 - HTTP 크롤러는 별도 초기화 불필요"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """async with 종료 - 정리할 리소스 없음"""
        pass

    async def delay(self, min_sec: float = 0.5, max_sec: float = 1.5) -> None:
        """랜덤 딜레이 (HTTP 크롤러는 더 짧은 기본값)"""
        await super().delay(min_sec, max_sec)

    def _fetch_html(self, url: str) -> str:
        """
        URL에서 HTML 가져오기

        매 요청마다 새로운 opener를 생성하여 세션/쿠키 간섭 방지.
        UTF-8 우선, 실패 시 EUC-KR로 디코딩.
        """
        start = time.perf_counter()
        try:
            opener = urllib.request.build_opener()
            opener.addheaders = [("User-Agent", self.user_agent)]
            response = opener.open(url, timeout=10)
            content = response.read()
            status = response.status
            elapsed_ms = (time.perf_counter() - start) * 1000

            try:
                html = content.decode("utf-8")
            except UnicodeDecodeError:
                html = content.decode("euc-kr", errors="replace")

            self.logger.http_request(
                method="GET",
                url=url,
                status=status,
                elapsed_ms=elapsed_ms,
                size=len(content),
                response_body=html,
            )
            return html

        except Exception as e:
            elapsed_ms = (time.perf_counter() - start) * 1000
            self.logger.http_error("GET", url, str(e), elapsed_ms)
            raise

    # === 선택적 구현 메서드 ===

    def is_identifier(self, query: str) -> bool:
        """
        쿼리가 식별자(ISBN, 상품코드 등)인지 판별

        서브클래스에서 오버라이드하여 식별자 패턴 정의.
        예: ISBN-10/13, 상품코드 등

        Args:
            query: 검색어

        Returns:
            True if identifier, False if keyword (기본값)
        """
        return False

    def search_by_identifier(self, identifier: str) -> tuple[str | None, str]:
        """
        식별자로 직접 상세 페이지 접근

        ISBN이나 상품코드 등 고유 식별자로 직접 상세 페이지에 접근.
        검색 과정 없이 1회 요청으로 결과 획득.

        Args:
            identifier: 식별자 (ISBN, 상품코드 등)

        Returns:
            (book_url, book_title) 또는 (None, "") if not found

        Raises:
            NotImplementedError: 식별자 검색을 지원하지 않는 경우
        """
        raise NotImplementedError(f"{self.name}은 식별자 검색을 지원하지 않습니다")

    def search_by_keyword(self, keyword: str) -> tuple[str | None, str]:
        """
        키워드로 검색 후 결과에서 최적 매칭 선택

        검색 페이지에서 결과를 파싱하여 가장 적합한 책 선택.

        Args:
            keyword: 검색어 (책 제목, 저자명 등)

        Returns:
            (book_url, book_title) 또는 (None, "") if not found

        Raises:
            NotImplementedError: 키워드 검색을 지원하지 않는 경우
        """
        raise NotImplementedError(f"{self.name}은 키워드 검색을 지원하지 않습니다")

    # === 자동 라우팅 (기본 구현) ===

    async def search_book(self, query: str) -> tuple[str | None, str]:
        """
        쿼리 타입에 따라 적절한 검색 메서드 호출

        1. is_identifier() == True → search_by_identifier() 시도
        2. 실패 시 또는 결과 없으면 → search_by_keyword() 폴백

        Args:
            query: 검색어 (책 제목 또는 ISBN)

        Returns:
            (book_url, book_title) 또는 (None, "") if not found
        """
        self.logger.search_start(
            query,
            session_id=self._session_id,
            original_query=self._original_query,
            attempt=self._current_attempt,
        )

        if self.is_identifier(query):
            try:
                result = self.search_by_identifier(query)
                if result[0]:
                    self.logger.search_complete(
                        query, found=True, title=result[1], method="identifier",
                        session_id=self._session_id,
                        original_query=self._original_query,
                        attempt=self._current_attempt,
                    )
                    return result
                # ISBN 검색 실패 시 키워드로 폴백하지 않음 (ISBN은 특정 판본)
                self.logger.search_complete(
                    query, found=False, method="identifier",
                    session_id=self._session_id,
                    original_query=self._original_query,
                    attempt=self._current_attempt,
                )
                return result
            except NotImplementedError:
                pass  # 식별자 검색 미지원 시 키워드로 폴백

        result = self.search_by_keyword(query)
        if result[0]:
            self.logger.search_complete(
                query, found=True, title=result[1], method="keyword",
                session_id=self._session_id,
                original_query=self._original_query,
                attempt=self._current_attempt,
            )
        else:
            self.logger.search_complete(
                query, found=False, method="keyword",
                session_id=self._session_id,
                original_query=self._original_query,
                attempt=self._current_attempt,
            )
        return result

    async def crawl(self, query: str, attempt: int = 1) -> PlatformRating | None:
        """
        책 검색부터 평점 추출까지 전체 플로우

        Args:
            query: 검색어
            attempt: 시도 번호 (1=최초, 2=재시도)

        Returns:
            PlatformRating 또는 None if not found
        """
        self._current_attempt = attempt
        start = time.perf_counter()
        try:
            book_url, book_title = await self.search_book(query)

            if not book_url:
                elapsed_ms = (time.perf_counter() - start) * 1000
                self.logger.crawl_complete(
                    query, success=False, elapsed_ms=elapsed_ms,
                    session_id=self._session_id,
                    original_query=self._original_query,
                    attempt=attempt,
                )
                return None

            await self.delay()
            rating, review_count = await self.get_rating(book_url)

            elapsed_ms = (time.perf_counter() - start) * 1000
            self.logger.crawl_complete(
                query,
                success=True,
                elapsed_ms=elapsed_ms,
                title=book_title,
                rating=rating,
                review_count=review_count,
                session_id=self._session_id,
                original_query=self._original_query,
                attempt=attempt,
            )

            return PlatformRating(
                platform=self.name,
                rating=rating,
                rating_scale=self.rating_scale,
                review_count=review_count,
                url=book_url,
                book_title=book_title,
            )
        except Exception as e:
            elapsed_ms = (time.perf_counter() - start) * 1000
            self.logger.error("crawl_failed", str(e), {"query": query})
            self.logger.crawl_complete(
                query, success=False, elapsed_ms=elapsed_ms,
                session_id=self._session_id,
                original_query=self._original_query,
                attempt=attempt,
            )
            return None
