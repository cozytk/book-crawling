import { PlatformRating, PLATFORM_META } from "@/lib/api";

export default function RatingCard({ rating }: { rating: PlatformRating }) {
  const meta = PLATFORM_META[rating.platform] || { label: rating.platform, color: "#666" };
  const score = rating.normalized_rating;
  const safeUrl = /^https?:\/\//i.test(rating.url) ? rating.url : null;
  return <article className="rating-card">
    <div className="rating-platform"><span className="platform-dot" style={{ background: meta.color }} />{meta.label}<span className="rating-scale">10점 환산</span></div>
    <div className="rating-score">{score === null ? "—" : score.toFixed(1)}<span>/ 10</span></div>
    <div className="rating-bar"><div style={{ width: `${Math.max(0, Math.min(100, (score ?? 0) * 10))}%`, background: meta.color }} /></div>
    <p className="rating-title">{rating.book_title || "제목 정보 없음"}</p>
    {rating.author && <p className="rating-metadata">{rating.author}</p>}
    <div className="rating-original"><span>{rating.rating === null ? "평점 정보 없음" : `원점수 ${rating.rating} / ${rating.rating_scale}`}</span><strong>{rating.rating_count != null ? `별점 참여 ${rating.rating_count.toLocaleString()}명` : rating.text_review_count != null ? `글 리뷰 ${rating.text_review_count.toLocaleString()}개` : rating.review_count != null ? `평가 ${rating.review_count.toLocaleString()}개` : "평가 수 수집되지 않음"}</strong></div>
    {rating.rating_count != null && rating.text_review_count != null && <p className="rating-metadata">글 리뷰 {rating.text_review_count.toLocaleString()}개</p>}
    <p className="rating-metadata">{rating.comparison_scope === "edition" ? "지정 ISBN 판본" : "작품 기준 · 판본은 사이트마다 다를 수 있음"}{rating.isbn ? ` · ${rating.isbn}` : ""}</p>
    {safeUrl && <a className="rating-link" href={safeUrl} target="_blank" rel="noopener noreferrer">{meta.label}에서 책 확인<span aria-hidden="true">↗</span></a>}
  </article>;
}
