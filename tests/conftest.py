"""공통 테스트 fixtures"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock


@pytest.fixture
def fixtures_dir():
    """테스트 fixtures 디렉토리 경로"""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def load_fixture(fixtures_dir):
    """fixture 파일 로드 헬퍼"""
    def _load(filename: str, encoding: str = "utf-8") -> str:
        return (fixtures_dir / filename).read_text(encoding=encoding)
    return _load


@pytest.fixture
def mock_aladin_key(monkeypatch):
    """알라딘 API 키 모킹"""
    monkeypatch.setenv("ALADIN_TTB_KEY", "test_ttb_key_12345")


@pytest.fixture
def mock_urlopen():
    """urllib.request.urlopen 모킹을 위한 헬퍼"""
    def _create_mock(content: bytes, encoding: str = "utf-8"):
        mock_response = MagicMock()
        mock_response.read.return_value = content
        mock_response.geturl.return_value = "https://example.com"
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        return mock_response
    return _create_mock
