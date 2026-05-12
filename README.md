
# TALASH — Talent Acquisition & Learning Automation for Smart Hiring


> **AI-powered academic recruitment pipeline for NUST.** Upload candidate CVs, let TALASH extract, verify, analyze, score, and rank them — then browse results through a live web dashboard.

---

## Overview

TALASH has two modes that work together:

- **Pipeline (`pipeline.py`)** — batch processes PDF CVs via CLI, extracts structured data using Google Gemini, runs 9 analysis modules, verifies publications against live academic APIs, and exports a formatted Excel report.
- **Web App (`app.py`)** — Flask dashboard that lets you upload CVs, trigger processing, browse ranked candidates, view detailed profiles, generate missing-info emails, and export results — all from a browser.

---

## Features

### 9 Analysis Modules (`core/analysis_engine.py`)

| Module | Description |
|--------|-------------|
| **3.1 Educational Profile** | Degree levels, institutions, GPA, education gap detection |
| **3.2 Research Profile** | Journals, conferences, HEC W1–W4 ranking, impact factors |
| **3.3 Student Supervision** | MS/PhD supervision counts, publications with students |
| **3.4 Books Authored** | Book records with publisher and year |
| **3.5 Patents** | Patent numbers, inventors, verification links, authorship role |
| **3.6 Topic Variability** | LLM-based clustering of research topics, diversity score |
| **3.7 Co-author Analysis** | Recurring collaborators, team size, collaboration diversity |
| **3.8 Professional Experience** | Overlap/gap detection, career progression, auto email draft |
| **3.9 Skill Alignment** | LLM-based evidence verification against job requirements |

### Publication Verification (`core/verifiers.py`)

- **Crossref** — DOI existence and paper verification
- **Semantic Scholar** — title-based lookup fallback
- **OpenAlex** — live impact factor retrieval
- **Beall's List** — predatory journal detection (embedded, no API key needed)
- **HEC Journal List** — W1/W2/W3/W4 category classification (embedded)
- **Google Patents** — patent existence verification

### Web Dashboard (`app.py`)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Main dashboard UI |
| `/api/dashboard` | GET | Stats: total candidates, avg score, distribution, top performers |
| `/api/candidates` | GET | Full candidate list with scores; supports `?q=` search |
| `/api/candidate/<id>` | GET | Full candidate profile with all evaluation data |
| `/api/candidate/<id>` | DELETE | Remove candidate from DB and JSON cache |
| `/api/rankings` | GET | Candidates sorted by overall score with rank numbers |
| `/api/upload` | POST | Upload one or more PDF CVs (50 MB limit) |
| `/api/uploads` | GET | List all uploaded PDF files |
| `/api/uploads/<filename>` | DELETE | Delete an uploaded PDF |
| `/api/process` | POST | Kick off pipeline in background thread; supports `resume` flag |
| `/api/process/status` | GET | Live pipeline status: running, message, progress % |
| `/api/export` | GET | Download full Excel report (`TALASH_Candidates.xlsx`) |
| `/api/export/csv` | GET | Download summary CSV of all candidates |
| `/api/candidate/<id>/missing_email` | GET | Generate/return LLM-written missing-info email |
| `/api/candidate/<id>/send_missing_email` | POST | Send missing-info email via SMTP |
| `/api/candidate/<id>/gap_email` | GET | Get employment gap clarification email |
| `/api/candidate/<id>/send_gap_email` | POST | Send gap email via SMTP |
| `/api/candidate/<id>/summary` | GET | LLM narrative summary; `?refresh=true` to regenerate |
| `/api/candidate/<id>/skills` | GET | Detailed skill analysis breakdown |
| `/api/bulk_missing_emails` | POST | Generate missing-info emails for ALL incomplete candidates |
| `/api/verify/journal` | POST | Live journal verification (Crossref + OpenAlex) |
| `/api/verify/university` | POST | Live university ranking lookup |
| `/api/verify/paper` | POST | Verify paper existence via Crossref + Semantic Scholar |
| `/api/db/migrate` | POST | Manually migrate JSON cache to SQLite |
| `/api/db/reanalyze` | POST | Re-run analysis engine on all cached candidates |

