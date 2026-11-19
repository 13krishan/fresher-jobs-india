"""Public company job-board APIs (Greenhouse, Lever, Ashby, SmartRecruiters).
These endpoints are published by the ATS vendors for exactly this use: showing a
company's open jobs on other sites. No login, no scraping of HTML."""
import logging

from ..http import get_json, html_to_text
from ..models import Job

log = logging.getLogger(__name__)

# Boards checked to have India openings. Add more here; unknown boards are skipped safely.
GREENHOUSE_BOARDS = ("groww", "inmobi", "druva", "slice", "phonepe", "postman", "rubrik",
                     "databricks", "stripe", "cloudflare", "okta", "mongodb", "elastic",
                     "gitlab", "twilio", "datadog", "zscaler", "nutanix", "coinbase", "airbnb")
LEVER_BOARDS = ("cred", "zeta", "upstox", "paytm", "meesho", "jar-app", "fampay", "spotdraft",
                "mindtickle", "whatfix", "leadsquared", "toptal", "palantir")
ASHBY_BOARDS = ("atlan", "zepto", "sarvam", "plivo", "kuku", "deel", "notion", "ramp")
SMARTRECRUITERS_COMPANIES = ("BoschGroup", "ServiceNow", "Experian", "Continental", "Visa")
SMARTRECRUITERS_PAGE = 100
SMARTRECRUITERS_MAX_PAGES = 10


def _greenhouse(board: str) -> list[Job]:
    data = get_json(f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs", {"content": "true"})
    return [Job(
        id=f"greenhouse:{board}:{j['id']}", source="greenhouse", title=j.get("title", ""),
        company=board.title(), location=(j.get("location") or {}).get("name", ""),
        url=j.get("absolute_url", ""), description=html_to_text(j.get("content", "")),
        posted_at=(j.get("updated_at") or "")[:10],
    ) for j in (data or {}).get("jobs", [])]


def _lever(board: str) -> list[Job]:
    data = get_json(f"https://api.lever.co/v0/postings/{board}", {"mode": "json"})
    if not isinstance(data, list):
        return []
    return [Job(
        id=f"lever:{board}:{j['id']}", source="lever", title=j.get("text", ""),
        company=board.replace("-", " ").title(),
        location=(j.get("categories") or {}).get("location", "") or "",
        url=j.get("hostedUrl", ""), description=html_to_text(j.get("descriptionPlain", "")),
        posted_at="",
    ) for j in data]


def _ashby(board: str) -> list[Job]:
    data = get_json(f"https://api.ashbyhq.com/posting-api/job-board/{board}")
    return [Job(
        id=f"ashby:{board}:{j['id']}", source="ashby", title=j.get("title", ""),
        company=board.title(), location=j.get("location", "") or "",
        url=j.get("jobUrl", ""), description=html_to_text(j.get("descriptionPlain", "")),
        posted_at=(j.get("publishedAt") or "")[:10],
    ) for j in (data or {}).get("jobs", [])]


def _smartrecruiters(company: str) -> list[Job]:
    jobs: list[Job] = []
    for page in range(SMARTRECRUITERS_MAX_PAGES):
        data = get_json(f"https://api.smartrecruiters.com/v1/companies/{company}/postings",
                        {"country": "in", "limit": SMARTRECRUITERS_PAGE,
                         "offset": page * SMARTRECRUITERS_PAGE})
        content = (data or {}).get("content", [])
        for j in content:
            loc = j.get("location") or {}
            jobs.append(Job(
                id=f"smartrecruiters:{j['id']}", source="smartrecruiters", title=j.get("name", ""),
                company=(j.get("company") or {}).get("name", company),
                location=", ".join(p for p in (loc.get("city"), loc.get("region"), "India") if p),
                url=f"https://jobs.smartrecruiters.com/{company}/{j['id']}",
                # function only: the "Entry Level" label is unreliable and would fool the fresher rule
                description=(j.get("function") or {}).get("label", ""),
                posted_at=(j.get("releasedDate") or "")[:10],
                extra={"experience_level": (j.get("experienceLevel") or {}).get("id", "")},
            ))
        if len(content) < SMARTRECRUITERS_PAGE:
            break
    return jobs


def fetch() -> list[Job]:
    plan = ([(_greenhouse, b) for b in GREENHOUSE_BOARDS] + [(_lever, b) for b in LEVER_BOARDS]
            + [(_ashby, b) for b in ASHBY_BOARDS] + [(_smartrecruiters, c) for c in SMARTRECRUITERS_COMPANIES])
    jobs: list[Job] = []
    for fn, board in plan:
        try:
            found = fn(board)
        except (KeyError, TypeError, AttributeError) as exc:  # unexpected payload shape
            log.warning("%s/%s skipped: %s", fn.__name__, board, exc)
            continue
        jobs.extend(found)
    log.info("ats boards: %d raw posts", len(jobs))
    return jobs
