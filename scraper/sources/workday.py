"""Workday career sites (public job-search JSON behind each company's careers page).
robots.txt on these sites allows the career-site paths and publishes sitemaps.
We send a few small searches per company, once a day."""
import logging
import os
import time

import requests

from ..http import USER_AGENT, html_to_text
from ..models import Job

# tenant, workday host number, career site name — checked to have India fresher posts
SITES = (
    ("citi", "wd5", "2"), ("db", "wd3", "DBWebsite"), ("marvell", "wd1", "MarvellCareers"),
    ("pg", "wd5", "1000"), ("hp", "wd5", "ExternalCareerSite"),
    ("pwc", "wd3", "Global_Experienced_Careers"), ("micron", "wd1", "External"),
    ("nvidia", "wd5", "NVIDIAExternalCareerSite"), ("adobe", "wd5", "external_experienced"),
    ("motorolasolutions", "wd5", "Careers"), ("pfizer", "wd1", "PfizerCareers"),
    ("abbott", "wd5", "abbottcareers"), ("autodesk", "wd1", "Ext"), ("intel", "wd1", "External"),
    ("mastercard", "wd1", "CorporateCareers"), ("salesforce", "wd12", "External_Career_Site"),
)
SEARCHES = ("intern india", "graduate india", "trainee india", "fresher", "junior india", "associate india")
PAGE_SIZE = 20
TIMEOUT_SECONDS = 15
PAUSE_SECONDS = 0.5

log = logging.getLogger(__name__)
_session = requests.Session()
_session.headers.update({"User-Agent": USER_AGENT, "Content-Type": "application/json",
                         "Accept": "application/json"})


def _site_jobs(tenant: str, wd: str, site: str) -> list[Job]:
    base = f"https://{tenant}.{wd}.myworkdayjobs.com"
    api = f"{base}/wday/cxs/{tenant}/{site}/jobs"
    found: dict[str, Job] = {}
    for query in SEARCHES:
        try:
            resp = _session.post(api, json={"appliedFacets": {}, "limit": PAGE_SIZE, "offset": 0,
                                            "searchText": query}, timeout=TIMEOUT_SECONDS)
            resp.raise_for_status()
            postings = resp.json().get("jobPostings", []) or []
        except (requests.RequestException, ValueError, AttributeError, TypeError) as exc:
            log.warning("workday %s '%s' failed: %s", tenant, query, exc)
            continue  # one failed search should not skip the other searches for this company
        for p in postings:
            path = p.get("externalPath", "")
            if not path or path in found:
                continue
            # externalPath looks like /job/India-Bengaluru/Title_JR123 — carries the city
            place = path.split("/")[2].replace("-", ", ") if path.count("/") >= 3 else ""
            found[path] = Job(
                id=f"workday:{tenant}:{path.rsplit('_', 1)[-1]}", source="workday",
                title=p.get("title", ""), company=tenant.upper() if len(tenant) <= 3 else tenant.title(),
                location=f"{p.get('locationsText', '')} | {place}",
                url=f"{base}/{site}{path}", description=html_to_text(" ".join(p.get("bulletFields", []))),
                posted_at="",
            )
        time.sleep(PAUSE_SECONDS)
    return list(found.values())


MAX_FAILED_SHARE = 0.5


def fetch() -> list[Job]:
    # Workday answers 429 to datacenter IPs (e.g. GitHub Actions). We respect that and do not
    # retry or rotate IPs: the daily cloud run sets WORKDAY_ENABLED=false.
    if os.getenv("WORKDAY_ENABLED", "true").lower() == "false":
        log.info("workday: disabled for this run")
        return []
    jobs: list[Job] = []
    empty_sites = 0
    for tenant, wd, site in SITES:
        try:
            found = _site_jobs(tenant, wd, site)
        except (KeyError, TypeError, AttributeError) as exc:  # unexpected payload shape
            log.warning("workday %s skipped: %s", tenant, exc)
            found = []
        empty_sites += not found
        jobs.extend(found)
    if empty_sites > MAX_FAILED_SHARE * len(SITES):
        log.error("workday: %d of %d sites returned nothing - check the API", empty_sites, len(SITES))
    log.info("workday: %d raw posts", len(jobs))
    return jobs
