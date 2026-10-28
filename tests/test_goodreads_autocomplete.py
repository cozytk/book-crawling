import json

import pytest

from crawlers.goodreads import GoodreadsCrawler


def book(**changes):
    return {'bookId':'1420','workId':'1885548','bookUrl':'/book/show/1420.Hamlet',
            'title':'Hamlet','bookTitleBare':'Hamlet','author':{'name':'William Shakespeare'},
            'avgRating':'4.03','ratingsCount':1096351,**changes}


def crawler():
    result=GoodreadsCrawler()
    result.expected_identity('Hamlet','William Shakespeare',strict_isbn=False)
    return result


def test_exact_work_aggregate_skips_detail_and_keeps_written_count_unknown(monkeypatch):
    result=crawler()
    calls=[]
    def fetch(url):
        calls.append(url)
        return json.dumps([book()]),url
    monkeypatch.setattr(result,'_fetch_with_redirect',fetch)
    assert result.search_by_keyword('Hamlet')==('https://www.goodreads.com/book/show/1420','Hamlet')
    assert result.rating_count==1096351 and result.text_review_count is None
    assert result._rating_loaded and result._cached_rating==4.03
    assert len(calls)==1 and '/book/auto_complete?format=json' in calls[0]


@pytest.mark.parametrize('changes',[{'author':{'name':'Kenneth Branagh'}},{'bookTitleBare':'Hamlet Study Guide'},
    {'avgRating':'8'},{'ratingsCount':'1.1m'},{'ratingsCount':True},{'ratingsCount':-1},
    {'bookUrl':'https://evil.example/book/show/1420.Hamlet'},{'bookUrl':'/book/show/999.Hamlet'},
    {'workId':''}])
def test_mismatched_or_rounded_autocomplete_values_are_rejected(changes):
    assert crawler()._autocomplete_aggregate(json.dumps([book(**changes)]),'Hamlet') is None


def test_larger_valid_work_population_wins_over_partial_volume():
    result=crawler()
    small=book(bookId='99',bookUrl='/book/show/99',ratingsCount=20)
    partial=book(bookTitleBare='Hamlet - Band I',ratingsCount=9999999)
    assert result._autocomplete_aggregate(json.dumps([small,partial,book()]),'Hamlet')[0].endswith('/1420')


def test_explicit_isbn_fallback_does_not_use_work_only_autocomplete(monkeypatch):
    result=crawler()
    result._original_query='9780521618748'
    calls=[]
    def fetch(url):
        calls.append(url)
        return '<p>No books found</p>',url
    monkeypatch.setattr(result,'_fetch_with_redirect',fetch)
    assert result.search_by_keyword('Hamlet')==(None,'')
    assert all('/auto_complete' not in url for url in calls)
