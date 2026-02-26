"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { getSearchHistory, SearchHistoryItem, PLATFORM_META } from "@/lib/api";

type SortBy = "created_at" | "avg_rating" | "total_reviews";
type Order = "asc" | "desc";

export default function HistoryPage() {
  const [searches, setSearches] = useState<SearchHistoryItem[]>([]);
  const [total, setTotal] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // 필터/정렬 상태
  const [sortBy, setSortBy] = useState<SortBy>("created_at");
  const [order, setOrder] = useState<Order>("desc");
  const [platformFilter, setPlatformFilter] = useState<string>("");
  const [page, setPage] = useState(0);
  const pageSize = 20;

  const fetchData = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await getSearchHistory({
        sort_by: sortBy,
        order,
        limit: pageSize,
        offset: page * pageSize,
        platform: platformFilter || undefined,
      });
      setSearches(data.searches);
      setTotal(data.total);
    } catch {
      setError("데이터를 불러올 수 없습니다");
    } finally {
      setIsLoading(false);
    }
  }, [sortBy, order, platformFilter, page]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // 플랫폼별 best 찾기
  const getBestByPlatform = (ratings: SearchHistoryItem["ratings"]) => {
    if (!ratings || ratings.length === 0) return null;
    const sorted = [...ratings]
      .filter((r) => r.normalized_rating !== null)
      .sort((a, b) => (b.normalized_rating || 0) - (a.normalized_rating || 0));
    return sorted[0] || null;
  };

  const platforms = Object.entries(PLATFORM_META);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">검색 히스토리</h1>
        <Link
          href="/"
          className="text-sm text-blue-600 hover:text-blue-800"
        >
          ← 검색으로 돌아가기
        </Link>
      </div>

      {/* 필터/정렬 컨트롤 */}
      <div className="bg-white rounded-xl border border-gray-200 p-4">
        <div className="flex flex-wrap gap-4 items-center">
          {/* 정렬 기준 */}
          <div className="flex items-center gap-2">
            <label className="text-sm text-gray-600">정렬:</label>
            <select
              value={sortBy}
              onChange={(e) => { setSortBy(e.target.value as SortBy); setPage(0); }}
              className="text-sm border border-gray-300 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="created_at">검색일</option>
              <option value="avg_rating">평균 평점</option>
              <option value="total_reviews">리뷰 수</option>
            </select>
          </div>

          {/* 정렬 순서 */}
          <button
            onClick={() => { setOrder(order === "desc" ? "asc" : "desc"); setPage(0); }}
            className="text-sm border border-gray-300 rounded-lg px-3 py-1.5 hover:bg-gray-50 transition-colors"
          >
            {order === "desc" ? "↓ 내림차순" : "↑ 오름차순"}
          </button>

          {/* 플랫폼 필터 */}
          <div className="flex items-center gap-2">
            <label className="text-sm text-gray-600">플랫폼:</label>
            <select
              value={platformFilter}
              onChange={(e) => { setPlatformFilter(e.target.value); setPage(0); }}
              className="text-sm border border-gray-300 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="">전체</option>
              {platforms.map(([key, meta]) => (
                <option key={key} value={key}>
                  {meta.label}
                </option>
              ))}
            </select>
          </div>

          <span className="text-sm text-gray-400 ml-auto">
            총 {total}건
          </span>
        </div>
      </div>

      {/* 에러 */}
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg p-4 text-center">
          {error}
        </div>
      )}

      {/* 로딩 */}
      {isLoading && (
        <div className="text-center py-12 text-gray-500">불러오는 중...</div>
      )}

      {/* 결과 목록 */}
      {!isLoading && searches.length === 0 && (
        <div className="text-center py-12 text-gray-500">
          검색 기록이 없습니다.
        </div>
      )}

      {!isLoading && searches.length > 0 && (
        <div className="space-y-3">
          {searches.map((search) => {
            const best = getBestByPlatform(search.ratings);
            return (
              <div
                key={search.id}
                className="bg-white rounded-xl border border-gray-200 p-5 hover:shadow-md transition-shadow"
              >
                <div className="flex items-start justify-between mb-3">
                  <div>
                    <h3 className="font-semibold text-lg">{search.query}</h3>
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
                    {search.avg_rating !== null && (
                      <p className="text-2xl font-bold tabular-nums">
                        {search.avg_rating.toFixed(2)}
                        <span className="text-sm font-normal text-gray-400">/10</span>
                      </p>
                    )}
                    <p className="text-xs text-gray-500">
                      {search.total_reviews.toLocaleString()}개 리뷰 · {search.platform_count}개 플랫폼
                    </p>
                  </div>
                </div>

                {/* 플랫폼별 평점 미니 뷰 */}
                {search.ratings && search.ratings.length > 0 && (
                  <div className="flex flex-wrap gap-2 mt-3">
                    {[...search.ratings]
                      .sort((a, b) => (b.normalized_rating || 0) - (a.normalized_rating || 0))
                      .map((r) => {
                        const meta = PLATFORM_META[r.platform] || { label: r.platform, color: "#666" };
                        return (
                          <span
                            key={r.platform}
                            className="inline-flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-full text-white"
                            style={{ backgroundColor: meta.color }}
                          >
                            {meta.label}
                            {r.normalized_rating !== null && (
                              <span className="font-bold">{r.normalized_rating.toFixed(1)}</span>
                            )}
                          </span>
                        );
                      })}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* 페이지네이션 */}
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
            {page + 1} / {Math.ceil(total / pageSize)}
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
