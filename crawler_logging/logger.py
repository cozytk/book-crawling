"""크롤러 전용 로거"""

import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .formatters import ConsoleFormatter, JsonFormatter


class CrawlerLogger:
    """
    크롤러 전용 로거

    - 콘솔: 사람이 읽기 쉬운 컬러 포맷
    - 파일: JSON Lines 포맷 (기계 분석용)

    Usage:
        logger = CrawlerLogger("kyobo")
        logger.http_request("GET", url, 200, 156.3, 2341)
        logger.search_complete("클린 코드", found=True, title="Clean Code")
        logger.rating_complete(9.8, 2404, method="api")
    """

    _root_logger: logging.Logger | None = None
    _file_handler: logging.FileHandler | None = None
    _console_handler: logging.StreamHandler | None = None

    def __init__(self, name: str):
        self.name = name
        self.logger = logging.getLogger(f"crawler.{name}")
        self._execution_id: str | None = None

    def set_execution_id(self, execution_id: str) -> None:
        """전체 검색 실행 ID 설정"""
        self._execution_id = execution_id

    @classmethod
    def configure(
        cls,
        level: str = "INFO",
        log_file: str | Path | None = None,
        console: bool = True,
        openobserve: bool = False,
        openobserve_url: str = "http://localhost:5080",
        openobserve_org: str = "default",
        openobserve_stream: str = "crawler",
        openobserve_user: str = "admin@example.com",
        openobserve_password: str = "admin123",
    ) -> None:
        """
        전역 로깅 설정

        Args:
            level: 로깅 레벨 (DEBUG, INFO, WARNING, ERROR)
            log_file: JSON Lines 로그 파일 경로
            console: 콘솔 출력 여부
            openobserve: OpenObserve로 로그 전송 여부
            openobserve_url: OpenObserve URL
            openobserve_org: OpenObserve 조직명
            openobserve_stream: OpenObserve 스트림명
            openobserve_user: OpenObserve 사용자
            openobserve_password: OpenObserve 비밀번호
        """
        root = logging.getLogger("crawler")
        log_level = getattr(logging, level.upper())
        root.setLevel(log_level)

        # 기존 핸들러 제거
        root.handlers.clear()

        # 콘솔 핸들러
        if console:
            console_handler = logging.StreamHandler(sys.stderr)
            console_handler.setFormatter(ConsoleFormatter())
            root.addHandler(console_handler)
            cls._console_handler = console_handler

        # 파일 핸들러 (JSON Lines)
        if log_file:
            log_path = Path(log_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(log_path, encoding="utf-8")
            file_handler.setFormatter(JsonFormatter())
            root.addHandler(file_handler)
            cls._file_handler = file_handler

        # OpenObserve 핸들러
        if openobserve:
            from .handlers import OpenObserveHandler

            oo_handler = OpenObserveHandler(
                url=openobserve_url,
                org=openobserve_org,
                stream=openobserve_stream,
                username=openobserve_user,
                password=openobserve_password,
            )
            oo_handler.setLevel(log_level)
            root.addHandler(oo_handler)

        cls._root_logger = root

    def _log(self, level: int, event: str, **kwargs: Any) -> None:
        """구조화된 로그 출력"""
        extra = {
            "crawler": self.name,
            "event": event,
            "execution_id": self._execution_id,
            **kwargs,
        }
        self.logger.log(level, "", extra=extra)

    # === HTTP 요청 로깅 ===

    def http_request(
        self,
        method: str,
        url: str,
        status: int,
        elapsed_ms: float,
        size: int = 0,
        response_body: str | None = None,
    ) -> None:
        """
        HTTP 요청/응답 로깅

        Args:
            method: HTTP 메서드 (GET, POST 등)
            url: 요청 URL
            status: 응답 상태 코드
            elapsed_ms: 응답 시간 (밀리초)
            size: 응답 크기 (바이트)
            response_body: 응답 본문 (DEBUG 레벨에서만 기록)
        """
        self._log(
            logging.DEBUG,
            "http_request",
            method=method,
            url=url,
            status=status,
            elapsed_ms=round(elapsed_ms, 1),
            size=size,
            response_body=response_body,
        )

    def http_error(
        self,
        method: str,
        url: str,
        error: str,
        elapsed_ms: float = 0,
    ) -> None:
        """HTTP 요청 실패 로깅"""
        self._log(
            logging.ERROR,
            "http_error",
            method=method,
            url=url,
            error=error,
            elapsed_ms=round(elapsed_ms, 1),
        )

    # === 검색 로깅 ===

    def search_start(
        self,
        query: str,
        session_id: str | None = None,
        original_query: str | None = None,
        attempt: int = 1,
    ) -> None:
        """검색 시작 로깅"""
        self._log(
            logging.INFO, "search_start",
            query=query,
            session_id=session_id,
            original_query=original_query,
            attempt=attempt,
        )

    def search_complete(
        self,
        query: str,
        found: bool,
        title: str = "",
        product_id: str = "",
        method: str = "",
        session_id: str | None = None,
        original_query: str | None = None,
        attempt: int = 1,
    ) -> None:
        """
        검색 완료 로깅

        Args:
            query: 검색어
            found: 검색 성공 여부
            title: 찾은 책 제목
            product_id: 상품 ID
            method: 검색 방식 (api, html, cloudscraper)
            session_id: 크롤링 세션 ID
            original_query: 최초 검색어
            attempt: 시도 번호
        """
        level = logging.INFO if found else logging.WARNING
        self._log(
            level,
            "search_complete",
            query=query,
            found=found,
            title=title,
            product_id=product_id,
            method=method,
            session_id=session_id,
            original_query=original_query,
            attempt=attempt,
        )

    # === 평점 로깅 ===

    def rating_complete(
        self,
        rating: float | None,
        review_count: int,
        method: str,
        rating_scale: int = 10,
    ) -> None:
        """
        평점 추출 완료 로깅

        Args:
            rating: 평점 (None이면 추출 실패)
            review_count: 리뷰 수
            method: 추출 방식 (api, html, json-ld)
            rating_scale: 평점 만점 (5 또는 10)
        """
        level = logging.INFO if rating is not None else logging.WARNING
        self._log(
            level,
            "rating_complete",
            rating=rating,
            rating_scale=rating_scale,
            review_count=review_count,
            method=method,
        )

    # === 크롤링 플로우 로깅 ===

    def crawl_start(self, query: str) -> None:
        """크롤링 시작 로깅"""
        self._log(logging.INFO, "crawl_start", query=query)

    def crawl_complete(
        self,
        query: str,
        success: bool,
        elapsed_ms: float,
        title: str = "",
        rating: float | None = None,
        review_count: int = 0,
        session_id: str | None = None,
        original_query: str | None = None,
        attempt: int = 1,
    ) -> None:
        """크롤링 완료 로깅"""
        level = logging.INFO if success else logging.WARNING
        self._log(
            level,
            "crawl_complete",
            query=query,
            success=success,
            elapsed_ms=round(elapsed_ms, 1),
            title=title,
            rating=rating,
            review_count=review_count,
            session_id=session_id,
            original_query=original_query,
            attempt=attempt,
        )

    def search_summary(
        self, query: str, results: list[dict[str, Any]], elapsed_ms: float, all_platforms: list[str] | None = None
    ) -> None:
        """
        전체 검색 실행 요약 로깅
        
        하나의 execution_id 아래 모든 플랫폼의 결과를 요약하여 기록합니다.
        OpenObserve 등에서 필드 누락 에러를 방지하기 위해 모든 플랫폼의 키를 생성합니다.
        """
        summary = {
            "query": query,
            "elapsed_ms": round(elapsed_ms, 1),
            "platform_count": len(results),
        }
        
        # 플랫폼별 결과 맵 생성
        results_map = {r["platform"]: r for r in results}
        
        # 모든 플랫폼에 대해 필드 생성 (데이터가 없으면 None/0)
        platforms_to_log = all_platforms or [r["platform"] for r in results]
        
        for p in platforms_to_log:
            res = results_map.get(p, {})
            # OpenObserve 대시보드에서는 비교를 위해 10점 만점 기준(normalized_rating)을 사용합니다.
            rating = res.get("rating")
            scale = res.get("rating_scale", 10)
            normalized = None
            if rating is not None:
                normalized = (rating * 2) if scale == 5 else rating
            
            summary[f"res_{p}_rating"] = normalized
            summary[f"res_{p}_reviews"] = res.get("review_count", 0)
            summary[f"res_{p}_elapsed"] = round(res.get("elapsed_ms", 0), 1)

        self._log(logging.INFO, "search_summary", **summary)

    # === 에러 로깅 ===

    def error(self, event: str, error: str, context: dict[str, Any] | None = None) -> None:
        """에러 로깅"""
        self._log(
            logging.ERROR,
            event,
            error=error,
            **(context or {}),
        )

    # === 디버그 로깅 ===

    def debug(self, debug_msg: str, **kwargs: Any) -> None:
        """디버그 메시지 로깅"""
        self._log(logging.DEBUG, "debug", debug_msg=debug_msg, **kwargs)

    def api_response(self, endpoint: str, data: dict[str, Any]) -> None:
        """API 응답 데이터 로깅 (DEBUG)"""
        self._log(
            logging.DEBUG,
            "api_response",
            endpoint=endpoint,
            data=data,
        )

    def parse_result(self, selector: str, value: Any) -> None:
        """파싱 결과 로깅 (DEBUG)"""
        self._log(
            logging.DEBUG,
            "parse_result",
            selector=selector,
            value=value,
        )
