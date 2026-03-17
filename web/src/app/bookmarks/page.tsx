"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { getBookmarks, removeBookmark, Bookmark } from "@/lib/bookmarks";

export default function BookmarksPage() {
  const [bookmarks, setBookmarks] = useState<Bookmark[]>([]);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    setBookmarks(getBookmarks());
    setLoaded(true);
  }, []);

  const handleRemove = (searchId: string) => {
    removeBookmark(searchId);
    setBookmarks(getBookmarks());
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">읽을 책</h1>
        <Link href="/" className="text-sm text-blue-600 hover:text-blue-800">
          ← 검색으로 돌아가기
        </Link>
      </div>

      {!loaded && (
        <div className="text-center py-12 text-gray-500">불러오는 중...</div>
      )}

      {loaded && bookmarks.length === 0 && (
        <div className="text-center py-16 space-y-3">
          <svg
            className="w-12 h-12 mx-auto text-gray-300"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth={1.5}
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z"
            />
          </svg>
          <p className="text-gray-500">저장한 책이 없습니다</p>
          <p className="text-sm text-gray-400">
            검색 결과나 히스토리에서 북마크 아이콘을 눌러 추가하세요
          </p>
        </div>
      )}

      {bookmarks.length > 0 && (
        <div className="space-y-3">
          {bookmarks.map((b) => (
            <div
              key={b.searchId}
              className="bg-white rounded-xl border border-gray-200 p-5 hover:shadow-md transition-shadow"
            >
              <div className="flex items-start justify-between">
                <div>
                  <div className="flex items-center gap-3">
                    <h3 className="font-semibold text-lg">{b.query}</h3>
                    <Link
                      href={`/history/${b.searchId}`}
                      className="text-xs text-blue-600 hover:text-blue-800"
                    >
                      상세 보기
                    </Link>
                  </div>
                  <p className="text-xs text-gray-400 mt-1">
                    {new Date(b.bookmarkedAt).toLocaleDateString("ko-KR", {
                      year: "numeric",
                      month: "long",
                      day: "numeric",
                    })}{" "}
                    저장
                  </p>
                </div>
                <div className="flex items-center gap-3">
                  <div className="text-right">
                    {b.avgRating !== null && (
                      <p className="text-2xl font-bold tabular-nums">
                        {b.avgRating.toFixed(2)}
                        <span className="text-sm font-normal text-gray-400">
                          /10
                        </span>
                      </p>
                    )}
                    <p className="text-xs text-gray-500">
                      {b.totalReviews.toLocaleString()}개 리뷰 ·{" "}
                      {b.platformCount}개 플랫폼
                    </p>
                  </div>
                  <button
                    onClick={() => handleRemove(b.searchId)}
                    title="읽을 책에서 제거"
                    className="p-1 rounded-md hover:bg-red-50 transition-colors"
                  >
                    <svg
                      className="w-5 h-5 text-gray-400 hover:text-red-500"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth={2}
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        d="M6 18L18 6M6 6l12 12"
                      />
                    </svg>
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
