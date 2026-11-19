"""Small HTTP helper: polite user agent, timeout, retries."""
import html
import logging
import re
import time

import requests

USER_AGENT = "fresher-jobs-india/1.0 (open-source job aggregator)"
TIMEOUT_SECONDS = 20
MAX_RETRIES = 3
BACKOFF_SECONDS = 2

log = logging.getLogger(__name__)
_session = requests.Session()
_session.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json"})


def get_json(url: str, params: dict | None = None):
    """GET a JSON endpoint. Returns parsed JSON, or None after all retries fail."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = _session.get(url, params=params, timeout=TIMEOUT_SECONDS)
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return resp.json()
        except (requests.RequestException, ValueError) as exc:
            log.warning("GET %s failed (attempt %d/%d): %s", url, attempt, MAX_RETRIES, exc)
            time.sleep(BACKOFF_SECONDS * attempt)
    return None


_TAG_RE = re.compile(r"<[^>]+>")
_SPACE_RE = re.compile(r"\s+")


def html_to_text(raw: str, limit: int = 1500) -> str:
    """Strip tags and entities, collapse whitespace, trim to `limit` chars."""
    text = html.unescape(_TAG_RE.sub(" ", html.unescape(raw or "")))
    return _SPACE_RE.sub(" ", text).strip()[:limit]
