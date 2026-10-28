"""Choose one work before comparing independently ranked shop editions."""
import re
from dataclasses import dataclass

from .aladin import AladinCrawler
from .kyobo import KyoboCrawler
from .transport import run_parser, active_transport
from .utils import is_isbn


@dataclass(frozen=True)
class WorkIdentity:
    author: str | None = None
    title: str | None = None
    isbn: str | None = None


def work_identity(query):
    """One shared factory; safe to call from an already running parser worker."""
    def identify():
        # The public Kyobo list supplies title/author/ISBN in one request and
        # keeps discovery independent of a slow or unavailable TTB account.
        crawler=KyoboCrawler()
        url,title=crawler.search_by_keyword(query)
        if url and crawler.book_author and crawler.book_isbn:
            writer_words=set(crawler.book_author.split())
            local_title=" ".join(w for w in query.split() if w not in writer_words) or query
            if not re.search(r"[가-힣]",query) and re.search(r"[가-힣]",title):
                local_title=re.sub(r"[A-Za-z][A-Za-z\s]*","",re.split(r"\s[-–—]\s|[:：]",title)[0]).strip("()[] ")
            return WorkIdentity(crawler.book_author,local_title,crawler.book_isbn)

        fallback=AladinCrawler()
        fallback.search_book_sync(query)
        item=getattr(fallback,"_current_item",{})
        author,_=fallback._parse_author(item.get("author",""))
        author_words=set((author or "").split())
        local_title=" ".join(w for w in query.split() if w not in author_words)
        return WorkIdentity(author,local_title or query,item.get("isbn13") or item.get("isbn"))
    transport=active_transport()
    return transport.memo(("work-identity",query),identify) if transport else identify()


async def resolve_work_identity(query: str) -> WorkIdentity:
    if is_isbn(query):
        return WorkIdentity()

    result, _ = await run_parser(lambda: work_identity(query))
    return result
