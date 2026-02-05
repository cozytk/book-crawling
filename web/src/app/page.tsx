"use client";

import { useState, useCallback, useMemo } from "react";
import { useRouter } from "next/navigation";
import SearchForm from "@/components/SearchForm";
import RatingGrid from "@/components/RatingGrid";
import LoadingSkeleton from "@/components/LoadingSkeleton";
import {
  searchBookStream,
  checkCache,
  PlatformRating,
  PLATFORM_META,
} from "@/lib/api";
import ReactMarkdown from "react-markdown";

type SortOption = "rating_desc" | "rating_asc" | "reviews_desc" | "reviews_asc";

const SORT_OPTIONS: { value: SortOption; label: string }[] = [
  { value: "rating_desc", label: "평점 높은 순" },
  { value: "rating_asc", label: "평점 낮은 순" },
  { value: "reviews_desc", label: "리뷰 많은 순" },
  { value: "reviews_asc", label: "리뷰 적은 순" },
];

const ALL_PLATFORMS = Object.keys(PLATFORM_META);

export default function Home() {
  const router = useRouter();
  const [ratings, setRatings] = useState<PlatformRating[]>([]);
  const [summary, setSummary] = useState<{
    id: string | null;
    query: string;
    avg_rating: number | null;
    total_reviews: number;
    platform_count: number;
  } | null>(null);
  const [source, setSource] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [description, setDescription] = useState<string | null>(null);

  // Cache choice state
  const [cachePrompt, setCachePrompt] = useState<{
    query: string;
    search: Record<string, unknown>;
  } | null>(null);

  // Platform filter state
  const [enabledPlatforms, setEnabledPlatforms] = useState<Set<string>>(
    new Set(ALL_PLATFORMS)
  );

  // Sort state
  const [sortOption, setSortOption] = useState<SortOption>("rating_desc");

  const sortedRatings = useMemo(() => {
    const sorted = [...ratings];
    switch (sortOption) {
      case "rating_desc":
        return sorted.sort((a, b) => {
          if (a.normalized_rating === null) return 1;
          if (b.normalized_rating === null) return -1;
          return b.normalized_rating - a.normalized_rating;
        });
      case "rating_asc":
        return sorted.sort((a, b) => {
          if (a.normalized_rating === null) return 1;
          if (b.normalized_rating === null) return -1;
          return a.normalized_rating - b.normalized_rating;
        });
      case "reviews_desc":
        return sorted.sort((a, b) => b.review_count - a.review_count);
      case "reviews_asc":
        return sorted.sort((a, b) => a.review_count - b.review_count);
      default:
        return sorted;
    }
  }, [ratings, sortOption]);

  const executeSearch = useCallback(
    async (query: string, forceRefresh: boolean = false) => {
      setIsLoading(true);
      setError(null);
      setRatings([]);
      setSummary(null);
      setSource(null);
      setDescription(null);
      setCachePrompt(null);

      const activePlatforms = Array.from(enabledPlatforms);
      const platforms =
        activePlatforms.length === ALL_PLATFORMS.length
          ? undefined
          : activePlatforms;

      try {
        await searchBookStream(
          query,
          (rating) => {
            setRatings((prev) => [...prev, rating]);
          },
          (searchSummary, src) => {
            setSummary(searchSummary);
            setSource(src);
            setIsLoading(false);
          },
          (err) => {
            setError(err);
            setIsLoading(false);
          },
          (chunk) => {
            setDescription((prev) => (prev || "") + chunk);
          },
          platforms,
          forceRefresh
        );

        const params = new URLSearchParams({ q: query });
        router.push(`/?${params.toString()}`, { scroll: false });
      } catch (e) {
        setError(
          e instanceof Error ? e.message : "검색 중 오류가 발생했습니다"
        );
        setIsLoading(false);
      }
    },
    [router, enabledPlatforms]
  );

  const handleSearch = useCallback(
    async (query: string) => {
      // First check cache
      try {
        const cacheResult = await checkCache(query);
        if (cacheResult.cached && cacheResult.search) {
          setCachePrompt({ query, search: cacheResult.search as Record<string, unknown> });
          return;
        }
      } catch {
        // Cache check failed, proceed with normal search
      }

      executeSearch(query);
    },
    [executeSearch]
  );

  const handleUseCached = useCallback(() => {
    if (!cachePrompt) return;
    executeSearch(cachePrompt.query, false);
  }, [cachePrompt, executeSearch]);

  const handleForceRefresh = useCallback(() => {
    if (!cachePrompt) return;
    executeSearch(cachePrompt.query, true);
  }, [cachePrompt, executeSearch]);

  const handleDismissCache = useCallback(() => {
    setCachePrompt(null);
  }, []);

  // Platform toggle handlers
  const toggleAllPlatforms = useCallback(() => {
    setEnabledPlatforms((prev) => {
      if (prev.size === ALL_PLATFORMS.length) {
        return new Set<string>();
      }
      return new Set(ALL_PLATFORMS);
    });
  }, []);

  const togglePlatform = useCallback((platform: string) => {
    setEnabledPlatforms((prev) => {
      const next = new Set(prev);
      if (next.has(platform)) {
        next.delete(platform);
      } else {
        next.add(platform);
      }
      return next;
    });
  }, []);

  const allEnabled = enabledPlatforms.size === ALL_PLATFORMS.length;
  const noneEnabled = enabledPlatforms.size === 0;

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

      {/* 플랫폼 필터 토글 */}
      <div className="max-w-2xl mx-auto">
        <div className="flex flex-wrap gap-2 justify-center">
          <button
            onClick={toggleAllPlatforms}
            className={`px-3 py-1.5 rounded-full text-sm font-medium border transition-colors ${
              allEnabled
                ? "bg-gray-800 text-white border-gray-800"
                : "bg-white text-gray-400 border-gray-300 hover:border-gray-400"
            }`}
          >
            전체
          </button>
          {ALL_PLATFORMS.map((platform) => {
            const meta = PLATFORM_META[platform];
            const enabled = enabledPlatforms.has(platform);
            return (
              <button
                key={platform}
                onClick={() => togglePlatform(platform)}
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
        {noneEnabled && (
          <p className="text-center text-xs text-red-500 mt-2">
            최소 1개 플랫폼을 선택해주세요
          </p>
        )}
      </div>

      {/* 캐시 확인 배너 */}
      {cachePrompt && (
        <div className="max-w-2xl mx-auto bg-amber-50 border border-amber-200 rounded-xl p-5">
          <p className="text-amber-800 font-medium mb-3">
            &ldquo;{cachePrompt.query}&rdquo;에 대한 이전 검색 결과가
            있습니다. 캐시된 결과를 볼까요?
          </p>
          <div className="flex gap-3">
            <button
              onClick={handleUseCached}
              className="px-4 py-2 bg-amber-600 text-white rounded-lg text-sm font-medium hover:bg-amber-700 transition-colors"
            >
              캐시 결과 보기
            </button>
            <button
              onClick={handleForceRefresh}
              className="px-4 py-2 bg-white text-amber-700 border border-amber-300 rounded-lg text-sm font-medium hover:bg-amber-100 transition-colors"
            >
              새로 검색
            </button>
            <button
              onClick={handleDismissCache}
              className="px-4 py-2 text-gray-500 text-sm hover:text-gray-700 transition-colors"
            >
              취소
            </button>
          </div>
        </div>
      )}

      {/* 에러 */}
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg p-4 text-center">
          {error}
        </div>
      )}

      {/* 책 소개 (AI 생성) */}
      {description && (
        <div className="bg-gradient-to-br from-slate-50 to-blue-50 border border-slate-200 rounded-2xl p-8 shadow-sm">
          <h3 className="text-sm font-semibold text-slate-500 uppercase tracking-wider mb-4">
            책 소개
          </h3>
          <div className="prose prose-slate max-w-none text-[15px] leading-[1.8] [&_h1]:text-xl [&_h1]:font-bold [&_h1]:mt-6 [&_h1]:mb-3 [&_h2]:text-lg [&_h2]:font-semibold [&_h2]:mt-5 [&_h2]:mb-2 [&_h3]:text-base [&_h3]:font-semibold [&_h3]:mt-4 [&_h3]:mb-2 [&_p]:mb-3 [&_p]:text-slate-700 [&_ul]:list-disc [&_ul]:pl-6 [&_ul]:mb-3 [&_ol]:list-decimal [&_ol]:pl-6 [&_ol]:mb-3 [&_li]:mb-1.5 [&_li]:text-slate-700 [&_strong]:font-semibold [&_strong]:text-slate-900 [&_em]:italic [&_a]:text-blue-600 [&_a]:underline [&_a]:underline-offset-2 [&_blockquote]:border-l-4 [&_blockquote]:border-slate-300 [&_blockquote]:pl-4 [&_blockquote]:italic [&_blockquote]:text-slate-500 [&_blockquote]:my-4 [&_hr]:my-6 [&_hr]:border-slate-200">
            <ReactMarkdown>{description}</ReactMarkdown>
          </div>
        </div>
      )}

      {/* 소개 로딩 중 (검색 시작했지만 description 아직 없을 때) */}
      {isLoading && !description && (
        <div className="bg-gradient-to-br from-slate-50 to-blue-50 border border-slate-200 rounded-2xl p-8 shadow-sm animate-pulse">
          <div className="h-3 bg-slate-200 rounded w-16 mb-5"></div>
          <div className="space-y-3">
            <div className="h-3.5 bg-slate-100 rounded w-full"></div>
            <div className="h-3.5 bg-slate-100 rounded w-11/12"></div>
            <div className="h-3.5 bg-slate-100 rounded w-5/6"></div>
            <div className="h-3.5 bg-slate-100 rounded w-full"></div>
            <div className="h-3.5 bg-slate-100 rounded w-4/6"></div>
          </div>
        </div>
      )}

      {/* 로딩 중 + 이미 도착한 결과 */}
      {isLoading && ratings.length === 0 && <LoadingSkeleton />}

      {/* 요약 (완료 시) */}
      {summary && (
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <h2 className="text-lg font-semibold mb-4">
            &ldquo;{summary.query}&rdquo; 검색 결과
            {source === "cache" && (
              <span className="ml-2 text-xs font-normal text-gray-400 bg-gray-100 px-2 py-1 rounded-full">
                캐시됨
              </span>
            )}
          </h2>
          <div className="flex gap-8 text-sm">
            {summary.avg_rating !== null && (
              <div>
                <span className="text-gray-500">평균 평점</span>
                <p className="text-2xl font-bold">
                  {summary.avg_rating.toFixed(2)}
                  <span className="text-sm font-normal text-gray-400">
                    /10
                  </span>
                </p>
              </div>
            )}
            <div>
              <span className="text-gray-500">총 리뷰 수</span>
              <p className="text-2xl font-bold">
                {summary.total_reviews.toLocaleString()}
                <span className="text-sm font-normal text-gray-400">개</span>
              </p>
            </div>
            <div>
              <span className="text-gray-500">플랫폼</span>
              <p className="text-2xl font-bold">
                {summary.platform_count}
                <span className="text-sm font-normal text-gray-400">개</span>
              </p>
            </div>
          </div>
        </div>
      )}

      {/* 결과 카드 (스트리밍 중에도 표시) */}
      {ratings.length > 0 && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            {isLoading && (
              <p className="text-sm text-gray-500">
                {ratings.length}개 플랫폼 결과 수신 중...
              </p>
            )}
            {!isLoading && <div />}
            <div className="flex items-center gap-2">
              <label
                htmlFor="sort-select"
                className="text-sm text-gray-500"
              >
                정렬:
              </label>
              <select
                id="sort-select"
                value={sortOption}
                onChange={(e) => setSortOption(e.target.value as SortOption)}
                className="text-sm border border-gray-300 rounded-lg px-3 py-1.5 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                {SORT_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <RatingGrid ratings={sortedRatings} />
        </div>
      )}
    </div>
  );
}
