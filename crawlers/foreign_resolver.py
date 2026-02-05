"""해외 플랫폼 검색어 해석기

한국어 검색어를 해외 플랫폼에서 사용할 수 있는 원서 제목과 ISBN으로 변환합니다.

변환 흐름:
1. 알라딘 API에서 원서 제목 조회
2. 원서 제목 없으면 ISBN/한국어 제목으로 외부 API 조회
3. 원서 ISBN 확보 → 해외 플랫폼에서 직접 접근
4. ISBN 없으면 원서 제목으로 키워드 검색
"""

from dataclasses import dataclass

from crawler_logging import CrawlerLogger
from crawlers.aladin import AladinCrawler
from crawlers.isbn_lookup import ISBNLookup

logger = CrawlerLogger("foreign_resolver")


@dataclass
class ForeignQuery:
    """해외 플랫폼 검색 정보

    Attributes:
        query: 키워드 검색어 (원서 제목 + 저자). None이면 해외 플랫폼 건너뛰기.
        isbn: ISBN (직접 상세페이지 접근용). None이면 키워드 검색만.
    """
    query: str | None = None
    isbn: str | None = None

    @property
    def available(self) -> bool:
        """해외 플랫폼 검색 가능 여부"""
        return self.query is not None


def _is_korean(text: str) -> bool:
    """한글이 포함되어 있는지 확인"""
    return any("\uac00" <= c <= "\ud7a3" for c in text)


async def _get_original_info(query: str) -> dict | None:
    """알라딘 API로 원서 정보(제목, 저자, isbn13) 조회"""
    async with AladinCrawler() as crawler:
        await crawler.search_book(query)
        return await crawler.get_original_title_info()


async def resolve_foreign_query(korean_query: str) -> ForeignQuery:
    """
    한국어 검색어를 해외 플랫폼 검색 정보로 변환

    Args:
        korean_query: 한국어 책 제목

    Returns:
        ForeignQuery (query=None이면 해외 플랫폼 검색 불가)
    """
    if not _is_korean(korean_query):
        # 영문 검색어는 그대로 사용
        return ForeignQuery(query=korean_query)

    info = await _get_original_info(korean_query)
    if not info:
        return ForeignQuery()

    original_title = info.get("title")
    original_author = info.get("author")
    isbn13 = info.get("isbn13")
    lookup = ISBNLookup()

    if original_title:
        # 알라딘에 원서 제목 있음 → 원서 제목으로 ISBN 조회
        foreign_isbn = lookup.get_isbn(original_title, original_author)
        if foreign_isbn:
            logger.debug(f"원서 연결: {original_title} → ISBN {foreign_isbn}")
        else:
            logger.debug(f"원서 연결 (ISBN 없음): {original_title}")
        return ForeignQuery(query=original_title, isbn=foreign_isbn)

    if isbn13:
        # 원서 제목 없음 → 외부 API에서 원서 정보 조회
        original = lookup.find_original(isbn=isbn13, korean_title=korean_query)
        if original:
            authors = original.get("authors", [])
            query = f"{original['title']} {authors[0]}" if authors else original["title"]
            isbn = original.get("isbn") or lookup.get_isbn(original["title"])
            if isbn:
                logger.debug(f"원서 연결: {query} → ISBN {isbn}")
            else:
                logger.debug(f"원서 연결 (ISBN 없음): {query}")
            return ForeignQuery(query=query, isbn=isbn)

    return ForeignQuery()
