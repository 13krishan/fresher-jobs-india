"""Remove duplicate posts that appear in several sources or several searches."""
import re

from .models import Job

# Lower number wins when two sources carry the same job (company boards are the original).
SOURCE_PRIORITY = {"greenhouse": 0, "lever": 0, "ashby": 0, "smartrecruiters": 0, "adzuna": 1}

_NON_ALNUM = re.compile(r"[^a-z0-9]+")
_COMPANY_SUFFIX = re.compile(
    r"\b(private|pvt|limited|ltd|llp|inc|technologies|technology|solutions|services|india)\b"
)
_TITLE_NOISE = re.compile(r"\b(urgent|hiring|immediate|joiner|joiners|opening|wfh|remote)\b")


def _norm(text: str) -> str:
    return _NON_ALNUM.sub(" ", (text or "").lower()).strip()


def normalize_company(name: str) -> str:
    return " ".join(_COMPANY_SUFFIX.sub(" ", _norm(name)).split())


def normalize_title(title: str) -> str:
    return " ".join(_TITLE_NOISE.sub(" ", _norm(title)).split())


def first_city(location: str) -> str:
    return _norm((location or "").split(",")[0])


def dedupe_key(job: Job) -> str:
    return "|".join((normalize_title(job.title), normalize_company(job.company), first_city(job.location)))


def dedupe(jobs: list[Job]) -> list[Job]:
    """Keep one job per (title, company, city) and per URL. Prefer company boards."""
    ranked = sorted(jobs, key=lambda j: SOURCE_PRIORITY.get(j.source, 9))
    seen_keys: set[str] = set()
    seen_urls: set[str] = set()
    kept: list[Job] = []
    for job in ranked:
        key = dedupe_key(job)
        url = job.url.split("?")[0].rstrip("/")
        if key in seen_keys or url in seen_urls:
            continue
        seen_keys.add(key)
        seen_urls.add(url)
        kept.append(job)
    return kept
