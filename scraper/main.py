"""Daily pipeline: fetch -> keep India fresher posts -> dedupe -> LLM tag -> write JSON for the site.

Run:  python -m scraper.main
"""
import csv
import io
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from .dedupe import dedupe
from .filters import is_fresher, is_in_india, is_junk, is_senior
from .models import Job
from .sources import adzuna, ats, workday
from .store import merge, to_records
from .tagger import tag_jobs

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "docs" / "data"
JOBS_FILE = DATA_DIR / "jobs.json"
META_FILE = DATA_DIR / "meta.json"
CSV_FILE = DATA_DIR / "jobs.csv"  # same rows as jobs.json, for the Google Sheet (IMPORTDATA)
CSV_COLUMNS = ("title", "company", "location", "city", "role", "job_type", "source", "posted_at", "url")
CACHE_FILE = ROOT / "data" / "tag_cache.json"
STORE_FILE = ROOT / "data" / "jobs_store.json"
USAGE_LOG = ROOT / "data" / "usage_log.jsonl"
FRESHER_LEVELS = ("internship",)  # boards over-use "entry_level" (Bosch tags seniors with it)

log = logging.getLogger("pipeline")


MIN_KEEP_RATIO = 0.7  # refuse to publish if the list shrinks below 70% of the last run


def _read_json(path: Path, default):
    """Missing file -> default. Corrupt file -> raise (never silently treat history as empty)."""
    try:
        return json.loads(path.read_text())
    except FileNotFoundError:
        return default


def _write_json(path: Path, data) -> None:
    """Atomic write: a killed run never leaves half-written JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1))
    tmp.replace(path)


def _write_csv(path: Path, rows: list[dict]) -> None:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=CSV_COLUMNS, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(buf.getvalue())
    tmp.replace(path)


def check_not_shrunk(published: int, previous: int) -> None:
    if previous >= 50 and published < MIN_KEEP_RATIO * previous:
        raise SystemExit(f"Refusing to publish: {published} posts vs {previous} last run "
                         "(a source or the LLM probably failed - see logs)")


def keep_fresher_india(jobs: list[Job]) -> list[Job]:
    """India + fresher, never senior titles (even if a board flags them entry-level), never junk."""
    return [j for j in jobs
            if is_in_india(j.location) and not is_senior(j.title) and not is_junk(j.title, j.company)
            and (is_fresher(j.title, j.description) or j.extra.get("experience_level") in FRESHER_LEVELS)]


def run() -> dict:
    load_dotenv(ROOT / ".env")
    raw = adzuna.fetch() + ats.fetch() + workday.fetch()
    filtered = keep_fresher_india(raw)
    live = frozenset(j.source for j in raw)  # sources that returned posts today
    pool = merge(_read_json(STORE_FILE, []), filtered, datetime.now(timezone.utc).date(), live)
    unique = dedupe(keep_fresher_india(pool))  # re-filter stored posts too, so rule fixes apply to history
    tagged, cache, usage = tag_jobs(unique, _read_json(CACHE_FILE, {}))
    tagged = [j for j in tagged if j.role]  # only publish posts the LLM could tag
    tagged.sort(key=lambda j: j.posted_at or "", reverse=True)

    stats = {
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "raw_today": len(raw), "india_fresher_today": len(filtered), "pool_30d": len(pool),
        "after_dedupe": len(unique), "published": len(tagged), "duplicates_removed": len(pool) - len(unique),
        "by_source": {s: sum(1 for j in tagged if j.source == s) for s in sorted({j.source for j in tagged})},
        "raw_by_source": {s: sum(1 for j in raw if j.source == s) for s in sorted({j.source for j in raw})},
        "llm_calls": usage.calls, "llm_input_tokens": usage.input_tokens,
        "llm_output_tokens": usage.output_tokens, "llm_posts_tagged": usage.posts_tagged,
    }
    check_not_shrunk(len(tagged), _read_json(META_FILE, {}).get("published", 0))
    public = [j.to_public_dict() for j in tagged]
    _write_json(JOBS_FILE, public)
    _write_csv(CSV_FILE, public)
    _write_json(META_FILE, stats)
    _write_json(STORE_FILE, to_records(unique))
    _write_json(CACHE_FILE, {k: v for k, v in cache.items() if k in {j.id for j in unique}})
    USAGE_LOG.parent.mkdir(parents=True, exist_ok=True)
    with USAGE_LOG.open("a") as fh:
        fh.write(json.dumps(stats) + "\n")
    log.info("done: %s", stats)
    return stats


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    result = run()
    if result["published"] == 0:
        raise SystemExit("No posts published - check API keys and logs above")
