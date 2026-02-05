export default function LoadingSkeleton() {
  return (
    <div className="space-y-6">
      {/* 요약 스켈레톤 */}
      <div className="bg-white rounded-xl border border-gray-200 p-6 animate-pulse">
        <div className="h-6 bg-gray-200 rounded w-48 mb-4" />
        <div className="flex gap-8">
          <div className="h-10 bg-gray-200 rounded w-32" />
          <div className="h-10 bg-gray-200 rounded w-32" />
        </div>
      </div>

      {/* 카드 그리드 스켈레톤 */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {Array.from({ length: 8 }).map((_, i) => (
          <div
            key={i}
            className="bg-white rounded-xl border border-gray-200 p-5 animate-pulse"
          >
            <div className="flex justify-between mb-3">
              <div className="h-6 bg-gray-200 rounded-full w-20" />
              <div className="h-8 bg-gray-200 rounded w-16" />
            </div>
            <div className="h-4 bg-gray-200 rounded w-3/4 mb-3" />
            <div className="h-2.5 bg-gray-200 rounded-full mb-3" />
            <div className="flex justify-between">
              <div className="h-3 bg-gray-200 rounded w-12" />
              <div className="h-3 bg-gray-200 rounded w-16" />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
