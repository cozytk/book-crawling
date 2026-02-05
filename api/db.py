"""Supabase 클라이언트 및 캐싱 로직"""

import os
from datetime import datetime, timedelta, timezone

from supabase import create_client, Client

CACHE_TTL_HOURS = 24

# 싱글톤 클라이언트 캐시
_client_cache: Client | None = None


def get_client() -> Client:
    """Supabase 클라이언트 생성 (싱글톤)"""
    global _client_cache
    if _client_cache is None:
        url = os.environ["SUPABASE_URL"]
        key = os.environ["SUPABASE_KEY"]
        _client_cache = create_client(url, key)
    return _client_cache


def find_cached_search(client: Client, query: str) -> dict | None:
    """
    24시간 이내 동일 쿼리 캐시 조회

    Returns:
        {"search": {...}, "ratings": [...]} or None
    """
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=CACHE_TTL_HOURS)).isoformat()

    result = (
        client.table("searches")
        .select("*")
        .eq("query", query)
        .gte("created_at", cutoff)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )

    if not result.data:
        return None

    search = result.data[0]
    ratings = (
        client.table("platform_ratings")
        .select("*")
        .eq("search_id", search["id"])
        .execute()
    )

    return {"search": search, "ratings": ratings.data}


def save_search_result(client: Client, query: str, results: list[dict]) -> dict:
    """
    검색 결과를 Supabase에 저장

    Args:
        query: 검색어
        results: PlatformRating.to_dict() 형태의 리스트

    Returns:
        저장된 search 레코드
    """
    # 평균 평점 계산
    ratings = [r["normalized_rating"] for r in results if r.get("normalized_rating")]
    avg_rating = sum(ratings) / len(ratings) if ratings else None
    total_reviews = sum(r.get("review_count", 0) for r in results)

    # searches 테이블에 저장
    search = (
        client.table("searches")
        .insert({
            "query": query,
            "avg_rating": avg_rating,
            "total_reviews": total_reviews,
            "platform_count": len(results),
        })
        .execute()
    )

    search_id = search.data[0]["id"]

    # platform_ratings 테이블에 저장
    if results:
        rows = [
            {
                "search_id": search_id,
                "platform": r["platform"],
                "rating": r.get("rating"),
                "rating_scale": r["rating_scale"],
                "normalized_rating": r.get("normalized_rating"),
                "review_count": r.get("review_count", 0),
                "book_title": r.get("book_title", ""),
                "url": r.get("url", ""),
            }
            for r in results
        ]
        client.table("platform_ratings").insert(rows).execute()

    return search.data[0]


def get_all_searches(
    client: Client,
    sort_by: str = "created_at",
    order: str = "desc",
    limit: int = 50,
    offset: int = 0,
    platform: str | None = None,
) -> dict:
    """
    검색 히스토리 조회 (최적화: 단일 쿼리 + DB 레벨 필터링)

    Returns:
        {"searches": [...], "total": int}
    """
    # 허용된 정렬 필드
    allowed_sort = {"created_at", "avg_rating", "total_reviews", "platform_count"}
    if sort_by not in allowed_sort:
        sort_by = "created_at"

    is_desc = order.lower() == "desc"

    # Foreign key 조인으로 한 번에 가져오기
    # platform_ratings(*)는 searches.id = platform_ratings.search_id 관계 활용
    query = (
        client.table("searches")
        .select("*, platform_ratings(*)", count="exact")
        .order(sort_by, desc=is_desc)
    )

    # 플랫폼 필터를 DB 레벨에서 적용
    if platform:
        # platform_ratings 테이블에서 해당 플랫폼이 있는 검색만 필터
        query = query.filter("platform_ratings.platform", "eq", platform)

    query = query.range(offset, offset + limit - 1)
    result = query.execute()

    searches = result.data
    total = result.count or len(searches)

    # Supabase는 중첩 객체를 ratings 키에 자동으로 매핑
    # platform_ratings(*)는 각 search의 "platform_ratings" 필드로 들어감
    for s in searches:
        s["ratings"] = s.pop("platform_ratings", [])

    return {"searches": searches, "total": total}
