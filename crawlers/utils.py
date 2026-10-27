"""크롤러 공통 유틸리티"""

import difflib
import re
import unicodedata


def title_score(query: str, title: str) -> float:
    """Popularity must never make an unrelated book a title match."""
    def normalize(value):
        return "".join(c for c in unicodedata.normalize("NFKC", value).casefold() if c.isalnum())

    q, t = normalize(query), normalize(title)
    if not q or not t:
        return 0.0
    if q == t:
        return 1.0
    if re.findall(r"\d+", q) and re.findall(r"\d+", q) != re.findall(r"\d+", t):
        return 0.0
    primary = normalize(re.split(r"\s[-–—]\s|[:：]", title)[0])
    if q == primary:
        return 0.98
    if re.search(r"[a-zA-Z]", query):
        words = re.findall(r"[a-z0-9]+", query.casefold())
        title_words = set(re.findall(r"[a-z0-9]+", title.casefold()))
        if not all(word in title_words for word in words):
            return 0.0
    if len(q) >= 3 and q in t:
        return 0.85
    # Short titles and volume numbers require exact matching.
    if len(q) < 4 or re.findall(r"\d+", q) != re.findall(r"\d+", t):
        return 0.0
    score = difflib.SequenceMatcher(None, q, t).ratio()
    return score if score >= 0.8 else 0.0


def is_isbn(query: str) -> bool:
    """ISBN-10 또는 ISBN-13 형식인지 확인

    Args:
        query: 검색어

    Returns:
        True if ISBN 형식 (10/13자리 숫자)
    """
    clean = query.replace("-", "").replace(" ", "")
    return (clean.isdigit() and len(clean) in (10, 13)) or (len(clean) == 10 and clean[:9].isdigit() and clean[-1].upper() == "X")


def clean_isbn(isbn: str) -> str:
    """ISBN에서 하이픈/공백 제거"""
    return isbn.replace("-", "").replace(" ", "")
