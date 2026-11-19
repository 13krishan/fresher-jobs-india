"""Shared job record shape used by every source."""
from dataclasses import dataclass, field, replace


@dataclass(frozen=True)
class Job:
    id: str            # stable id: "<source>:<source id>"
    source: str        # adzuna | greenhouse | lever | ashby | smartrecruiters
    title: str
    company: str
    location: str      # raw location text from the source
    url: str
    description: str   # plain text, trimmed
    posted_at: str     # ISO date (YYYY-MM-DD) or ""
    role: str = ""     # filled by the LLM tagger
    city: str = ""     # filled by the LLM tagger
    job_type: str = "" # Internship | Full-time, filled by the LLM tagger
    extra: dict = field(default_factory=dict)

    def with_tags(self, role: str, city: str, job_type: str) -> "Job":
        return replace(self, role=role, city=city, job_type=job_type)

    def to_public_dict(self) -> dict:
        return {
            "id": self.id,
            "source": self.source,
            "title": self.title,
            "company": self.company,
            "location": self.location,
            "url": self.url,
            "posted_at": self.posted_at,
            "role": self.role,
            "city": self.city,
            "job_type": self.job_type,
            "snippet": self.description[:280],
        }
