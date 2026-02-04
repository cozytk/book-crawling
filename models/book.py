from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class PlatformRating:
    """플랫폼별 책 평점 정보"""

    platform: str  # 플랫폼 이름 (kyobo, yes24, aladin 등)
    rating: float | None  # 평점 (None if not available)
    rating_scale: int  # 만점 기준 (5 or 10)
    review_count: int  # 리뷰 수
    url: str  # 책 상세 페이지 URL
    book_title: str = ""  # 플랫폼에서 찾은 책 제목
    crawled_at: datetime = field(default_factory=datetime.now)

    @property
    def normalized_rating(self) -> float | None:
        """10점 만점으로 정규화된 평점"""
        if self.rating is None:
            return None
        if self.rating_scale == 5:
            return self.rating * 2
        return self.rating


@dataclass
class BookSearchResult:
    """책 검색 결과 집합"""

    query: str  # 검색어
    results: list[PlatformRating] = field(default_factory=list)

    def add_result(self, rating: PlatformRating) -> None:
        self.results.append(rating)

    def to_dict(self) -> dict:
        return {
            "query": self.query,
            "results": [
                {
                    "platform": r.platform,
                    "rating": r.rating,
                    "rating_scale": r.rating_scale,
                    "normalized_rating": r.normalized_rating,
                    "review_count": r.review_count,
                    "book_title": r.book_title,
                    "url": r.url,
                    "crawled_at": r.crawled_at.isoformat(),
                }
                for r in self.results
            ],
        }

    def summary(self) -> str:
        """결과 요약 문자열"""
        lines = [f"검색어: {self.query}", "-" * 50]
        for r in self.results:
            rating_str = f"{r.rating}/{r.rating_scale}" if r.rating else "N/A"
            lines.append(
                f"{r.platform:10} | 평점: {rating_str:8} | 리뷰: {r.review_count:5}개"
            )
        return "\n".join(lines)
