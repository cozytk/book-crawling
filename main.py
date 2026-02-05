#!/usr/bin/env python3
"""
Book Review Crawler - Multi-Platform Rating Collector
책 제목으로 여러 플랫폼의 평점과 리뷰 수를 수집합니다.
"""

import argparse
import asyncio
import json
import time
import uuid
from datetime import datetime

import pandas as pd

from crawler_logging import CrawlerLogger

# 메인 로거
logger = CrawlerLogger("main")

from crawlers import (
    KyoboCrawler,
    Yes24Crawler,
    AladinCrawler,
    GoodreadsCrawler,
    AmazonCrawler,
    LibraryThingCrawler,
    SarakCrawler,
    WatchaCrawler,
)
from crawlers.base import BaseCrawler
from crawlers.foreign_resolver import resolve_foreign_query, ForeignQuery
from models.book import BookSearchResult, PlatformRating


# 사용 가능한 크롤러 레지스트리
# HTTP 기반 + Playwright 기반 모두 지원 (병렬 실행 가능)
CRAWLERS: dict[str, type[BaseCrawler]] = {
    # 국내 플랫폼 (HTTP)
    "aladin": AladinCrawler,
    "kyobo": KyoboCrawler,
    "yes24": Yes24Crawler,
    "sarak": SarakCrawler,
    "watcha": WatchaCrawler,
    # 해외 플랫폼 (HTTP)
    "goodreads": GoodreadsCrawler,
    "amazon": AmazonCrawler,
    # 해외 플랫폼 (Playwright - Cloudflare 우회)
    "librarything": LibraryThingCrawler,
}

# 해외 플랫폼 (한국어 검색어 시 원서 제목 사용)
FOREIGN_PLATFORMS = {"goodreads", "amazon", "librarything"}


async def crawl_platform(
    crawler_cls: type[BaseCrawler],
    query: str,
    fallback_query: str | None = None,
    original_query: str | None = None,
    execution_id: str | None = None,
) -> PlatformRating | None:
    """
    단일 플랫폼 크롤링 (스레드 기반 병렬 실행)

    각 크롤러를 별도 스레드에서 실행하여 동기 블로킹 I/O(urllib, cloudscraper)가
    이벤트 루프를 차단하지 않도록 함. GIL은 네트워크 I/O 중 해제되므로
    실제 병렬 HTTP 요청이 가능.

    Args:
        crawler_cls: 크롤러 클래스
        query: 검색어 (ISBN 또는 제목)
        fallback_query: 폴백 검색어 (query 실패 시 재시도)
        original_query: 최초 검색어 (사용자 입력 원본)
        execution_id: 전체 검색 실행 ID
    """
    session_id = uuid.uuid4().hex[:8]
    orig = original_query or query

    async def _execute():
        async with crawler_cls() as crawler:
            crawler.set_session(session_id, orig, execution_id=execution_id)
            result = await crawler.crawl(query, attempt=1)
            # 검색 실패 시 폴백 쿼리로 재시도
            if result is None and fallback_query and fallback_query != query:
                result = await crawler.crawl(fallback_query, attempt=2)
            return result

    return await asyncio.to_thread(lambda: asyncio.run(_execute()))


async def crawl_all_platforms(
    query: str, platforms: list[str] | None = None
) -> BookSearchResult:
    """
    여러 플랫폼에서 병렬로 크롤링

    모든 크롤러가 HTTP 기반이므로 병렬 실행 가능.
    한국어 검색어 + Goodreads 포함 시 알라딘에서 원서 제목을 조회하여 사용.

    Args:
        query: 검색어 (책 제목)
        platforms: 크롤링할 플랫폼 목록 (None이면 전체)

    Returns:
        BookSearchResult 객체
    """
    execution_id = uuid.uuid4().hex[:8]
    logger.set_execution_id(execution_id)
    logger.crawl_start(query)

    if platforms is None:
        platforms = list(CRAWLERS.keys())

    # 유효한 플랫폼만 필터링
    valid_platforms = [p for p in platforms if p in CRAWLERS]
    if not valid_platforms:
        print(f"Error: 유효한 플랫폼이 없습니다. 사용 가능: {list(CRAWLERS.keys())}")
        return BookSearchResult(query=query)

    # 해외 플랫폼 검색어 해석
    foreign = ForeignQuery()
    has_foreign = any(p in FOREIGN_PLATFORMS for p in valid_platforms)
    if has_foreign:
        foreign = await resolve_foreign_query(query)

    # 플랫폼별 검색어 결정 (해외 플랫폼: ISBN 우선 → 원서 제목 폴백)
    tasks = []
    task_platforms = []  # tasks와 1:1 대응하는 플랫폼 목록
    for p in valid_platforms:
        if p in FOREIGN_PLATFORMS:
            if foreign.isbn:
                # ISBN으로 검색, 실패 시 원서 제목으로 폴백
                tasks.append(crawl_platform(
                    CRAWLERS[p], foreign.isbn, foreign.query, original_query=query, execution_id=execution_id
                ))
                task_platforms.append(p)
            elif foreign.query:
                # ISBN 없으면 원서 제목으로 검색
                tasks.append(crawl_platform(
                    CRAWLERS[p], foreign.query, original_query=query, execution_id=execution_id
                ))
                task_platforms.append(p)
            else:
                # 원서 정보 없음 → 해외 플랫폼 건너뛰기
                logger.debug(f"[{p}] 원서 정보 없음, 건너뛰기")
        else:
            tasks.append(crawl_platform(CRAWLERS[p], query, original_query=query, execution_id=execution_id))
            task_platforms.append(p)

    start_time = time.perf_counter()
    results = await asyncio.gather(*tasks, return_exceptions=True)
    total_elapsed_ms = (time.perf_counter() - start_time) * 1000

    # 결과 수집
    search_result = BookSearchResult(query=query)
    summary_data = []

    for platform, result in zip(task_platforms, results):
        if isinstance(result, Exception):
            print(f"[{platform}] 에러 발생: {result}")
        elif result is not None:
            search_result.add_result(result)
            summary_data.append({
                "platform": platform,
                "rating": result.normalized_rating,
                "review_count": result.review_count,
            })
        else:
            summary_data.append({
                "platform": platform,
                "rating": None,
                "review_count": 0,
            })

    # 전체 요약 로그 기록 (모든 플랫폼 필드를 포함하여 스키마 일관성 유지)
    all_platform_names = list(CRAWLERS.keys())
    logger.search_summary(query, summary_data, total_elapsed_ms, all_platform_names)

    return search_result


