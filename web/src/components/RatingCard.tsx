import { PlatformRating, PLATFORM_META } from "@/lib/api";

export default function RatingCard({ rating }: { rating: PlatformRating }) {
  const meta = PLATFORM_META[rating.platform] || { label: rating.platform, color: "#666" };
  const score = rating.normalized_rating;
  const safeUrl = /^https?:\/\//i.test(rating.url) ? rating.url : null;
  const volumes = rating.volume_results ?? [];
  return <article className="rating-card">
    <div className="rating-platform"><span className="platform-dot" style={{ background: meta.color }} />{meta.label}<span className="rating-scale">10점 환산</span></div>
    <div className="rating-score">{score === null ? "—" : score.toFixed(1)}<span>/ 10</span></div>
    <div className="rating-bar"><div style={{ width: `${Math.max(0, Math.min(100, (score ?? 0) * 10))}%`, background: meta.color }} /></div>
    <p className="rating-title">{rating.book_title || "제목 정보 없음"}</p>
    {rating.author && <p className="rating-metadata">{rating.author}</p>}
    <div className="rating-original"><span>{rating.rating === null ? "평점 정보 없음" : `${volumes.length ? "권별 평균" : "원점수"} ${Number(rating.rating.toFixed(3))} / ${rating.rating_scale}`}</span><strong>{rating.rating_count != null ? `${volumes.length ? "권별 별점 참여 합계" : "별점 참여"} ${rating.rating_count.toLocaleString()}${volumes.length ? "건" : "명"}` : rating.text_review_count != null ? `글 리뷰 ${volumes.length ? "합계 " : ""}${rating.text_review_count.toLocaleString()}개` : rating.review_count != null ? `평가 ${volumes.length ? "합계 " : ""}${rating.review_count.toLocaleString()}개` : "평가 수 수집되지 않음"}</strong></div>
    {rating.rating_count != null && rating.text_review_count != null && <p className="rating-metadata">글 리뷰 {rating.text_review_count.toLocaleString()}개</p>}
    {rating.short_review_count != null && <p className="rating-metadata">{rating.platform === "yes24" ? "한줄평" : "100자평"} {volumes.length ? "합계 " : ""}{rating.short_review_count.toLocaleString()}개</p>}
    <p className="rating-metadata">{volumes.length ? rating.edition_note : rating.comparison_scope === "edition" ? "지정 ISBN 판본" : "작품 기준 · 판본은 사이트마다 다를 수 있음"}{rating.isbn ? ` · ${rating.isbn}` : ""}</p>
    {volumes.length > 0 && <details className="volume-details">
      <summary>권별 점수와 상품 보기 · {volumes.filter(v => v.rating !== null).length}/{volumes.length}권 확인</summary>
      <ul>{volumes.map(v => <li key={`${v.volume}-${v.isbn ?? v.url ?? "missing"}`}>
        <div><strong>{v.volume}권</strong><span>{v.rating === null ? "평점 미확인" : `${Number(v.rating.toFixed(3))} / ${v.rating_scale}`}</span></div>
        <p>{v.book_title}</p>
        <p>{v.rating_count != null ? `별점 참여 ${v.rating_count.toLocaleString()}명` : v.text_review_count != null ? `글 리뷰 ${v.text_review_count.toLocaleString()}개` : v.review_count != null ? `평가 ${v.review_count.toLocaleString()}개` : "평가 수 미확인"}{v.isbn ? ` · ${v.isbn}` : ""}</p>
        {v.rating_count != null && v.text_review_count != null && <p>글 리뷰 {v.text_review_count.toLocaleString()}개</p>}
        {v.short_review_count != null && <p>{rating.platform === "yes24" ? "한줄평" : "100자평"} {v.short_review_count.toLocaleString()}개</p>}
        {v.url && /^https?:\/\//i.test(v.url) && <a href={v.url} target="_blank" rel="noopener noreferrer">{v.volume}권 상품 확인 ↗</a>}
      </li>)}</ul>
    </details>}
    {safeUrl && <a className="rating-link" href={safeUrl} target="_blank" rel="noopener noreferrer">{meta.label}에서 {volumes.length ? "대표권" : "책"} 확인<span aria-hidden="true">↗</span></a>}
  </article>;
}
