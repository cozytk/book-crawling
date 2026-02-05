"""크롤러 공통 유틸리티"""


def is_isbn(query: str) -> bool:
    """ISBN-10 또는 ISBN-13 형식인지 확인

    Args:
        query: 검색어

    Returns:
        True if ISBN 형식 (10/13자리 숫자)
    """
    clean = query.replace("-", "").replace(" ", "")
    return clean.isdigit() and len(clean) in (10, 13)


def clean_isbn(isbn: str) -> str:
    """ISBN에서 하이픈/공백 제거"""
    return isbn.replace("-", "").replace(" ", "")
