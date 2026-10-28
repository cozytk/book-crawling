from unittest.mock import patch
from crawlers.goodreads import GoodreadsCrawler
from crawlers.amazon import AmazonCrawler
from crawlers.isbn_lookup import OpenLibraryProvider
from crawlers.aladin import AladinCrawler
from crawlers.utils import author_matches, title_score


def test_unicode_author_names_never_match_merely_because_latin_tokens_are_empty():
    assert not author_matches(['Фёдор Михайлович Достоевский'], 'Сергей Аркадьевич Андреевский')
    assert author_matches(['Фёдор Михайлович Достоевский'], 'Федор Михайлович Достоевский')
    assert author_matches('Gabriel García Márquez','Gabriel Garcia Marquez')
    assert not author_matches('Albert Camus','Albert Smith')


def test_titles_allow_diacritic_and_locative_spelling_without_relaxing_derivative_or_volume_gates():
    assert title_score('Cien anos de soledad','Cien años de soledad')
    assert title_score('Братья Карамазовы','Бра́тья Карама́зовы')
    assert title_score('수레바퀴 아래','수레바퀴 아래서')
    assert not title_score('수레바퀴 아래','수레바퀴 아래서 해설')
    assert not title_score('데미안','데미안에서')
    assert not title_score('해리 포터 상','해리 포터 하')


def test_goodreads_uses_verified_author_and_population_before_minor_title_differences():
    c=GoodreadsCrawler()
    c.expected_identity('Братья Карамазовы',['Фёдор Михайлович Достоевский','Fyodor Dostoevsky'],False)
    def card(identifier,title,author,count):
        return f'''<div class="Book"><span data-testid="book-item-title"><a href="/book/show/{identifier}">{title}</a></span>
        <a href="/author/show/1">{author}</a><span data-testid="book-item-ratings-count">{count} ratings</span></div>'''
    html=card('1','Братья Карамазовы','Сергей Аркадьевич Андреевский','39')
    html+=card('2','Братья Карамазовы (Paperback)','Fyodor Dostoevsky','420k')
    html+=card('3','Братья Карамазовы','Fyodor Dostoevsky','7')
    with patch.object(c,'_fetch_with_redirect',return_value=(html,'https://www.goodreads.com/search')):
        url,title=c.search_by_keyword('Братья Карамазовы')
    assert url.endswith('/2')
    assert c.rating_count is None  # 420k must not become an exact output count.


def test_amazon_population_outranks_exact_title_after_work_identity_gates():
    c=AmazonCrawler()
    c.expected_identity('One Hundred Years of Solitude','Gabriel García Márquez',False)
    def card(asin,title,author,count):
        return f'''<div data-component-type="s-search-result" data-asin="{asin}"><div data-cy="title-recipe"><h2><span>{title}</span></h2>
        <div class="a-row a-size-base a-color-secondary">by {author}</div></div><div data-cy="reviews-block"><span class="a-icon-alt">4.5 out of 5 stars</span><a aria-label="{count} ratings">({count})</a></div></div>'''
    html=card('B0BFK4THKQ','One Hundred Years of Solitude','Gabriel García Márquez','3,151')
    html+=card('0060883286','One Hundred Years of Solitude: A Novel (Harper Perennial Modern Classics)','Gabriel Garcia Marquez','22,018')
    with patch.object(c,'_fetch_with_headers',return_value=html):
        url,_=c.search_by_keyword('One Hundred Years of Solitude')
    assert url.endswith('/0060883286') and c.rating_count==22018


def test_catalog_english_title_must_belong_to_the_same_verified_work():
    provider=OpenLibraryProvider()
    initial={'docs':[{'key':'/works/OL274505W','title':'Cien años de soledad','author_name':['Gabriel García Márquez'],
                     'isbn':['9780307474728'],'edition_count':208}]}
    matching={'docs':[{'key':'/works/OL274505W','editions':{'docs':[{'title':'One Hundred Years of Solitude','language':['eng'],'isbn':['9780140278767']}]}}]}
    with patch.object(provider,'_api_get',side_effect=[initial,matching]) as fetch:
        result=provider.search('Cien anos de soledad','Gabriel Garcia Marquez')
    assert result.english_title=='One Hundred Years of Solitude' and result.english_isbn=='9780140278767'
    assert 'key%3A%22%2Fworks%2FOL274505W%22' in fetch.call_args[0][0]
    matching['docs'][0]['key']='/works/OL999W'
    with patch.object(provider,'_api_get',side_effect=[initial,matching]):
        result=provider.search('Cien anos de soledad','Gabriel Garcia Marquez')
    assert result.english_title is None


async def test_aladin_title_search_prefers_reviewed_edition_and_reuses_verified_aggregate():
    c=AladinCrawler()
    c.ttb_key='fixture'
    c._prefer_popular_edition=True
    c.expected_identity('이방인','알베르 카뮈',False)
    def row(item,author,count):
        return f'''<div class="ss_book_list"><ul><li>[국내도서] <a class="bo3" href="https://www.aladin.co.kr/shop/wproduct.aspx?ItemId={item}">이방인</a></li>
        <li>{author} (지은이), 김화영 (옮긴이) | 민음사</li><li>9.0 ({count}) | 세일즈포인트 : 10000</li></ul></div>'''
    html=row('1','다른 저자',999)+row('11267296','알베르 카뮈',222)+row('212246612','알베르 카뮈',88)
    item={'itemId':11267296,'title':'이방인','author':'알베르 카뮈 (지은이), 김화영 (옮긴이)',
          'isbn13':'9788937462665','link':'https://www.aladin.co.kr/shop/wproduct.aspx?ItemId=11267296',
          'subInfo':{'ratingInfo':{'ratingScore':9.0,'ratingCount':222,'commentReviewCount':208}}}
    with patch.object(c,'_fetch_html',return_value=html),patch.object(c,'_api_request',return_value={'item':[item]}) as fetch:
        url,title=c.search_book_sync('이방인')
        score,count=await c.get_rating(url)
    assert '11267296' in url and score==9.0 and count==222 and fetch.call_count==1
