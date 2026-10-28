"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { getSearch, searchBook, SearchResult } from "@/lib/api";
import BookmarkButton from "@/components/BookmarkButton";
import RatingGrid from "@/components/RatingGrid";

const compareNormalizedDesc = (a: SearchResult["ratings"][number], b: SearchResult["ratings"][number]) => {
  if (a.normalized_rating === null && b.normalized_rating === null) return 0;
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
        result.search.requested_platforms ?? result.ratings.map((rating) => rating.platform),
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
  }, [loadDetail, result, router]);

  useEffect(() => {
    loadDetail();
  }, [loadDetail]);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap gap-3 items-center justify-between">
        <h1 className="text-2xl font-bold">검색 결과 상세</h1>
        <div className="flex flex-wrap items-center gap-3">
          {result && result.search.id && (
            <BookmarkButton
              searchId={result.search.id}
              query={result.search.query}
              avgRating={result.search.avg_rating}
              totalReviews={result.search.total_reviews}
              platformCount={result.search.platform_count}
            />
          )}
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
            ← 기록로 돌아가기
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
          {result.search.legacy_validation && <p className="notice">이전 수집 규칙으로 저장한 결과입니다. 결과 업데이트를 누르면 현재 기준으로 다시 확인합니다.</p>}
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
                    : "평점 없음"}
                </p>
              </div>
              <div>
                <span className="text-gray-500">평가 수</span>
                <p className="text-xl font-bold">
                  {result.search.total_reviews == null ? "미확인" : `${result.search.total_reviews.toLocaleString()}개`}
                </p>
              </div>
              <div>
                <span className="text-gray-500">플랫폼 수</span>
                <p className="text-xl font-bold">{result.search.platform_count}개</p>
              </div>
            </div>
          </div>

          <RatingGrid ratings={[...result.ratings].sort(compareNormalizedDesc)} />
        </>
      )}
    </div>
  );
}
