"""ISBN 조회 모듈 - 원서 제목으로 ISBN 검색

확장 가능한 구조:
- ISBNProvider: 추상 기본 클래스
- GoogleBooksProvider: Google Books API
- OpenLibraryProvider: Open Library API (무료, 키 불필요)

사용 예:
    lookup = ISBNLookup()
    isbn = lookup.get_isbn("Siddhartha", "Hermann Hesse")
"""

import difflib
import json
import os
import urllib.parse
import urllib.request
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class ISBNResult:
    """ISBN 조회 결과"""

    isbn: str
    title: str
    authors: list[str]
    provider: str

    @property
    def isbn_13(self) -> str | None:
        """ISBN-13 반환 (13자리인 경우)"""
        return self.isbn if len(self.isbn) == 13 else None

    @property
    def isbn_10(self) -> str | None:
        """ISBN-10 반환 (10자리인 경우)"""
        return self.isbn if len(self.isbn) == 10 else None


class ISBNProvider(ABC):
    """ISBN 조회 프로바이더 추상 클래스"""

    name: str = "base"
    timeout: int = 10

    @abstractmethod
    def search(self, title: str, author: str | None = None) -> ISBNResult | None:
        """
        제목과 저자로 ISBN 검색

        Args:
            title: 책 제목
            author: 저자명 (선택)

        Returns:
            ISBNResult 또는 None
        """
        pass

    def _build_query(self, title: str, author: str | None = None) -> str:
        """검색 쿼리 구성"""
        # 불필요한 공백 및 괄호 제거
        import re
        clean_title = re.sub(r'[\(\):]', ' ', title).strip()
        if author:
            # 저자명에서 '(지은이)', '(옮긴이)' 등 제거
            clean_author = re.sub(r'\(.*?\)', '', author).replace(',', ' ').strip()
            return f"{clean_title} {clean_author}"
        return clean_title


