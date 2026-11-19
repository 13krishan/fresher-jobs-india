"""Keep posts across days so the list grows even when a source gives few new posts.
A post stays for KEEP_DAYS after we last saw it, then drops off."""
from dataclasses import asdict, replace
from datetime import date, timedelta

from .models import Job

KEEP_DAYS = 30


def to_record(job: Job, seen_on: str) -> dict:
    return {**asdict(job), "first_seen": job.extra.get("first_seen", seen_on), "last_seen": seen_on}


def from_record(rec: dict) -> Job:
    fields = {k: v for k, v in rec.items() if k not in ("first_seen", "last_seen")}
    extra = {**fields.get("extra", {}), "first_seen": rec.get("first_seen", ""),
             "last_seen": rec.get("last_seen", "")}
    return Job(**{**fields, "extra": extra})


def merge(stored: list[dict], fresh: list[Job], today: date) -> list[Job]:
    """Union of stored and fresh posts. Fresh copies win (newer data) but keep first_seen.
    Posts not seen for KEEP_DAYS are dropped."""
    cutoff = (today - timedelta(days=KEEP_DAYS)).isoformat()
    by_id = {r["id"]: from_record(r) for r in stored if r.get("last_seen", "") >= cutoff}
    for job in fresh:
        old = by_id.get(job.id)
        first_seen = old.extra.get("first_seen") if old else today.isoformat()
        by_id[job.id] = replace(job, extra={**job.extra, "first_seen": first_seen,
                                            "last_seen": today.isoformat()})
    return list(by_id.values())


def to_records(jobs: list[Job]) -> list[dict]:
    return [{**asdict(j), "first_seen": j.extra.get("first_seen", ""),
             "last_seen": j.extra.get("last_seen", "")} for j in jobs]
