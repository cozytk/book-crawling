"""크롤러 공통 유틸리티"""

import json
import math
import re
import unicodedata

# Name variants observed in the source catalogs. These map people, never scores.
AUTHOR_ALIASES = {
    "tolstoy": ("레프 니콜라예비치 톨스토이", "레프 톨스토이", "Leo Tolstoy", "Lev Tolstoy", "Лев Толстой", "Л. Н. Толстой"),
    "maugham": ("서머싯 몸", "서머셋 몸", "서머셋 모옴", "서머싯 모옴", "Somerset Maugham"),
    "dostoevsky": ("표도르 도스토옙스키","표도르 도스토예프스키","Fyodor Dostoevsky","Fyodor Dostoyevsky","Федор Достоевский","Фёдор Достоевский"),
}


def author_keys(value):
    normalize = lambda text: "".join(c for c in unicodedata.normalize("NFKC", str(text)).casefold() if c.isalpha())
    text = normalize(" ".join(value) if isinstance(value, list) else value)
    keys={key for key, aliases in AUTHOR_ALIASES.items() if any(normalize(alias) in text for alias in aliases)}
    if text in {"도스토예프스키","도스토옙스키"}:
        keys.add("dostoevsky")
    return keys


def bilingual_titles(value):
    """Accept explicit alternate-script titles, not arbitrary subtitle fragments."""
    parts = re.split(r"\s[/=-]\s", value)
    def scripts(part):
        return {unicodedata.name(c, "").split(" ")[0] for c in part if c.isalpha()}
    if len(parts) > 1 and len({tuple(sorted(scripts(p))) for p in parts}) > 1:
        return parts
    return [value]


def candidate_score(query, title, author="", expected_author=None):
    if expected_author and (not author or not author_matches(expected_author, author)):
        return 0.0
    score = title_score(query, title)
    if score or not author:
        return score
    # "title author" and "author title" are supported only when the removed
    # words occur in this candidate's actual author metadata.
    author_words = set(re.findall(r"[\w]+", str(author).casefold())) - {"저", "역", "지은이", "옮긴이"}
    words = query.split()
    remaining = [w for w in words if w.casefold() not in author_words]
    return title_score(" ".join(remaining), title) if remaining != words and remaining else 0.0


def edition_preference(query, title):
    """Within a verified work, prefer volume 1 when no volume was requested."""
    if re.search(r"\d|(?<![가-힣])[상중하](?![가-힣])", query):
        return 0
    match = re.search(r"(?:\s|\()(\d{1,2})\s*(?:권|부|편)?(?:\)|\s|$)", title)
    return -min(int(match.group(1)), 99) if match else 0


def volume_info(title):
    """Explicit trailing volume labels; a numeric work title is not a volume."""
    main=re.split(r'\s[-–—]\s|[:：]',title,maxsplit=1)[0].strip()
    match=re.match(r'^(.*?)\s*(?:\s|[.(（])([1-9]\d?|[상중하])\s*(?:권|부|편)?\s*[)）]?\s*(?:\([^)]*\))?$',main)
    return (match.group(1).strip(' .('),match.group(2)) if match else (title,None)


