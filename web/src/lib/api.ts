import { SSEParser } from "./sse";

const API_URL = "";

export interface PlatformRating {
  platform: string;
  rating: number | null;
  rating_scale: number;
  normalized_rating: number | null;
  review_count: number | null;
  rating_count?: number | null;
  text_review_count?: number | null;
  short_review_count?: number | null;
  isbn?: string | null;
  author?: string | null;
  edition_note?: string | null;
  comparison_scope?: "work" | "edition" | "volume_group";
  volume_results?: VolumeRating[];
  aggregation_method?: string | null;
  aggregate_complete?: boolean | null;
  publisher?: string | null;
  translator?: string | null;
  book_title: string;
  url: string;
  crawled_at: string;
}

export interface VolumeRating {
  volume: string;
  book_title: string;
  isbn?: string | null;
  url?: string;
  rating: number | null;
  rating_scale?: number;
  rating_count?: number | null;
  text_review_count?: number | null;
  short_review_count?: number | null;
  review_count?: number | null;
  status: string;
}

export interface SearchResult {
  source: "cache" | "crawl";
  search: {
    id: string | null;
    query: string;
    avg_rating: number | null;
    total_reviews: number | null;
    counts_complete?: boolean;
    legacy_validation?: boolean;
    platform_count: number;
    missing_platforms?: string[];
    created_at?: string;
    storage_saved?: boolean;
    requested_platforms?: string[];
  };
  ratings: PlatformRating[];
}

export interface PlatformInfo {
  name: string;
  type: "domestic" | "foreign";
}

export interface PlatformStatus {
  platform: string;
  status: "done" | "unavailable" | "timeout" | "blocked" | "not_found" | "identity_mismatch" | "parse_error" | "network_error";
  reason?: string;
}

export async function searchBook(
  query: string,
  platforms?: string[],
  options?: {
    force_refresh?: boolean;
    include_description?: boolean;
  }
): Promise<SearchResult> {
  const res = await fetch(`${API_URL}/api/search`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      query,
      platforms: platforms || null,
      force_refresh: options?.force_refresh || false,
      include_description: options?.include_description || false,
    }),
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

export async function checkCache(query: string, platforms?: string[]): Promise<CacheCheckResult> {
  const params = new URLSearchParams({ query });
  platforms?.forEach((platform) => params.append("platforms", platform));
  const res = await fetch(
    `${API_URL}/api/search/check?${params}`
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
  forceRefresh?: boolean,
  signal?: AbortSignal,
  onStatus?: (status: PlatformStatus) => void
): Promise<void> {
  const res = await fetch(`${API_URL}/api/search/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    signal,
    body: JSON.stringify({
      query,
      platforms: platforms || null,
      force_refresh: forceRefresh || false,
      include_description: Boolean(onDescription),
    }),
  });

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: "서버 오류" }));
    throw new Error(error.detail || `HTTP ${res.status}`);
  }

  const reader = res.body?.getReader();
  if (!reader) throw new Error("ReadableStream not supported");

  const decoder = new TextDecoder();
  let completed = false;
  let failed = false;
  const parser = new SSEParser((event, data) => {
    const parsed = JSON.parse(data);
    if (event === "done") {
      completed = true;
      if (!failed) onDone(parsed.search, parsed.source);
    } else if (event === "error") {
      failed = true;
      onError(parsed.message || "검색 중 오류가 발생했습니다");
    } else if (event === "description_chunk") {
      onDescription?.(parsed.chunk);
    } else if (event === "platform_status") {
      onStatus?.(parsed as PlatformStatus);
    } else if (event === "rating" || event === "message") {
      onResult(parsed as PlatformRating);
    }
  });
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      parser.push(decoder.decode(value, { stream: true }));
    }
    parser.push(decoder.decode());
    if (!completed) throw new Error("검색 연결이 끊어졌습니다. 다시 검색해주세요.");
  } finally {
    await reader.cancel().catch(() => {});
    reader.releaseLock();
  }
}

/** 검색 히스토리 조회 */
export interface SearchHistoryItem {
  id: string;
  query: string;
  avg_rating: number | null;
  total_reviews: number | null;
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
  sort_platform?: string;
  with_count?: boolean;
}): Promise<SearchHistoryResponse> {
  const searchParams = new URLSearchParams();
  if (params?.sort_by) searchParams.set("sort_by", params.sort_by);
  if (params?.order) searchParams.set("order", params.order);
  if (params?.limit) searchParams.set("limit", String(params.limit));
  if (params?.offset) searchParams.set("offset", String(params.offset));
  if (params?.platform) searchParams.set("platform", params.platform);
  if (params?.sort_platform) searchParams.set("sort_platform", params.sort_platform);
  if (params?.with_count !== undefined) searchParams.set("with_count", String(params.with_count));

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