class GoogleBooksProvider(ISBNProvider):
    """Google Books API 프로바이더"""

    name = "google_books"
    base_url = "https://www.googleapis.com/books/v1/volumes"

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.environ.get("GOOGLE_BOOKS_API_KEY", "")
        if not self.api_key:
            self._load_api_key_from_env()

    def _load_api_key_from_env(self):
        """Load API key from .env file"""
        env_paths = [".env", os.path.join(os.path.dirname(__file__), "..", ".env")]
        for env_path in env_paths:
            if os.path.exists(env_path):
                with open(env_path) as f:
                    for line in f:
                        if line.startswith("GOOGLE_BOOKS_API_KEY="):
                            self.api_key = line.strip().split("=", 1)[1]
                            return

    def is_available(self) -> bool:
        """API 키가 설정되어 있는지 확인"""
        return bool(self.api_key)

    def _api_get(self, url: str) -> dict | None:
        """Google Books API GET 요청"""
        req = urllib.request.Request(url)
        req.add_header("User-Agent", "Mozilla/5.0")
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))

    @staticmethod
    def _extract_isbn(identifiers: list[dict]) -> str | None:
        """industryIdentifiers에서 ISBN 추출 (ISBN-13 우선)"""
        isbn = None
        for ident in identifiers:
            if ident.get("type") == "ISBN_13":
                return ident.get("identifier")
            elif ident.get("type") == "ISBN_10" and not isbn:
                isbn = ident.get("identifier")
        return isbn

    def search(self, title: str, author: str | None = None) -> ISBNResult | None:
        if not self.is_available():
            return None

        query = self._build_query(title, author)
        # Google Books Advanced Search syntax
        import re
        clean_title = re.sub(r'[\(\):]', ' ', title).strip()
        search_query = f"intitle:\"{clean_title}\""
        if author:
            clean_author = re.sub(r'\(.*?\)', '', author).split(',')[0].strip()
            if clean_author:
                search_query += f" inauthor:\"{clean_author}\""

        encoded = urllib.parse.quote(search_query)
        url = f"{self.base_url}?q={encoded}&key={self.api_key}"

        try:
            data = self._api_get(url)
            if not data or data.get("totalItems", 0) == 0:
                return None

            # 첫 번째 결과에서 ISBN 추출
            for item in data.get("items", []):
                info = item.get("volumeInfo", {})
                item_title = info.get("title", "")
                item_authors = info.get("authors", [])

                # 제목 유사도 체크 (0.7 이상)
                similarity = difflib.SequenceMatcher(None, title.lower(), item_title.lower()).ratio()
                # 부분 일치 체크 (예: 원서 제목이 책 제목에 포함되는 경우)
                if title.lower() in item_title.lower() or item_title.lower() in title.lower():
                    similarity = max(similarity, 0.8)

                if similarity < 0.6: # 조금 더 완화
                    continue

                isbn = self._extract_isbn(info.get("industryIdentifiers", []))
                if isbn:
                    return ISBNResult(
                        isbn=isbn,
                        title=item_title,
                        authors=item_authors,
                        provider=self.name,
                    )

            return None

        except Exception as e:
            print(f"[{self.name}] 검색 실패: {e}")
            return None

    def _find_english_edition(self, search_url: str) -> dict | None:
        """
        Google Books 검색 결과에서 영어판 찾기 (공통 로직)

        검색 결과의 첫 번째 항목이:
        - 비아시아 언어면 → 그 자체가 원서 (직접 반환)
        - 아시아 언어면 → 저자명으로 영어판 검색

        Args:
            search_url: Google Books API 검색 URL

        Returns:
            {"title": str, "authors": list[str], "isbn": str|None} 또는 None
        """
        try:
            data = self._api_get(search_url)
            if not data or not data.get("items"):
                return None

            info = data["items"][0].get("volumeInfo", {})
            language = info.get("language", "")
            authors = info.get("authors", [])

            # 비아시아 언어면 그 자체가 원서
            if language not in ("ko", "ja", "zh"):
                title = info.get("title", "")
                if title:
                    return {
                        "title": title,
                        "authors": authors,
                        "isbn": self._extract_isbn(info.get("industryIdentifiers", [])),
                    }
                return None

            # 아시아 언어 → 저자명으로 영어판 검색
            for author in authors:
                result = self._find_english_edition_by_author(author)
                if result:
                    return result
            return None

        except Exception:
            return None

    def find_original_by_isbn(self, isbn: str) -> dict | None:
        """ISBN으로 Google Books에서 원서 정보 조회"""
        if not self.is_available():
            return None
        key_param = f"&key={self.api_key}" if self.api_key else ""
        url = f"{self.base_url}?q=isbn:{isbn}{key_param}"
        return self._find_english_edition(url)

    def _find_english_edition_by_author(self, author: str) -> dict | None:
        """저자명으로 영어판 검색 (공통 로직)"""
        base = self.base_url
        key_param = f"&key={self.api_key}" if self.api_key else ""

        encoded = urllib.parse.quote(f'inauthor:"{author}"')
        search_url = f"{base}?q={encoded}&langRestrict=en&maxResults=5{key_param}"

        data = self._api_get(search_url)
        if not data or not data.get("items"):
            return None

        for item in data.get("items", []):
            eng_info = item.get("volumeInfo", {})
            eng_title = eng_info.get("title", "")
            if eng_title:
                return {
                    "title": eng_title,
                    "authors": eng_info.get("authors", []),
                    "isbn": self._extract_isbn(
                        eng_info.get("industryIdentifiers", [])
                    ),
                }
        return None

    def find_original_by_korean_title(self, korean_title: str) -> dict | None:
        """한국어 제목으로 Google Books 검색 → 영어판 찾기"""
        if not self.is_available():
            return None
        key_param = f"&key={self.api_key}" if self.api_key else ""
        encoded = urllib.parse.quote(f'intitle:"{korean_title}"')
        url = f"{self.base_url}?q={encoded}{key_param}"
        return self._find_english_edition(url)

    def find_original_by_romanized_author(self, author: str) -> dict | None:
        """로마자 저자명으로 Google Books에서 영어판 검색"""
        if not self.is_available():
            return None
        try:
            return self._find_english_edition_by_author(author)
        except Exception:
            return None


