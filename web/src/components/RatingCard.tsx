import { PlatformRating, PLATFORM_META } from "@/lib/api";

interface RatingCardProps {
  rating: PlatformRating;
}

export default function RatingCard({ rating }: RatingCardProps) {
  const meta = PLATFORM_META[rating.platform] || {
    label: rating.platform,
    color: "#666",
  };
  const normalized = rating.normalized_rating;
  const barWidth = normalized ? (normalized / 10) * 100 : 0;

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5 hover:shadow-md transition-shadow">
      {/* 플랫폼 헤더 */}
      <div className="flex items-center justify-between mb-3">
        <span
          className="text-sm font-semibold px-2.5 py-1 rounded-full text-white"
          style={{ backgroundColor: meta.color }}
        >
          {meta.label}
        </span>
        {normalized !== null && (
          <span className="text-2xl font-bold tabular-nums">
            {normalized.toFixed(1)}
            <span className="text-sm font-normal text-gray-400">/10</span>
          </span>
        )}
      </div>

      {/* 책 제목 */}
      <p className="text-sm text-gray-700 mb-3 truncate" title={rating.book_title}>
        {rating.book_title || "-"}
      </p>

      {/* 평점 바 */}
      <div className="w-full bg-gray-100 rounded-full h-2.5 mb-3">
        <div
          className="h-2.5 rounded-full transition-all duration-500"
          style={{ width: `${barWidth}%`, backgroundColor: meta.color }}
        />
      </div>

      {/* 하단 정보 */}
      <div className="flex items-center justify-between text-xs text-gray-500">
        <span>
          {rating.rating !== null
            ? `${rating.rating}/${rating.rating_scale}`
            : "N/A"}
        </span>
        <span>{rating.review_count.toLocaleString()}개 리뷰</span>
      </div>

      {/* 링크 */}
      <a
        href={rating.url}
        target="_blank"
        rel="noopener noreferrer"
        className="mt-3 block text-center text-xs text-blue-600 hover:text-blue-800
                   py-1.5 border border-blue-200 rounded-lg hover:bg-blue-50 transition-colors"
      >
        상세 페이지 보기
      </a>
    </div>
  );
}