### Candidate Scoring & Recommendation

| Score | Recommendation |
|-------|---------------|
| >= 60 | **Hire** |
| >= 45 | **Shortlist** |
| >= 30 | **Review** |
| < 30  | **Reject** |

---

## Project Structure

```
Talash/
├── app.py                   # Flask web application — dashboard + REST API
├── pipeline.py              # CLI batch processor — runs full pipeline
├── config.py                # API keys, model, SMTP, paths, table schemas
├── database.py              # SQLite helpers — init, CRUD, bulk migration
├── rescore_fast.py          # Re-score all candidates locally (no LLM, instant)
├── split_pdf.py             # Split a multi-candidate PDF into individual files
├── free_apis.py             # Standalone free-API verification helpers
├── requirements.txt
├── .env.example             # Environment variable template
│
├── core/
│   ├── analysis_engine.py   # All 9 analysis modules
│   ├── llm_extractor.py     # Gemini extraction, email drafting, SMTP sender
│   ├── pdf_parser.py        # PDF text extraction (pdfplumber, table-aware)
│   ├── excel_writer.py      # Formatted multi-sheet Excel export
│   ├── verifiers.py         # Live publication/patent verification APIs
│   └── ranking_verifier.py  # Journal ranking lookup (HEC, Beall's, OpenAlex)
│
├── data/
│   ├── journal_database.py      # Embedded HEC W1-W4 journal list
│   ├── conference_rankings.py   # Embedded conference ranking data
│   └── university_rankings.py   # Embedded university ranking data
│
├── utils/
│   └── normalizer.py        # Date/salary/degree normalization, missing field detection
│
├── templates/
│   └── index.html           # Dashboard frontend (served by Flask)
├── static/
│   └── style.css            # Dashboard styles
│
├── cvs/
│   └── split/               # Individual candidate PDFs go here
└── output/
    ├── TALASH_Candidates.xlsx         # Full Excel export
    ├── raw_json/                      # Extracted candidate JSON (one file per CV)
    ├── .checkpoint.json               # Pipeline resume checkpoint
    ├── missing_email_<id>.txt         # Missing-info email drafts
    ├── gap_email_<id>.txt             # Employment gap email drafts
    └── summary_<id>.txt              # LLM narrative summaries
```

---

## Installation

```bash
git clone https://github.com/your-org/talash.git
cd talash
pip install -r requirements.txt
```

---

## Configuration

Copy `.env.example` to `.env` and fill in your values:

```env
# Gemini API keys — dual key with automatic quota rotation
GEMINI_API_KEY_1=your-key-1
GEMINI_API_KEY_2=your-key-2

# SMTP — for sending emails automatically
# Gmail: enable 2FA then create an App Password at myaccount.google.com/apppasswords
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_gmail@gmail.com
SMTP_PASSWORD=your_16_char_app_password
SMTP_FROM=your_gmail@gmail.com
```

> **Security:** Never commit `.env` or `config.py` with real API keys to Git. Both are listed in `.gitignore`.

---

## Usage

### Option 1 — Web Dashboard

```bash
python app.py
```

Open `http://localhost:5000` in your browser. From there you can:

1. Upload PDFs via the dashboard
2. Click **Process** to run the pipeline in the background
3. Watch live status updates
4. Browse, search, and sort ranked candidates
5. View full profiles, skill breakdowns, and LLM summaries
6. Generate and send missing-info or gap emails per candidate, or in bulk
7. Export results to Excel or CSV

### Option 2 — Command Line (Batch)

```bash
# Basic run
python pipeline.py --input cvs/split/ --output output/

# With missing-info email generation
python pipeline.py --input cvs/split/ --output output/ --emails

# Resume an interrupted run (skips already-processed CVs)
python pipeline.py --input cvs/split/ --output output/ --resume

# All options
python pipeline.py \
  --input  cvs/split/  \    # folder containing individual PDF CVs
  --output output/     \    # destination for Excel + email drafts
  --emails             \    # generate missing-info email drafts
  --resume             \    # skip already-processed candidates
  --delay  2                # seconds between Gemini API calls (default: 2)
```

