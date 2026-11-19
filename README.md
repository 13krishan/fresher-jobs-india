# Fresher Jobs India

A live, searchable page of fresher jobs and internships in India. Every day it collects posts from public job APIs, removes duplicates, tags each post by **role**, **city** and **job type** with an LLM (Gemini), and republishes the page on its own.

| | |
|---|---|
| **Live site** | https://13krishan.github.io/fresher-jobs-india/ |
| **Data, accuracy check, cost, prompts** | [Google Sheet](https://docs.google.com/spreadsheets/d/1oHeBKIPCxXZcuK4IH8HBIiEkwRGpj_asiD3MEtfg3Nk/edit) |
| **Refresh** | Every day at 06:00 IST via GitHub Actions |

## Results

| Metric | Value |
|---|---|
| Live posts | ~380 (India, fresher/intern only, deduplicated) |
| Role tag accuracy (50 random posts, hand-checked) | **88%** |
| City tag accuracy | **98%** |
| Job type (Internship / Full-time) accuracy | **92%** |
| All three tags right on the same post | **78%** |
| LLM cost per 1,000 posts | **$0.19** standard, **$0.09** with Gemini Batch API |
| Actually paid | $0 (Gemini free tier) |

Accuracy and cost are calculated with formulas in the sheet, from the hand-check rows and the token log in [`data/usage_log.jsonl`](data/usage_log.jsonl).

## How it works

```
GitHub Actions (daily 06:00 IST)
  └─ python -m scraper.main
       1. Fetch     Adzuna India API (one-time seed) + public job boards:
                    Greenhouse, Lever, Ashby, SmartRecruiters, Workday
       2. Filter    India only; fresher by title words (intern, trainee, SDE I...) or
                    text ("0-1 years", "freshers"); never senior titles; drop test/junk posts
       3. Store     merge with the last 30 days; sources that ran today are authoritative,
                    so closed jobs drop off the same day
       4. Dedupe    same title+company+city, same URL, or same company+city+description
                    (reposts with a new title); company boards win over aggregators
       5. Tag       Gemini 3.5 Flash-Lite, 25 posts per call, temperature 0, JSON schema
                    with enum lists so labels can't be invented; tags cached by job id
       6. Publish   docs/data/jobs.json + jobs.csv + meta.json → commit → GitHub Pages
```

| Path | What it holds |
|---|---|
| `scraper/sources/` | One module per source; official or public APIs only |
| `scraper/filters.py` | India, fresher, senior and junk rules |
| `scraper/dedupe.py` | Duplicate removal |
| `scraper/store.py` | 30-day post store |
| `scraper/tagger.py` | Gemini prompt, schema, batching, fallbacks, cache, token usage |
| `scraper/main.py` | Pipeline and safety checks |
| `docs/` | Static search page (plain HTML/JS) and published data |
| `tests/` | 41 pytest tests |

## Respecting site terms

- Only official APIs or the public job-board endpoints that ATS vendors publish for showing jobs on other sites.
- No login-walled sites (LinkedIn, Naukri, Indeed). Nothing that robots.txt disallows: Internshala blocks its search and job-detail pages, so it is not used.
- Adzuna results carry a visible "Adzuna" link on every card, as their terms require.
- Workday answers GitHub's servers with HTTP 429, so the cloud run switches Workday off instead of retrying or rotating IPs.
- Every card links to the original post.

## What broke and how it was fixed

| Problem | Fix |
|---|---|
| Adzuna's free tier is 25 API calls in total, not per day | Used 14 calls once as a seed; daily refresh runs on free company job boards; posts stay 30 days |
| `gemini-2.5-flash-lite` was retired for new users (404) | Moved to `gemini-3.5-flash-lite` |
| The new model often returned 503 (busy) | Retries plus two fallback models; a batch with under half its tags also tries the next model |
| Workday returned 429 to every request from GitHub Actions | Respect it: `WORKDAY_ENABLED=false` in the workflow |
| Fresher rule matched "SDE II/III" as well as "SDE I" | Whole-word regex, with tests |
| Same ad reposted under a new title; "Test"/"demooo" posts; Bosch tagging senior roles as entry level | Description-based dedupe, junk filter, senior check that also catches `IN_RBAI_Senior...`, board "entry level" flags trusted only for internships |
| Old copies of posts stayed for 30 days after they stopped passing the filters | Sources that ran today are authoritative in the store |
| Silent failure: if Gemini failed, the run could still pass and publish a much smaller list | Run stops if the list shrinks by more than 30%; corrupt data files raise instead of being treated as empty; atomic writes; bad API key fails fast |

## Where the LLM goes wrong (from the hand-check)

- Apprenticeships and CA industrial training tagged Full-time (4 of 50), although the prompt says apprentice = Internship.
- When a post never says what the person will do, the model guesses a role instead of choosing Other (2).
- Close categories and mismatched title/description pairs mixed up (4).
- A state with no city tagged Other City instead of Unknown (1).

Next: set job type with a rule before the LLM, add a confidence field so unclear posts go to Other, and add one-line definitions for the close categories.

## AI tools used

- **Claude Code** (Claude Opus 5.5): wrote the pipeline, tests, page and workflow; did a first pass of the 50-post check, which was then reviewed and corrected by hand.
- **silent-failure-hunter** agent (ECC agent library): reviewed the pipeline for swallowed errors; its findings became the safety checks above.
- **Gemini 3.5 Flash-Lite** (Gemini API): tags every post. The full prompt is in [`scraper/tagger.py`](scraper/tagger.py) and on the sheet's "AI tools & prompts" tab.

## Run locally

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env   # add GEMINI_API_KEY (and ADZUNA_APP_ID / ADZUNA_APP_KEY for a seed)
.venv/bin/pytest -q
ADZUNA_MAX_CALLS=0 .venv/bin/python -m scraper.main
python3 -m http.server -d docs 8000
```