def title_score(query: str, title: str) -> float:
    """Identity gates precede ranking; subtitles cannot hide a derivative work."""
    def normalize(value):
        value=unicodedata.normalize('NFC',''.join(c for c in unicodedata.normalize('NFD',unicodedata.normalize('NFKC',value).casefold())
                                               if unicodedata.category(c)!='Mn'))
        # A Korean locative ending can differ between the user's short title
        # and the catalog spelling ("아래" / "아래서"). Do not allow arbitrary
        # extra words: all derivative and volume gates below still apply.
        value=re.sub(r'아래서(?=$|\s*[(\[])','아래',value)
        # German catalogs vary the final proper-name genitive (e.g. an older
        # spelling ending in -s). Require a long title and an explicit
        # genitive article; this is not a general suffix/fuzzy-title rule.
        if len(value.split())>=4 and re.search(r'\b(?:des|eines)\b',value):
            value=re.sub(r'\b([a-z]{6,})s(?=$|\s*[(\[])',r'\1',value)
        return "".join(c for c in value if c.isalnum())

    title = re.split(r"\s+by\s+", title, flags=re.I)[0]
    q, t = normalize(query), normalize(title)
    if not q or not t:
        return 0.0
    derivatives = [r"해설", r"워크북", r"문제집", r"독후감", r"요약", r"만화", r"그래픽\s*노[블벨]", r"어린이", r"청소년",
                   r"\bworkbook\b", r"\bstudy guide\b", r"\bsummary\b", r"\babridged\b", r"\badapted\b",
                   r"\bgraphic (?:novel|history|adaptation)\b", r"\bretold\b", r"\bgraded reader\b"]
    if any(bool(re.search(pattern, query, re.I)) != bool(re.search(pattern, title, re.I)) for pattern in derivatives):
        return 0.0
    def volumes(value):
        return re.findall(r"(?<![가-힣])([상중하])(?:권|편)?(?=$|[\s)\]])|(?:제\s*)?(\d+)\s*(?:권|부|편)(?![가-힣])", value)
    if volumes(query) and volumes(query) != volumes(title):
        return 0.0
    if q == t:
        return 1.0
    if re.search(r"[가-힣]", query) and q in t:
        remainder = t.replace(q, "", 1)
        if remainder and remainder.isascii() and remainder.isalpha():
            return 0.90
    if re.findall(r"\d+", q) and re.findall(r"\d+", q) != re.findall(r"\d+", t):
        return 0.0
    primary = normalize(re.split(r"\s[-–—]\s|[:：]", title)[0])
    if q == primary:
        return 0.98
    if q == normalize(re.sub(r"\([^)]*\)|\[[^]]*\]", "", title)):
        return 0.96
    # An unspecified work may be sold in several volumes. A requested volume
    # still passes the explicit volume/number gates above (1 must not match 10).
    if not re.search(r"\d", query) and not volumes(query):
        main = re.split(r"\s[-–—]\s|[:：]", title)[0]
        main = re.sub(r"\s*\([^)]*\)|\[[^]]*\]", "", main).strip()
        without_volume = re.sub(r"\s+(?:[1-9]\d?|[상중하])\s*(?:권|부|편)?$", "", main)
        if q == normalize(without_volume):
            return 0.94
    if re.search(r"[a-zA-Z]", query):
        words = re.findall(r"[a-z0-9]+", query.casefold())
        title_words = set(re.findall(r"[a-z0-9]+", title.casefold()))
        if not all(word in title_words for word in words):
            return 0.0
    # Parenthesized publication notes and bilingual titles are allowed; arbitrary
    # appended words (e.g. 데미안 해설) are not title identity evidence.
    without_notes = normalize(re.sub(r"\([^)]*\)|\[[^]]*\]", "", re.split(r"\s[-–—]\s|[:：]", title)[0]))
    if q == without_notes:
        return 0.96
    if re.search(r"[가-힣]", query) and q in without_notes:
        remainder = without_notes.replace(q, "", 1)
        if remainder and remainder.isascii() and remainder.isalpha():
            return 0.90
    if not re.search(r"[가-힣]", query) and re.search(r"[가-힣]", title):
        english = normalize(re.sub(r"[가-힣]+", "", title))
        if q == english:
            return 0.90
    return 0.0


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


def isbn13(value: str) -> str:
    value = clean_isbn(str(value)).upper()
    if len(value) == 10:
        prefix = "978" + value[:9]
        if not prefix.isdigit():
            return ""
        return prefix + str((10 - sum(int(n) * (1 if i % 2 == 0 else 3) for i, n in enumerate(prefix)) % 10) % 10)
    return value if len(value) == 13 and value.isdigit() else ""


def isbn_matches(expected, candidates):
    return bool(isbn13(expected)) and any(isbn13(expected) == isbn13(candidate) for candidate in candidates)


