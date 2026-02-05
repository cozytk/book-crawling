"use client";

import { useState } from "react";

interface SearchFormProps {
  onSearch: (query: string) => void;
  isLoading: boolean;
  initialQuery?: string;
}

export default function SearchForm({
  onSearch,
  isLoading,
  initialQuery = "",
}: SearchFormProps) {
  const [query, setQuery] = useState(initialQuery);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (query.trim() && !isLoading) {
      onSearch(query.trim());
    }
  };

  return (
    <form onSubmit={handleSubmit} className="flex gap-3">
      <input
        type="text"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="책 제목을 입력하세요"
        className="flex-1 px-4 py-3 border border-gray-300 rounded-lg
                   focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent
                   text-base placeholder-gray-400"
        disabled={isLoading}
      />
      <button
        type="submit"
        disabled={isLoading || !query.trim()}
        className="px-6 py-3 bg-blue-600 text-white rounded-lg font-medium
                   hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed
                   transition-colors"
      >
        {isLoading ? (
          <span className="flex items-center gap-2">
            <svg
              className="animate-spin h-4 w-4"
              viewBox="0 0 24 24"
              fill="none"
            >
              <circle
                className="opacity-25"
                cx="12"
                cy="12"
                r="10"
                stroke="currentColor"
                strokeWidth="4"
              />
              <path
                className="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
              />
            </svg>
            검색 중...
          </span>
        ) : (
          "검색"
        )}
      </button>
    </form>
  );
}
