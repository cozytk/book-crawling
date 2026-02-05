import { PlatformRating } from "@/lib/api";
import RatingCard from "./RatingCard";

interface RatingGridProps {
  ratings: PlatformRating[];
}

export default function RatingGrid({ ratings }: RatingGridProps) {
  if (ratings.length === 0) {
    return (
      <div className="text-center py-12 text-gray-500">
        검색 결과가 없습니다.
      </div>
    );
  }

  // 정규화 평점 기준 내림차순 정렬 (null은 뒤로)
  const sorted = [...ratings].sort((a, b) => {
    if (a.normalized_rating === null) return 1;
    if (b.normalized_rating === null) return -1;
    return b.normalized_rating - a.normalized_rating;
  });

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
      {sorted.map((r) => (
        <RatingCard key={r.platform} rating={r} />
      ))}
    </div>
  );
}
