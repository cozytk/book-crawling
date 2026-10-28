import pytest

from crawlers.amazon import AmazonCrawler


def widget(asin='0060883286', score='4.6', count='4,580 global ratings'):
    # Shape observed in the public native search-card rating popover.
    return f'''<h2 data-hook="acr-average-stars-rating-text">
      <span>{score} out of 5</span><span>Average rating: {score} out of 5 stars</span></h2>
      <span data-hook="total-review-count">{count}</span>
      <a href="/portal/customer-reviews/{asin}/ref=acr_search_hist_5">5 star 80%</a>
      <a href="/dp/{asin}#customerReviews">See customer reviews</a>'''


def test_popover_reads_exact_aggregate_not_histogram_or_price():
    assert AmazonCrawler._parse_verified_popover(widget()+'<p>$99.99 9,729 reviews</p>', '0060883286') == (4.6, 4580)


@pytest.mark.parametrize('html', [widget(asin='B000000001'), widget(score='8'), widget(count='80%'),
    widget(count='4580 customer reviews'), widget().replace('href=', 'data-unlinked='),
    widget()+'<a href="/dp/B000000001">Other product</a>',
    widget().replace('/dp/0060883286', 'https://evil.example/dp/0060883286')])
def test_unbound_or_invalid_popover_is_rejected(html):
    assert AmazonCrawler._parse_verified_popover(html, '0060883286') is None


def test_only_preverified_product_can_use_titleless_widget(monkeypatch):
    crawler=AmazonCrawler()
    crawler.expected_identity('One Hundred Years of Solitude','Gabriel Garcia Marquez')
    product={'url':'https://www.amazon.com/dp/0060883286','title':'One Hundred Years of Solitude',
             'source_author':'Gabriel Garcia Marquez'}
    crawler._verified_product=product
    calls=[]
    def fetch(url, extra_headers=None):
        calls.append(url)
        return widget()
    monkeypatch.setattr(crawler,'_fetch_with_headers',fetch)
    assert crawler.search_by_identifier('0060883286') == (product['url'],product['title'])
    assert crawler.rating_count==4580 and crawler.text_review_count is None
    assert crawler._rating_loaded and len(calls)==1 and '/review/widgets/' in calls[0]
    crawler._verified_product=None
    calls.clear()
    assert crawler.search_by_identifier('0060883286')==(None,'')
    assert all('/review/widgets/' not in url for url in calls)