class OpenLibraryProvider(ISBNProvider):
    """Open Library API 프로바이더 (무료, API 키 불필요)"""

    name = "open_library"
    base_url = "https://openlibrary.org/search.json"

    def _api_get(self, url: str) -> dict | None:
        """Open Library API GET 요청"""
        req = urllib.request.Request(url)
        req.add_header("User-Agent", "BookCrawler/1.0")
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def search(self, title: str, author: str | None = None) -> ISBNResult | None:
        query = self._build_query(title, author)
        encoded = urllib.parse.quote(query)
        url = f"{self.base_url}?q={encoded}&limit=5"

        try:
            data = self._api_get(url)
            if not data:
                return None

            docs = data.get("docs", [])
            if not docs:
                return None

            # 첫 번째 결과에서 ISBN 추출
            for doc in docs:
                isbn_list = doc.get("isbn", [])
                if isbn_list:
                    # ISBN-13 우선 (13자리)
                    isbn_13 = next(
                        (i for i in isbn_list if len(i) == 13 and i.isdigit()), None
                    )
                    isbn_10 = next(
                        (i for i in isbn_list if len(i) == 10), None
                    )
                    isbn = isbn_13 or isbn_10

                    if isbn:
                        return ISBNResult(
                            isbn=isbn,
                            title=doc.get("title", ""),
                            authors=doc.get("author_name", []),
                            provider=self.name,
                        )

            return None

        except Exception as e:
            print(f"[{self.name}] 검색 실패: {e}")
            return None

    def find_original_by_isbn(self, isbn: str) -> dict | None:
        """
        ISBN으로 Open Library에서 원서 작품 정보 조회

        Edition → Work 연결을 사용하여 한국어판 ISBN에서 원서 제목/ISBN을 찾습니다.

        Args:
            isbn: ISBN-13 또는 ISBN-10 (한국어판)

        Returns:
            {"title": str, "authors": list[str], "isbn": str|None} 또는 None
        """
        try:
            # Step 1: ISBN → Edition → Work key
            edition = self._api_get(f"https://openlibrary.org/isbn/{isbn}.json")
            if not edition:
                return None

            works = edition.get("works", [])
            if not works:
                return None
            work_key = works[0].get("key")
            if not work_key:
                return None

            # Step 2: Work → 원서 제목
            work = self._api_get(f"https://openlibrary.org{work_key}.json")
            if not work:
                return None

            title = work.get("title")
            if not title:
                return None

            # Step 3: Work → Editions → 영문판 ISBN 찾기
            editions_url = f"https://openlibrary.org{work_key}/editions.json?limit=20"
            editions_data = self._api_get(editions_url)

            original_isbn = None
            if editions_data:
                for ed in editions_data.get("entries", []):
                    # 영어판 우선 (언어 필드가 있는 경우)
                    langs = ed.get("languages", [])
                    lang_keys = [l.get("key", "") for l in langs]
                    is_english = "/languages/eng" in lang_keys

                    ed_isbns = ed.get("isbn_13", []) or ed.get("isbn_10", [])
                    if ed_isbns and is_english:
                        original_isbn = ed_isbns[0]
                        break

                # 영어판 못 찾으면, 한국어판이 아닌 첫 번째 에디션 사용
                if not original_isbn:
                    for ed in editions_data.get("entries", []):
                        langs = ed.get("languages", [])
                        lang_keys = [l.get("key", "") for l in langs]
                        is_korean = "/languages/kor" in lang_keys

                        ed_isbns = ed.get("isbn_13", []) or ed.get("isbn_10", [])
                        if ed_isbns and not is_korean:
                            original_isbn = ed_isbns[0]
                            break

            return {
                "title": title,
                "authors": [],
                "isbn": original_isbn,
            }

        except Exception:
            return None


def _scrape_yes24_original_author(korean_title: str) -> str | None:
    """
    Yes24에서 한국어 제목으로 검색하여 로마자 저자명 추출

    Args:
        korean_title: 한국어 책 제목

    Returns:
        로마자 저자명 또는 None
    """
    import re

    try:
        # Step 1: Yes24 검색
        encoded_title = urllib.parse.quote(korean_title)
        search_url = f"https://www.yes24.com/Product/Search?domain=ALL&query={encoded_title}"

        req = urllib.request.Request(search_url)
        req.add_header("User-Agent", "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36")

        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8")

        # Step 2: 첫 번째 검색 결과의 상품 URL 추출
        # <a class="gd_name" href="/product/goods/123456">
        pattern = r'<a\s+class="gd_name"\s+href="(/product/goods/\d+)"'
        match = re.search(pattern, html, re.IGNORECASE)
        if not match:
            return None

        goods_path = match.group(1)
        detail_url = f"https://www.yes24.com{goods_path}"

        # Step 3: 상세 페이지에서 로마자 저자명 추출
        req = urllib.request.Request(detail_url)
        req.add_header("User-Agent", "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36")

        with urllib.request.urlopen(req, timeout=10) as resp:
            detail_html = resp.read().decode("utf-8")

        # <span class="name_other">(Author Name)</span>
        author_pattern = r'<span\s+class="name_other">\(([^)]+)\)</span>'
        author_match = re.search(author_pattern, detail_html)
        if author_match:
            return author_match.group(1).strip()

        return None

    except Exception:
        return None


