import json

import pytest

from crawlers.goodreads import GoodreadsCrawler
from crawlers.utils import candidate_score


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


def test_modern_hyphenated_book_url_still_proves_the_same_book_id():
    result=crawler()
    assert result._autocomplete_aggregate(json.dumps([book(bookUrl='/book/show/1420-hamlet')]),'Hamlet')[0].endswith('/1420')
    result.expected_identity('Miserables','Victor Hugo',strict_isbn=False)
    actual=book(bookId='36377471',workId='3208463',bookUrl='/book/show/36377471-les-miserables',
                title='Les Miserables',bookTitleBare='Les Miserables',author={'name':'Victor Hugo'},
                avgRating='4.22',ratingsCount=868925)
    assert result._autocomplete_aggregate(json.dumps([actual]),'Miserables')[0].endswith('/36377471')
    assert result.rating_count==868925


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


def test_catalog_article_alias_requires_matching_author_and_preserves_gates():
    assert candidate_score('Miserables','Les Miserables','Victor Hugo','Victor Hugo')
    assert candidate_score('Stranger','The Stranger','Albert Camus','Albert Camus')
    assert not candidate_score('Miserables','Les Miserables','Other Author','Victor Hugo')
    assert not candidate_score('Miserables','Les Miserables','Victor Hugo')
    assert not candidate_score('Miserables','Les Miserables Study Guide','Victor Hugo','Victor Hugo')
    assert not candidate_score('Les Miserables 1','Miserables 2','Victor Hugo','Victor Hugo')


def test_missing_top_five_work_is_rediscovered_by_observed_full_title(monkeypatch):
    result=crawler()
    result.expected_identity('Miserables',['Victor Hugo'],strict_isbn=False)
    calls=[]
    actual=book(bookId='36377471',bookUrl='/book/show/36377471-les-miserables',title='Les Miserables',
                bookTitleBare='Les Miserables',author={'name':'Victor Hugo'},avgRating='4.22',ratingsCount=868927)
    def fetch(url):
        calls.append(url)
        if 'q=Les%20Miserables' in url:
            return json.dumps([actual]),url
        if '/auto_complete' in url:
            return json.dumps([book(author={'name':'Other Author'})]),url
        return '<div><a class="bookTitle" href="/book/show/36377471-les-miserables">Les Miserables</a></div>',url
    monkeypatch.setattr(result,'_fetch_with_redirect',fetch)
    assert result.search_by_keyword('Miserables')[0].endswith('/36377471')
    assert result.rating_count==868927 and len(calls)==3


def test_observed_title_alone_cannot_bypass_author_revalidation(monkeypatch):
    result=crawler()
    result.expected_identity('Miserables',['Victor Hugo'],strict_isbn=False)
    def fetch(url):
        if '/auto_complete' in url:
            return json.dumps([book(bookTitleBare='Les Miserables',author={'name':'Another Author'})]),url
        return '<a class="bookTitle" href="/book/show/1420">Les Miserables</a>',url
    monkeypatch.setattr(result,'_fetch_with_redirect',fetch)
    assert result.search_by_keyword('Miserables')==(None,'')
