from dataclasses import dataclass, field
from datetime import datetime
import math


@dataclass
class PlatformRating:
    """플랫폼별 책 평점 정보"""

    platform: str  # 플랫폼 이름 (kyobo, yes24, aladin 등)
    rating: float | None  # 평점 (None if not available)
    rating_scale: int  # 만점 기준 (5 or 10)
    review_count: int | None  # legacy combined display count; None means unknown
    url: str  # 책 상세 페이지 URL
    book_title: str = ""  # 플랫폼에서 찾은 책 제목
    crawled_at: datetime = field(default_factory=datetime.now)
    rating_count: int | None = None
    text_review_count: int | None = None
    isbn: str | None = None
    author: str | None = None
    edition_note: str | None = None
    comparison_scope: str = "work"
    volume_results: list[dict] = field(default_factory=list)
    aggregation_method: str | None = None
    aggregate_complete: bool | None = None
    publisher: str | None = None
    translator: str | None = None
    short_review_count: int | None = None

    def __post_init__(self):
        try:
            number = float(self.rating)
            self.rating = number if math.isfinite(number) and 0 <= number <= self.rating_scale else None
        except (ValueError, TypeError):
            self.rating = None

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
                    "rating_count": r.rating_count,
                    "text_review_count": r.text_review_count,
                    **({'short_review_count':r.short_review_count} if r.short_review_count is not None else {}),
                    "isbn": r.isbn,
                    "author": r.author,
                    "edition_note": r.edition_note,
                    "comparison_scope": r.comparison_scope,
                    **({"volume_results":r.volume_results,"aggregation_method":r.aggregation_method,
                        "aggregate_complete":r.aggregate_complete,"publisher":r.publisher,"translator":r.translator}
                       if r.volume_results else {}),
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
                f"{r.platform:10} | 평점: {rating_str:8} | 평가: {r.review_count if r.review_count is not None else '미확인'}"
            )
        return "\n".join(lines)
