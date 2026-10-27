"""Book search, streaming results, and saved history."""
import asyncio
import json
from uuid import UUID
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator, ValidationError
from api.db import get_client, find_cached_search, save_search_result, get_all_searches, get_saved_search, summarize
from api.services.crawler_service import CRAWLERS, crawl_all, crawl_all_stream, get_available_platforms
from api.services.ai_service import generate_book_description, generate_book_description_stream

router = APIRouter()


class SearchRequest(BaseModel):
    query: str = Field(max_length=300)
    platforms: list[str] | None = None
    include_description: bool = False
    force_refresh: bool = False

    @field_validator("query")
    @classmethod
    def clean_query(cls, value):
        value = " ".join(value.split())
        if not value:
            raise ValueError("검색어를 입력해주세요")
        return value

    @field_validator("platforms")
    @classmethod
    def validate_platforms(cls, value):
        if value is not None:
            if not value or any(p not in CRAWLERS for p in value):
                raise ValueError("지원하는 플랫폼을 하나 이상 선택해주세요")
            return list(dict.fromkeys(value))
        return value


def cached_for(client, query, platforms=None):
    cached = find_cached_search(client, query)
    if not cached:
        return None
    selected = set(platforms if platforms is not None else CRAWLERS)
    found = {r["platform"] for r in cached["ratings"]}
    covered = set(cached["search"].get("requested_platforms", found))
    if not selected.issubset(covered):
        return None
    ratings = [r for r in cached["ratings"] if r["platform"] in selected]
    return {"search": {**cached["search"], **summarize(ratings)}, "ratings": ratings}


async def lookup(req):
    try:
        client = await asyncio.to_thread(get_client)
        cached = None if req.force_refresh else await asyncio.to_thread(cached_for, client, req.query, req.platforms)
        return client, cached
    except Exception:
        return None, None


async def persist(client, query, results, platforms=None):
    if client and results:
        try:
            return await asyncio.to_thread(save_search_result, client, query, results, list(platforms if platforms is not None else CRAWLERS))
        except Exception:
            pass
    return {"id": None, "query": query, **summarize(results)}


def with_coverage(search, ratings, platforms):
    found = {r["platform"] for r in ratings}
    selected = platforms if platforms is not None else CRAWLERS
    return {**search, "missing_platforms": [p for p in selected if p not in found]}


@router.post("/search")
async def search_book(req: SearchRequest):
    client, cached = await lookup(req)
    if cached:
        response = {"source": "cache", **cached}
    else:
        result = await crawl_all(req.query, req.platforms)
        ratings = result.to_dict()["results"]
        response = {"source": "crawl", "search": await persist(client, req.query, ratings, req.platforms), "ratings": ratings}
    response["description"] = await generate_book_description(req.query) if req.include_description and response["ratings"] else None
    response["search"] = with_coverage(response["search"], response["ratings"], req.platforms)
    return response


@router.get("/search/check")
async def check_cache(query: str, platforms: list[str] | None = Query(default=None)):
    try:
        req = SearchRequest(query=query, platforms=platforms)
    except ValidationError:
        raise HTTPException(status_code=422, detail="검색어와 플랫폼을 확인해주세요")
    _, cached = await lookup(req)
    return {"cached": True, "search": cached["search"]} if cached else {"cached": False}


@router.get("/search/{search_id}")
async def get_search(search_id: UUID):
    try:
        saved = await asyncio.to_thread(get_saved_search, get_client(), str(search_id))
    except Exception:
        raise HTTPException(status_code=503, detail="데이터베이스 연결 실패")
    if saved is None:
        raise HTTPException(status_code=404, detail="검색 결과를 찾을 수 없습니다")
    return {"source": "cache", **saved}


def sse(event, data):
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/search/stream")
async def search_book_stream(req: SearchRequest):
    client, cached = await lookup(req)

    async def events():
        queue = asyncio.Queue()
        async def crawl():
            try:
                if cached:
                    for rating in cached["ratings"]:
                        await queue.put(("rating", rating))
                else:
                    async for rating in crawl_all_stream(req.query, req.platforms):
                        await queue.put(("rating", rating))
            except Exception:
                await queue.put(("error", {"message": "검색 중 오류가 발생했습니다"}))
            finally:
                await queue.put(("crawl_done", None))

        async def describe():
            try:
                if req.include_description:
                    async for chunk in generate_book_description_stream(req.query):
                        await queue.put(("description_chunk", {"chunk": chunk}))
            except Exception:
                pass
            finally:
                await queue.put(("description_done", None))

        tasks = [asyncio.create_task(crawl()), asyncio.create_task(describe())]
        results = []
        complete = set()
        try:
            while len(complete) < 2:
                try:
                    event, data = await asyncio.wait_for(queue.get(), timeout=15)
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
                    continue
                if event.endswith("_done"):
                    complete.add(event)
                    continue
                if event == "rating":
                    results.append(data)
                yield sse(event, data)
            search = cached["search"] if cached else await persist(client, req.query, results, req.platforms)
            yield sse("done", {"source": "cache" if cached else "crawl", "search": with_coverage(search, results, req.platforms)})
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

    return StreamingResponse(events(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.get("/searches")
async def list_searches(sort_by: str = "created_at", order: str = "desc",
                        limit: int = Query(default=50, ge=1, le=500),
                        offset: int = Query(default=0, ge=0), platform: str | None = None,
                        sort_platform: str | None = None, with_count: bool = True):
    try:
        return await asyncio.to_thread(get_all_searches, get_client(), sort_by, order, limit, offset,
                                       platform, sort_platform, with_count)
    except Exception:
        raise HTTPException(status_code=503, detail="데이터베이스 연결 실패")


@router.get("/platforms")
async def list_platforms():
    return {"platforms": get_available_platforms()}
