import asyncio
import random
from abc import ABC, abstractmethod

from playwright.async_api import Page, async_playwright, Browser

from models.book import PlatformRating


class BasePlatformCrawler(ABC):
    """플랫폼 크롤러 베이스 클래스"""

    name: str = "base"
    base_url: str = ""
    rating_scale: int = 10  # 기본 만점 기준

    def __init__(self):
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

    async def delay(self, min_sec: float = 1.0, max_sec: float = 3.0) -> None:
        """랜덤 딜레이"""
        await asyncio.sleep(random.uniform(min_sec, max_sec))

    @abstractmethod
    async def search_book(self, query: str) -> tuple[str | None, str]:
        """
        책 검색 후 상세 페이지 URL 반환

        Args:
            query: 검색어 (책 제목 또는 ISBN)

        Returns:
            (book_url, book_title) 또는 (None, "") if not found
        """
        pass

    @abstractmethod
    async def get_rating(self, url: str) -> tuple[float | None, int]:
        """
        상세 페이지에서 평점/리뷰수 추출

        Args:
            url: 책 상세 페이지 URL

        Returns:
            (rating, review_count)
        """
        pass

    async def crawl(self, query: str) -> PlatformRating | None:
        """
        책 검색부터 평점 추출까지 전체 플로우

        Args:
            query: 검색어

        Returns:
            PlatformRating 또는 None if not found
        """
        try:
            book_url, book_title = await self.search_book(query)

            if not book_url:
                print(f"[{self.name}] 검색 결과 없음: {query}")
                return None

            await self.delay()
            rating, review_count = await self.get_rating(book_url)

            return PlatformRating(
                platform=self.name,
                rating=rating,
                rating_scale=self.rating_scale,
                review_count=review_count,
                url=book_url,
                book_title=book_title,
            )
        except Exception as e:
            print(f"[{self.name}] 크롤링 실패: {e}")
            return None
