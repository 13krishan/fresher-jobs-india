"""Daily pipeline: fetch -> keep India fresher posts -> dedupe -> LLM tag -> write JSON for the site.

Run:  python -m scraper.main
"""
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from .dedupe import dedupe
from .filters import is_fresher, is_in_india
from .models import Job
from .sources import adzuna, ats
from .tagger import tag_jobs

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "docs" / "data"
JOBS_FILE = DATA_DIR / "jobs.json"
META_FILE = DATA_DIR / "meta.json"
CACHE_FILE = ROOT / "data" / "tag_cache.json"
USAGE_LOG = ROOT / "data" / "usage_log.jsonl"
FRESHER_LEVELS = ("entry_level", "internship")

log = logging.getLogger("pipeline")


def _read_json(path: Path, default):
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def _write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1))


def keep_fresher_india(jobs: list[Job]) -> list[Job]:
    return [j for j in jobs if is_in_india(j.location) and (
        is_fresher(j.title, j.description) or j.extra.get("experience_level") in FRESHER_LEVELS)]


def run() -> dict:
    load_dotenv(ROOT / ".env")
    raw = adzuna.fetch() + ats.fetch()
    filtered = keep_fresher_india(raw)
    unique = dedupe(filtered)
    tagged, cache, usage = tag_jobs(unique, _read_json(CACHE_FILE, {}))
    tagged = [j for j in tagged if j.role]  # only publish posts the LLM could tag
    tagged.sort(key=lambda j: j.posted_at or "", reverse=True)

    stats = {
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "raw": len(raw), "india_fresher": len(filtered), "after_dedupe": len(unique),
        "published": len(tagged), "duplicates_removed": len(filtered) - len(unique),
        "by_source": {s: sum(1 for j in tagged if j.source == s) for s in sorted({j.source for j in tagged})},
        "llm_calls": usage.calls, "llm_input_tokens": usage.input_tokens,
        "llm_output_tokens": usage.output_tokens, "llm_posts_tagged": usage.posts_tagged,
    }
    _write_json(JOBS_FILE, [j.to_public_dict() for j in tagged])
    _write_json(META_FILE, stats)
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
