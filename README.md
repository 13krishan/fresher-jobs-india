# Fresher Jobs India

A live page of fresher jobs and internships in India. Every day it collects posts from public job APIs, removes duplicates, tags each post by **role** and **city** with an LLM (Gemini), and publishes a searchable page.

**Live site:** https://13krishan.github.io/fresher-jobs-india/

## How it works

```
GitHub Actions (daily 06:00 IST)
  └─ python -m scraper.main
       1. Fetch     Adzuna India API + public ATS boards (Greenhouse, Lever, Ashby, SmartRecruiters, Workday)
       2. Filter    keep India + fresher posts (title words, "0-1 years", entry-level flags)
       3. Dedupe    same title + company + city, or same URL → keep one (company board wins)
       4. Tag       Gemini, 25 posts per call, JSON-schema output, cached by job id
       5. Publish   docs/data/jobs.json + meta.json → commit → GitHub Pages
```

| Folder | What it holds |
|---|---|
| `scraper/sources/` | One module per source; official/public APIs only |
| `scraper/filters.py` | India + fresher rules |
| `scraper/dedupe.py` | Duplicate removal |
| `scraper/tagger.py` | Gemini prompt, schema, batching, cache, token usage |
| `docs/` | Static search page (no framework) |
| `data/` | Tag cache and per-run usage log (for cost per 1,000 posts) |

## Respecting site terms
Only official APIs or public job-board endpoints that ATS vendors publish for embedding jobs. No login-walled sites (LinkedIn, Naukri, Indeed) and nothing disallowed in robots.txt (Internshala blocks its search and detail pages, so it is not used). Adzuna results are credited on the page as their terms require. Each card links to the original post.

## Run locally
```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env   # add ADZUNA_APP_ID, ADZUNA_APP_KEY, GEMINI_API_KEY
.venv/bin/pytest -q
.venv/bin/python -m scraper.main
python3 -m http.server -d docs 8000
```
