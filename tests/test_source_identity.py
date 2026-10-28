import time
from unittest.mock import AsyncMock
from types import SimpleNamespace

import pytest

from api import source_identity,platform_cache
from api.local_store import LocalStore
from api.services import crawler_service
from crawlers.foreign_resolver import ForeignQuery
from crawlers.work_identity import WorkIdentity
from models.book import PlatformRating


def product(**overrides):
    value={'version':1,'platform':'amazon','query':'햄릿','title':'Hamlet','url':'https://www.amazon.com/dp/1451669410',
           'source_author':'William Shakespeare','local_author':'윌리엄 셰익스피어','provenance':'aside_book_search',
           'observed_at':'2026-10-29T00:00:00+09:00','expires_at':time.time()+100}
    return {**value,**overrides}


@pytest.mark.parametrize('override',[{'url':'https://example.com/dp/1451669410'},
    {'url':'https://www.amazon.com/dp/1451669410?redirect=evil'},
    {'url':'https://www.amazon.com/s?k=Hamlet'},{'expires_at':0},{'query':'다른 책'},
    {'source_author':''},{'version':0},{'provenance':'unverified_search_snippet'}])
def test_invalid_product_discovery_is_rejected(override):
    assert source_identity.validate(product(**override),'햄릿') is None


async def test_product_identity_is_separate_from_rating_and_schema_caches(tmp_path):
    store=LocalStore(str(tmp_path/'cache.sqlite3'))
    await source_identity.write(store,product())
    loaded=await source_identity.read(store,'  햄릿  ')
    assert loaded['url'].endswith('/1451669410')
    assert not any('rating' in key or 'review' in key for key in loaded)
    assert store.platform_cached('햄릿','amazon') is None


async def test_verified_product_fetches_fresh_detail_and_skips_blocked_discovery(tmp_path,monkeypatch):
    store=LocalStore(str(tmp_path/'cache.sqlite3'))
    store.cache_source_identity('햄릿','amazon',product())
    monkeypatch.setattr(crawler_service,'resolve_work_identity',AsyncMock(return_value=WorkIdentity('셰익스피어','햄릿','9788937460036')))
    foreign=AsyncMock(side_effect=AssertionError('No catalog/search is needed for a verified product'))
    monkeypatch.setattr(crawler_service,'resolve_foreign_query',foreign)
    detail=AsyncMock(return_value=PlatformRating('amazon',4.5,5,11502,'https://www.amazon.com/dp/1451669410','Hamlet',rating_count=11502))
    monkeypatch.setattr(crawler_service,'crawl_platform',detail)
    result=await crawler_service.crawl_all('햄릿',['amazon'],True,store)
    assert result.results[0].rating_count==11502
    assert detail.call_args.args[1]=='1451669410'
    assert detail.call_args.kwargs['identity_title']=='Hamlet'
    assert detail.call_args.kwargs['expected_author']=='William Shakespeare'
    foreign.assert_not_awaited()


async def test_wrong_local_author_cannot_reuse_a_cached_namesake(tmp_path,monkeypatch):
    store=LocalStore(str(tmp_path/'cache.sqlite3'))
    store.cache_source_identity('햄릿','amazon',product(local_author='다른 작가'))
    monkeypatch.setattr(crawler_service,'resolve_work_identity',AsyncMock(return_value=WorkIdentity('셰익스피어','햄릿','9788937460036')))
    monkeypatch.setattr(crawler_service,'resolve_foreign_query',AsyncMock(return_value=ForeignQuery(query='Hamlet',author='William Shakespeare')))
    detail=AsyncMock(return_value=None)
    monkeypatch.setattr(crawler_service,'crawl_platform',detail)
    await crawler_service.crawl_all('햄릿',['amazon'],True,store)
    assert detail.call_args.args[1]=='Hamlet'


async def test_explicit_isbn_never_substitutes_an_audited_work_product(monkeypatch):
    read=AsyncMock(return_value=product())
    monkeypatch.setattr(source_identity,'read',read)
    monkeypatch.setattr(crawler_service,'resolve_foreign_query',AsyncMock(return_value=ForeignQuery(query='9788937460036',isbn='9788937460036')))
    detail=AsyncMock(return_value=None)
    monkeypatch.setattr(crawler_service,'crawl_platform',detail)
    await crawler_service.crawl_all('9788937460036',['amazon'],True)
    read.assert_not_awaited()
    assert detail.call_args.args[1]=='9788937460036'


async def test_verified_alternate_is_tried_before_repeating_blocked_search(tmp_path,monkeypatch):
    store=LocalStore(str(tmp_path/'cache.sqlite3'))
    store.cache_source_identity('햄릿','amazon',product(alternates=[{'url':'https://www.amazon.com/dp/0141396504','title':'Hamlet','source_author':'William Shakespeare'}]))
    monkeypatch.setattr(crawler_service,'resolve_work_identity',AsyncMock(return_value=WorkIdentity('셰익스피어','햄릿')))
    foreign=AsyncMock(side_effect=AssertionError('The audited alternate succeeds'))
    monkeypatch.setattr(crawler_service,'resolve_foreign_query',foreign)
    detail=AsyncMock(side_effect=[None,PlatformRating('amazon',4.5,5,11502,'https://www.amazon.com/dp/0141396504','Hamlet')])
    monkeypatch.setattr(crawler_service,'crawl_platform',detail)
    result=await crawler_service.crawl_all('햄릿',['amazon'],True,store)
    assert result.results[0].rating==4.5
    assert [call.args[1] for call in detail.call_args_list]==['1451669410','0141396504']
    foreign.assert_not_awaited()


async def test_successful_server_discovery_learns_only_product_metadata(tmp_path,monkeypatch):
    store=LocalStore(str(tmp_path/'cache.sqlite3'))
    monkeypatch.setattr(crawler_service,'resolve_work_identity',AsyncMock(return_value=WorkIdentity('셰익스피어','햄릿')))
    monkeypatch.setattr(crawler_service,'resolve_foreign_query',AsyncMock(return_value=ForeignQuery(query='Hamlet',author='William Shakespeare')))
    monkeypatch.setattr(crawler_service,'active_transport',lambda:SimpleNamespace(diagnostics={'amazon':{'method':'verified_search_card'}}))
    monkeypatch.setattr(crawler_service,'crawl_platform',AsyncMock(return_value=PlatformRating('amazon',4.5,5,11502,'https://www.amazon.com/dp/1451669410','Hamlet',author='William Shakespeare')))
    await crawler_service.crawl_all('햄릿',['amazon'],True,store)
    discovered=await source_identity.read(store,'햄릿')
    assert discovered['url'].endswith('/1451669410') and discovered['provenance']=='server_verified_search_card'
    assert not any('rating' in key or 'review' in key for key in discovered)
