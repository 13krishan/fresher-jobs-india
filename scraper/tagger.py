"""Tag each job with role, city and job type using Gemini (REST, JSON-schema output).

- Posts are sent in batches to cut per-call overhead.
- Tags are cached by job id, so the daily run only pays for NEW posts.
- Token usage is recorded so we can report cost per 1,000 posts.
"""
import json
import logging
import os
import time
from dataclasses import dataclass

import requests

from .models import Job

ROLES = (
    "Software Engineering", "Data & Analytics", "AI / ML", "DevOps & Cloud", "QA & Testing",
    "Cybersecurity", "Product Management", "UI/UX & Design", "Marketing", "Sales & Business Development",
    "Finance & Accounting", "HR & Recruiting", "Operations & Supply Chain", "Customer Support",
    "Content & Writing", "Consulting", "Core Engineering (Mech/Elec/Civil)", "Legal", "Other",
)
CITIES = (
    "Bengaluru", "Mumbai", "Pune", "Hyderabad", "Chennai", "Delhi", "Gurugram", "Noida", "Kolkata",
    "Ahmedabad", "Jaipur", "Kochi", "Coimbatore", "Indore", "Chandigarh", "Thiruvananthapuram",
    "Remote", "Multiple Cities", "Other City", "Unknown",
)
JOB_TYPES = ("Internship", "Full-time")

DEFAULT_MODEL = "gemini-3.5-flash-lite"
FALLBACK_MODELS = ("gemini-3.1-flash-lite", "gemini-flash-lite-latest")  # used when the main one is busy/retired
API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
BATCH_SIZE = 25
SECONDS_BETWEEN_CALLS = 4.5   # stays under free-tier 15 requests/minute
MAX_RETRIES = 3
TIMEOUT_SECONDS = 90

PROMPT = """You label Indian fresher job posts. For EACH post return:
- role: exactly one of {roles}
- city: exactly one of {cities}
  Map aliases (Bangalore->Bengaluru, Gurgaon->Gurugram, New Delhi->Delhi, Cochin->Kochi, Trivandrum->Thiruvananthapuram, Navi Mumbai/Thane->Mumbai).
  Use "Remote" if work-from-home, "Multiple Cities" if 2+ cities, "Other City" for an Indian city not listed, "Unknown" if no location.
- job_type: "Internship" if it is an internship/intern/apprenticeship, else "Full-time".
Pick the role from what the person will DO, not the company's industry. Example: "Sales intern at a software company" -> "Sales & Business Development".
Return one object per post, same id as given.

Posts:
{posts}"""

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Usage:
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    posts_tagged: int = 0

    def add(self, input_tokens: int, output_tokens: int, posts: int) -> "Usage":
        return Usage(self.calls + 1, self.input_tokens + input_tokens,
                     self.output_tokens + output_tokens, self.posts_tagged + posts)


def _post_payload(job: Job) -> dict:
    return {"id": job.id, "title": job.title, "company": job.company,
            "location": job.location, "description": job.description[:600]}


def build_request(jobs: list[Job]) -> dict:
    prompt = PROMPT.format(roles=", ".join(ROLES), cities=", ".join(CITIES),
                           posts=json.dumps([_post_payload(j) for j in jobs], ensure_ascii=False))
    schema = {"type": "ARRAY", "items": {"type": "OBJECT", "properties": {
        "id": {"type": "STRING"},
        "role": {"type": "STRING", "enum": list(ROLES)},
        "city": {"type": "STRING", "enum": list(CITIES)},
        "job_type": {"type": "STRING", "enum": list(JOB_TYPES)},
    }, "required": ["id", "role", "city", "job_type"]}}
    return {"contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0, "responseMimeType": "application/json",
                                 "responseSchema": schema}}


def parse_response(body: dict) -> tuple[dict[str, dict], int, int]:
    """Return ({job_id: tag}, input_tokens, output_tokens). Drops invalid labels."""
    text = body["candidates"][0]["content"]["parts"][0]["text"]
    meta = body.get("usageMetadata", {})
    tags = {}
    items = json.loads(text)
    for item in items:
        if item.get("id") and item.get("role") in ROLES and item.get("city") in CITIES \
                and item.get("job_type") in JOB_TYPES:
            tags[item["id"]] = {"role": item["role"], "city": item["city"], "job_type": item["job_type"]}
    if len(tags) < len(items):
        log.warning("%d of %d returned labels were invalid and dropped", len(items) - len(tags), len(items))
    return tags, meta.get("promptTokenCount", 0), meta.get("candidatesTokenCount", 0)


MIN_BATCH_COVERAGE = 0.5  # fewer tags than this share of the batch -> try the next model


def _call_gemini(jobs: list[Job], api_key: str, model: str) -> tuple[dict[str, dict], int, int]:
    """Try the main model, then each fallback. Returns the first result covering enough of the batch."""
    best: tuple[dict[str, dict], int, int] = ({}, 0, 0)
    for candidate in (model, *[m for m in FALLBACK_MODELS if m != model]):
        result = _call_model(jobs, api_key, candidate)
        if result is not None and len(result[0]) >= MIN_BATCH_COVERAGE * len(jobs):
            return result
        if result is not None and len(result[0]) > len(best[0]):
            best = result
        log.warning("model %s gave %s tags for %d posts, trying next",
                    candidate, "no" if result is None else len(result[0]), len(jobs))
    return best


def _call_model(jobs: list[Job], api_key: str, model: str) -> tuple[dict[str, dict], int, int] | None:
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.post(API_URL.format(model=model), json=build_request(jobs),
                                 headers={"x-goog-api-key": api_key}, timeout=TIMEOUT_SECONDS)
            if resp.status_code == 404:  # model retired: no point retrying it
                return None
            if resp.status_code in (400, 401, 403):  # bad key/config: fail fast with a clear message
                raise RuntimeError(f"Gemini auth/config error {resp.status_code}: {resp.text[:200]}")
            if resp.status_code == 429:
                log.warning("Gemini rate limit, waiting (attempt %d)", attempt)
                time.sleep(30 * attempt)
                continue
            resp.raise_for_status()
            return parse_response(resp.json())
        except (requests.RequestException, KeyError, IndexError, ValueError) as exc:
            log.warning("%s batch failed (attempt %d/%d): %s", model, attempt, MAX_RETRIES, exc)
            time.sleep(5 * attempt)
    return None


def tag_jobs(jobs: list[Job], cache: dict[str, dict]) -> tuple[list[Job], dict[str, dict], Usage]:
    """Return (tagged jobs, updated cache, usage for this run). Untaggable jobs keep empty tags."""
    api_key = os.getenv("GEMINI_API_KEY")
    model = os.getenv("GEMINI_MODEL", DEFAULT_MODEL)
    todo = [j for j in jobs if j.id not in cache]
    new_cache = dict(cache)
    usage = Usage()
    if todo and not api_key:
        raise RuntimeError(f"GEMINI_API_KEY not set: {len(todo)} new posts cannot be tagged")
    if todo:
        log.info("tagging %d new posts with %s (%d cached)", len(todo), model, len(jobs) - len(todo))
        for start in range(0, len(todo), BATCH_SIZE):
            batch = todo[start:start + BATCH_SIZE]
            tags, tin, tout = _call_gemini(batch, api_key, model)
            new_cache.update(tags)
            usage = usage.add(tin, tout, len(tags))
            if start + BATCH_SIZE < len(todo):
                time.sleep(SECONDS_BETWEEN_CALLS)
    tagged = [j.with_tags(**new_cache[j.id]) if j.id in new_cache else j for j in jobs]
    return tagged, new_cache, usage
