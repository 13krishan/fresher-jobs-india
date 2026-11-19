"""Rules that decide whether a post is (a) in India and (b) for freshers."""
import re

INDIA_PLACES = (
    "india", "bengaluru", "bangalore", "mumbai", "pune", "hyderabad", "chennai",
    "delhi", "new delhi", "gurugram", "gurgaon", "noida", "kolkata", "ahmedabad",
    "jaipur", "kochi", "cochin", "coimbatore", "indore", "chandigarh", "trivandrum",
    "thiruvananthapuram", "mysore", "mysuru", "nagpur", "lucknow", "bhubaneswar",
    "vadodara", "surat", "visakhapatnam", "goa", "mohali", "navi mumbai", "thane",
)

# Whole-word matches only, so "SDE I" does not match "SDE II".
FRESHER_TITLE_RE = re.compile(
    r"\b(interns?|internship|trainee|freshers?|graduate|new grad|entry[- ]level|junior|jr\.?"
    r"|apprentice(ship)?|campus|associate software engineer|(sde|engineer|analyst|developer)"
    r"[- ]?(1|i)|level[- ]?1|l1)(?![\w])",
    re.IGNORECASE,
)

# "0-1 years", "0 to 2 yrs", "0 - 1 year", "freshers can apply"
FRESHER_TEXT_RE = re.compile(
    r"\b0\s*(?:-|–|to)\s*[12]\s*(?:years?|yrs?)\b|\bfreshers?\b|\bno experience\b"
    r"|\bentry[- ]level\b|\brecent graduates?\b",
    re.IGNORECASE,
)

# Letter boundaries (not \b) so "IN_RBAI_Senior Engineer" is caught too.
SENIOR_TITLE_RE = re.compile(
    r"(?<![a-z])(senior|sr\.?|lead|principal|staff|manager|director|head|architect|vp|consultant)(?![a-z])",
    re.IGNORECASE,
)


JUNK_COMPANIES = {"test", "demo", "abc", "xyz", "na", "n a", "company", "confidential test"}
JUNK_TITLE_RE = re.compile(r"^\W*(test\w*|d+e*m+o+\w*|d+e+o+m+\w*|asdf\w*|sample\w*|dummy\w*)\W*$", re.IGNORECASE)
MIN_TITLE_CHARS = 4


def is_junk(title: str, company: str) -> bool:
    """Test/demo posts that some boards leave live (e.g. company 'Test', title 'demooo')."""
    t = (title or "").strip()
    c = re.sub(r"[^a-z ]", " ", (company or "").lower()).strip()
    return len(t) < MIN_TITLE_CHARS or bool(JUNK_TITLE_RE.match(t)) or c in JUNK_COMPANIES


def is_senior(title: str) -> bool:
    return bool(SENIOR_TITLE_RE.search(title or ""))


def is_in_india(location: str) -> bool:
    loc = (location or "").lower()
    return any(place in loc for place in INDIA_PLACES)


def is_fresher(title: str, description: str) -> bool:
    """Fresher if the title says so, or the text says 0-1/0-2 yrs / freshers,
    and the title is not clearly senior."""
    t = title or ""
    if SENIOR_TITLE_RE.search(t):
        return False
    if FRESHER_TITLE_RE.search(t):
        return True
    return bool(FRESHER_TEXT_RE.search(description or ""))