### Splitting a Multi-Candidate PDF

If you receive one large PDF with all CVs combined, edit `input_pdf` inside `split_pdf.py` then run:

```bash
python split_pdf.py
```

It detects candidate boundaries by the phrase `"Candidate for the Post of"` and writes individual files to `cvs/split/`.

### Re-scoring Without LLM (Fast)

To re-run only the scoring logic on already-extracted candidates with no Gemini calls (runs in seconds):

```bash
python rescore_fast.py
```

Useful after adjusting scoring weights in `config.py` without reprocessing any PDFs.

---

## Output

### Excel Report (`output/TALASH_Candidates.xlsx`)

Multi-sheet workbook with formatted tables, freeze panes, and alternating row colours:

| Sheet | Contents |
|-------|----------|
| `Candidates` | Personal info, overall scores, flags for all candidates |
| `Education` | Degree records with gap flags and duration |
| `Experience` | Employment history with overlap/gap detection |
| `Publications` | Papers with venue, HEC rank, impact factor, predatory flag |
| `Supervision` | Student supervision records |
| `Patents` | Patent records with verification status |
| `Skills` | Skill alignment scores with evidence level |

### Email Drafts

| File | When generated |
|------|---------------|
| `missing_email_<id>.txt` | Candidate CV is missing critical fields (name, DOB, education, etc.) |
| `gap_email_<id>.txt` | Unexplained employment gaps or overlapping job dates detected |
| `summary_<id>.txt` | LLM narrative summary (on-demand via `/api/candidate/<id>/summary`) |

All drafts can be sent via SMTP directly from the dashboard or the API.

---

## How It Works

```
PDF CVs (cvs/split/)
        │
        ▼
  split_pdf.py          ← splits combined PDF into individual files (one-time)
        │
        ▼
  pdf_parser.py         ← pdfplumber, table-aware text extraction
        │
        ▼
  llm_extractor.py      ← Gemini API, dual-key fallback, structured JSON output
        │
        ▼
  normalizer.py         ← dates, salaries, degrees, missing field detection
        │
        ▼
  analysis_engine.py    ← 9 modules: education, research, experience, skills...
        │
        ├──▶ verifiers.py       ← Crossref, OpenAlex, Semantic Scholar, HEC, Beall's
        ├──▶ email drafts       ← LLM-written missing-info and gap emails
        │
        ▼
  excel_writer.py       ← formatted multi-sheet Excel workbook
        │
        ▼
  database.py           ← SQLite storage (powers the web dashboard)
        │
        ▼
  app.py                ← Flask REST API + browser dashboard
```

---

## Database

TALASH uses **SQLite** (`talash.db`) as a lightweight backend for the web dashboard. On first startup, `app.py` automatically migrates any existing JSON files from `output/raw_json/` into the database — no setup required.

To manually trigger migration:

```bash
curl -X POST http://localhost:5000/api/db/migrate
```

---

## Dependencies

| Package | Purpose |
|---------|---------|
| `Flask`, `Flask-CORS` | Web dashboard and REST API |
| `google-generativeai` | Gemini LLM for extraction, summaries, email drafting |
| `pdfplumber` | PDF text and table extraction |
| `pypdf` | PDF splitting (`split_pdf.py`) |
| `openpyxl` | Excel report generation |
| `requests` | Live API verification calls |
| `python-dateutil` | Date normalization |
| `python-dotenv` | Environment variable loading from `.env` |
| `tqdm` | CLI progress bars |

All publication verification APIs (Crossref, OpenAlex, Semantic Scholar) are **free and require no authentication key**.

---


## Contributors

- **Misbah Shaheen** 
- **Hareem Fatima**
  GitHub: [HareemFatima5](https://github.com/HareemFatima5)

---

## License

Internal use — NUST TALASH Recruitment System.
