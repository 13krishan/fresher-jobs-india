import pytest

from scraper.dedupe import dedupe
from scraper.filters import is_fresher, is_in_india
from scraper.models import Job


def make_job(**overrides) -> Job:
    base = dict(id="x:1", source="adzuna", title="Software Engineer Intern", company="Acme Pvt Ltd",
                location="Bengaluru, Karnataka", url="https://a.com/1", description="", posted_at="")
    return Job(**{**base, **overrides})


@pytest.mark.parametrize("title,expected", [
    ("Software Engineer, Intern", True),
    ("SDE I - Backend", True),
    ("SDE II - AI", False),
    ("SDE III - Devops", False),
    ("Graduate Trainee - Finance", True),
    ("Senior Data Analyst", False),
    ("Product Manager", False),
    ("Junior Accountant", True),
    ("Internal Auditor", False),
])
def test_is_fresher_by_title(title, expected):
    assert is_fresher(title, "") is expected


def test_is_fresher_by_experience_text():
    assert is_fresher("Data Analyst", "Experience required: 0-1 years")
    assert is_fresher("Sales Executive", "Freshers can apply")
    assert not is_fresher("Data Analyst", "Experience: 3-5 years")


def test_senior_title_beats_fresher_text():
    assert not is_fresher("Senior Engineer", "freshers welcome")


@pytest.mark.parametrize("loc,expected", [
    ("Bangalore, IND", True), ("Gurugram, Haryana", True), ("Remote - India", True),
    ("San Francisco, CA", False), ("", False),
])
def test_is_in_india(loc, expected):
    assert is_in_india(loc) is expected


def test_dedupe_removes_same_job_with_company_suffix_noise():
    a = make_job(id="adzuna:1", company="Acme Technologies Pvt Ltd", url="https://a.com/1")
    b = make_job(id="greenhouse:1", source="greenhouse", company="Acme", url="https://b.com/9")
    kept = dedupe([a, b])
    assert len(kept) == 1
    assert kept[0].source == "greenhouse"  # company board preferred over aggregator


def test_dedupe_removes_same_url():
    a = make_job(id="a", title="Intern A", url="https://a.com/1?utm=x")
    b = make_job(id="b", title="Intern B", url="https://a.com/1")
    assert len(dedupe([a, b])) == 1


def test_dedupe_keeps_same_title_in_different_cities():
    a = make_job(id="a", location="Pune", url="https://a.com/1")
    b = make_job(id="b", location="Chennai", url="https://a.com/2")
    assert len(dedupe([a, b])) == 2


def test_dedupe_treats_fresher_and_freshers_titles_as_same():
    a = make_job(id="a", title="Business Development Associate (Freshers)", url="https://a.com/1")
    b = make_job(id="b", title="Business Development Associate (Fresher)", url="https://a.com/2")
    assert len(dedupe([a, b])) == 1


def test_dedupe_catches_repost_with_new_title_but_same_description():
    desc = "We are seeking a motivated fresher to join our Business Development team as a Pre-sales " \
           "Associate. In this entry-level role, you will support the sales cycle by researching prospects."
    a = make_job(id="a", title="BD Associate", description=desc, url="https://a.com/1")
    b = make_job(id="b", title="BD Representative", description=desc, url="https://a.com/2")
    assert len(dedupe([a, b])) == 1


def test_dedupe_keeps_short_generic_descriptions_apart():
    a = make_job(id="a", title="Sales Intern", description="Apply now", url="https://a.com/1")
    b = make_job(id="b", title="HR Intern", description="Apply now", url="https://a.com/2")
    assert len(dedupe([a, b])) == 2


@pytest.mark.parametrize("title,company,expected", [
    ("demooo", "Test", True), ("deomm", "Acme", True), ("Test", "Acme", True),
    ("QA Test Engineer Intern", "Acme", False), ("Data Analyst Intern", "Test", True),
    ("Demo Engineer Trainee", "Acme", False),
])
def test_is_junk(title, company, expected):
    from scraper.filters import is_junk
    assert is_junk(title, company) is expected


def test_keep_fresher_india_drops_senior_even_if_flagged_entry_level():
    from scraper.main import keep_fresher_india
    senior = make_job(title="Assistant Manager / Senior Engineer", extra={"experience_level": "entry_level"})
    junior = make_job(id="y", title="Jr Developer", url="https://a.com/2")
    assert [j.id for j in keep_fresher_india([senior, junior])] == ["y"]


def test_senior_with_underscore_prefix_is_caught():
    assert not is_fresher("IN_RBAI_Senior Process Engineer Trainee", "")
    assert not is_fresher("BGSW_SAP_REFX_Consultant", "freshers")
