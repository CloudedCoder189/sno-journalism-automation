# SNO Journalism Automation Dashboard

A local Flask dashboard that automates repetitive publishing work for a student journalism website running on **SNO / WordPress**.

The project combines two workflows: an **Article Publisher** for scheduled story drafts and a **Staff Bio Publisher** for extracting staff biographies from PDF and creating SNO staff-profile drafts. Browser automation is handled with Playwright using an authorized, locally saved SNO login session.

## Features

### Article Publisher

- schedule-based publishing dashboard
- today's article, upcoming schedule and full schedule views
- search by student/author
- article loading from `.txt` and `.docx`
- preview before upload
- Playwright automation that fills:
  - story title
  - secondary headline / deck
  - writer name
  - writer job title
  - story body
  - category
- saves the story as a **draft**
- dry-run mode and duplicate-upload protection
- profile images / story images remain manual

### Staff Bio Publisher

- upload a numbered staff-bio PDF
- extract names and biography text with PyMuPDF
- remove editing/finalization markers from the source document
- infer the full name from the opening sentence
- match staff positions from a CSV file, with `Reporter` as the default
- preview, search and export cleaned profiles
- Playwright automation that:
  - uses the real full name
  - bolds the first occurrence of the full name in the bio
  - fills Staff Position
  - leaves Staff Group blank
  - leaves Staff Bio Teaser for Story Page blank
  - selects the configured Staff Year (default `2026-2027`)
  - saves a staff profile draft
- batch actions for selected profiles, all not-created profiles, or all profiles again
- individual profiles can intentionally be created again when a replacement draft is needed
- profile images remain manual

## Why Playwright?

Direct REST/XML-RPC attempts were unreliable for the target SNO installation, so this project automates the same authenticated WordPress/SNO interface used by the site's web manager.

The repository never stores login credentials. The operator signs in manually once, and Playwright stores that browser session **locally** in `playwright_sno_profile/`. That directory is ignored by Git and must never be shared.

## Project Structure

```text
sno-journalism-automation/
├── app.py
├── article_loader.py
├── article_schedule.py
├── article_uploader.py
├── browser_sno_article_client.py
├── browser_sno_staff_client.py
├── prepare_sno_login.py
├── staff_bio_extractor.py
├── staff_data.py
├── staff_uploader.py
├── articles/                 # public demo articles
├── sample_data/              # fake demo schedules/profiles only
├── data/                     # local generated state (ignored)
├── uploads/                  # uploaded staff PDFs (ignored)
├── exports/                  # generated CSV exports (ignored)
├── debug/                    # browser screenshots (ignored)
├── static/
├── templates/
├── .env.example
├── .gitignore
└── requirements.txt
```

## Setup

Create a virtual environment and install the dependencies:

```bash
python -m venv .venv
```

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
playwright install chromium
Copy-Item .env.example .env
```

macOS/Linux:

```bash
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
cp .env.example .env
```

Edit `.env` and set `SNO_SITE` to the SNO website you are authorized to manage. Keep both dry-run flags enabled during initial testing.

## Save an Authorized SNO Login Session

```bash
python prepare_sno_login.py
```

A Chromium window opens. Sign in normally, wait until the SNO dashboard loads, then return to the terminal and press Enter.

The login session is saved locally in `playwright_sno_profile/`. **Never commit, zip, or share this folder.**

## Run

```bash
python app.py
```

Then open `http://127.0.0.1:5000`.

## Demo vs. Real Data

The repository contains only fake sample records under `sample_data/`. The app reads those files on a fresh clone so the dashboard is immediately viewable.

When you upload a real staff-bio PDF or mark articles/profiles as created, runtime copies/state are written under `data/`, which is ignored by Git. This prevents real student biographies, preview URLs and publishing state from accidentally being committed.

## Dry-Run Modes

```env
DRY_RUN_ARTICLES=true
DRY_RUN_STAFF=true
```

Set a flag to `false` only after the matching workflow has been tested and the browser session is logged into an account authorized to manage the site.

## Security / Privacy

Do not commit or share:

- `.env`
- `playwright_sno_profile/`
- uploaded staff PDFs
- real student biography CSV files
- preview/draft URLs
- debug screenshots containing SNO pages

The included `.gitignore` excludes all of these runtime artifacts.

## Notes

SNO and WordPress interfaces can change. The browser clients intentionally use multiple fallback selectors, but a future SNO/plugin redesign may require selector updates.

This project should only be used on websites and accounts the operator is authorized to administer.
