import json

from crawlers.sarak import SarakCrawler
from crawlers.yes24 import Yes24Crawler


async def test_sarak_compares_own_votes_instead_of_yes24_written_review_rank(monkeypatch):
    def identify(self,keyword):
        self._candidate_products=[{'url':'https://www.yes24.com/product/goods/7381053','title':'페스트','support':412},
            {'url':'https://www.yes24.com/product/goods/4827619','title':'페스트','support':162}]
        self.book_author='알베르 까뮈'
        return self._candidate_products[0]['url'],'페스트'
    monkeypatch.setattr(Yes24Crawler,'search_by_keyword',identify)
    crawler=SarakCrawler()
    crawler.expected_identity('페스트','알베르 카뮈',False)
    calls=[]
    def fetch(url):
        calls.append(url)
        if 'book-statistics-summary' in url:
            identifier=url.split('/')[-2]
            count=251 if identifier=='4827619' else 14
            return json.dumps({'goodsNo':int(identifier),'starPointAverageForBookInfo':9.1,
                               'userWhoDidVoteThisBookCount':count,'reviewCount':160 if count==251 else 12})
        return '<script type="application/ld+json">'+json.dumps({'@type':'Book','sku':'4827619','name':'페스트',
            'isbn':'9788937462672','author':{'name':'알베르 까뮈'}})+'</script>'
    monkeypatch.setattr(crawler,'_fetch_html',fetch)
    assert crawler.search_by_keyword('페스트')==('https://sarak.yes24.com/reading-note/book/4827619','페스트')
    assert await crawler.get_rating('https://sarak.yes24.com/reading-note/book/4827619')==(9.1,251)
    assert crawler.text_review_count==160 and len(calls)==3


def test_explicit_isbn_does_not_compare_other_sarak_editions(monkeypatch):
    def identify(self,keyword):
        self._candidate_products=[{'url':'https://www.yes24.com/product/goods/999','title':'페스트','support':9999}]
        return 'https://www.yes24.com/product/goods/4827619','페스트'
    monkeypatch.setattr(Yes24Crawler,'search_by_keyword',identify)
    crawler=SarakCrawler()
    crawler._original_query='9788937462672'
    monkeypatch.setattr(crawler,'_fetch_html',lambda url:(_ for _ in ()).throw(AssertionError('No other edition request')))
    assert crawler.search_by_keyword('9788937462672')[0].endswith('/4827619')
