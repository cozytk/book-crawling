"""검색 API 라우트"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from api.db import get_client, find_cached_search, save_search_result
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


@router.get("/platforms")
async def list_platforms():
    """사용 가능한 플랫폼 목록"""
    return {"platforms": get_available_platforms()}
