"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import dynamic from "next/dynamic";
const ReactMarkdown = dynamic(() => import("react-markdown"));
import SearchForm from "@/components/SearchForm";
import RatingGrid from "@/components/RatingGrid";
import BookmarkButton from "@/components/BookmarkButton";
import { searchBookStream, PLATFORM_META, PlatformRating, PlatformStatus, SearchResult } from "@/lib/api";

const ALL = Object.keys(PLATFORM_META);
const DOMESTIC = ["aladin", "kyobo", "yes24", "sarak"];
const FOREIGN = ["goodreads", "amazon", "librarything"];
const EXAMPLES = ["데미안", "사피엔스", "클린 코드"];

export default function Home() {
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<string[]>(DOMESTIC);
  const [current, setCurrent] = useState<string | null>(null);
  const [requested, setRequested] = useState<string[]>([]);
  const [ratings, setRatings] = useState<PlatformRating[]>([]);
  const [statuses, setStatuses] = useState<Record<string, PlatformStatus>>({});
  const [summary, setSummary] = useState<SearchResult["search"] | null>(null);
  const [source, setSource] = useState("");
  const [loading, setLoading] = useState(false);
  const [cancelled, setCancelled] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [description, setDescription] = useState("");
  const [withDescription, setWithDescription] = useState(false);
  const [sort, setSort] = useState("rating");
  const controller = useRef<AbortController | null>(null);
  const initialSearch = useRef<((title: string, refresh?: boolean, platforms?: string[]) => Promise<void>) | null>(null);

  const execute = useCallback(async (title: string, refresh = false, platforms = selected) => {
    const clean = title.trim();
    if (!clean || !platforms.length) return;
    controller.current?.abort();
    const active = new AbortController();
    controller.current = active;
    setQuery(clean); setCurrent(clean); setRequested([...platforms]); setRatings([]); setStatuses({});
    setSummary(null); setSource(""); setError(null); setDescription(""); setLoading(true); setCancelled(false);
    window.history.replaceState(null, "", `/?${new URLSearchParams({ q: clean, p: platforms.join(",") })}`);
    try {
      await searchBookStream(clean,
        (rating) => { if (controller.current === active) setRatings((previous) => [...previous.filter((r) => r.platform !== rating.platform), rating]); },
        (value, origin) => { if (controller.current === active) { setSummary(value); setSource(origin); } },
        (message) => { if (controller.current === active) setError(message); },
        withDescription ? (chunk) => { if (controller.current === active) setDescription((previous) => previous + chunk); } : undefined,
        platforms, refresh, active.signal,
        (status) => { if (controller.current === active) setStatuses((previous) => ({ ...previous, [status.platform]: status })); });
    } catch (failure) {
      if (controller.current === active && !active.signal.aborted) setError(failure instanceof Error ? failure.message : "검색 중 오류가 발생했습니다.");
    } finally {
      if (controller.current === active) setLoading(false);
    }
  }, [selected, withDescription]);

  initialSearch.current = execute;
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const title = params.get("q");
    const stored = [...new Set((params.get("p") || "").split(",").filter((p) => ALL.includes(p)))];
    const platforms = stored.length ? stored : DOMESTIC;
    if (title) {
      setSelected(platforms);
      void initialSearch.current?.(title, false, platforms);
    }
    return () => controller.current?.abort();
  }, []);

  const sorted = useMemo(() => [...ratings].sort((a, b) => {
    if (sort === "reviews") return (b.review_count ?? -1) - (a.review_count ?? -1);
    if (a.normalized_rating == null && b.normalized_rating == null) return 0;
    if (a.normalized_rating == null) return 1;
    if (b.normalized_rating == null) return -1;
    return b.normalized_rating - a.normalized_rating;
  }), [ratings, sort]);
  const completed = summary ? requested.length : Object.keys(statuses).length;
  const matched = ratings.filter((r) => r.normalized_rating !== null);
  const average = summary?.avg_rating ?? (matched.length ? matched.reduce((sum, r) => sum + r.normalized_rating!, 0) / matched.length : null);

  function toggle(platform: string) {
    setSelected((previous) => previous.includes(platform) ? previous.filter((p) => p !== platform) : [...previous, platform]);
  }

  return (
    <div className="home-page">
      <section className="hero">
        <div className="eyebrow"><span /> 다음 한 권을 위한 탐색</div>
        <h1>한 권의 책,<br /><em>여러 독자의 시선.</em></h1>
        <p>서점과 독서 커뮤니티의 평점을 한곳에서.<br className="mobile-break" /> 읽기 전, 다른 독자들의 평가를 살펴보세요.</p>
      </section>

      <section className="search-panel" aria-label="책 검색">
        <SearchForm query={query} onQueryChange={setQuery} onSearch={(title) => void execute(title)} isLoading={loading} disabled={!selected.length} />
        <div className="search-examples"><span>이런 책은 어때요?</span>{EXAMPLES.map((title) => <button key={title} onClick={() => void execute(title)} disabled={!selected.length}>{title}<span aria-hidden="true">↗</span></button>)}</div>
        <div className="platform-controls">
          <div className="platform-heading"><span>비교할 플랫폼 <strong>{selected.length}</strong></span><div className="preset-buttons">
            <button aria-pressed={selected.length === DOMESTIC.length && DOMESTIC.every((p) => selected.includes(p))} onClick={() => setSelected(DOMESTIC)}>국내</button>
            <button aria-pressed={selected.length === FOREIGN.length && FOREIGN.every((p) => selected.includes(p))} onClick={() => setSelected(FOREIGN)}>해외</button>
            <button aria-pressed={selected.length === ALL.length} onClick={() => setSelected(ALL)}>전체</button>
          </div></div>
          <div className="platform-chips">{ALL.map((platform) => <button key={platform} aria-pressed={selected.includes(platform)} onClick={() => toggle(platform)} className={selected.includes(platform) ? "selected" : ""}>
            <span className="platform-dot" style={{ background: PLATFORM_META[platform].color }} />{PLATFORM_META[platform].label}<span className="chip-check" aria-hidden="true">{selected.includes(platform) ? "✓" : "+"}</span>
          </button>)}</div>
          <div className="search-options"><span>{selected.length ? "제목 또는 ISBN으로 검색할 수 있어요." : "플랫폼을 하나 이상 선택해주세요."}</span>
            <label><input type="checkbox" checked={withDescription} onChange={(e) => setWithDescription(e.target.checked)} /> AI 책 소개 함께 보기</label>
          </div>
        </div>
      </section>

      {current ? <section className="results-section" aria-label="검색 결과" aria-busy={loading}>
        <div className="results-heading"><div><div className="eyebrow">{loading ? "독자들의 평가를 찾고 있어요" : cancelled ? "검색을 중단했어요" : "검색 결과"}</div><h2>{current}</h2></div>
          <div className="result-actions">{summary?.id && <BookmarkButton searchId={summary.id} query={current} avgRating={summary.avg_rating} totalReviews={summary.total_reviews} platformCount={summary.platform_count} />}
            {loading ? <button className="text-button" onClick={() => { controller.current?.abort(); setCancelled(true); setLoading(false); }}>검색 중단</button> : <button className="text-button" onClick={() => void execute(current, true, requested)}>↻ 새로 조회</button>}
          </div>
        </div>

        <div className="search-progress" role="status" aria-live="polite"><span className={loading ? "pulse-dot" : "complete-dot"} />
          {loading ? `${requested.length}개 중 ${completed}개 플랫폼 확인 · 결과가 도착하면 바로 보여드려요` : `${ratings.length}개 플랫폼에서 결과를 찾았습니다`}
          {source === "cache" && <span className="cache-label">이전 검색 결과</span>}
        </div>
        <div className="progress-track"><div style={{ width: `${requested.length ? completed / requested.length * 100 : 0}%` }} /></div>
        {error && <div className="notice error" role="alert">{error} <button onClick={() => void execute(current, true, requested)}>다시 시도</button></div>}

        {ratings.length > 0 && <>
          <div className="comparison-summary"><div><span>10점 환산 평균</span><strong>{average?.toFixed(1) ?? "—"}<small>/ 10</small></strong></div><p>플랫폼마다 판본과 평가 방식이 달라요.<br />점수와 함께 평가 수, 책 제목을 확인하세요.</p></div>
          <div className="result-toolbar"><span>플랫폼별 평가 <strong>{ratings.length}</strong></span><label><span className="sr-only">결과 정렬</span><select value={sort} onChange={(event) => setSort(event.target.value)}><option value="rating">평점 높은 순</option><option value="reviews">평가 많은 순</option></select></label></div>
          <RatingGrid ratings={sorted} />
        </>}
        {loading && !ratings.length && <div className="waiting-state"><span className="search-spinner" /><p>선택한 사이트에서 책을 찾고 있습니다.</p><span>사이트 응답에 따라 잠시 걸릴 수 있어요.</span></div>}
        {!loading && !ratings.length && !error && <div className="empty-results"><span aria-hidden="true">⌕</span><h3>{cancelled ? "검색을 중단했습니다" : "일치하는 결과를 찾지 못했어요"}</h3><p>정확한 책 제목이나 ISBN으로 다시 검색해보세요.<br />사이트의 수집 제한으로 결과가 없을 수도 있습니다.</p></div>}

        <div className="platform-statuses">{requested.map((platform) => {
          const found = ratings.some((r) => r.platform === platform);
          const status = statuses[platform];
          const pending = loading && !status && !summary;
          const label = status?.status === "blocked" ? "수집 제한" : status?.status === "timeout" ? "시간 초과" : status?.status === "parse_error" ? "일부 정보 미확인" : found ? "✓ 확인" : pending ? "확인 중…" : status?.status === "not_found" || status?.status === "identity_mismatch" ? "일치 결과 없음" : cancelled && !status ? "중단" : "연결 불가";
          return <div key={platform} className={found ? "found" : ""} title={status?.reason}><span>{PLATFORM_META[platform].label}</span><span>{label}</span></div>;
        })}</div>
        {summary?.storage_saved === false && ratings.length > 0 && <p className="notice">검색 결과는 표시했지만 기록을 저장하지 못했습니다. 잠시 후 새로 조회해주세요.</p>}
        {summary?.created_at && <p className="result-timestamp">{new Date(summary.created_at).toLocaleString("ko-KR")} 기준 · 이전 결과는 최대 24시간 재사용합니다.</p>}
        {description && <details className="description-panel" open><summary>AI 책 소개</summary><p className="description-disclaimer">AI가 생성한 내용으로 사실과 다를 수 있습니다.</p><div className="prose"><ReactMarkdown>{description}</ReactMarkdown></div></details>}
      </section> : <section className="how-it-works"><div><span className="step-number">01</span><h2>책 한 권을 검색하고</h2><p>제목이나 ISBN을 입력하세요.</p></div><div><span className="step-number">02</span><h2>여러 평가를 나란히</h2><p>같은 10점 기준으로 비교하세요.</p></div><div><span className="step-number">03</span><h2>나의 다음 책으로</h2><p>마음에 들면 <Link href="/bookmarks">읽을 책</Link>에 담아두세요.</p></div></section>}
      <p className="data-note">별점 참여 수와 글 리뷰 수를 구분하며, 확인하지 못한 수치는 표시하지 않습니다. 판본·집계 기준·수집 시점에 차이가 있습니다. ISBN을 지정해도 플랫폼 평점은 여러 판본과 합산될 수 있으며, 일부 사이트는 수집이 제한될 수 있습니다.</p>
    </div>
  );
}
