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
    sort_platform: str | None = None,
) -> dict:
    """
    검색 히스토리 조회

    Returns:
        {"searches": [...], "total": int}
    """
    # 허용된 정렬 필드
    allowed_sort = {
        "created_at",
        "avg_rating",
        "total_reviews",
        "platform_count",
        "platform_rating",
    }
    if sort_by not in allowed_sort:
        sort_by = "created_at"

    is_desc = order.lower() == "desc"
    base_columns = "id,query,avg_rating,total_reviews,platform_count,created_at"

    # 플랫폼 평점 정렬은 해당 플랫폼 relation 기준으로 order
    sort_target_platform = None
    if sort_by == "platform_rating":
        sort_target_platform = platform or sort_platform
        if not sort_target_platform:
            sort_by = "created_at"

    if sort_target_platform:
        # 플랫폼 평점 정렬은 platform_ratings 기준으로 먼저 정렬 후 searches를 조인
        query = (
            client.table("platform_ratings")
            .select(
                f"search_id, normalized_rating, searches!inner({base_columns})",
                count="exact",
            )
            .eq("platform", sort_target_platform)
            .order("normalized_rating", desc=is_desc)
            .range(offset, offset + limit - 1)
        )
    elif platform:
        # 플랫폼 필터는 inner join으로 search 목록만 빠르게 조회
        query = (
            client.table("searches")
            .select(f"{base_columns}, platform_ratings!inner(platform)", count="exact")
            .eq("platform_ratings.platform", platform)
            .order(sort_by, desc=is_desc)
            .range(offset, offset + limit - 1)
        )
    else:
        query = (
            client.table("searches")
            .select(base_columns, count="exact")
            .order(sort_by, desc=is_desc)
            .range(offset, offset + limit - 1)
        )

    result = query.execute()
    raw_rows = result.data or []
    total = result.count or len(raw_rows)

    if sort_target_platform:
        searches = []
        seen_ids: set[str] = set()
        for row in raw_rows:
            search = row.get("searches")
            if not search:
                continue
            sid = search.get("id")
            if not sid or sid in seen_ids:
                continue
            seen_ids.add(sid)
            searches.append(search)
    else:
        searches = raw_rows

    # relation 필드는 상세 ratings 조회 전에 제거
    for s in searches:
        s.pop("platform_ratings", None)

    if not searches:
        return {"searches": [], "total": total}

    # 현재 페이지 search_id 기준으로 ratings만 조회 (전체 join보다 빠름)
    search_ids = [s["id"] for s in searches]
    ratings_query = (
        client.table("platform_ratings")
        .select("*")
        .in_("search_id", search_ids)
    )
    if platform:
        ratings_query = ratings_query.eq("platform", platform)

    ratings_result = ratings_query.execute()
    ratings = ratings_result.data or []

    ratings_map: dict[str, list[dict]] = {}
    for rating in ratings:
        search_id = rating["search_id"]
        ratings_map.setdefault(search_id, []).append(rating)

    for s in searches:
        s["ratings"] = ratings_map.get(s["id"], [])

    return {"searches": searches, "total": total}
