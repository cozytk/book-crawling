"""Storage, authentication, and deadline regressions for the Vercel deployment."""
import asyncio
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from api.app import app
from api.blob_store import BlobStore, blob
from api.db import get_all_searches, save_search_result, get_saved_search
from api.services import crawler_service
from models.book import PlatformRating


@pytest.fixture
def store():
    files = {}

    def put(path, body, **options):
        assert options["access"] == "private"
        assert options["allow_overwrite"] == ("/cache/" in path or "/platforms/" in path)
        files[path] = body

    def get(path, **options):
        assert options["access"] == "private"
        if path not in files:
            raise blob.BlobNotFoundError("not found")
        return SimpleNamespace(body=files[path])

    def query(**options):
        return iter(SimpleNamespace(pathname=p) for p in sorted(files) if p.startswith(options["prefix"]))

    with patch.object(blob, "put_blob", put), patch.object(blob, "get_blob", get), patch.object(blob, "query_blobs", query):
        yield BlobStore()


def sample(platform="yes24", score=9):
    return {"platform": platform, "rating": score, "rating_scale": 10,
            "normalized_rating": score, "review_count": 12, "book_title": "데미안", "url": "https://example.com"}


def test_private_blob_roundtrip_and_query_scope(store):
    first = save_search_result(store, "데미안", [sample()], ["yes24"])
    second = save_search_result(store, "사피엔스", [sample("kyobo", 8)], ["kyobo"])
    assert get_saved_search(store, first["id"])["ratings"][0]["platform"] == "yes24"
    assert store.cached("데미안", "2000")["search"]["requested_platforms"] == ["yes24"]
    assert store.cached("데미안", "9999") is None
    assert store.get("missing") is None
    history = get_all_searches(store)
    assert [s["id"] for s in history["searches"]] == [second["id"], first["id"]]
    assert get_all_searches(store, platform="yes24")["total"] == 1
    assert get_all_searches(store, sort_by="avg_rating", order="asc")["searches"][0]["id"] == second["id"]


def test_blob_api_persist_and_stream_cache_roundtrip(store):
    async def results(*args):
        yield sample()
    with patch("api.routes.search.get_client", return_value=store), patch("api.routes.search.crawl_all_stream", results):
        with TestClient(app) as client:
            response = client.post("/api/search/stream", json={"query": "데미안", "platforms": ["yes24"]})
            assert '"storage_saved": true' in response.text
            response = client.post("/api/search/stream", json={"query": "데미안", "platforms": ["yes24"]})
            assert '"source": "cache"' in response.text
            assert client.get("/api/searches").json()["total"] == 1
            assert client.get("/api/search/check?query=데미안").json() == {"cached": False}


def test_backend_requires_service_token(monkeypatch):
    monkeypatch.setenv("API_SERVICE_TOKEN", "test-service-secret")
    with TestClient(app) as client:
        assert client.get("/api/platforms").status_code == 401
        assert client.get("/api/platforms", headers={"x-api-token": "wrong"}).status_code == 401
        assert client.get("/api/platforms", headers={"x-api-token": "test-service-secret"}).status_code == 200
        assert client.get("/health").status_code == 200


async def test_slow_platform_does_not_block_other_results(monkeypatch, empty_work_identity):
    async def crawl(cls, query, **kwargs):
        if cls.name == "kyobo":
            await asyncio.sleep(10)
        return PlatformRating(cls.name, 9, 10, 12, "https://example.com", query)
    monkeypatch.setattr(crawler_service, "PLATFORM_TIMEOUT", .02)
    monkeypatch.setattr(crawler_service, "crawl_platform", crawl)
    statuses = []
    results = [r async for r in crawler_service.crawl_all_stream("데미안", ["yes24", "kyobo"], statuses.append)]
    assert [r["platform"] for r in results] == ["yes24"]
    assert {s["platform"]: s["status"] for s in statuses} == {"yes24": "done", "kyobo": "timeout"}