class ISBNLookup:
    """
    ISBN 조회 통합 클래스

    여러 프로바이더를 순차적으로 시도하여 ISBN 조회.
    기본 순서: Google Books → Open Library
    """

    def __init__(self, providers: list[ISBNProvider] | None = None):
        if providers is not None:
            self.providers = providers
        else:
            # 기본 프로바이더 설정
            self.providers = []

            # Google Books (API 키가 있으면 사용)
            google = GoogleBooksProvider()
            if google.is_available():
                self.providers.append(google)

            # Open Library (항상 사용 가능)
            self.providers.append(OpenLibraryProvider())

    def get_isbn(self, title: str, author: str | None = None) -> str | None:
        """
        ISBN 조회 (문자열만 반환)

        Args:
            title: 책 제목
            author: 저자명 (선택)

        Returns:
            ISBN 문자열 또는 None
        """
        result = self.search(title, author)
        return result.isbn if result else None

    def search(self, title: str, author: str | None = None) -> ISBNResult | None:
        """
        ISBN 조회 (전체 결과 반환)

        Args:
            title: 책 제목
            author: 저자명 (선택)

        Returns:
            ISBNResult 또는 None
        """
        for provider in self.providers:
            result = provider.search(title, author)
            if result:
                return result
        return None

    def find_original(
        self, isbn: str | None = None, korean_title: str | None = None
    ) -> dict | None:
        """
        원서 작품 정보 조회

        한국어판 ISBN 또는 한국어 제목에서 원서 제목과 ISBN을 찾습니다.
        시도 순서: ISBN → 한국어 제목 (Google Books 저자 추출 → 영어판 검색)

        Args:
            isbn: ISBN-13 또는 ISBN-10 (한국어판)
            korean_title: 한국어 책 제목

        Returns:
            {"title": str, "authors": list[str], "isbn": str|None} 또는 None
        """
        # 방법 1: ISBN으로 조회 (Open Library Work 기반 / Google Books)
        if isbn:
            for provider in self.providers:
                if hasattr(provider, "find_original_by_isbn"):
                    result = provider.find_original_by_isbn(isbn)
                    if result:
                        return result

        # 방법 2: 한국어 제목으로 Google Books 검색 → 저자 추출 → 영어판 검색
        if korean_title:
            for provider in self.providers:
                if hasattr(provider, "find_original_by_korean_title"):
                    result = provider.find_original_by_korean_title(korean_title)
                    if result:
                        return result

        # 방법 3: Yes24에서 로마자 저자명 추출 → Google Books 영어판 검색
        if korean_title:
            romanized_author = _scrape_yes24_original_author(korean_title)
            if romanized_author:
                for provider in self.providers:
                    if hasattr(provider, "find_original_by_romanized_author"):
                        result = provider.find_original_by_romanized_author(romanized_author)
                        if result:
                            return result

        return None

    def add_provider(self, provider: ISBNProvider, priority: int = -1):
        """
        프로바이더 추가

        Args:
            provider: ISBN 프로바이더
            priority: 삽입 위치 (-1이면 맨 뒤)
        """
        if priority < 0:
            self.providers.append(provider)
        else:
            self.providers.insert(priority, provider)


# 싱글톤 인스턴스 (편의용)
_default_lookup: ISBNLookup | None = None


def get_isbn(title: str, author: str | None = None) -> str | None:
    """
    ISBN 조회 헬퍼 함수

    Args:
        title: 책 제목
        author: 저자명 (선택)

    Returns:
        ISBN 문자열 또는 None
    """
    global _default_lookup
    if _default_lookup is None:
        _default_lookup = ISBNLookup()
    return _default_lookup.get_isbn(title, author)
