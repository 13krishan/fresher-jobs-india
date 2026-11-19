"""Adzuna official job search API (India). Needs a free app_id / app_key.
Terms: https://developer.adzuna.com — results must credit Adzuna (done on the page)."""
import logging
import os

from ..http import get_json, html_to_text
from ..models import Job

API_URL = "https://api.adzuna.com/v1/api/jobs/in/search/{page}"
QUERIES = ("fresher", "internship", "graduate trainee", "entry level", "junior", "trainee", "intern")
PAGES_PER_QUERY = 3
DEFAULT_MAX_CALLS = 10  # free tier is small; posts accumulate across days, so 10 calls/day is enough
RESULTS_PER_PAGE = 50
MAX_DAYS_OLD = 30

log = logging.getLogger(__name__)


def _to_job(item: dict) -> Job:
    return Job(
        id=f"adzuna:{item['id']}",
        source="adzuna",
        title=html_to_text(item.get("title", ""), 200),
        company=(item.get("company") or {}).get("display_name", "") or "Unknown",
        location=(item.get("location") or {}).get("display_name", "") or "India",
        url=item.get("redirect_url", ""),
        description=html_to_text(item.get("description", "")),
        posted_at=(item.get("created") or "")[:10],
    )


def fetch() -> list[Job]:
    app_id, app_key = os.getenv("ADZUNA_APP_ID"), os.getenv("ADZUNA_APP_KEY")
    if not app_id or not app_key:
        log.warning("Adzuna skipped: ADZUNA_APP_ID / ADZUNA_APP_KEY not set")
        return []
    max_calls = int(os.getenv("ADZUNA_MAX_CALLS", DEFAULT_MAX_CALLS))
    plan = [(q, p) for p in range(1, PAGES_PER_QUERY + 1) for q in QUERIES][:max_calls]
    jobs: list[Job] = []
    exhausted: set[str] = set()
    for query, page in plan:
        if query in exhausted:
            continue
        data = get_json(API_URL.format(page=page), params={
            "app_id": app_id, "app_key": app_key, "what": query,
            "results_per_page": RESULTS_PER_PAGE, "max_days_old": MAX_DAYS_OLD,
            "content-type": "application/json",
        })
        results = (data or {}).get("results", [])
        jobs.extend(_to_job(r) for r in results if r.get("id"))
        if len(results) < RESULTS_PER_PAGE:
            exhausted.add(query)
    log.info("adzuna: %d raw posts", len(jobs))
    return jobs
