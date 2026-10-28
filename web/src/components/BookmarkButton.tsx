"use client";

import { useState, useEffect } from "react";
import { isBookmarked, toggleBookmark, Bookmark } from "@/lib/bookmarks";

interface BookmarkButtonProps {
  searchId: string;
  query: string;
  avgRating: number | null;
  totalReviews: number | null;
  platformCount: number;
  size?: "sm" | "md";
}

export default function BookmarkButton({
  searchId,
  query,
  avgRating,
  totalReviews,
  platformCount,
  size = "md",
}: BookmarkButtonProps) {
  const [bookmarked, setBookmarked] = useState(false);

  useEffect(() => {
    setBookmarked(isBookmarked(searchId));
  }, [searchId]);

  const handleClick = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    const bookmark: Bookmark = {
      searchId,
      query,
      avgRating,
      totalReviews,
      platformCount,
      bookmarkedAt: new Date().toISOString(),
    };
    const added = toggleBookmark(bookmark);
    setBookmarked(added);
  };

  const sizeClass = size === "sm" ? "w-5 h-5" : "w-6 h-6";

  return (
    <button
      onClick={handleClick}
      title={bookmarked ? "읽을 책에서 제거" : "읽을 책에 추가"}
      aria-label={bookmarked ? "읽을 책에서 제거" : "읽을 책에 추가"}
      aria-pressed={bookmarked}
      className="bookmark-button"
    >
      <svg
        className={sizeClass}
        viewBox="0 0 24 24"
        fill={bookmarked ? "#2563eb" : "none"}
        stroke={bookmarked ? "#2563eb" : "#9ca3af"}
        strokeWidth={2}
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z"
        />
      </svg>
    </button>
  );
}
