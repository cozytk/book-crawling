import asyncio
import json
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest

from crawlers.amazon import AmazonCrawler
from crawlers.isbn_lookup import OpenLibraryProvider
from crawlers.transport import SearchTransport, run_parser, FetchFailure


@pytest.mark.parametrize('title,author,expected',[
    ('The Remains of the Day','Kazuo Ishiguro, カズオ イシグロ, 石黑 一雄','Kazuo Ishiguro'),
    ('Sapiens','Yuval Noah Harari, ユヴァル.ノア.ハラリ','Yuval Noah Harari'),
    ("L'insoutenable légèreté de l'être",'Milan Kundera, ミラン.クンデラ','Milan Kundera'),
])
def test_catalog_queries_use_one_author_alias_without_relaxing_validation(title,author,expected):
    p=OpenLibraryProvider()
    data={'docs':[{'title':title,'author_name':['Another Writer'],'isbn':['9780679731726'],'edition_count':1000},
                  {'title':title,'author_name':[expected],'isbn':['9780571154913'],'edition_count':10}]}
    with patch.object(p,'_api_get',return_value=data) as fetch:
        result=p.search(title,author)
    query=parse_qs(urlsplit(fetch.call_args_list[0].args[0]).query)['q'][0]
    assert expected in query and 'イシグロ' not in query and 'クンデラ' not in query and 'ハラリ' not in query
    assert "L'insoutenable" not in query
    assert result.isbn=='9780571154913'


def card(asin='0679731725',author='Kazuo Ishiguro',label='29,411 ratings',stars='4.4 out of 5 stars',fmt='Paperback'):
    return f'''<div data-component-type="s-search-result" data-asin="{asin}">
      <div data-cy="title-recipe"><a href="/dp/{asin}"><h2><span>The Remains of the Day: Winner of the Nobel Prize in Literature</span></h2></a>
      <div class="a-row a-size-base a-color-secondary">by {author} | Sep 12, 1990</div></div>
      <div data-cy="reviews-block"><span class="a-icon-alt">{stars}</span><a href="/dp/{asin}#customerReviews" aria-label="{label}"><span>(29.4K)</span></a></div>
      <div data-cy="price-recipe"><a class="a-text-bold" href="/dp/{asin}">{fmt}</a></div>
      Other formats: Audiobook</div>'''


@pytest.mark.parametrize('label,stars', [('29,411 ratings','4.4 out of 5 stars'),('29,411개 평가','별 5개 중 4.4')])
async def test_verified_modern_amazon_card_avoids_detail_request_and_rounded_count(label,stars):
    c=AmazonCrawler()
    c.expected_identity('The Remains of the Day','Kazuo Ishiguro',strict_isbn=False)
    html=card(author='Other Writer')+card(label=label,stars=stars)
    with patch.object(c,'_fetch_with_headers',return_value=html) as fetch:
        result=await c.crawl('The Remains of the Day')
    assert fetch.call_count==1
    assert result.rating==4.4 and result.rating_count==29411 and result.text_review_count is None
    assert result.isbn=='9780679731726'


async def test_amazon_prefers_a_rated_verified_edition_over_an_unrated_first_result():
    c=AmazonCrawler()
    c.expected_identity('The Remains of the Day','Kazuo Ishiguro',strict_isbn=False)
    html=card(asin='0571154913',stars='',label='')+card()
    with patch.object(c,'_fetch_with_headers',return_value=html) as fetch:
        result=await c.crawl('The Remains of the Day')
    assert result.url.endswith('/0679731725') and result.rating==4.4 and fetch.call_count==1


def test_amazon_never_treats_compact_count_as_exact_or_accepts_another_asin_popover():
    c=AmazonCrawler()
    with patch.object(c,'_fetch_with_headers',return_value=card(label='')):
        c.search_by_keyword('The Remains of the Day')
    assert c.rating_count is None and c._cached_review_count is None
    html=card().replace('<span class="a-icon-alt">','<span data-a-popover=\'{"url":"/popover?asin=OTHERASIN1"}\'></span><span class="a-icon-alt">')
    with patch.object(c,'_fetch_with_headers',return_value=html):
        c.search_by_keyword('The Remains of the Day')
    assert c._cached_rating is None


def test_amazon_native_isbn_field_excludes_recommendation_identifiers():
    c=AmazonCrawler()
    c.expected_identity('The Remains of the Day','Kazuo Ishiguro')
    html='<span id="productTitle">The Remains of the Day</span><div id="bylineInfo">Kazuo Ishiguro</div><div id="detailBullets_feature_div"><li>ISBN-13 : 9780679731726</li></div><div>Recommendation ISBN-13 9780451530172</div>'
    assert c._verify_product(html,'The Remains of the Day','9780679731726')
    assert c.book_isbn=='9780679731726'
    assert not c._verify_product(html,'The Remains of the Day','9780451530172')


async def test_success_status_amazon_checkpoint_is_reported_as_blocked():
    async def handler(request):
        return httpx.Response(200,text='<title>Robot Check</title>')
    async with SearchTransport(httpx.AsyncClient(transport=httpx.MockTransport(handler))) as transport:
        with pytest.raises(FetchFailure) as exc:
            await transport.get('https://www.amazon.com/dp/0679731725')
    assert exc.value.status=='blocked'
