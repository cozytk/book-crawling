"""해외 플랫폼 검색어 해석기

한국어 검색어를 해외 플랫폼에서 사용할 수 있는 원서 제목과 ISBN으로 변환합니다.

변환 흐름:
1. 알라딘 API에서 원서 제목 조회
2. 원서 제목 없으면 ISBN/한국어 제목으로 외부 API 조회
3. 원서 ISBN 확보 → 해외 플랫폼에서 직접 접근
4. ISBN 없으면 원서 제목으로 키워드 검색
"""

from dataclasses import dataclass
import asyncio
import re

from crawler_logging import CrawlerLogger
from crawlers.aladin import AladinCrawler
from crawlers.isbn_lookup import ISBNLookup
from crawlers.utils import is_isbn, clean_isbn
from crawlers.transport import run_parser
from crawlers.yes24 import original_author_for_isbn
from crawlers.work_identity import work_identity

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
    author: str | list[str] | None = None
    related_isbns: tuple[str, ...] = ()

    @property
    def available(self) -> bool:
        """해외 플랫폼 검색 가능 여부"""
        return self.query is not None or self.isbn is not None


def _is_korean(text: str) -> bool:
    """한글이 포함되어 있는지 확인"""
    return any("\uac00" <= c <= "\ud7a3" for c in text)


async def _get_original_info(query: str) -> dict | None:
    """알라딘 API로 원서 정보(제목, 저자, isbn13) 조회"""
    async with AladinCrawler() as crawler:
        await crawler.search_book(query)
        return await crawler.get_original_title_info()


async def resolve_foreign_query(korean_query: str) -> ForeignQuery:
    # Providers use blocking HTTP. Isolate them from the ASGI event loop.
    result, _ = await run_parser(lambda: asyncio.run(_resolve_foreign_query(korean_query)))
    return result


async def _resolve_foreign_query(korean_query: str) -> ForeignQuery:
    """
    한국어 검색어를 해외 플랫폼 검색 정보로 변환

    Args:
        korean_query: 한국어 책 제목

    Returns:
        ForeignQuery (query=None이면 해외 플랫폼 검색 불가)
    """
    if is_isbn(korean_query):
        isbn = clean_isbn(korean_query)
        return ForeignQuery(query=isbn, isbn=isbn)
    identity = work_identity(korean_query)
    info = await _get_original_info(identity.isbn or korean_query)
    if not info:
        lookup = ISBNLookup()
        roman_author = None
        if identity.isbn:
            try:
                roman_author = original_author_for_isbn(identity.isbn, identity.author)
                original = lookup.find_original(isbn=identity.isbn)
                if original:
                    return ForeignQuery(query=original["title"],isbn=original.get("isbn"),
                                        author=original.get("authors") or roman_author,
                                        related_isbns=original.get("related_isbns", ()))
            except Exception:
                pass
        if not _is_korean(korean_query):
            candidate = lookup.search(korean_query, roman_author)
            return ForeignQuery(query=(candidate.english_title or candidate.title) if candidate else korean_query,
                                isbn=(candidate.english_isbn or candidate.isbn) if candidate else None,
                                author=candidate.authors if candidate else None,
                                related_isbns=candidate.related_isbns if candidate else ())
        return ForeignQuery()

    original_title = info.get("title")
    original_author = info.get("author")
    isbn13 = info.get("isbn13")
    lookup = ISBNLookup()
    # Author names copied from the verified Korean edition provide a query in
    # the original script. Never take an unrelated first shop/search result.
    try:
        original_author = original_author_for_isbn(isbn13, original_author) or original_author
    except Exception:
        pass

    if original_title:
        # 알라딘에 원서 제목 있음 → 원서 제목으로 ISBN 조회
        primary = re.split(r"[:：]", original_title, maxsplit=1)[0].strip()
        # The author is verified from the selected ISBN. Try the main title
        # first so descriptive subtitles do not add two failed catalog calls.
        first_title=primary if original_author else original_title
        candidate = lookup.search(first_title, original_author)
        # A verified edition supplies the original title and writer. Its
        # descriptive subtitle is not required on another edition of that work.
        if not candidate and first_title != original_title:
            candidate = lookup.search(original_title, original_author)
        # The original title may be a translation not indexed by the search
        # catalog (e.g. French title of a Czech work). A verified local ISBN
        # can still establish the Edition -> Work connection.
        if not candidate and isbn13:
            original=lookup.find_original(isbn=isbn13)
            if original and original.get('isbn') and not _is_korean(original.get('title','')):
                return ForeignQuery(query=original['title'],isbn=original['isbn'],
                    author=original.get('authors') or re.split(r'[,、，]',original_author or ''),
                    related_isbns=original.get('related_isbns',()))
        foreign_isbn = (candidate.english_isbn or candidate.isbn) if candidate else None
        if foreign_isbn:
            logger.debug(f"원서 연결: {original_title} → ISBN {foreign_isbn}")
        else:
            logger.debug(f"원서 연결 (ISBN 없음): {original_title}")
        query = re.split(r"\s[-–—]\s|[:：]|\s/\s", (candidate.english_title or candidate.title) if candidate else primary,maxsplit=1)[0].strip()
        return ForeignQuery(query=query, isbn=foreign_isbn,
                            author=candidate.authors if candidate else re.split(r"[,、，]", original_author or ""),
                            related_isbns=candidate.related_isbns if candidate else ())

    if isbn13:
        # 원서 제목 없음 → 외부 API에서 원서 정보 조회
        original = lookup.find_original(isbn=isbn13, korean_title=korean_query)
        if original:
            authors = original.get("authors", [])
            query = original["title"]
            isbn = original.get("isbn") or lookup.get_isbn(original["title"])
            if isbn:
                logger.debug(f"원서 연결: {query} → ISBN {isbn}")
            else:
                logger.debug(f"원서 연결 (ISBN 없음): {query}")
            return ForeignQuery(query=query, isbn=isbn, author=authors or original_author,
                                related_isbns=original.get("related_isbns", ()))

    return ForeignQuery()
