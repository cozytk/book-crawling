"use client";

import { useState, useEffect, useCallback, useMemo } from "react";
import Link from "next/link";
import { getSearchHistory, SearchHistoryItem, PLATFORM_META } from "@/lib/api";

type SortBy = "created_at" | "avg_rating" | "total_reviews" | "platform_rating";
type Order = "asc" | "desc";

const ALL_PLATFORMS = Object.keys(PLATFORM_META);

function compareNullableNumber(a: number | null | undefined, b: number | null | undefined, desc: boolean): number {
  if (a == null && b == null) return 0;
  if (a == null) return 1;
  if (b == null) return -1;
  return desc ? b - a : a - b;
}

function getPlatformNormalizedRating(
  ratings: SearchHistoryItem["ratings"],
  platform: string
): number | null {
  const match = ratings.find((r) => r.platform === platform);
  return match?.normalized_rating ?? null;
}

function compareRatingsDesc(
  a: SearchHistoryItem["ratings"][number],
  b: SearchHistoryItem["ratings"][number]
): number {
  if (a.normalized_rating === null) return 1;
  if (b.normalized_rating === null) return -1;
  return b.normalized_rating - a.normalized_rating;
}

export default function HistoryPage() {
  const [allSearches, setAllSearches] = useState<SearchHistoryItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // 필터/정렬 상태
  const [sortBy, setSortBy] = useState<SortBy>("created_at");
  const [order, setOrder] = useState<Order>("desc");
  const [selectedPlatforms, setSelectedPlatforms] = useState<Set<string>>(
    new Set(ALL_PLATFORMS)
  );
  const [sortPlatform, setSortPlatform] = useState<string>("aladin");
  const [page, setPage] = useState(0);
  const pageSize = 20;

  const fetchData = useCallback(async (background = false) => {
    if (background) {
      setIsRefreshing(true);
    } else {
      setIsLoading(true);
    }
    setError(null);

    try {
      // 초기 1회에 넉넉히 로드하고, 이후 필터/정렬은 클라이언트에서 즉시 처리
      const data = await getSearchHistory({
        sort_by: "created_at",
        order: "desc",
        limit: 500,
        offset: 0,
        with_count: false,
      });
      setAllSearches(data.searches);
    } catch {
      setError("데이터를 불러올 수 없습니다");
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const allSelected = selectedPlatforms.size === ALL_PLATFORMS.length;

  const filteredSearches = useMemo(() => {
    if (allSelected) return allSearches;

    return allSearches.filter((search) =>
      search.ratings.some((r) => selectedPlatforms.has(r.platform))
    );
  }, [allSearches, selectedPlatforms, allSelected]);

  const sortedSearches = useMemo(() => {
    const desc = order === "desc";
    const sorted = [...filteredSearches];

    sorted.sort((a, b) => {
      if (sortBy === "created_at") {
        const aTs = new Date(a.created_at).getTime();
        const bTs = new Date(b.created_at).getTime();
        return desc ? bTs - aTs : aTs - bTs;
      }

      if (sortBy === "avg_rating") {
        const cmp = compareNullableNumber(a.avg_rating, b.avg_rating, desc);
        if (cmp !== 0) return cmp;
      }

      if (sortBy === "total_reviews") {
        const cmp = desc
          ? b.total_reviews - a.total_reviews
          : a.total_reviews - b.total_reviews;
        if (cmp !== 0) return cmp;
      }

      if (sortBy === "platform_rating") {
        const aRating = getPlatformNormalizedRating(a.ratings, sortPlatform);
        const bRating = getPlatformNormalizedRating(b.ratings, sortPlatform);
        const cmp = compareNullableNumber(aRating, bRating, desc);
        if (cmp !== 0) return cmp;
      }

      // tie-breaker: 최신순
      return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
    });

    return sorted;
  }, [filteredSearches, order, sortBy, sortPlatform]);

  const total = sortedSearches.length;

  useEffect(() => {
    const maxPage = Math.max(0, Math.ceil(total / pageSize) - 1);
    if (page > maxPage) {
      setPage(maxPage);
    }
  }, [total, page]);

  const pagedSearches = useMemo(() => {
    const start = page * pageSize;
    const end = start + pageSize;
    return sortedSearches.slice(start, end);
  }, [sortedSearches, page]);

  const platforms = Object.entries(PLATFORM_META);

  const toggleAllPlatforms = useCallback(() => {
    // 전체 선택 = 모든 플랫폼 표시
    setSelectedPlatforms(new Set(ALL_PLATFORMS));
    setPage(0);
  }, []);

  const selectSinglePlatform = useCallback((platform: string) => {
    // 플랫폼 태그 클릭 = 해당 플랫폼 단일 선택
    setSelectedPlatforms(new Set([platform]));
    setPage(0);
  }, []);

  const handleTagClick = useCallback((platform: string) => {
    setSelectedPlatforms(new Set([platform]));
    setPage(0);
  }, []);

  const hasData = allSearches.length > 0;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">검색 히스토리</h1>
        <Link href="/" className="text-sm text-blue-600 hover:text-blue-800">
          ← 검색으로 돌아가기
        </Link>
      </div>

      {/* 필터/정렬 컨트롤 */}
      <div className="bg-white rounded-xl border border-gray-200 p-4 space-y-4">
        <div className="flex flex-wrap gap-4 items-center">
          <div className="flex items-center gap-2">
            <label className="text-sm text-gray-600">정렬:</label>
            <select
              value={sortBy}
              onChange={(e) => {
                setSortBy(e.target.value as SortBy);
                setPage(0);
              }}
              className="text-sm border border-gray-300 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="created_at">검색일</option>
              <option value="avg_rating">평균 평점</option>
              <option value="total_reviews">리뷰 수</option>
              <option value="platform_rating">플랫폼 평점</option>
            </select>
          </div>

          {sortBy === "platform_rating" && (
            <div className="flex items-center gap-2">
              <label className="text-sm text-gray-600">기준 플랫폼:</label>
              <select
                value={sortPlatform}
                onChange={(e) => {
                  setSortPlatform(e.target.value);
                  setPage(0);
                }}
                className="text-sm border border-gray-300 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                {platforms.map(([key, meta]) => (
                  <option key={key} value={key}>
                    {meta.label}
                  </option>
                ))}
              </select>
            </div>
          )}

          <button
            onClick={() => {
              setOrder(order === "desc" ? "asc" : "desc");
              setPage(0);
            }}
            className="text-sm border border-gray-300 rounded-lg px-3 py-1.5 hover:bg-gray-50 transition-colors"
          >
            {order === "desc" ? "↓ 내림차순" : "↑ 오름차순"}
          </button>

          <button
            onClick={() => fetchData(true)}
            disabled={isRefreshing || isLoading}
            className="text-sm border border-gray-300 rounded-lg px-3 py-1.5 hover:bg-gray-50 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isRefreshing ? "새로고침 중..." : "히스토리 새로고침"}
          </button>

          <div className="ml-auto flex items-center gap-3">
            {isRefreshing && (
              <span className="text-xs text-blue-600 animate-pulse">
                최신 데이터 반영 중...
              </span>
            )}
            <span className="text-sm text-gray-400">총 {total}건</span>
          </div>
        </div>

        <div className="flex flex-wrap gap-2">
          <button
            onClick={toggleAllPlatforms}
            className={`px-3 py-1.5 rounded-full text-sm font-medium border transition-colors ${
              allSelected
                ? "bg-gray-800 text-white border-gray-800"
                : "bg-white text-gray-400 border-gray-300 hover:border-gray-400"
            }`}
          >
            전체
          </button>
          {ALL_PLATFORMS.map((platform) => {
            const meta = PLATFORM_META[platform];
            const enabled = selectedPlatforms.has(platform);
            return (
              <button
                key={platform}
                onClick={() => selectSinglePlatform(platform)}
                className="px-3 py-1.5 rounded-full text-sm font-medium border transition-colors"
                style={
                  enabled
                    ? {
                        backgroundColor: meta.color,
                        color: "#fff",
                        borderColor: meta.color,
                      }
                    : {
                        backgroundColor: "#fff",
                        color: "#9ca3af",
                        borderColor: "#d1d5db",
                      }
                }
              >
                {meta.label}
              </button>
            );
          })}
        </div>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg p-4 text-center">
          {error}
        </div>
      )}

      {isLoading && !hasData && (
        <div className="text-center py-12 text-gray-500">불러오는 중...</div>
      )}

      {!isLoading && pagedSearches.length === 0 && (
        <div className="text-center py-12 text-gray-500">검색 기록이 없습니다.</div>
      )}

      {pagedSearches.length > 0 && (
        <div className={`space-y-3 transition-opacity ${isRefreshing ? "opacity-70" : "opacity-100"}`}>
          {pagedSearches.map((search) => {
            const displayedRatings = allSelected
              ? search.ratings
              : search.ratings.filter((r) => selectedPlatforms.has(r.platform));

            const validRatings = displayedRatings
              .map((r) => r.normalized_rating)
              .filter((v): v is number => v !== null);

            const displayAvg = allSelected
              ? search.avg_rating
              : validRatings.length > 0
                ? validRatings.reduce((acc, v) => acc + v, 0) / validRatings.length
                : null;

            const displayReviews = allSelected
              ? search.total_reviews
              : displayedRatings.reduce((acc, r) => acc + r.review_count, 0);

            const displayPlatformCount = allSelected
              ? search.platform_count
              : displayedRatings.length;

            return (
              <div
                key={search.id}
                className="bg-white rounded-xl border border-gray-200 p-5 hover:shadow-md transition-shadow"
              >
                <div className="flex items-start justify-between mb-3">
                  <div>
                    <div className="flex items-center gap-3">
                      <h3 className="font-semibold text-lg">{search.query}</h3>
                      <Link
                        href={`/history/${search.id}`}
                        className="text-xs text-blue-600 hover:text-blue-800"
                      >
                        상세 보기
                      </Link>
                    </div>
                    <p className="text-xs text-gray-400 mt-1">
                      {new Date(search.created_at).toLocaleDateString("ko-KR", {
                        year: "numeric",
                        month: "long",
                        day: "numeric",
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                    </p>
                  </div>
                  <div className="text-right">
                    {displayAvg !== null && (
                      <p className="text-2xl font-bold tabular-nums">
                        {displayAvg.toFixed(2)}
                        <span className="text-sm font-normal text-gray-400">/10</span>
                      </p>
                    )}
                    <p className="text-xs text-gray-500">
                      {displayReviews.toLocaleString()}개 리뷰 · {displayPlatformCount}개 플랫폼
                    </p>
                  </div>
                </div>

                {displayedRatings.length > 0 && (
                  <div className="flex flex-wrap gap-2 mt-3">
                    {[...displayedRatings]
                      .sort(compareRatingsDesc)
                      .map((r) => {
                        const meta = PLATFORM_META[r.platform] || {
                          label: r.platform,
                          color: "#666",
                        };
                        return (
                          <button
                            key={r.platform}
                            onClick={() => handleTagClick(r.platform)}
                            className="inline-flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-full text-white"
                            style={{ backgroundColor: meta.color }}
                          >
                            {meta.label}
                            {r.normalized_rating !== null && (
                              <span className="font-bold">{r.normalized_rating.toFixed(1)}</span>
                            )}
                          </button>
                        );
                      })}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {total > pageSize && (
        <div className="flex justify-center gap-2 py-4">
          <button
            onClick={() => setPage(Math.max(0, page - 1))}
            disabled={page === 0}
            className="px-4 py-2 text-sm border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            이전
          </button>
          <span className="px-4 py-2 text-sm text-gray-600">
            {page + 1} / {Math.max(1, Math.ceil(total / pageSize))}
          </span>
          <button
            onClick={() => setPage(page + 1)}
            disabled={(page + 1) * pageSize >= total}
            className="px-4 py-2 text-sm border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            다음
          </button>
        </div>
      )}
    </div>
  );
}
