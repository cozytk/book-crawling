from unittest.mock import patch
import pytest

from api.services.volume_service import aggregate_volumes, collect_volumes
from api.services.crawler_service import rating_dict, rating_from_dict
from crawlers.work_identity import WorkIdentity, resolve_work_identity
from crawlers.kyobo import KyoboCrawler
from models.book import PlatformRating
from crawlers.utils import volume_info


def book(volume,score,count=10,url=None):
    return {'volume':str(volume),'book_title':f'레 미제라블 {volume}','rating':score,'rating_scale':10,
            'url':url or f'https://example.com/{volume}','review_count':count,'rating_count':count,'text_review_count':None,'status':'done'}


def test_volume_mean_is_equal_weight_not_review_weight_and_roundtrips_cache():
    identity=WorkIdentity('빅토르 위고','레 미제라블',publisher='민음사',translator='정기수',volume_total=5)
    rows=[book(n,score,1000 if n==1 else 1) for n,score in enumerate([9.7,9.9,10,9.6,10],1)]
    result=aggregate_volumes('kyobo',identity,rows)
    assert result.rating==pytest.approx(9.84) and result.aggregate_complete
    assert result.rating_count==1004 and result.text_review_count is None
    assert result.isbn is None and len(result.volume_results)==5
    restored=rating_from_dict(rating_dict(result))
    assert restored.rating==pytest.approx(9.84) and len(restored.volume_results)==5


def test_missing_and_duplicate_volumes_never_become_zero_or_get_counted_twice():
    identity=WorkIdentity('A','A Book',volume_total=3)
    result=aggregate_volumes('yes24',identity,[book(1,8),book(3,10)])
    assert result.rating==9 and not result.aggregate_complete
    assert result.rating_count is None and len(result.volume_results)==3
    assert next(e for e in result.volume_results if e['volume']=='2')['rating'] is None
    duplicate=aggregate_volumes('yes24',identity,[book(1,8,url='https://example.com/same'),book(2,8,url='https://example.com/same')])
    assert duplicate.rating==8 and not duplicate.aggregate_complete


def test_volume_labels_do_not_treat_numeric_work_titles_as_series():
    assert volume_info('레 미제라블 5')[1]=='5'
    assert volume_info('전쟁과 평화(상)')[1]=='상'
    assert volume_info('1984')[1] is None


def item(volume,publisher,translator,count,isbn):
    return f'''<div class="prod_item" data-isbn="{isbn}"><a class="prod_info" href="/detail/{isbn}">레 미제라블 {volume}</a>
      <div class="prod_author_group"><a class="author rep">빅토르 위고</a><span class="type">저자(글)</span><a class="author">{translator}</a><span class="type">번역</span></div>
      <div class="prod_publish"><a class="text">{publisher}</a></div><span class="review_klover_text">9.8</span><span class="review_desc">({count})</span></div>'''


async def test_identity_groups_publisher_and_translator_then_orders_all_volumes():
    html=''.join(item(n,'민음사','정기수',50,'97889374630'+str(n)+'3') for n in [3,1,5,2,4])
    html+=item(1,'다른 출판사','다른 번역자',200,'9780000000001')
    html+=item(1,'민음사','다른 번역자',60,'9780000000002')
    with patch.object(KyoboCrawler,'_fetch_html',return_value=html):
        identity=await resolve_work_identity('레 미제라블')
    assert identity.publisher=='민음사' and identity.translator=='정기수'
    assert [e['volume'] for e in identity.editions]==['1','2','3','4','5']
    with patch.object(KyoboCrawler,'_fetch_html',return_value=html):
        exact=await resolve_work_identity('레 미제라블 1')
    assert not exact.editions
    assert not (await resolve_work_identity('9788937463013')).editions


async def test_all_failed_volumes_keep_blocked_status_instead_of_negative_cache():
    identity=WorkIdentity('A','Book',editions=({'volume':'1','title':'Book 1','isbn':'1','url':'u'}, {'volume':'2','title':'Book 2','isbn':'2','url':'v'}))
    async def crawl(edition,on_failure):
        on_failure('blocked')
        return None
    failures=[]
    result=await collect_volumes('yes24',identity,crawl,rating_dict,1,failures.append)
    assert result is None and failures==['blocked']
