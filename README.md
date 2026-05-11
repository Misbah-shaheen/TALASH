# TALASH — Pre-Processing Module

**Talent Acquisition & Learning Automation for Smart Hiring**  
CS417 – LLMs, Spring 2026 · BSDS-2K23

---

## What This Module Does

Takes a folder of raw PDF CVs (specifically NUST HR portal form exports) and outputs:
- A **multi-sheet Excel workbook** — one sheet per relational table
- **JSON cache files** per candidate (for debugging and module 2 reuse)
- Optional **missing-info email drafts** per candidate

---

## Project Structure

```
talash/
├── pipeline.py          ← Main entry point — run this
├── config.py            ← Table schemas, prompts, API config
├── requirements.txt
├── .env.example         ← Copy to .env, add your API key
│
├── core/
│   ├── pdf_parser.py    ← pdfplumber-based text extraction
│   ├── llm_extractor.py ← Claude API calls, JSON parsing
│   └── excel_writer.py  ← Multi-sheet openpyxl workbook
│
└── utils/
    └── normalizer.py    ← Dates, salaries, IDs, degree levels
```

---

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
# Edit .env → add your ANTHROPIC_API_KEY
```

---

## Running

```bash
# Basic run
python pipeline.py --input ./cvs --output ./output

# With missing-info emails
python pipeline.py --input ./cvs --output ./output --emails

# Resume interrupted run (skips already-processed PDFs)
python pipeline.py --input ./cvs --output ./output --resume

# Slower rate (if hitting API limits)
python pipeline.py --input ./cvs --output ./output --delay 3.0
```

---

## Output

```
output/
├── TALASH_Candidates.xlsx     ← Main deliverable
│   ├── 📖 Data Dictionary
│   ├── 📋 Personal Info       (1 row per candidate)
│   ├── 🎓 Education           (N rows per candidate)
│   ├── 💼 Experience
│   ├── 📄 Publications
│   ├── 🛠 Skills
│   ├── 🔬 Patents
│   ├── 📚 Books
│   ├── 🏆 Awards
│   └── 👥 References
│
├── raw_json/
│   ├── candidate_001.json     ← Full JSON per candidate (for analysis modules)
│   └── ...
│
├── email_cand_002.txt         ← Missing-info emails (if --emails flag used)
└── .checkpoint.json           ← Resume checkpoint
```

---

## Relational Schema

All tables are linked via `candidate_id` (FK → `personal_info.candidate_id`).

| Table | PK | Key Fields |
|---|---|---|
| personal_info | candidate_id | name, salary, employment, apply_date |
| education | record_id | degree_level, institution, GPA, year |
| experience | record_id | job_title, org, start/end, duration_months |
| publications | record_id | pub_type, venue, impact_factor_claimed, authorship_role |
| skills | record_id | skill_name, category, evidence_level* |
| patents | record_id | patent_number, country, is_lead_inventor |
| books | record_id | publisher, isbn, authorship_role |
| awards | record_id | award_type, issuing_body |
| references | record_id | ref_name, designation, contact |

*`evidence_level` filled by M2 Skill Alignment module.

---

## Design Decisions

### Why LLM extraction instead of regex?

The NUST HR form uses a two-column layout that breaks standard PDF text extraction order. LLMs handle this gracefully — they understand semantic context regardless of spatial layout.

### Why cached JSON?

Each LLM call costs money. The `raw_json/` cache means analysis modules (M2/M3) can reload data without re-calling the API.

### Why `impact_factor_claimed` not `impact_factor_verified`?

Per the project spec, Research Profile Analysis (Module 2) must verify impact factors from external sources (WoS/Scopus), not trust CV self-reporting. This module only extracts what the candidate claimed.

### Salary normalization

Some candidates enter salary in thousands (e.g., "200" meaning PKR 200,000). The normalizer detects values < 5,000 and multiplies by 1,000.

---

## Notes for Analysis Modules (M2/M3)

Load the JSON cache to avoid re-parsing PDFs:

```python
import json
from pathlib import Path

candidates = []
for f in Path("output/raw_json").glob("*.json"):
    candidates.append(json.loads(f.read_text()))

# Access structured data
for c in candidates:
    name = c["personal_info"]["full_name"]
    pubs = c["publications"]
    for pub in pubs:
        print(pub["title"], pub["impact_factor_claimed"])
```
