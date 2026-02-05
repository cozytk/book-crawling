import asyncio
import random
import time
from abc import ABC, abstractmethod

from playwright.async_api import Page, async_playwright, Browser

from crawler_logging import CrawlerLogger
from models.book import PlatformRating


class BaseCrawler(ABC):
    """모든 크롤러의 공통 베이스 클래스

    세션 관리, 로깅, 딜레이 등 플랫폼 무관 공통 기능 제공.
    서브클래스: BasePlatformCrawler (Playwright), BaseHttpCrawler (HTTP)
    """

    name: str = "base"
    base_url: str = ""
    rating_scale: int = 10

    def __init__(self):
        self.logger = CrawlerLogger(self.name)
        self._session_id: str | None = None
        self._original_query: str | None = None
        self._current_attempt: int = 1

    def set_session(self, session_id: str, original_query: str, execution_id: str | None = None) -> None:
        """크롤링 세션 정보 설정"""
        self._session_id = session_id
        self._original_query = original_query
        if execution_id:
            self.logger.set_execution_id(execution_id)

    async def delay(self, min_sec: float = 1.0, max_sec: float = 3.0) -> None:
        """랜덤 딜레이"""
        await asyncio.sleep(random.uniform(min_sec, max_sec))

    @abstractmethod
    async def search_book(self, query: str) -> tuple[str | None, str]:
        """책 검색 후 상세 페이지 URL 반환"""
        pass

    @abstractmethod
    async def get_rating(self, url: str) -> tuple[float | None, int]:
        """상세 페이지에서 평점/리뷰수 추출"""
        pass

    @abstractmethod
    async def crawl(self, query: str, attempt: int = 1) -> PlatformRating | None:
        """책 검색부터 평점 추출까지 전체 플로우"""
        pass


class BasePlatformCrawler(BaseCrawler):
    """Playwright 기반 크롤러 베이스 클래스"""

    def __init__(self):
        super().__init__()
        self._playwright = None
        self._browser: Browser | None = None
        self._page: Page | None = None

    async def __aenter__(self):
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(headless=True)
        self._page = await self._browser.new_page()
        await self._page.set_extra_http_headers(
            {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._page:
            await self._page.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

    @property
    def page(self) -> Page:
        if self._page is None:
            raise RuntimeError("Crawler not initialized. Use async with.")
        return self._page

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
            self.logger.search_start(
                query,
                session_id=self._session_id,
                original_query=self._original_query,
                attempt=attempt,
            )
            book_url, book_title = await self.search_book(query)

            if not book_url:
                elapsed_ms = (time.perf_counter() - start) * 1000
                self.logger.search_complete(
                    query, found=False, method="playwright",
                    session_id=self._session_id,
                    original_query=self._original_query,
                    attempt=attempt,
                )
                self.logger.crawl_complete(
                    query, success=False, elapsed_ms=elapsed_ms,
                    session_id=self._session_id,
                    original_query=self._original_query,
                    attempt=attempt,
                )
                return None

            self.logger.search_complete(
                query, found=True, title=book_title, method="playwright",
                session_id=self._session_id,
                original_query=self._original_query,
                attempt=attempt,
            )

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
