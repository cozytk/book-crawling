"""모델 클래스 테스트"""

import pytest
from datetime import datetime

from models.book import PlatformRating, BookSearchResult


class TestPlatformRating:
    """PlatformRating 테스트"""

    def test_create_rating_with_10_scale(self):
        """10점 만점 평점 생성"""
        rating = PlatformRating(
            platform="kyobo",
            rating=9.8,
            rating_scale=10,
            review_count=127,
            url="https://kyobobook.co.kr/product/123",
            book_title="클린 코드",
        )

        assert rating.platform == "kyobo"
        assert rating.rating == 9.8
        assert rating.rating_scale == 10
        assert rating.review_count == 127
        assert rating.book_title == "클린 코드"

    def test_create_rating_with_5_scale(self):
        """5점 만점 평점 생성 (Goodreads)"""
        rating = PlatformRating(
            platform="goodreads",
            rating=4.35,
            rating_scale=5,
            review_count=1471,
            url="https://goodreads.com/book/123",
            book_title="Clean Code",
        )

        assert rating.platform == "goodreads"
        assert rating.rating == 4.35
        assert rating.rating_scale == 5

    def test_normalized_rating_10_scale(self):
        """10점 만점 정규화 (변환 없음)"""
        rating = PlatformRating(
            platform="kyobo",
            rating=9.8,
            rating_scale=10,
            review_count=100,
            url="https://example.com",
        )

        assert rating.normalized_rating == 9.8

    def test_normalized_rating_5_scale(self):
        """5점 만점 → 10점 만점 정규화"""
        rating = PlatformRating(
            platform="goodreads",
            rating=4.35,
            rating_scale=5,
            review_count=100,
            url="https://example.com",
        )

        assert rating.normalized_rating == 8.7  # 4.35 * 2

    def test_normalized_rating_none(self):
        """평점 없음 처리"""
        rating = PlatformRating(
            platform="kyobo",
            rating=None,
            rating_scale=10,
            review_count=0,
            url="https://example.com",
        )

        assert rating.normalized_rating is None

    def test_crawled_at_auto_set(self):
        """crawled_at 자동 설정"""
        before = datetime.now()
        rating = PlatformRating(
            platform="test",
            rating=5.0,
            rating_scale=10,
            review_count=10,
            url="https://example.com",
        )
        after = datetime.now()

        assert before <= rating.crawled_at <= after


class TestBookSearchResult:
    """BookSearchResult 테스트"""

    def test_create_empty_result(self):
        """빈 검색 결과 생성"""
        result = BookSearchResult(query="클린 코드")

        assert result.query == "클린 코드"
        assert result.results == []

    def test_add_result(self):
        """결과 추가"""
        result = BookSearchResult(query="클린 코드")
        rating = PlatformRating(
            platform="kyobo",
            rating=9.8,
            rating_scale=10,
            review_count=127,
            url="https://example.com",
        )

        result.add_result(rating)

        assert len(result.results) == 1
        assert result.results[0].platform == "kyobo"

    def test_add_multiple_results(self):
        """복수 결과 추가"""
        result = BookSearchResult(query="클린 코드")

        platforms = ["kyobo", "yes24", "aladin"]
        for platform in platforms:
            rating = PlatformRating(
                platform=platform,
                rating=9.5,
                rating_scale=10,
                review_count=100,
                url=f"https://{platform}.com",
            )
            result.add_result(rating)

        assert len(result.results) == 3

    def test_to_dict(self):
        """딕셔너리 변환"""
        result = BookSearchResult(query="클린 코드")
        rating = PlatformRating(
            platform="kyobo",
            rating=9.8,
            rating_scale=10,
            review_count=127,
            url="https://example.com",
            book_title="클린 코드",
        )
        result.add_result(rating)

        data = result.to_dict()

        assert data["query"] == "클린 코드"
        assert len(data["results"]) == 1
        assert data["results"][0]["platform"] == "kyobo"
        assert data["results"][0]["rating"] == 9.8
        assert data["results"][0]["normalized_rating"] == 9.8
        assert "crawled_at" in data["results"][0]

    def test_to_dict_with_5_scale(self):
        """5점 만점 딕셔너리 변환"""
        result = BookSearchResult(query="Clean Code")
        rating = PlatformRating(
            platform="goodreads",
            rating=4.35,
            rating_scale=5,
            review_count=1471,
            url="https://example.com",
        )
        result.add_result(rating)

        data = result.to_dict()

        assert data["results"][0]["rating"] == 4.35
        assert data["results"][0]["normalized_rating"] == 8.7

    def test_summary(self):
        """요약 문자열 생성"""
        result = BookSearchResult(query="클린 코드")
        rating = PlatformRating(
            platform="kyobo",
            rating=9.8,
            rating_scale=10,
            review_count=127,
            url="https://example.com",
        )
        result.add_result(rating)

        summary = result.summary()

        assert "클린 코드" in summary
        assert "kyobo" in summary
        assert "9.8/10" in summary
        assert "127" in summary

    def test_summary_with_none_rating(self):
        """평점 없는 경우 요약"""
        result = BookSearchResult(query="테스트")
        rating = PlatformRating(
            platform="test",
            rating=None,
            rating_scale=10,
            review_count=0,
            url="https://example.com",
        )
        result.add_result(rating)

        summary = result.summary()

        assert "N/A" in summary
