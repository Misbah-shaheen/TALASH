
# TALASH — Talent Acquisition & Learning Automation for Smart Hiring

> **AI-powered academic recruitment pipeline** for NUST (National University of Sciences and Technology). Extracts, verifies, analyzes, and ranks candidate CVs with zero manual effort.

---

## What It Does

TALASH reads PDF CVs, extracts structured candidate data using Google Gemini, runs 9 analytical modules, verifies publications against live academic databases, detects career gaps, and exports everything to a formatted Excel report — automatically.

---

## Features

### 9 Analysis Modules
| Module | Description |
|--------|-------------|
| **3.1 Educational Profile** | Degree levels, institutions, GPA, gap detection |
| **3.2 Research Profile** | Journals, conferences, HEC W1–W4 ranking, impact factors |
| **3.3 Student Supervision** | MS/PhD supervision counts, student publications |
| **3.4 Books Authored** | Book records with publisher and year |
| **3.5 Patents** | Patent numbers, inventors, verification links, authorship role |
| **3.6 Topic Variability** | LLM-based clustering of research topics |
| **3.7 Co-author Analysis** | Recurring collaborators, team size, diversity score |
| **3.8 Professional Experience** | Overlap/gap detection, career progression, auto email draft |
| **3.9 Skill Alignment** | LLM-based evidence verification against job requirements |

### Publication Verification (5 Live Checks)
- **Crossref** — DOI existence and paper verification
- **Semantic Scholar** — title-based lookup fallback
- **OpenAlex** — live impact factor retrieval
- **Beall's List** — predatory journal detection (embedded, no API needed)
- **HEC Journal List** — W1/W2/W3/W4 category classification (embedded)
- **Google Patents / SerpAPI** — patent existence verification

### Smart Automation
- **Dual Gemini API key** with automatic quota rotation and fallback
- **Checkpoint/resume** — stops and continues without reprocessing completed CVs
- **Missing-info email drafts** — auto-generates personalised candidate emails when critical fields are absent
- **Structured Excel output** — multi-sheet workbook with formatted tables, freeze panes, alternating row colours

---

## Project Structure

```
talash/
├── pipeline.py              # Main entry point — orchestrates full pipeline
├── config.py                # API keys, model settings, SMTP, paths, table schemas
├── core/
│   ├── pdf_parser.py        # PDF text extraction (pdfplumber, table-aware)
│   ├── llm_extractor.py     # Gemini extraction + SMTP email sender
│   ├── analysis_engine.py   # All 9 analysis modules
│   ├── excel_writer.py      # Formatted multi-sheet Excel export
│   ├── verifiers.py         # Live publication/patent verification APIs
│   └── ranking_verifier.py  # Journal ranking lookup
├── utils/
│   └── normalizer.py        # Date, salary, degree normalization + missing field detection
└── cvs/                     # Drop input PDF CVs here
```

---

## Installation

```bash
# Clone the repository
git clone https://github.com/your-org/talash.git
cd talash

# Install dependencies
pip install -r requirements.txt
```

**Requirements:**
```
google-generativeai
pdfplumber
openpyxl
requests
python-dateutil
```

---

## Configuration

Edit `config.py` before running:

```python
# Gemini API keys (dual-key with auto-rotation on quota hit)
GEMINI_API_KEY_1 = "your-key-1"
GEMINI_API_KEY_2 = "your-key-2"

# Model
MODEL = "gemini-3.1-flash-lite-preview"

# SMTP (optional — for sending missing-info emails)
SMTP_HOST     = "smtp.gmail.com"
SMTP_PORT     = 587
SMTP_USER     = "your@email.com"
SMTP_PASSWORD = "your-app-password"
SMTP_ENABLED  = True   # set False to only save drafts locally

# Directories
INPUT_DIR  = "cvs/"      # folder with PDF CVs
OUTPUT_DIR = "output/"   # Excel + email drafts saved here
```

---

## Usage

### Basic — process all CVs and export Excel

