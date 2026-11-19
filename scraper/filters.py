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

SENIOR_TITLE_RE = re.compile(
    r"\b(senior|sr\.?|lead|principal|staff|manager|director|head|architect|vp)\b",
    re.IGNORECASE,
)


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
