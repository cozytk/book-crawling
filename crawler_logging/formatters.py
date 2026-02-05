"""로그 포매터"""

import json
import logging
from datetime import datetime, timezone
from typing import Any


class ConsoleFormatter(logging.Formatter):
    """
    콘솔용 사람이 읽기 쉬운 포맷

    출력 예시:
    2024-01-15 10:30:45 [INFO] [kyobo] 검색 완료: "클린 코드" → S000001032980
    2024-01-15 10:30:45 [DEBUG] [kyobo] HTTP GET https://... (245ms, 45KB)
    """

    # ANSI 색상 코드
    COLORS = {
        logging.DEBUG: "\033[36m",  # Cyan
        logging.INFO: "\033[32m",   # Green
        logging.WARNING: "\033[33m",  # Yellow
        logging.ERROR: "\033[31m",  # Red
    }
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

    def format(self, record: logging.LogRecord) -> str:
        # 기본 타임스탬프
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 레벨 색상
        level_color = self.COLORS.get(record.levelno, "")
        level_name = record.levelname

        # extra 데이터 추출
        crawler = getattr(record, "crawler", "")
        event = getattr(record, "event", "")

        # 기본 prefix
        prefix = f"{self.DIM}{timestamp}{self.RESET} [{level_color}{level_name}{self.RESET}]"
        if crawler:
            prefix += f" [{self.BOLD}{crawler}{self.RESET}]"

        # 이벤트별 포맷팅
        message = self._format_event(record, event)

        return f"{prefix} {message}"

    def _format_event(self, record: logging.LogRecord, event: str) -> str:
        """이벤트 타입별 메시지 포맷팅"""

        if event == "http_request":
            method = getattr(record, "method", "GET")
            url = getattr(record, "url", "")
            status = getattr(record, "status", 0)
            elapsed_ms = getattr(record, "elapsed_ms", 0)
            size = getattr(record, "size", 0)

            # URL 축약 (너무 길면)
            if len(url) > 80:
                url = url[:77] + "..."

            size_str = self._format_size(size)
            return f"HTTP {method} {url}\n  → {status} ({elapsed_ms:.0f}ms, {size_str})"

        elif event == "http_error":
            method = getattr(record, "method", "GET")
            url = getattr(record, "url", "")
            error = getattr(record, "error", "")
            return f"HTTP {method} 실패: {url}\n  → {error}"

        elif event == "search_start":
            query = getattr(record, "query", "")
            return f"검색 중: \"{query}\""

        elif event == "search_complete":
            query = getattr(record, "query", "")
            found = getattr(record, "found", False)
            title = getattr(record, "title", "")
            product_id = getattr(record, "product_id", "")
            method = getattr(record, "method", "")

            if found:
                method_str = f" ({method})" if method else ""
                id_str = f" → {product_id}" if product_id else ""
                return f"검색 완료: \"{title}\"{id_str}{method_str}"
            else:
                return f"검색 결과 없음: \"{query}\""

        elif event == "rating_complete":
            rating = getattr(record, "rating", None)
            rating_scale = getattr(record, "rating_scale", 10)
            review_count = getattr(record, "review_count", 0)
            method = getattr(record, "method", "")

            if rating is not None:
                method_str = f" ({method})" if method else ""
                normalized = rating * 2 if rating_scale == 5 else rating
                return f"평점: {normalized}/10, 리뷰: {review_count:,}개{method_str}"
            else:
                return f"평점 추출 실패 (리뷰: {review_count:,}개)"

        elif event == "crawl_start":
            query = getattr(record, "query", "")
            return f"크롤링 시작: \"{query}\""

        elif event == "crawl_complete":
            success = getattr(record, "success", False)
            elapsed_ms = getattr(record, "elapsed_ms", 0)
            title = getattr(record, "title", "")
            rating = getattr(record, "rating", None)
            review_count = getattr(record, "review_count", 0)

            if success:
                return f"크롤링 완료: \"{title}\" ({elapsed_ms:.0f}ms)"
            else:
                return f"크롤링 실패 ({elapsed_ms:.0f}ms)"

        elif event == "api_response":
            endpoint = getattr(record, "endpoint", "")
            data = getattr(record, "data", {})
            # 데이터를 간략히 표시
            data_str = json.dumps(data, ensure_ascii=False)
            if len(data_str) > 200:
                data_str = data_str[:197] + "..."
            return f"API 응답 [{endpoint}]: {data_str}"

        elif event == "parse_result":
            selector = getattr(record, "selector", "")
            value = getattr(record, "value", "")
            return f"파싱: {selector} = {value}"

        elif event == "debug":
            debug_msg = getattr(record, "debug_msg", "")
            return debug_msg

        else:
            # 기본: 모든 extra 필드 출력
            error = getattr(record, "error", "")
            if error:
                return f"{event}: {error}"
            return event

    def _format_size(self, size: int) -> str:
        """바이트 크기를 읽기 쉬운 형식으로"""
        if size < 1024:
            return f"{size}B"
        elif size < 1024 * 1024:
            return f"{size / 1024:.1f}KB"
        else:
            return f"{size / (1024 * 1024):.1f}MB"


class JsonFormatter(logging.Formatter):
    """
    JSON Lines 포맷 (기계 분석용)

    출력 예시:
    {"ts":"2024-01-15T10:30:45.123Z","level":"INFO","crawler":"kyobo","event":"search_complete",...}
    """

    def format(self, record: logging.LogRecord) -> str:
        # 기본 필드
        log_entry: dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
        }

        # extra 필드 추가 (내부 속성 제외)
        skip_attrs = {
            "name", "msg", "args", "created", "filename", "funcName",
            "levelname", "levelno", "lineno", "module", "msecs",
            "pathname", "process", "processName", "relativeCreated",
            "stack_info", "exc_info", "exc_text", "thread", "threadName",
            "taskName", "message",
        }

        for key, value in record.__dict__.items():
            if key not in skip_attrs and not key.startswith("_"):
                # JSON 직렬화 가능한 값만 포함
                if isinstance(value, (str, int, float, bool, type(None), list, dict)):
                    log_entry[key] = value
                else:
                    log_entry[key] = str(value)

        return json.dumps(log_entry, ensure_ascii=False)
