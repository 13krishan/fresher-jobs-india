from datetime import date

from scraper.models import Job
from scraper.store import merge, to_records


def job(i: str, title: str = "Intern") -> Job:
    return Job(id=i, source="lever", title=title, company="Acme", location="Pune",
               url=f"https://a.com/{i}", description="", posted_at="")


def test_merge_keeps_old_posts_and_adds_new():
    stored = to_records(merge([], [job("a")], date(2026, 11, 1)))
    merged = merge(stored, [job("b")], date(2026, 11, 2))
    assert {j.id for j in merged} == {"a", "b"}


def test_merge_keeps_first_seen_and_updates_last_seen():
    stored = to_records(merge([], [job("a")], date(2026, 11, 1)))
    merged = merge(stored, [job("a", "Intern v2")], date(2026, 11, 5))
    assert merged[0].title == "Intern v2"
    assert merged[0].extra["first_seen"] == "2026-11-01"
    assert merged[0].extra["last_seen"] == "2026-11-05"


def test_merge_drops_posts_not_seen_for_30_days():
    stored = to_records(merge([], [job("a")], date(2026, 10, 1)))
    merged = merge(stored, [], date(2026, 11, 15))
    assert merged == []
