"""Versioned, source-specific TTLs; transient failures never get a 24h TTL."""
import asyncio
import time
from collections import OrderedDict
from threading import Lock

SCHEMA_VERSION = 24
TTL = {"done": 86400, "not_found": 600, "identity_mismatch": 600,
       "blocked": 60, "timeout": 15, "parse_error": 30, "network_error": 15, "unavailable": 30}
_entries = OrderedDict()
_lock = Lock()


async def read(store, query, platform):
    key = (getattr(store, "path", type(store).__name__), query.casefold(), platform)
    with _lock:
        value = _entries.get(key)
    if value and value["expires_at"] > time.time():
        return value
    if store and hasattr(store, "platform_cached"):
        try:
            value = await asyncio.wait_for(asyncio.to_thread(store.platform_cached, query, platform), 1.5)
            if value and value.get("schema_version") == SCHEMA_VERSION and value["expires_at"] > time.time():
                return value
        except Exception:
            pass
    return None


async def write(store, query, platform, status, rating, reason):
    value = {"schema_version": SCHEMA_VERSION, "status": status, "rating": rating,
             "reason": reason, "expires_at": time.time() + TTL.get(status, 30)}
    key = (getattr(store, "path", type(store).__name__), query.casefold(), platform)
    with _lock:
        _entries[key] = value
        _entries.move_to_end(key)
        while len(_entries) > 512:
            _entries.popitem(last=False)
    if store and hasattr(store, "cache_platform"):
        try:
            await asyncio.wait_for(asyncio.to_thread(store.cache_platform, query, platform, value), 3)
        except Exception:
            pass


def clear_memory():
    with _lock:
        _entries.clear()
