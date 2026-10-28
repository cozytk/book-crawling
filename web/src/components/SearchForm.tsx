"use client";

interface SearchFormProps {
  onSearch: (query: string) => void;
  query: string;
  onQueryChange: (query: string) => void;
  isLoading: boolean;
  disabled?: boolean;
}

export default function SearchForm({ onSearch, query, onQueryChange, isLoading, disabled }: SearchFormProps) {
  return (
    <form className="search-form" onSubmit={(event) => {
      event.preventDefault();
      if (query.trim() && !disabled) onSearch(query.trim());
    }} role="search">
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden="true"><circle cx="10.8" cy="10.8" r="7.3" /><path d="m16 16 5 5" /></svg>
      <input type="search" name="q" value={query} onChange={(event) => onQueryChange(event.target.value)}
        placeholder="어떤 책이 궁금한가요?" aria-label="책 제목 또는 ISBN" maxLength={300} autoComplete="off" />
      <button type="submit" className="primary-button" disabled={disabled || !query.trim()}>
        {isLoading ? "다시 검색" : "평점 비교"}<span aria-hidden="true">↗</span>
      </button>
    </form>
  );
}
