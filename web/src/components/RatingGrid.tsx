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

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
      {ratings.map((r) => (
        <RatingCard key={r.platform} rating={r} />
      ))}
    </div>
  );
}
