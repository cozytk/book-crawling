"""Private, append-only search records on Vercel Blob.

Each search owns its files, so concurrent writes never replace a shared index.
The history screen operates on the most recent 500 records.
"""
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from itertools import islice
from uuid import uuid4

from vercel.blob import sync as blob


class BlobStore:
    HISTORY_LIMIT = 500

    @staticmethod
    def _cache_path(query):
        key = hashlib.sha256(query.casefold().encode()).hexdigest()
        return f"v3/cache/{key}.json"

    def platform_cached(self, query, platform):
        key = hashlib.sha256(query.casefold().encode()).hexdigest()
        return self._read(f"v3/platforms/{platform}/{key}.json")

    def cache_platform(self, query, platform, value):
        key = hashlib.sha256(query.casefold().encode()).hexdigest()
        self._write(f"v3/platforms/{platform}/{key}.json", value, overwrite=True)

    def _read(self, path):
        try:
            return json.loads(blob.get_blob(path, access="private").body)
        except blob.BlobNotFoundError:
            return None

    @staticmethod
    def _write(path, payload, overwrite=False):
        blob.put_blob(path, json.dumps(payload, ensure_ascii=False).encode(),
                      access="private", content_type="application/json",
                      allow_overwrite=overwrite, cache_control_max_age=60)

    def save(self, query, results, platforms=None):
        from api.db import summarize
        now = datetime.now(timezone.utc)
        search = {"schema_version": 3, "id": str(uuid4()), "query": query, "created_at": now.isoformat(),
                  "requested_platforms": platforms or [], **summarize(results)}
        payload = {"search": search, "ratings": results}
        # Alphabetical listing puts the newest immutable records first.
        reverse_time = 9999999999999999 - int(now.timestamp() * 1000000)
        self._write(f'records/{search["id"]}.json', payload)
        # The canonical record commits first. Independent indexes then write in
        # parallel, so a cache hit can always retrieve the referenced record.
        with ThreadPoolExecutor(max_workers=2) as pool:
            history = pool.submit(self._write, f'v3/history/{reverse_time:016d}-{search["id"]}.json', payload)
            cache = pool.submit(self._write, self._cache_path(query), payload, True)
            history.result()
            try:
                cache.result()
            except blob.BlobError:
                pass
        return search

    def get(self, search_id):
        return self._read(f"records/{search_id}.json")

    def cached(self, query, cutoff):
        saved = self._read(self._cache_path(query))
        if saved and saved["search"]["created_at"] >= cutoff:
            return saved
        return None

    def history(self, sort_by, order, limit, offset, platform, sort_platform, with_count):
        items = list(islice(blob.query_blobs(prefix="v3/history/", page_size=500), self.HISTORY_LIMIT))
        with ThreadPoolExecutor(max_workers=12) as pool:
            records = [r for r in pool.map(self._read, [i.pathname for i in items]) if r]
        target = platform or (sort_platform if sort_by == "platform_rating" else None)
        if target:
            records = [r for r in records if any(p["platform"] == target for p in r["ratings"])]

        def key(record):
            if sort_by == "platform_rating" and target:
                return next((p.get("normalized_rating") for p in record["ratings"] if p["platform"] == target), None)
            return record["search"].get(sort_by, record["search"]["created_at"])

        rated = [r for r in records if key(r) is not None]
        unrated = [r for r in records if key(r) is None]
        records = sorted(rated, key=key, reverse=order.lower() == "desc") + unrated
        page = records[offset:offset + limit]
        return {"total": len(records) if with_count else len(page), "searches": [
            {**r["search"], "ratings": [p for p in r["ratings"] if not platform or p["platform"] == platform]}
            for r in page
        ]}
