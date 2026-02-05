"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import SearchForm from "@/components/SearchForm";
import RatingGrid from "@/components/RatingGrid";
import LoadingSkeleton from "@/components/LoadingSkeleton";
import { searchBook, SearchResult } from "@/lib/api";

export default function Home() {
  const router = useRouter();
  const [result, setResult] = useState<SearchResult | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSearch = async (query: string) => {
    setIsLoading(true);
    setError(null);
    setResult(null);

    try {
      const data = await searchBook(query);
      setResult(data);

      // URL 업데이트 (뒤로가기 지원)
      const params = new URLSearchParams({ q: query });
      router.push(`/?${params.toString()}`, { scroll: false });
    } catch (e) {
      setError(e instanceof Error ? e.message : "검색 중 오류가 발생했습니다");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="space-y-8">
      {/* 히어로 섹션 */}
      <div className="text-center space-y-4 py-8">
        <h1 className="text-3xl font-bold">책 평점 비교</h1>
        <p className="text-gray-500">
          8개 플랫폼의 평점을 한번에 비교하세요
        </p>
      </div>

      {/* 검색 폼 */}
      <div className="max-w-2xl mx-auto">
        <SearchForm onSearch={handleSearch} isLoading={isLoading} />
      </div>

      {/* 에러 */}
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg p-4 text-center">
          {error}
        </div>
      )}

      {/* 로딩 */}
      {isLoading && <LoadingSkeleton />}

      {/* 결과 */}
      {result && !isLoading && (
        <div className="space-y-6">
          {/* 요약 */}
          <div className="bg-white rounded-xl border border-gray-200 p-6">
            <h2 className="text-lg font-semibold mb-4">
              &ldquo;{result.search.query}&rdquo; 검색 결과
              {result.source === "cache" && (
                <span className="ml-2 text-xs font-normal text-gray-400 bg-gray-100 px-2 py-1 rounded-full">
                  캐시됨
                </span>
              )}
            </h2>
            <div className="flex gap-8 text-sm">
              {result.search.avg_rating !== null && (
                <div>
                  <span className="text-gray-500">평균 평점</span>
                  <p className="text-2xl font-bold">
                    {result.search.avg_rating.toFixed(2)}
                    <span className="text-sm font-normal text-gray-400">
                      /10
                    </span>
                  </p>
                </div>
              )}
              <div>
                <span className="text-gray-500">총 리뷰 수</span>
                <p className="text-2xl font-bold">
                  {result.search.total_reviews.toLocaleString()}
                  <span className="text-sm font-normal text-gray-400">개</span>
                </p>
              </div>
              <div>
                <span className="text-gray-500">플랫폼</span>
                <p className="text-2xl font-bold">
                  {result.search.platform_count}
                  <span className="text-sm font-normal text-gray-400">개</span>
                </p>
              </div>
            </div>
          </div>

          {/* 카드 그리드 */}
          <RatingGrid ratings={result.ratings} />
        </div>
      )}
    </div>
  );
}
