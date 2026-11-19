"""Remove duplicate posts that appear in several sources or several searches."""
import re

from .models import Job

# Lower number wins when two sources carry the same job (company boards are the original).
SOURCE_PRIORITY = {"greenhouse": 0, "lever": 0, "ashby": 0, "smartrecruiters": 0, "adzuna": 1}

_NON_ALNUM = re.compile(r"[^a-z0-9]+")
_COMPANY_SUFFIX = re.compile(
    r"\b(private|pvt|limited|ltd|llp|inc|technologies|technology|solutions|services|india)\b"
)
_TITLE_NOISE = re.compile(
    r"\b(urgent|hiring|immediate|joiner|joiners|opening|openings|wfh|remote|fresher|freshers|for|s)\b")
DESC_KEY_CHARS = 150  # reposts of one ad often change the title but keep the description


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


def description_key(job: Job) -> str | None:
    """company + city + start of description; None when the description is too short to trust."""
    desc = _norm(job.description)
    if len(desc) < DESC_KEY_CHARS:
        return None
    return "|".join((normalize_company(job.company), first_city(job.location), desc[:DESC_KEY_CHARS]))


def dedupe(jobs: list[Job]) -> list[Job]:
    """Keep one job per (title, company, city), per (company, city, description) and per URL.
    Prefer company boards over aggregators."""
    ranked = sorted(jobs, key=lambda j: SOURCE_PRIORITY.get(j.source, 9))
    seen: set[str] = set()
    kept: list[Job] = []
    for job in ranked:
        keys = {"t:" + dedupe_key(job), "u:" + job.url.split("?")[0].rstrip("/")}
        desc_key = description_key(job)
        if desc_key:
            keys.add("d:" + desc_key)
        if keys & seen:
            continue
        seen |= keys
        kept.append(job)
    return kept
