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

    def connect(self):
        return sqlite3.connect(self.path, timeout=10)

    def save(self, query, results, platforms=None):
        from api.db import summarize
        search = {"id": str(uuid4()), "query": query, "created_at": datetime.now(timezone.utc).isoformat(), **summarize(results)}
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
