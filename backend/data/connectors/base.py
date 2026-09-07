"""Shared HTTP helpers with disk cache + soft failure.

Reconfigure-only: uses requests if installed, else urllib stdlib.
Never raises — returns None/empty on missing keys, quota, or network error.
"""

import csv
import io
import json
import os
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta

try:
    import requests  # optional, preferred
except Exception:  # pragma: no cover
    requests = None

CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".cache")
os.makedirs(CACHE_DIR, exist_ok=True)


def _cache_path(key: str) -> str:
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in key)[:120]
    return os.path.join(CACHE_DIR, f"{safe}.json")


def cache_read(key: str, max_age_hours: float):
    try:
        path = _cache_path(key)
        if not os.path.exists(path):
            return None
        age = time.time() - os.path.getmtime(path)
        if age > max_age_hours * 3600:
            return None
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def cache_write(key: str, payload) -> None:
    try:
        with open(_cache_path(key), "w", encoding="utf-8") as f:
            json.dump(payload, f, default=str)
    except Exception:
        pass


def http_get(url: str, params: dict | None = None, headers: dict | None = None,
             timeout: int = 20, cache_key: str | None = None,
             cache_hours: float = 0):
    """GET with optional disk cache. Returns (text, from_cache). None on failure."""
    if cache_key and cache_hours > 0:
        hit = cache_read(cache_key, cache_hours)
        if hit is not None and isinstance(hit, dict) and "text" in hit:
            return hit["text"], True
    try:
        if requests is not None:
            r = requests.get(url, params=params, headers=headers or {}, timeout=timeout)
            if r.status_code != 200:
                raise RuntimeError(f"HTTP {r.status_code} for {url}")
            text = r.text
        else:
            query = f"?{urllib.parse.urlencode(params or {})}" if params else ""
            req = urllib.request.Request(url + query, headers=headers or {})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                text = resp.read().decode("utf-8", errors="replace")
        if cache_key and cache_hours > 0:
            cache_write(cache_key, {"text": text, "at": datetime.utcnow().isoformat()})
        return text, False
    except Exception as e:
        # Quota / network failure → serve stale cache regardless of age
        if cache_key:
            try:
                path = _cache_path(cache_key)
                if os.path.exists(path):
                    with open(path, "r", encoding="utf-8") as f:
                        stale = json.load(f)
                    if isinstance(stale, dict) and "text" in stale:
                        print(f"[connectors] {url} failed ({e}); serving stale cache.")
                        return stale["text"], True
            except Exception:
                pass
        print(f"[connectors] GET failed {url}: {e}")
        return None, False


def parse_csv_rows(text: str):
    try:
        reader = csv.DictReader(io.StringIO(text))
        return list(reader)
    except Exception:
        return []
