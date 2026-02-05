"""검색 API 라우트"""

import json
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from api.db import get_client, find_cached_search, save_search_result, get_all_searches
from api.services.crawler_service import crawl_all, get_available_platforms

router = APIRouter()


class SearchRequest(BaseModel):
    query: str
    platforms: list[str] | None = None


class PlatformInfo(BaseModel):
    name: str
    type: str


@router.post("/search")
async def search_book(req: SearchRequest):
    """
    책 검색 API

    1. Supabase 캐시 확인 (24시간 이내 동일 쿼리)
    2. 캐시 히트 → 즉시 반환
    3. 캐시 미스 → 크롤러 실행 → 결과 저장 → 반환
    """
    if not req.query.strip():
        raise HTTPException(status_code=400, detail="검색어를 입력해주세요")

    query = req.query.strip()

    # 1. 캐시 확인
    try:
        client = get_client()
        cached = find_cached_search(client, query)
        if cached:
            return {
                "source": "cache",
                "search": cached["search"],
                "ratings": cached["ratings"],
            }
    except Exception:
        # Supabase 연결 실패 시 캐시 없이 진행
        client = None

    # 2. 크롤링 실행
    result = await crawl_all(query, req.platforms)
    result_dicts = result.to_dict()["results"]

    # 3. 결과 저장 (Supabase 연결 가능한 경우)
    search_record = None
    if client and result_dicts:
        try:
            search_record = save_search_result(client, query, result_dicts)
        except Exception:
            pass

    # 4. 응답
    ratings = [r["normalized_rating"] for r in result_dicts if r.get("normalized_rating")]
    avg_rating = sum(ratings) / len(ratings) if ratings else None
    total_reviews = sum(r.get("review_count", 0) for r in result_dicts)

    return {
        "source": "crawl",
        "search": {
            "id": search_record["id"] if search_record else None,
            "query": query,
            "avg_rating": round(avg_rating, 2) if avg_rating else None,
            "total_reviews": total_reviews,
            "platform_count": len(result_dicts),
        },
        "ratings": result_dicts,
    }


@router.get("/search/{search_id}")
async def get_search(search_id: str):
    """캐시된 검색 결과 조회"""
    try:
        client = get_client()
    except Exception:
        raise HTTPException(status_code=503, detail="데이터베이스 연결 실패")

    search = (
        client.table("searches")
        .select("*")
        .eq("id", search_id)
        .limit(1)
        .execute()
    )

    if not search.data:
        raise HTTPException(status_code=404, detail="검색 결과를 찾을 수 없습니다")

    ratings = (
        client.table("platform_ratings")
        .select("*")
        .eq("search_id", search_id)
        .execute()
    )

    return {
        "source": "cache",
        "search": search.data[0],
        "ratings": ratings.data,
    }


@router.post("/search/stream")
async def search_book_stream(req: SearchRequest):
    """
    SSE 스트리밍 검색 API

    각 플랫폼 결과를 개별 SSE 이벤트로 전송.
    마지막에 event: done으로 요약 전송.
    """
    if not req.query.strip():
        raise HTTPException(status_code=400, detail="검색어를 입력해주세요")

    query = req.query.strip()

    # 캐시 확인
    try:
        client = get_client()
        cached = find_cached_search(client, query)
        if cached:
            # 캐시 히트: 각 결과를 개별 이벤트로 전송 후 done
            async def cached_stream():
                for r in cached["ratings"]:
                    yield f"data: {json.dumps(r, ensure_ascii=False)}\n\n"
                yield f"event: done\ndata: {json.dumps({'source': 'cache', 'search': cached['search']}, ensure_ascii=False)}\n\n"
            return StreamingResponse(cached_stream(), media_type="text/event-stream")
    except Exception:
        client = None

    async def event_stream():
        from api.services.crawler_service import crawl_all_stream
        results = []
        async for result in crawl_all_stream(query, req.platforms):
            results.append(result)
            yield f"data: {json.dumps(result, ensure_ascii=False)}\n\n"

        # DB에 저장
        search_record = None
        if client and results:
            try:
                search_record = save_search_result(client, query, results)
            except Exception:
                pass

        # 요약 계산
        ratings = [r["normalized_rating"] for r in results if r.get("normalized_rating")]
        avg_rating = sum(ratings) / len(ratings) if ratings else None
        total_reviews = sum(r.get("review_count", 0) for r in results)

        summary = {
            "source": "crawl",
            "search": {
                "id": search_record["id"] if search_record else None,
                "query": query,
                "avg_rating": round(avg_rating, 2) if avg_rating else None,
                "total_reviews": total_reviews,
                "platform_count": len(results),
            },
        }
        yield f"event: done\ndata: {json.dumps(summary, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/searches")
async def list_searches(
    sort_by: str = "created_at",
    order: str = "desc",
    limit: int = 50,
    offset: int = 0,
    platform: str | None = None,
):
    """
    검색 히스토리 조회

    Query params:
        sort_by: created_at | avg_rating | total_reviews
        order: asc | desc
        limit: 페이지 크기 (기본 50)
        offset: 시작 위치
        platform: 특정 플랫폼 필터 (optional)
    """
    try:
        client = get_client()
    except Exception:
        raise HTTPException(status_code=503, detail="데이터베이스 연결 실패")

    return get_all_searches(client, sort_by=sort_by, order=order, limit=limit, offset=offset, platform=platform)


@router.get("/platforms")
async def list_platforms():
    """사용 가능한 플랫폼 목록"""
    return {"platforms": get_available_platforms()}
