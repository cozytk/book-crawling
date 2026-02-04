#!/usr/bin/env python3
"""
Book Review Crawler - Multi-Platform Rating Collector
책 제목으로 여러 플랫폼의 평점과 리뷰 수를 수집합니다.
"""

import argparse
import asyncio
import json
import sys
from datetime import datetime

import pandas as pd

from crawlers import KyoboCrawler, Yes24Crawler, AladinCrawler
from crawlers.base import BasePlatformCrawler
from models.book import BookSearchResult, PlatformRating


# 사용 가능한 크롤러 레지스트리 (알라딘 우선 - API 기반으로 가장 빠름)
CRAWLERS: dict[str, type[BasePlatformCrawler]] = {
    "aladin": AladinCrawler,
    "kyobo": KyoboCrawler,
    "yes24": Yes24Crawler,
}


async def crawl_platform(
    crawler_cls: type[BasePlatformCrawler], query: str
) -> PlatformRating | None:
    """단일 플랫폼 크롤링"""
    async with crawler_cls() as crawler:
        return await crawler.crawl(query)


def crawl_browser_platform_sync(platform: str, query: str) -> PlatformRating | None:
    """Playwright 기반 크롤러를 별도 프로세스에서 실행 (urllib과의 충돌 방지)"""
    import subprocess

    # 쿼리에서 특수문자 이스케이프
    escaped_query = query.replace("\\", "\\\\").replace('"', '\\"')
    crawler_name = f"{platform.title()}Crawler"

    code = f'''
import asyncio
import json
from crawlers import {crawler_name}

async def main():
    async with {crawler_name}() as crawler:
        result = await crawler.crawl("{escaped_query}")
        if result:
            print(json.dumps({{
                "platform": result.platform,
                "rating": result.rating,
                "rating_scale": result.rating_scale,
                "review_count": result.review_count,
                "url": result.url,
                "book_title": result.book_title,
            }}, ensure_ascii=False))

asyncio.run(main())
'''
    try:
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            timeout=60,
        )

        if result.returncode != 0:
            if "검색 결과 없음" not in result.stderr:
                print(f"[{platform}] subprocess 에러 (rc={result.returncode})")
                if result.stderr:
                    print(f"  stderr: {result.stderr[:200]}")
            return None

        # 출력에서 JSON 부분만 추출 (print 문 등 제외)
        for line in result.stdout.strip().split("\n"):
            if line.startswith("{"):
                data = json.loads(line)
                return PlatformRating(
                    platform=data["platform"],
                    rating=data["rating"],
                    rating_scale=data["rating_scale"],
                    review_count=data["review_count"],
                    url=data["url"],
                    book_title=data["book_title"],
                )
        return None
    except subprocess.TimeoutExpired:
        print(f"[{platform}] 타임아웃")
        return None
    except Exception as e:
        print(f"[{platform}] 에러 발생: {e}")
        return None


async def crawl_browser_platform_subprocess(platform: str, query: str) -> PlatformRating | None:
    """비동기 래퍼 - 실제 작업은 별도 스레드에서 실행"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, crawl_browser_platform_sync, platform, query)


async def crawl_all_platforms(
    query: str, platforms: list[str] | None = None
) -> BookSearchResult:
    """
    여러 플랫폼에서 병렬로 크롤링

    Args:
        query: 검색어 (책 제목)
        platforms: 크롤링할 플랫폼 목록 (None이면 전체)

    Returns:
        BookSearchResult 객체
    """
    if platforms is None:
        platforms = list(CRAWLERS.keys())

    # 유효한 플랫폼만 필터링
    valid_platforms = [p for p in platforms if p in CRAWLERS]
    if not valid_platforms:
        print(f"Error: 유효한 플랫폼이 없습니다. 사용 가능: {list(CRAWLERS.keys())}")
        return BookSearchResult(query=query)

    print(f"\n{'=' * 60}")
    print(f"검색어: {query}")
    print(f"플랫폼: {', '.join(valid_platforms)}")
    print(f"{'=' * 60}\n")

    # HTTP 기반 크롤러와 Playwright 기반 크롤러 분리
    from crawlers.base_http import BaseHttpCrawler

    http_platforms = []
    browser_platforms = []

    for p in valid_platforms:
        crawler_cls = CRAWLERS[p]
        if issubclass(crawler_cls, BaseHttpCrawler):
            http_platforms.append(p)
        else:
            browser_platforms.append(p)

    results_map = {}

    # HTTP 기반 크롤러 먼저 병렬 실행 (빠름)
    if http_platforms:
        http_tasks = [crawl_platform(CRAWLERS[p], query) for p in http_platforms]
        http_results = await asyncio.gather(*http_tasks, return_exceptions=True)
        for p, r in zip(http_platforms, http_results):
            results_map[p] = r

    # Playwright 기반 크롤러는 별도 프로세스에서 실행 (urllib과의 충돌 방지)
    for p in browser_platforms:
        result = await crawl_browser_platform_subprocess(p, query)
        results_map[p] = result

    # 원래 순서대로 결과 정렬
    results = [results_map[p] for p in valid_platforms]

    # 결과 수집
    search_result = BookSearchResult(query=query)

    for platform, result in zip(valid_platforms, results):
        if isinstance(result, Exception):
            print(f"[{platform}] 에러 발생: {result}")
        elif result is not None:
            search_result.add_result(result)

    return search_result


def print_results(result: BookSearchResult) -> None:
    """결과 출력"""
    print(f"\n{'=' * 60}")
    print(f"검색 결과: {result.query}")
    print(f"{'=' * 60}")

    if not result.results:
        print("검색 결과가 없습니다.")
        return

    print(f"\n{'플랫폼':<10} {'평점':<12} {'리뷰 수':<10} {'책 제목'}")
    print("-" * 70)

    for r in result.results:
        rating_str = f"{r.rating}/{r.rating_scale}" if r.rating else "N/A"
        title_short = r.book_title[:30] + "..." if len(r.book_title) > 30 else r.book_title
        print(f"{r.platform:<10} {rating_str:<12} {r.review_count:<10} {title_short}")

    print("-" * 70)

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

    args = parser.parse_args()

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
