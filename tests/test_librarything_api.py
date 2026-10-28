"""Official Work Info response semantics and verified ISBN routing."""
import asyncio
import json
from unittest.mock import patch

import httpx
import pytest

from crawlers.librarything import LibraryThingCrawler
from crawlers.transport import SearchTransport, PageResponse, run_parser


ISBN = "9780192833983"


def response(**overrides):
    item = {"id":ISBN, "type":"isbn", "work":"995",
            "link":"https://www.librarything.com/work/995", "copies":"34338",
            "reviews":"520", "rating":8.51}
    item.update(overrides)
    return "/* official helper code omitted */\nLT_workinfo(" + json.dumps({ISBN:item}) + ");"


async def test_work_info_uses_verified_isbn_and_skips_blocked_html():
    calls=[]
    async def handler(request):
        calls.append(request)
        return httpx.Response(200, text=response())
    async with SearchTransport(httpx.AsyncClient(transport=httpx.MockTransport(handler))):
        def search():
            crawler=LibraryThingCrawler()
            crawler.expected_identity("War and Peace", "Leo Tolstoy", strict_isbn=False)
            crawler._preferred_isbn=ISBN
            return asyncio.run(crawler.crawl("War and Peace"))
        record, failure = await run_parser(search)
    assert failure is None and len(calls)==1
    assert calls[0].url.path=="/api/json/workinfo.js"
    assert calls[0].url.params['ids']==ISBN
    assert record.url=="https://www.librarything.com/work/995"
    assert record.rating==4.255 and record.rating_scale==5
    assert record.text_review_count==520 and record.review_count==520
    assert record.rating_count is None  # copies are not star-rating participants
    assert record.author=="Leo Tolstoy" and record.comparison_scope=="work"


def test_catalog_work_isbns_can_resolve_a_sparse_or_split_librarything_work():
    partial="9781909115033"
    payload={partial:{"id":partial,"type":"isbn","work":"3796965",
        "link":"https://www.librarything.com/work/3796965","copies":"978","reviews":"17","rating":8.75},
        ISBN:{"id":ISBN,"type":"isbn","work":"995","link":"https://www.librarything.com/work/995",
              "copies":"34338","reviews":"520","rating":8.51}}
    crawler=LibraryThingCrawler()
    crawler._related_isbns=(ISBN,)
    body='LT_workinfo('+json.dumps(payload)+');'
    with patch('crawlers.librarything.fetch_sync',return_value=PageResponse(body,'https://www.librarything.com')):
        assert crawler._work_info(partial)[0]=='https://www.librarything.com/work/995'
    assert crawler.book_isbn==ISBN and crawler._cached_rating==4.255
    # A user-specified ISBN is not expanded to the other catalog editions.
    exact=LibraryThingCrawler()
    with patch('crawlers.librarything.fetch_sync',return_value=PageResponse(body,'https://www.librarything.com')):
        assert exact._work_info(partial)[0]=='https://www.librarything.com/work/3796965'


def test_catalog_isbn_outlier_cannot_win_by_a_larger_unrelated_work():
    # Native audit: one Werther catalog ISBN mapped to Fathers and Sons. That
    # unrelated work had more copies than Werther, which had 32 ISBN votes.
    correct=['9788494653148','9780140445039']
    wrong='9788498198294'
    def item(isbn,work,copies):
        return {'id':isbn,'type':'isbn','work':work,'link':f'https://www.librarything.com/work/{work}',
                'copies':str(copies),'reviews':'155','rating':7.23}
    payload={isbn:item(isbn,'28158',9488) for isbn in correct}
    payload[wrong]=item(wrong,'3493',10235)
    crawler=LibraryThingCrawler()
    crawler._related_isbns=tuple(correct)
    with patch('crawlers.librarything.fetch_sync',return_value=PageResponse('LT_workinfo('+json.dumps(payload)+');','https://www.librarything.com')):
        assert crawler._work_info(wrong)[0]=='https://www.librarything.com/work/28158'
    # Explicit ISBN searches retain the site's exact mapping.
    exact=LibraryThingCrawler()
    with patch('crawlers.librarything.fetch_sync',return_value=PageResponse('LT_workinfo('+json.dumps(payload)+');','https://www.librarything.com')):
        assert exact._work_info(wrong)[0]=='https://www.librarything.com/work/3493'


@pytest.mark.parametrize('overrides', [
    {'id':'9780451530172'}, {'type':'lccn'}, {'link':'https://example.com/work/995'},
    {'link':'https://www.librarything.com/work/7701'}, {'work':'0'}, {'rating':11},
    {'rating':float('nan')},
])
def test_work_info_rejects_wrong_identifiers_untrusted_links_and_scores(overrides):
    crawler=LibraryThingCrawler()
    with patch('crawlers.librarything.fetch_sync',return_value=PageResponse(response(**overrides),'https://www.librarything.com')):
        assert crawler._work_info(ISBN)==(None,"")
    assert not crawler._rating_loaded


def test_work_info_zero_is_not_a_zero_star_average_and_unknown_counts_stay_unknown():
    crawler=LibraryThingCrawler()
    with patch('crawlers.librarything.fetch_sync',return_value=PageResponse(response(rating=0,reviews=None),'https://www.librarything.com')):
        assert crawler._work_info(ISBN)[0]
    assert crawler._cached_rating is None
    assert crawler.text_review_count is None and crawler.rating_count is None


def test_work_info_never_evaluates_javascript_or_uses_another_response_entry():
    crawler=LibraryThingCrawler()
    for body in ['LT_workinfo({});',response()+'\nthrow new Error("unexpected script")']:
        with patch('crawlers.librarything.fetch_sync',return_value=PageResponse(body,'https://www.librarything.com')):
            assert crawler._work_info(ISBN)==(None,"")


async def test_librarything_api_request_spacing_is_cancelable_and_shared():
    times=[]
    async def handler(request):
        times.append(asyncio.get_running_loop().time())
        return httpx.Response(200,text='LT_workinfo({});')
    async with SearchTransport(httpx.AsyncClient(transport=httpx.MockTransport(handler))) as transport:
        first='https://www.librarything.com/api/json/workinfo.js?ids=1'
        second='https://www.librarything.com/api/json/workinfo.js?ids=2'
        await asyncio.gather(transport.get(first),transport.get(first),transport.get(second))
        assert len(times)==2 and times[1]-times[0]>=0.98
        task=asyncio.create_task(transport.get(second+'&cancel=1'))
        await asyncio.sleep(0)
        task.cancel()
        await asyncio.gather(task,return_exceptions=True)
    assert len(times)==2
