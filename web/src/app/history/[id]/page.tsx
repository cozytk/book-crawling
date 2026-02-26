"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { getSearch, searchBook, SearchResult, PLATFORM_META } from "@/lib/api";

const compareNormalizedDesc = (a: SearchResult["ratings"][number], b: SearchResult["ratings"][number]) => {
  if (a.normalized_rating === null) return 1;
  if (b.normalized_rating === null) return -1;
  return b.normalized_rating - a.normalized_rating;
};

export default function HistoryDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const id = params.id;

  const [result, setResult] = useState<SearchResult | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isUpdating, setIsUpdating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadDetail = useCallback(async () => {
    if (!id) return;
    setIsLoading(true);
    setError(null);
    try {
      const data = await getSearch(id);
      setResult(data);
    } catch {
      setError("검색 기록을 불러올 수 없습니다");
    } finally {
      setIsLoading(false);
    }
  }, [id]);

  const handleRefresh = useCallback(async () => {
    if (!result?.search.query) return;
    setIsUpdating(true);
    setError(null);
    try {
      const refreshed = await searchBook(
        result.search.query,
        undefined,
        { force_refresh: true }
      );
      if (refreshed.search.id) {
        router.replace(`/history/${refreshed.search.id}`);
      } else {
        await loadDetail();
      }
    } catch {
      setError("업데이트 중 오류가 발생했습니다");
    } finally {
      setIsUpdating(false);
    }
  }, [loadDetail, result?.search.query, router]);

  useEffect(() => {
    loadDetail();
  }, [loadDetail]);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">검색 히스토리 상세</h1>
        <div className="flex items-center gap-3">
          <button
            onClick={handleRefresh}
            disabled={!result || isUpdating}
            className="px-3 py-1.5 text-sm border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isUpdating ? "업데이트 중..." : "결과 업데이트"}
          </button>
          <Link
            href="/history"
            className="text-sm text-blue-600 hover:text-blue-800"
          >
            ← 히스토리로 돌아가기
          </Link>
        </div>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg p-4 text-center">
          {error}
        </div>
      )}

      {isLoading && (
        <div className="text-center py-12 text-gray-500">불러오는 중...</div>
      )}

      {!isLoading && result && (
        <>
          <div className="bg-white rounded-xl border border-gray-200 p-5">
            <h2 className="text-xl font-semibold">{result.search.query}</h2>
            <p className="text-xs text-gray-400 mt-1">
              {result.search.created_at
                ? new Date(result.search.created_at).toLocaleString("ko-KR")
                : "-"}
            </p>

            <div className="flex flex-wrap gap-6 mt-4 text-sm">
              <div>
                <span className="text-gray-500">평균 평점</span>
                <p className="text-xl font-bold">
                  {result.search.avg_rating !== null
                    ? `${result.search.avg_rating.toFixed(2)} / 10`
                    : "N/A"}
                </p>
              </div>
              <div>
                <span className="text-gray-500">리뷰 수</span>
                <p className="text-xl font-bold">
                  {result.search.total_reviews.toLocaleString()}개
                </p>
              </div>
              <div>
                <span className="text-gray-500">플랫폼 수</span>
                <p className="text-xl font-bold">{result.search.platform_count}개</p>
              </div>
            </div>
          </div>

          <div className="space-y-3">
            {[...result.ratings]
              .sort(compareNormalizedDesc)
              .map((rating) => {
                const meta = PLATFORM_META[rating.platform] || {
                  label: rating.platform,
                  color: "#666",
                };
                return (
                  <div
                    key={rating.platform}
                    className="bg-white rounded-xl border border-gray-200 p-5"
                  >
                    <div className="flex items-center justify-between mb-3">
                      <span
                        className="text-sm font-semibold px-2.5 py-1 rounded-full text-white"
                        style={{ backgroundColor: meta.color }}
                      >
                        {meta.label}
                      </span>
                      <span className="text-2xl font-bold tabular-nums">
                        {rating.normalized_rating !== null
                          ? rating.normalized_rating.toFixed(1)
                          : "N/A"}
                        <span className="text-sm font-normal text-gray-400">/10</span>
                      </span>
                    </div>
                    <p className="text-sm text-gray-700 mb-1">
                      {rating.book_title || "-"}
                    </p>
                    <p className="text-xs text-gray-500">
                      {rating.review_count.toLocaleString()}개 리뷰
                    </p>
                    <a
                      href={rating.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="mt-3 inline-block text-xs text-blue-600 hover:text-blue-800"
                    >
                      상세 페이지 보기
                    </a>
                  </div>
                );
              })}
          </div>
        </>
      )}
    </div>
  );
}
