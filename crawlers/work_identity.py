"""Choose one work before comparing independently ranked shop editions."""
import re
from dataclasses import dataclass

from .aladin import AladinCrawler
from .kyobo import KyoboCrawler
from .transport import run_parser, active_transport
from .utils import is_isbn, volume_info


@dataclass(frozen=True)
class WorkIdentity:
    author: str | None = None
    title: str | None = None
    isbn: str | None = None
    editions: tuple[dict, ...] = ()
    publisher: str | None = None
    translator: str | None = None
    volume_total: int | None = None


def work_identity(query):
    """One shared factory; safe to call from an already running parser worker."""
    def identify():
        # The public Kyobo list supplies title/author/ISBN in one request and
        # keeps discovery independent of a slow or unavailable TTB account.
        crawler=KyoboCrawler()
        url,title=crawler.search_by_keyword(query)
        groups={}
        for candidate in getattr(crawler,"discovery_candidates",[]):
            if not candidate["author"] or not candidate["isbn"]:
                continue
            key=candidate["author_id"] or re.sub(r"\W","",candidate["author"]).casefold()
            groups.setdefault(key,{})[candidate["isbn"]]=candidate
        if groups:
            # Rank a work's author group before its spelling/volume variant.
            # An exact-title namesake must not outrank a well-supported work
            # merely because the latter is sold as volumes 1 and 2.
            group=max(groups.values(),key=lambda entries:(sum(c["reviews"] for c in entries.values()),len(entries)))
            editions=()
            family_chosen=None
            if not volume_info(query)[1]:
                families={}
                for candidate in group.values():
                    base,volume=volume_info(candidate['title'])
                    if candidate.get('publisher'):
                        key=(candidate['publisher'],candidate.get('translator',''),re.sub(r'\W','',base),bool(volume))
                        label=volume or 'single'
                        previous=families.setdefault(key,{}).get(label)
                        if not previous or candidate['reviews']>previous['reviews']:
                            families[key][label]={**candidate,'volume':volume}
                if families:
                    family=max(families.values(),key=lambda entries:sum(c['reviews'] for c in entries.values()))
                    family_chosen=max(family.values(),key=lambda c:c['reviews'])
                    if len(family)>1 and all(c['volume'] for c in family.values()):
                        order=lambda c:int(c['volume']) if c['volume'].isdigit() else {'상':1,'중':2,'하':3}[c['volume']]
                        editions=tuple(sorted(family.values(),key=order))
            chosen=editions[0] if editions else family_chosen or max(group.values(),key=lambda c:(c["reviews"],c["score"]))
            title=chosen["title"]
            url=chosen["url"]
            crawler.book_author=chosen["author"]
            crawler.book_isbn=chosen["isbn"]
            transport=active_transport()
            if transport:
                for edition in editions or (chosen,):
                    transport.memo(("kyobo-selected",query,edition["isbn"]),lambda edition=edition:edition)
                    transport.memo(("kyobo-selected",edition['isbn'],edition['isbn']),lambda edition=edition:edition)
        if url and crawler.book_author and crawler.book_isbn:
            writer_words=set(crawler.book_author.split())
            local_title=" ".join(w for w in query.split() if w not in writer_words) or query
            if not re.search(r"[가-힣]",query) and re.search(r"[가-힣]",title):
                local_title=re.sub(r"[A-Za-z][A-Za-z\s]*","",re.split(r"\s[-–—]\s|[:：]",title)[0]).strip("()[] ")
            total=next((s['total'] for s in getattr(crawler,'series_sizes',[]) if groups and s['publisher']==chosen.get('publisher') and s['translator']==chosen.get('translator')),None)
            return WorkIdentity(crawler.book_author,local_title,crawler.book_isbn,
                editions if groups else (),chosen.get('publisher') if groups else None,chosen.get('translator') if groups else None,total)

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
