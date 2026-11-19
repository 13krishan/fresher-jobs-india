import json

from scraper.models import Job
from scraper.tagger import build_request, parse_response, tag_jobs


def job(i: str) -> Job:
    return Job(id=i, source="adzuna", title="Data Analyst Intern", company="Acme", location="Gurgaon",
               url=f"https://a.com/{i}", description="SQL, Excel", posted_at="2026-11-18")


def gemini_body(items: list[dict]) -> dict:
    return {"candidates": [{"content": {"parts": [{"text": json.dumps(items)}]}}],
            "usageMetadata": {"promptTokenCount": 1000, "candidatesTokenCount": 120}}


def test_parse_response_keeps_valid_and_drops_invalid_labels():
    body = gemini_body([
        {"id": "a", "role": "Data & Analytics", "city": "Gurugram", "job_type": "Internship"},
        {"id": "b", "role": "Astronaut", "city": "Gurugram", "job_type": "Internship"},
    ])
    tags, tin, tout = parse_response(body)
    assert tags == {"a": {"role": "Data & Analytics", "city": "Gurugram", "job_type": "Internship"}}
    assert (tin, tout) == (1000, 120)


def test_build_request_uses_json_schema_and_includes_posts():
    req = build_request([job("a")])
    assert req["generationConfig"]["responseMimeType"] == "application/json"
    assert "Data Analyst Intern" in req["contents"][0]["parts"][0]["text"]


def test_tag_jobs_uses_cache_and_skips_api(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    cache = {"a": {"role": "Data & Analytics", "city": "Gurugram", "job_type": "Internship"}}
    tagged, new_cache, usage = tag_jobs([job("a")], cache)
    assert tagged[0].role == "Data & Analytics"
    assert usage.calls == 0
    assert new_cache == cache and new_cache is not cache
