const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface PlatformRating {
  platform: string;
  rating: number | null;
  rating_scale: number;
  normalized_rating: number | null;
  review_count: number;
  book_title: string;
  url: string;
  crawled_at: string;
}

export interface SearchResult {
  source: "cache" | "crawl";
  search: {
    id: string | null;
    query: string;
    avg_rating: number | null;
    total_reviews: number;
    platform_count: number;
  };
  ratings: PlatformRating[];
}

export interface PlatformInfo {
  name: string;
  type: "domestic" | "foreign";
}

export async function searchBook(
  query: string,
  platforms?: string[]
): Promise<SearchResult> {
  const res = await fetch(`${API_URL}/api/search`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, platforms: platforms || null }),
  });

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: "서버 오류" }));
    throw new Error(error.detail || `HTTP ${res.status}`);
  }

  return res.json();
}

export async function getSearch(searchId: string): Promise<SearchResult> {
  const res = await fetch(`${API_URL}/api/search/${searchId}`);
  if (!res.ok) throw new Error("검색 결과를 찾을 수 없습니다");
  return res.json();
}

export async function getPlatforms(): Promise<PlatformInfo[]> {
  const res = await fetch(`${API_URL}/api/platforms`);
  if (!res.ok) throw new Error("플랫폼 목록을 가져올 수 없습니다");
  const data = await res.json();
  return data.platforms;
}

/** 플랫폼별 표시 정보 */
export const PLATFORM_META: Record<
  string,
  { label: string; color: string }
> = {
  aladin: { label: "알라딘", color: "#2b7de9" },
  kyobo: { label: "교보문고", color: "#00264d" },
  yes24: { label: "Yes24", color: "#ff3c3c" },
  sarak: { label: "사락", color: "#6b4fbb" },
  watcha: { label: "왓챠", color: "#ff0558" },
  goodreads: { label: "Goodreads", color: "#553b08" },
  amazon: { label: "Amazon", color: "#ff9900" },
  librarything: { label: "LibraryThing", color: "#425a2b" },
};
