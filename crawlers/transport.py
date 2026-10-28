"""Cancelable async HTTP behind the existing synchronous HTML parsers.

Parsers run on bounded workers. Their network calls use one async connection
pool on the ASGI loop; canceling a parser scope cancels its HTTP waiters too.
"""
import asyncio
import contextvars
import concurrent.futures
from collections import Counter
from dataclasses import dataclass
from urllib.parse import urlsplit, urljoin
from threading import Lock

import httpx
from weakref import WeakKeyDictionary

_current = contextvars.ContextVar("search_transport", default=None)
_scope = contextvars.ContextVar("search_http_scope", default=None)
WORKERS = concurrent.futures.ThreadPoolExecutor(max_workers=16, thread_name_prefix="parser")
_domain_limits = WeakKeyDictionary()


class SearchAborted(BaseException):
    pass


class FetchFailure(Exception):
    def __init__(self, status):
        super().__init__(status)
        self.status = status


@dataclass
class PageResponse:
    text: str
    url: str


class Scope:
    def __init__(self):
        self.pending = set()
        self.closed = False
        self.failure_status = None

    def close(self):
        self.closed = True
        for future in list(self.pending):
            future.cancel()


class SearchTransport:
    def __init__(self, client=None, browser_client=None):
        self.loop = asyncio.get_running_loop()
        self.use_browser_http = client is None or browser_client is not None
        self.browser_client = browser_client
        self.client = client or httpx.AsyncClient(follow_redirects=False, timeout=httpx.Timeout(8, connect=4),
                                                 limits=httpx.Limits(max_connections=20, max_keepalive_connections=12))
        self.requests = {}
        self.waiters = Counter()
        self.domains = _domain_limits.setdefault(self.loop, {})
        self.counts = Counter()
        self.diagnostics = {}
        self.memo_values = {}
        self.memo_lock = Lock()

    async def __aenter__(self):
        self.token = _current.set(self)
        return self

    async def __aexit__(self, *exc):
        _current.reset(self.token)
        for task in self.requests.values():
            if not task.done():
                task.cancel()
        await asyncio.gather(*self.requests.values(), return_exceptions=True)
        await self.client.aclose()
        if self.browser_client is not None:
            await self.browser_client.close()

    async def _request(self, url, headers):
        for _ in range(6):
            domain = urlsplit(url).hostname
            semaphore = self.domains.setdefault(domain, asyncio.Semaphore(3))
            try:
                async with semaphore:
                    self.counts[domain] += 1
                    if self.use_browser_http and domain in {"pedia.watcha.com", "www.goodreads.com"}:
                        from curl_cffi.requests import AsyncSession
                        from curl_cffi.requests.exceptions import Timeout, RequestException
                        if self.browser_client is None:
                            self.browser_client = AsyncSession(impersonate="chrome", timeout=8)
                        try:
                            page = await self.browser_client.get(url, headers=headers, allow_redirects=False)
                        except Timeout:
                            raise FetchFailure("timeout") from None
                        except RequestException:
                            raise FetchFailure("network_error") from None
                        response_headers = {k: v for k, v in page.headers.items()
                                            if k.lower() not in {"content-encoding", "content-length"}}
                        response = httpx.Response(page.status_code, content=page.content, headers=response_headers,
                                                  request=httpx.Request("GET", str(page.url)))
                    else:
                        response = await self.client.get(url, headers=headers, follow_redirects=False)
            except httpx.TimeoutException:
                raise FetchFailure("timeout") from None
            except httpx.HTTPError:
                raise FetchFailure("network_error") from None
            if response.is_redirect:
                location = urljoin(url, response.headers.get("location", ""))
                if urlsplit(location).scheme not in {"http", "https"}:
                    raise FetchFailure("network_error")
                if urlsplit(location).hostname != domain:
                    headers = {k: v for k, v in (headers or {}).items() if k.lower() in {"user-agent", "accept", "accept-language"}}
                url = location
                continue
            if response.status_code in {401, 403, 429, 503} or response.headers.get("x-amzn-waf-action") in {"challenge", "captcha"}:
                raise FetchFailure("blocked")
            if response.status_code == 404:
                raise FetchFailure("not_found")
            if not response.is_success:
                raise FetchFailure("network_error")
            try:
                text = response.content.decode("utf-8")
            except UnicodeDecodeError:
                text = response.content.decode("cp949", errors="replace")
            if any(marker in text[:10000].lower() for marker in ("/cdn-cgi/challenge-platform", "performing security verification", "validatecaptcha", "awswafcookiedomainlist", "awswafintegration")):
                raise FetchFailure("blocked")
            return PageResponse(text, str(response.url))
        raise FetchFailure("network_error")

    async def get(self, url, headers=None):
        key = (url, tuple(sorted((headers or {}).items())))
        task = self.requests.get(key)
        if task is None or task.cancelled():
            task = self.requests[key] = asyncio.create_task(self._request(url, headers))
        self.waiters[key] += 1
        try:
            return await asyncio.shield(task)
        finally:
            self.waiters[key] -= 1
            if self.waiters[key] == 0 and not task.done():
                task.cancel()

    def memo(self, key, factory):
        with self.memo_lock:
            future = self.memo_values.get(key)
            own = future is None
            if own:
                future = self.memo_values[key] = concurrent.futures.Future()
        if own:
            try:
                future.set_result(factory())
            except BaseException as exc:
                future.set_exception(exc)
        return future.result()


def active_transport():
    return _current.get()


def fetch_sync(url, headers=None):
    transport = _current.get()
    if transport is None:
        return None  # Standalone legacy/fixture callers retain their injected IO.
    scope = _scope.get()
    if scope and scope.closed:
        raise SearchAborted()
    future = asyncio.run_coroutine_threadsafe(transport.get(url, headers), transport.loop)
    if scope:
        scope.pending.add(future)
        if scope.closed:
            future.cancel()
    try:
        return future.result(timeout=12)
    except concurrent.futures.CancelledError:
        raise SearchAborted() from None
    except concurrent.futures.TimeoutError:
        future.cancel()
        if scope:
            scope.failure_status = "timeout"
        raise FetchFailure("timeout") from None
    except FetchFailure as exc:
        if scope:
            scope.failure_status = exc.status
        raise
    finally:
        if scope:
            scope.pending.discard(future)


async def run_parser(function):
    scope = Scope()
    token = _scope.set(scope)
    context = contextvars.copy_context()
    _scope.reset(token)
    try:
        value = await asyncio.get_running_loop().run_in_executor(WORKERS, context.run, function)
        return value, scope.failure_status
    finally:
        scope.close()
