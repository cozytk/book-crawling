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

/** 캐시 확인 API */
export interface CacheCheckResult {
  cached: boolean;
  search?: SearchResult["search"];
}

export async function checkCache(query: string): Promise<CacheCheckResult> {
  const res = await fetch(
    `${API_URL}/api/search/check?query=${encodeURIComponent(query)}`
  );
  if (!res.ok) {
    return { cached: false };
  }
  return res.json();
}

/** SSE 스트리밍 검색 - 결과를 하나씩 콜백으로 전달 */
export async function searchBookStream(
  query: string,
  onResult: (rating: PlatformRating) => void,
  onDone: (summary: SearchResult["search"], source: string) => void,
  onError: (error: string) => void,
  onDescription?: (description: string) => void,
  platforms?: string[],
  forceRefresh?: boolean
): Promise<void> {
  const res = await fetch(`${API_URL}/api/search/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      query,
      platforms: platforms || null,
      force_refresh: forceRefresh || false,
    }),
  });

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: "서버 오류" }));
    throw new Error(error.detail || `HTTP ${res.status}`);
  }

  const reader = res.body?.getReader();
  if (!reader) throw new Error("ReadableStream not supported");

  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";

    let eventType = "message";
    for (const line of lines) {
      if (line.startsWith("event: ")) {
        eventType = line.slice(7).trim();
      } else if (line.startsWith("data: ")) {
        const data = line.slice(6);
        try {
          const parsed = JSON.parse(data);
          if (eventType === "done") {
            onDone(parsed.search, parsed.source);
          } else if (eventType === "description") {
            onDescription?.(parsed.description);
          } else {
            onResult(parsed as PlatformRating);
          }
        } catch {
          // skip invalid JSON
        }
        eventType = "message";
      }
    }
  }
}

/** 검색 히스토리 조회 */
export interface SearchHistoryItem {
  id: string;
  query: string;
  avg_rating: number | null;
  total_reviews: number;
  platform_count: number;
  created_at: string;
  ratings: PlatformRating[];
}

export interface SearchHistoryResponse {
  searches: SearchHistoryItem[];
  total: number;
}

export async function getSearchHistory(params?: {
  sort_by?: string;
  order?: string;
  limit?: number;
  offset?: number;
  platform?: string;
}): Promise<SearchHistoryResponse> {
  const searchParams = new URLSearchParams();
  if (params?.sort_by) searchParams.set("sort_by", params.sort_by);
  if (params?.order) searchParams.set("order", params.order);
  if (params?.limit) searchParams.set("limit", String(params.limit));
  if (params?.offset) searchParams.set("offset", String(params.offset));
  if (params?.platform) searchParams.set("platform", params.platform);

  const res = await fetch(`${API_URL}/api/searches?${searchParams}`);
  if (!res.ok) throw new Error("검색 히스토리를 가져올 수 없습니다");
  return res.json();
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
