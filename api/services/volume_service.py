"""Collect a verified publisher/translator's volumes without counting a set twice."""
import asyncio

from models.book import PlatformRating


def aggregate_volumes(platform, identity, entries):
    # Keep failed volumes in the evidence list; never turn them into zero stars.
    valid=[entry for entry in entries if entry.get('rating') is not None]
    unique={entry['url']:entry for entry in valid}
    valid=list(unique.values())
    if not valid:
        return None
    scale=valid[0]['rating_scale']
    valid=[entry for entry in valid if entry['rating_scale']==scale]
    labels=[str(e['volume']) for e in entries]
    expected=list(map(str,range(1,(identity.volume_total or max(map(int,labels)))+1))) if all(v.isdigit() for v in labels) else labels
    for label in expected:
        if label not in labels:
            entries.append({'volume':label,'book_title':f'{identity.title} {label}','rating':None,'status':'unavailable'})
    complete=len(valid)==len(expected) and set(labels)==set(expected)
    total=lambda key:sum(e[key] for e in entries) if complete and all(e.get(key) is not None for e in entries) else None
    first=valid[0]
    count=len(valid)
    note=f"{identity.publisher or ''} · {identity.translator or ''} · {count}/{len(expected)}권 단순 평균".strip(' ·')
    if not complete:
        note+=' · 일부 권 미확인'
    return PlatformRating(platform,round(sum(e['rating'] for e in valid)/count,6),scale,total('review_count'),
        first['url'],identity.title or first['book_title'],rating_count=total('rating_count'),
        text_review_count=total('text_review_count'),author=identity.author,
        short_review_count=total('short_review_count'),
        comparison_scope='volume_group',edition_note=note,volume_results=entries,
        aggregation_method='volume_mean',aggregate_complete=complete,
        publisher=identity.publisher,translator=identity.translator)


async def collect_volumes(platform, identity, crawl, serialize, timeout, on_failure=None):
    async def one(edition):
        failures=[]
        try:
            rating=await asyncio.wait_for(crawl(edition,failures.append),timeout)
            if rating:
                return {**serialize(rating),'volume':edition['volume'],'status':'done' if rating.rating is not None else 'parse_error'}
            status=failures[-1] if failures else 'not_found'
        except asyncio.TimeoutError:
            status='timeout'
        except Exception:
            status='network_error'
        return {'volume':edition['volume'],'book_title':edition['title'],'isbn':edition['isbn'],
                'url':edition['url'] if platform=='kyobo' else '', 'rating':None,'status':status}
    entries=await asyncio.gather(*(one(edition) for edition in identity.editions))
    result=aggregate_volumes(platform,identity,entries)
    if result is None and on_failure:
        rank={'identity_mismatch':6,'blocked':5,'timeout':4,'network_error':4,'parse_error':3,'unavailable':2,'not_found':1}
        on_failure(max((e['status'] for e in entries),key=lambda value:rank.get(value,0)))
    return result
