"""Deterministic HTTP-count/timing benchmark for Yes24 + Sarak.

Usage: python scripts/benchmark_requests.py [source-root]
Fixed mock pages and 50ms mock network latency. No external site is contacted.
"""
import asyncio
import json
import random
import sys
import time
import io
import tarfile
import tempfile
import subprocess
from pathlib import Path
from unittest.mock import patch

root = Path(__file__).resolve().parents[1]
arguments = sys.argv[1:]
temporary = None
if "--baseline-ref" in arguments:
    baseline_ref = arguments[arguments.index("--baseline-ref") + 1]
    temporary = tempfile.TemporaryDirectory()
    source_root = Path(temporary.name)
    archive = subprocess.check_output(["git", "archive", baseline_ref], cwd=root)
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        tar.extractall(source_root, filter="data")
else:
    source_root = Path(arguments[0]).resolve() if arguments and not arguments[0].startswith("--") else root
workload = arguments[arguments.index("--workload") + 1] if "--workload" in arguments else "shared-search"
sys.path.insert(0,str(source_root))
sys.path.insert(1,str(root))
from api.services.crawler_service import crawl_all_stream

random.seed(17)
requests = 0

def body(url):
    if 'search.kyobobook' in url:
        return (root/'tests/fixtures/kyobo_search.html').read_text()
    if 'Product/Search' in url:
        return (root/'tests/fixtures/yes24_search.html').read_text()
    if 'book-statistics-summary' in url:
        return json.dumps({'starPointAverageForBookInfo':8.7,'userWhoDidVoteThisBookCount':100})
    if '/goods/' in url.lower():
        return (root/'tests/fixtures/yes24_detail.html').read_text()
    raise ValueError('unexpected mock URL')

class Response:
    status=200
    def __init__(self,url): self.url=url
    def read(self): return body(self.url).encode()
class Opener:
    def open(self,url,timeout=None):
        global requests
        requests+=1
        time.sleep(.05)
        return Response(url)

async def run():
    first=None
    started=time.perf_counter()
    results=[]
    platforms = ['kyobo'] if workload == 'cached-score' else ['yes24','sarak']
    async for result in crawl_all_stream('Clean Code',platforms):
        if first is None: first=time.perf_counter()-started
        results.append(result)
    return {'workload':workload,'http_requests':requests,'first_result_seconds':round(first,3),'complete_seconds':round(time.perf_counter()-started,3),'results':len(results),'mock_latency_ms':50}

if (source_root/'crawlers/transport.py').exists():
    import httpx
    RealClient=httpx.AsyncClient
    async def handler(request):
        global requests
        requests+=1
        await asyncio.sleep(.05)
        return httpx.Response(200,text=body(str(request.url)))
    def client(**kwargs):
        return RealClient(transport=httpx.MockTransport(handler),follow_redirects=False)
    with patch('crawlers.transport.httpx.AsyncClient',client):
        report=asyncio.run(run())
else:
    with patch('urllib.request.build_opener',return_value=Opener()):
        report=asyncio.run(run())
print(json.dumps(report))