def valid_rating(value, scale, best=None):
    try:
        value = float(value)
        if best is not None and float(best) != scale:
            return None
        return value if math.isfinite(value) and 0 <= value <= scale else None
    except (TypeError, ValueError):
        return None


def count_number(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(str(value).replace(",", ""))
        return int(number) if math.isfinite(number) and number >= 0 and number.is_integer() else None
    except (TypeError, ValueError):
        return None


def json_nodes(soup):
    def walk(value):
        if isinstance(value, list):
            for entry in value:
                yield from walk(entry)
        elif isinstance(value, dict):
            yield value
            # Only JSON-LD graphs, never recommendations nested in a Book.
            if "@graph" in value:
                yield from walk(value["@graph"])
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            yield from walk(json.loads(script.get_text()))
        except (ValueError, TypeError):
            continue


def book_node(soup, title, allow_product=False):
    for node in json_nodes(soup):
        kinds = node.get("@type", [])
        kinds = [kinds] if isinstance(kinds, str) else kinds
        if not set(kinds) & ({"Book", "Product"} if allow_product else {"Book"}):
            continue
        if title and not title_score(title, str(node.get("name", ""))):
            continue
        return node
    return None


def author_matches(expected, actual, strict_script=False):
    """Only compare compatible scripts; never infer translated-name aliases."""
    if not expected or not actual:
        return True
    if isinstance(expected, (list, tuple)):
        return any(author_matches(name, actual, strict_script=True) for name in expected if name)
    expected_text = " ".join(expected) if isinstance(expected, list) else str(expected)
    actual_text = " ".join(actual) if isinstance(actual, list) else str(actual)
    left_keys, right_keys = author_keys(expected_text), author_keys(actual_text)
    if left_keys and right_keys:
        return bool(left_keys & right_keys)
    if expected_text.strip() in {"도스토예프스키","도스토옙스키"} and not right_keys:
        return False
    def scripts(text):
        return {unicodedata.name(c, "").split(" ")[0] for c in text if c.isalpha()}
    if strict_script and not scripts(expected_text) & scripts(actual_text):
        return False
    if bool(re.search(r"[가-힣]", expected_text)) != bool(re.search(r"[가-힣]", actual_text)):
        return not strict_script and not left_keys
    if re.search(r"[가-힣]", expected_text):
        compact = lambda value: "".join(re.findall(r"[가-힣]", value))
        left_name, right_name = compact(expected_text), compact(actual_text)
        if len(left_name) >= 3 and left_name in right_name:
            return True
    def normalize(value):
        # Latin-only tokenization made any two Cyrillic names match because
        # both token sets were empty. Fold accents but retain Unicode letters.
        folded=unicodedata.normalize('NFC',''.join(c for c in unicodedata.normalize('NFD',value.casefold())
                                                if unicodedata.category(c)!='Mn'))
        return set(re.findall(r'[^\W\d_]+',folded)) - {"by", "author", "지은이", "옮긴이"}
    left, right = normalize(expected_text), normalize(actual_text)
    return len(left & right) >= min(2, len(left), len(right)) if left and right else False


def structured_isbns(container):
    """Only explicit product identifier fields, never arbitrary page text."""
    values = []
    for node in [container, *container.select('[data-isbn], [data-isbn13], [data-isbn10], [data-bid], [data-pid], [name="isbn"], [itemprop="isbn"]')]:
        for attr in ("data-isbn", "data-isbn13", "data-isbn10", "data-bid", "data-pid", "content", "value"):
            value = node.get(attr)
            if value and is_isbn(str(value)):
                values.append(str(value))
        if node.get("itemprop") == "isbn":
            values.append(node.get_text(strip=True))
    for node in container.select('[id*="isbn"], [id*="ISBN"]'):
        values.extend(re.findall(r"(?<!\d)(?:97[89][\d -]{10,20}|[\d -]{9,18}[\dX])(?!\d)", node.get_text(" ", strip=True)))
    return values
