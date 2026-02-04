"""HTTP 전용 크롤러 베이스 클래스 - 브라우저 없음"""

import asyncio
import random
import urllib.request
from abc import ABC, abstractmethod

from models.book import PlatformRating


class BaseHttpCrawler(ABC):
    """
    HTTP 전용 크롤러 베이스 클래스

    Playwright 브라우저 없이 순수 HTTP 요청으로 크롤링하는 크롤러의 베이스 클래스.
    Yes24처럼 JavaScript 렌더링이 필요 없는 사이트에 적합.

    장점:
    - 메모리 사용량 최소화 (~20MB vs Playwright ~200MB)
    - 빠른 실행 속도 (브라우저 초기화 불필요)
    - 단순한 구조

    단점:
    - JavaScript로 렌더링되는 컨텐츠 접근 불가
    - 복잡한 상호작용 불가
    """

    name: str = "base_http"
    base_url: str = ""
    rating_scale: int = 10
    user_agent: str = "Mozilla/5.0"

    async def __aenter__(self):
        """async with 진입 - HTTP 크롤러는 별도 초기화 불필요"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """async with 종료 - 정리할 리소스 없음"""
        pass

    def _fetch_html(self, url: str) -> str:
        """
        URL에서 HTML 가져오기

        매 요청마다 새로운 opener를 생성하여 세션/쿠키 간섭 방지.
        UTF-8 우선, 실패 시 EUC-KR로 디코딩.
        """
        opener = urllib.request.build_opener()
        opener.addheaders = [("User-Agent", self.user_agent)]
        response = opener.open(url, timeout=10)
        content = response.read()

        try:
            return content.decode("utf-8")
        except UnicodeDecodeError:
            return content.decode("euc-kr", errors="replace")

    async def delay(self, min_sec: float = 0.5, max_sec: float = 1.5) -> None:
        """랜덤 딜레이 (HTTP 크롤러는 더 짧은 기본값)"""
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