```bash
python pipeline.py --input cvs/ --output output/
```

### With missing-info email generation

```bash
python pipeline.py --input cvs/ --output output/ --emails
```

### Resume an interrupted run (skips already-processed CVs)

```bash
python pipeline.py --input cvs/ --output output/ --resume
```

### All options

```bash
python pipeline.py \
  --input  cvs/          \   # folder containing PDF CVs
  --output output/       \   # destination for Excel + email files
  --emails               \   # generate missing-info email drafts
  --resume               \   # resume from checkpoint
  --delay  2             \   # seconds between Gemini API calls (default: 2)
```

---

## Output

### Excel Workbook (`output/talash_results.xlsx`)
Each section is exported as a separate sheet:

| Sheet | Contents |
|-------|----------|
| `Candidates` | Personal info, scores, flags for all candidates |
| `Education` | Degree records with gap flags and duration |
| `Experience` | Employment history with overlap/gap detection |
| `Publications` | Papers with venue, HEC rank, impact factor, predatory flag |
| `Supervision` | Student supervision records |
| `Patents` | Patent records with verification status |
| `Skills` | Skill alignment scores with evidence level |

### Email Drafts (`output/missing_email_<candidate_id>.txt`)
Automatically generated when a candidate CV is missing critical fields such as:
- Date of birth, CNIC, phone, email
- Education records or degree sub-fields
- Employment start dates or organisation names
- Claimed publications with incomplete entries

---

## How the Pipeline Works

```
PDF CVs (input/)
     │
     ▼
PDF Parser          ← pdfplumber, table-aware extraction
     │
     ▼
LLM Extractor       ← Gemini API, dual-key fallback, structured JSON output
     │
     ▼
Normalizer          ← dates, salaries, degrees, missing field detection
     │
     ▼
Analysis Engine     ← 9 modules: education, research, experience, skills...
     │
     ├──▶ Verifiers     ← Crossref, OpenAlex, Semantic Scholar, HEC, Beall's
     │
     ├──▶ Email Drafts  ← LLM-written personalised missing-info emails
     │
     ▼
Excel Writer        ← Multi-sheet formatted workbook
     │
     ▼
output/talash_results.xlsx
```

---

## Missing Info Email System

When a CV is incomplete, TALASH auto-drafts a professional email to the candidate:

1. `detect_missing_fields()` scans extracted data for empty critical fields
2. If any are found and `--emails` flag is set, `build_missing_info_email()` calls Gemini to write a personalised, polite clarification email
3. The draft is saved to `output/missing_email_<candidate_id>.txt`
4. If SMTP is enabled in `config.py`, it is sent automatically

Fields checked: full name, date of birth, current salary, email, phone, CNIC, post applied for, education records, experience records, and claimed publications.

---

## API Credits

All verification APIs used are **free and require no authentication key** except Gemini:

| API | Purpose |
|-----|---------|
| [Crossref](https://www.crossref.org/documentation/retrieve-metadata/rest-api/) | DOI and paper verification |
| [Semantic Scholar](https://www.semanticscholar.org/product/api) | Title-based paper lookup |
| [OpenAlex](https://openalex.org/) | Impact factors, journal metadata |
| [Google Gemini](https://ai.google.dev/) | CV extraction, email drafting, analysis |

Beall's predatory journal list and HEC W1–W4 journal categories are embedded directly — no internet required for those checks.

---

## Notes

- Scanned/image PDFs with no extractable text are flagged and skipped automatically
- All API calls include polite delays and retry logic to respect rate limits
- The checkpoint file (`.checkpoint.json`) is saved after each CV so a crash loses at most one candidate
- SMTP credentials are only needed if you want emails sent automatically; otherwise drafts are saved as `.txt` files

---

## Contributors

- **Misbah Shaheen** 
- **Hareem Fatima**
  GitHub: [HareemFatima5](https://github.com/HareemFatima5)

---

## License

Internal use — NUST TALASH Recruitment System.
