"""OpenObserve 로그 핸들러"""

import atexit
import json
import logging
import urllib.request
from base64 import b64encode
from datetime import datetime, timezone, timedelta
from typing import Any

# 모든 OpenObserve 핸들러 인스턴스 추적 (종료 시 flush용)
_handlers: list["OpenObserveHandler"] = []


def _flush_all_handlers() -> None:
    """프로그램 종료 시 모든 핸들러 flush"""
    for handler in _handlers:
        handler.flush()


atexit.register(_flush_all_handlers)


class OpenObserveHandler(logging.Handler):
    """
    OpenObserve HTTP API로 로그 전송하는 핸들러

    API: POST /api/{org}/{stream}/_json
    인증: Basic Auth (base64 encoded)
    포맷: JSON Array
    """

    def __init__(
        self,
        url: str = "http://localhost:5080",
        org: str = "default",
        stream: str = "crawler",
        username: str = "admin@example.com",
        password: str = "admin123",
        buffer_size: int = 10,
    ):
        super().__init__()
        self.endpoint = f"{url}/api/{org}/{stream}/_json"
        self.auth = b64encode(f"{username}:{password}".encode()).decode()
        _handlers.append(self)
        self._buffer: list[dict[str, Any]] = []
        self._buffer_size = buffer_size

    def emit(self, record: logging.LogRecord) -> None:
        """로그 레코드를 버퍼에 추가하고 일정량 모이면 전송"""
        try:
            log_entry = self._format_record(record)
            self._buffer.append(log_entry)

            if len(self._buffer) >= self._buffer_size:
                self.flush()
        except Exception:
            self.handleError(record)

    def _format_record(self, record: logging.LogRecord) -> dict[str, Any]:
        """LogRecord를 OpenObserve 형식으로 변환"""
        data: dict[str, Any] = {
            "_timestamp": int(record.created * 1_000_000),  # microseconds
            "ts": datetime.fromtimestamp(
                record.created, tz=timezone(timedelta(hours=9))
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
        }

        # extra 필드 추가 (crawler, event, rating 등)
        skip_attrs = {
            "name", "msg", "args", "created", "filename", "funcName",
            "levelname", "levelno", "lineno", "module", "msecs",
            "pathname", "process", "processName", "relativeCreated",
            "stack_info", "exc_info", "exc_text", "thread", "threadName",
            "taskName", "message",
        }

        for key, value in record.__dict__.items():
            if key not in skip_attrs and not key.startswith("_"):
                if isinstance(value, (str, int, float, bool, type(None))):
                    data[key] = value
                elif isinstance(value, (list, dict)):
                    data[key] = value

        return data

    def flush(self) -> None:
        """버퍼의 로그를 OpenObserve로 전송"""
        if not self._buffer:
            return

        try:
            body = json.dumps(self._buffer).encode("utf-8")
            req = urllib.request.Request(
                self.endpoint,
                data=body,
                method="POST",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Basic {self.auth}",
                },
            )
            urllib.request.urlopen(req, timeout=5)
        except Exception:
            pass  # 로그 전송 실패 시 무시 (크롤링에 영향 없도록)
        finally:
            self._buffer.clear()

    def close(self) -> None:
        """핸들러 종료 시 남은 버퍼 전송"""
        self.flush()
        super().close()
