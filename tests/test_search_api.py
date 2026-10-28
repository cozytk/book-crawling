"""Regression coverage for the actual API, storage, and concurrent search path."""
import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from api.app import app
from api.local_store import LocalStore
from api.db import save_search_result, get_all_searches
from api.services import crawler_service
from crawlers.foreign_resolver import ForeignQuery
from models.book import PlatformRating


@pytest.fixture
def client(tmp_path):
    store = LocalStore(str(tmp_path / "searches.sqlite3"))
    with patch("api.routes.search.get_client", return_value=store):
        with TestClient(app) as client:
            yield client, store


def rating(platform="yes24", value=9.0):
    return {"platform": platform, "rating": value, "rating_scale": 10,
            "normalized_rating": value, "review_count": 12,
            "book_title": "데미안", "url": "https://example.com/book"}


def test_cache_scope_and_summary(client):
    api, store = client
    save_search_result(store, "데미안", [rating(), rating("kyobo", 0)])
    response = api.post("/api/search", json={"query": "  데미안 ", "platforms": ["yes24"]}).json()
    assert response["source"] == "cache"
    assert [r["platform"] for r in response["ratings"]] == ["yes24"]
    assert response["search"]["avg_rating"] == 9
    assert response["search"]["total_reviews"] == 12
    assert api.get("/api/search/check", params={"query": "데미안"}).json() == {"cached": False}
    assert api.get("/api/search/check", params={"query": "데미안", "platforms": "yes24"}).json()["cached"]
    assert get_all_searches(store)["searches"][0]["avg_rating"] == 4.5


def test_stream_cache_history_roundtrip(client):
    api, store = client
    record = save_search_result(store, "데미안", [rating()])
    response = api.post("/api/search/stream", json={"query": "데미안", "platforms": ["yes24"]})
    assert "event: rating" in response.text
    assert "event: done" in response.text
    assert "description_chunk" not in response.text
    saved = api.get(f'/api/search/{record["id"]}').json()
    assert saved["ratings"][0]["book_title"] == "데미안"
    assert api.get("/api/searches").json()["total"] == 1
    # The existing history screen requests 500 rows for instant local filters.
    response = api.get("/api/searches?limit=500&offset=0&with_count=false")
    assert response.status_code == 200
    assert len(response.json()["searches"]) == 1


def test_partial_search_does_not_freeze_failures_for_24_hours(client):
    api, store = client
    save_search_result(store, "데미안", [rating()], list(crawler_service.CRAWLERS))
    assert api.get("/api/search/check?query=데미안").json() == {"cached": False}
    assert api.get("/api/search/check?query=데미안&platforms=yes24").json()["cached"]


@pytest.mark.parametrize("payload", [{"query": " "}, {"query": "x", "platforms": []}, {"query": "x", "platforms": ["wrong"]}])
def test_invalid_search(client, payload):
    assert client[0].post("/api/search", json=payload).status_code == 422
    assert client[0].post("/api/search/stream", json=payload).status_code == 422


def test_force_refresh_and_stream_save(client):
    api, store = client
    save_search_result(store, "데미안", [rating()])
    async def results(*args):
        yield rating(value=8)
    with patch("api.routes.search.crawl_all_stream", results):
        response = api.post("/api/search/stream", json={"query": "데미안", "platforms": ["yes24"], "force_refresh": True})
    assert '"source": "crawl"' in response.text
    assert get_all_searches(store)["total"] == 2
    reopened = LocalStore(store.path)
    assert get_all_searches(reopened)["searches"][0]["avg_rating"] == 8


async def test_domestic_stream_does_not_wait_for_foreign_resolution():
    resolved = asyncio.Event()
    async def resolve(query):
        await resolved.wait()
        return ForeignQuery(query="Demian")
    async def crawl(cls, query, *args, **kwargs):
        return PlatformRating(cls.name, 4, 5, 1, "https://example.com", query)
    with patch.object(crawler_service, "resolve_foreign_query", resolve), patch.object(crawler_service, "crawl_platform", crawl):
        stream = crawler_service.crawl_all_stream("데미안", ["yes24", "goodreads", "yes24"])
        first = await asyncio.wait_for(anext(stream), 1)
        assert first["platform"] == "yes24"
        resolved.set()
        rest = [r async for r in stream]
        assert [r["platform"] for r in rest] == ["goodreads"]


def test_description_opt_in_and_failure_finishes(client):
    api, _ = client
    async def results(*args):
        yield rating()
    async def description(*args):
        yield "설명"
        raise RuntimeError("provider unavailable")
    with patch("api.routes.search.crawl_all_stream", results), patch("api.routes.search.generate_book_description_stream", description):
        response = api.post("/api/search/stream", json={"query": "데미안", "platforms": ["yes24"], "include_description": True})
    assert "description_chunk" in response.text
    assert "event: done" in response.text