def print_results(result: BookSearchResult) -> None:
    """결과 출력"""
    print(f"\n{'=' * 60}")
    print(f"검색 결과: {result.query}")
    print(f"{'=' * 60}")

    if not result.results:
        print("검색 결과가 없습니다.")
        return

    for r in result.results:
        # 10점 만점으로 정규화하여 표시
        rating_str = f"{r.normalized_rating}/10" if r.normalized_rating is not None else "N/A"
        print(f"\n[{r.platform}] {r.book_title}")
        print(f"  평점: {rating_str} | 리뷰: {r.review_count:,}개")
        print(f"  URL: {r.url}")

    print(f"\n{'-' * 60}")

    # 평균 평점 계산 (정규화된 10점 만점 기준)
    ratings = [r.normalized_rating for r in result.results if r.normalized_rating]
    if ratings:
        avg_rating = sum(ratings) / len(ratings)
        print(f"\n평균 평점 (10점 만점): {avg_rating:.2f}")

    total_reviews = sum(r.review_count for r in result.results)
    print(f"총 리뷰 수: {total_reviews:,}개")


def save_results(result: BookSearchResult, output: str, format: str) -> None:
    """결과 저장"""
    if format == "csv":
        rows = []
        for r in result.results:
            rows.append(
                {
                    "query": result.query,
                    "platform": r.platform,
                    "rating": r.rating,
                    "rating_scale": r.rating_scale,
                    "normalized_rating": r.normalized_rating,
                    "review_count": r.review_count,
                    "book_title": r.book_title,
                    "url": r.url,
                    "crawled_at": r.crawled_at.isoformat(),
                }
            )
        df = pd.DataFrame(rows)
        df.to_csv(output, index=False, encoding="utf-8-sig")
        print(f"\n결과가 {output}에 저장되었습니다.")

    elif format == "json":
        with open(output, "w", encoding="utf-8") as f:
            json.dump(result.to_dict(), f, ensure_ascii=False, indent=2)
        print(f"\n결과가 {output}에 저장되었습니다.")


def main():
    parser = argparse.ArgumentParser(
        description="책 제목으로 여러 플랫폼의 평점과 리뷰 수를 수집합니다.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  python main.py --query "클린 코드"
  python main.py --query "해리 포터" --platforms kyobo,yes24
  python main.py --query "사피엔스" --output ratings.csv --format csv
        """,
    )

    parser.add_argument(
        "--query", "-q", type=str, required=True, help="검색할 책 제목"
    )

    parser.add_argument(
        "--platforms",
        "-p",
        type=str,
        default=None,
        help=f"크롤링할 플랫폼 (쉼표로 구분). 사용 가능: {', '.join(CRAWLERS.keys())}",
    )

    parser.add_argument(
        "--output", "-o", type=str, default=None, help="출력 파일 경로"
    )

    parser.add_argument(
        "--format",
        "-f",
        type=str,
        choices=["csv", "json"],
        default="csv",
        help="출력 형식 (기본: csv)",
    )

    parser.add_argument(
        "--log-level",
        type=str,
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="로깅 레벨 (기본: INFO)",
    )

    parser.add_argument(
        "--log-file",
        type=str,
        default=None,
        help="로그 파일 경로 (JSON Lines 포맷)",
    )

    parser.add_argument(
        "--no-openobserve",
        action="store_true",
        help="OpenObserve 로그 전송 비활성화 (기본: 활성화)",
    )

    parser.add_argument(
        "--openobserve-url",
        type=str,
        default="http://localhost:5080",
        help="OpenObserve URL (기본: http://localhost:5080)",
    )

    args = parser.parse_args()

    # 로깅 설정
    CrawlerLogger.configure(
        level=args.log_level,
        log_file=args.log_file,
        console=True,
        openobserve=not args.no_openobserve,
        openobserve_url=args.openobserve_url,
    )

    # 플랫폼 파싱
    platforms = None
    if args.platforms:
        platforms = [p.strip().lower() for p in args.platforms.split(",")]

    # 크롤링 실행
    result = asyncio.run(crawl_all_platforms(args.query, platforms))

    # 결과 출력
    print_results(result)

    # 결과 저장 (옵션)
    if args.output:
        save_results(result, args.output, args.format)


if __name__ == "__main__":
    main()
