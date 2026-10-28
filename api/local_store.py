"""Durable local storage when Supabase has not been configured."""

import json
import sqlite3
from pathlib import Path
from uuid import uuid4
from datetime import datetime, timezone


class LocalStore:
    def __init__(self, path: str):
        self.path = path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS searches (id TEXT PRIMARY KEY, query TEXT, created_at TEXT, payload TEXT)")
            db.execute("CREATE TABLE IF NOT EXISTS source_cache (key TEXT PRIMARY KEY, payload TEXT)")

    def platform_cached(self, query, platform):
        with self.connect() as db:
            row = db.execute("SELECT payload FROM source_cache WHERE key = ?", (f"{query.casefold()}:{platform}",)).fetchone()
        return json.loads(row[0]) if row else None

    def source_identity_cached(self,query,platform):
        from api.source_identity import normalize
        return self.platform_cached(normalize(query),f'identity-v1-{platform}')

    def cache_source_identity(self,query,platform,value):
        from api.source_identity import normalize
        self.cache_platform(normalize(query),f'identity-v1-{platform}',value)

    def cache_platform(self, query, platform, value):
        with self.connect() as db:
            db.execute("INSERT OR REPLACE INTO source_cache VALUES (?, ?)", (f"{query.casefold()}:{platform}", json.dumps(value)))

    def connect(self):
        return sqlite3.connect(self.path, timeout=10)

    def save(self, query, results, platforms=None):
        from api.db import summarize
        from api.platform_cache import SCHEMA_VERSION
        search = {"schema_version": SCHEMA_VERSION, "id": str(uuid4()), "query": query, "created_at": datetime.now(timezone.utc).isoformat(), **summarize(results)}
        if platforms is not None:
            search["requested_platforms"] = platforms
        payload = {"search": search, "ratings": results}
        with self.connect() as db:
            db.execute("INSERT INTO searches VALUES (?, ?, ?, ?)", (search["id"], query, search["created_at"], json.dumps(payload, ensure_ascii=False)))
        return search

    def get(self, search_id):
        with self.connect() as db:
            row = db.execute("SELECT payload FROM searches WHERE id = ?", (search_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def cached(self, query, cutoff):
        with self.connect() as db:
            row = db.execute("SELECT payload FROM searches WHERE query = ? AND created_at >= ? ORDER BY created_at DESC LIMIT 1", (query, cutoff)).fetchone()
        return json.loads(row[0]) if row else None

    def history(self, sort_by, order, limit, offset, platform, sort_platform, with_count):
        with self.connect() as db:
            rows = db.execute("SELECT payload FROM searches").fetchall()
        records = [json.loads(row[0]) for row in rows]
        target = platform or (sort_platform if sort_by == "platform_rating" else None)
        if target:
            records = [r for r in records if any(p["platform"] == target for p in r["ratings"])]
        def sort_key(record):
            if sort_by == "platform_rating":
                return next((p.get("normalized_rating") for p in record["ratings"] if p["platform"] == target), None)
            return record["search"].get(sort_by, record["search"]["created_at"])
        rated = [r for r in records if sort_key(r) is not None]
        unrated = [r for r in records if sort_key(r) is None]
        records = sorted(rated, key=sort_key, reverse=order.lower() == "desc") + unrated
        page = records[offset:offset + limit]
        return {"total": len(records) if with_count else len(page), "searches": [
            {**r["search"], "ratings": [p for p in r["ratings"] if not platform or p["platform"] == platform]} for r in page
        ]}
