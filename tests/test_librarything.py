"""LibraryThingCrawler 테스트"""

import json
import urllib.error
from unittest.mock import patch

import pytest

from crawlers.librarything import LibraryThingCrawler


class MockResponse:
    """urllib 응답 모킹용 컨텍스트 매니저"""

    def __init__(self, body: str):
        self._body = body.encode("utf-8")

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class TestLibraryThingNormalizeWorkUrl:
    """work URL 정규화 테스트"""

    def test_normalize_direct_work_url(self):
        crawler = LibraryThingCrawler()
        normalized = crawler._normalize_work_url(
            "https://www.librarything.com/work/5382831/t/Clean-Code"
        )
        assert normalized == "https://www.librarything.com/work/5382831"

    def test_normalize_duckduckgo_redirect_url(self):
        crawler = LibraryThingCrawler()
        normalized = crawler._normalize_work_url(
            "//duckduckgo.com/l/?uddg=https%3A%2F%2Fwww.librarything.com%2Fwork%2F5382831%2Ft%2FClean-Code"
        )
        assert normalized == "https://www.librarything.com/work/5382831"


class TestLibraryThingSearchFallback:
    """검색 우회 로직 테스트"""

    def test_search_via_fallback_uses_duckduckgo_when_brave_fails(self):
        crawler = LibraryThingCrawler()
        with patch.object(crawler, "_search_via_brave", return_value=(None, "")):
            with patch.object(
                crawler,
                "_search_via_duckduckgo",
                return_value=("https://www.librarything.com/work/5382831", "Clean Code"),
            ):
                url, title = crawler._search_via_fallback("Clean Code")

        assert url == "https://www.librarything.com/work/5382831"
        assert title == "Clean Code"

    def test_search_via_brave_retries_once_on_429(self, monkeypatch):
        crawler = LibraryThingCrawler()
        monkeypatch.setenv("BRAVE_SEARCH_API_KEY", "test-key")

        payload = {
            "web": {
                "results": [
                    {
                        "url": "https://www.librarything.com/work/5382831/t/Clean-Code",
                        "title": "Clean Code | LibraryThing",
                    }
                ]
            }
        }
        http_429 = urllib.error.HTTPError(
            "https://api.search.brave.com/res/v1/web/search",
            429,
            "Too Many Requests",
            hdrs=None,
            fp=None,
        )

        with patch("crawlers.librarything.urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = [
                http_429,
                MockResponse(json.dumps(payload)),
            ]
            url, title = crawler._search_via_brave("Clean Code")

        assert url == "https://www.librarything.com/work/5382831"
        assert title == "Clean Code"

    def test_search_via_duckduckgo_extracts_work_url(self):
        crawler = LibraryThingCrawler()
        html = """
        <html>
          <a class="result__a"
             href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fwww.librarything.com%2Fwork%2F5382831%2Ft%2FClean-Code">
             Clean Code: A Handbook of Agile Software Craftsmanship | LibraryThing
          </a>
        </html>
        """

        with patch(
            "crawlers.librarything.urllib.request.urlopen",
            return_value=MockResponse(html),
        ):
            url, title = crawler._search_via_duckduckgo("Clean Code")

        assert url == "https://www.librarything.com/work/5382831"
        assert title.startswith("Clean Code")


@pytest.mark.asyncio
async def test_get_rating_uses_cache():
    """캐시된 평점 즉시 반환"""
    crawler = LibraryThingCrawler()
    crawler._cached_rating = 4.2
    crawler._cached_review_count = 123

    rating, review_count = await crawler.get_rating("https://www.librarything.com/work/5382831")

    assert rating == 4.2
    assert review_count == 123
