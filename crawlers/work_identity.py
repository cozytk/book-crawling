"""Choose one work before comparing independently ranked shop editions."""
import asyncio
import re
from dataclasses import dataclass

from .aladin import AladinCrawler
from .transport import run_parser
from .utils import is_isbn


@dataclass(frozen=True)
class WorkIdentity:
    author: str | None = None
    title: str | None = None
    isbn: str | None = None


async def resolve_work_identity(query: str) -> WorkIdentity:
    if is_isbn(query):
        return WorkIdentity()

    async def identify():
        async with AladinCrawler() as crawler:
            await crawler.search_book(query)
            item = getattr(crawler, "_current_item", {})
            author, _ = crawler._parse_author(item.get("author", ""))
            author_words = set((author or "").split())
            title = " ".join(w for w in query.split() if w not in author_words)
            if not re.search(r"[가-힣]", query) and re.search(r"[가-힣]", item.get("title", "")):
                main = re.split(r"\s[-–—]\s|[:：]", item["title"])[0]
                korean = re.sub(r"[A-Za-z][A-Za-z\s]*", "", main).strip()
                if re.search(r"[가-힣]", korean):
                    title = korean
            return WorkIdentity(author, title or query, item.get("isbn13") or item.get("isbn"))

    result, _ = await run_parser(lambda: asyncio.run(identify()))
    return result
