"""
TALASH Configuration
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ── Gemini API - Dual Key with Automatic Fallback ─────────────────────────────
# Primary key used first; on quota/error automatically rotates to secondary key
GEMINI_API_KEY   = os.getenv("GEMINI_API_KEY_1", "")
GEMINI_API_KEY_2 = os.getenv("GEMINI_API_KEY_2", "")
GEMINI_API_KEYS  = [GEMINI_API_KEY, GEMINI_API_KEY_2]   # rotation list
MODEL_NAME       = "gemini-3.1-flash-lite-preview"
MODEL            = MODEL_NAME   # alias so both names resolve
MAX_TOKENS       = 16000

# ── SMTP Email Settings (set in .env or environment) ──────────────────────────
SMTP_HOST     = os.getenv("SMTP_HOST",     "smtp.gmail.com")
SMTP_PORT     = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER     = os.getenv("SMTP_USER",     "")          # e.g. yourapp@gmail.com
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")          # Gmail App Password
SMTP_FROM     = os.getenv("SMTP_FROM",     SMTP_USER)
SMTP_ENABLED  = bool(SMTP_USER and SMTP_PASSWORD)

# ── File paths ────────────────────────────────────────────────────────────────
BASE_DIR        = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER   = os.path.join(BASE_DIR, "cvs")
OUTPUT_FOLDER   = os.path.join(BASE_DIR, "output")
TEMPLATE_FOLDER = os.path.join(BASE_DIR, "templates")
STATIC_FOLDER   = os.path.join(BASE_DIR, "static")

os.makedirs(UPLOAD_FOLDER,   exist_ok=True)
os.makedirs(OUTPUT_FOLDER,   exist_ok=True)
os.makedirs(TEMPLATE_FOLDER, exist_ok=True)
os.makedirs(STATIC_FOLDER,   exist_ok=True)

# ── Table schemas ─────────────────────────────────────────────────────────────
TABLE_SCHEMAS = {
    "personal_info": [
        "candidate_id", "full_name", "father_guardian_name", "date_of_birth",
        "nationality", "gender", "marital_status", "current_salary_pkr",
        "expected_salary_pkr", "present_employment", "current_employer",
        "apply_date", "post_applied_for", "department", "institution_applied_to",
    ],
    "education": [
        "record_id", "candidate_id", "degree_level", "degree_name",
        "specialization", "institution", "grade_gpa_percentage", "grade_type",
        "passing_year", "board_university", "country", "is_postdoc",
        "education_gap_flag", "qs_rank", "the_rank", "institution_quality",
    ],
    "experience": [
        "record_id", "candidate_id", "job_title", "organization", "location",
        "country", "employment_type", "start_date", "end_date", "is_current",
        "duration_months", "overlap_flag", "gap_before_months",
    ],
    "publications": [
        "record_id", "candidate_id", "pub_type", "title", "first_author",
        "candidate_is_first", "co_authors", "co_author_count", "venue_name",
        "year", "impact_factor_claimed", "wos_indexed", "scopus_indexed",
        "quartile", "is_predatory", "authorship_role", "core_rank", "is_a_star",
        "conference_maturity", "proceedings_publisher", "quality_assessment",
    ],
    "skills": [
        "record_id", "candidate_id", "skill_name", "skill_category",
        "skill_source", "evidence_level",
    ],
    "patents": [
        "record_id", "candidate_id", "patent_title", "patent_number",
        "filing_date", "grant_date", "country", "inventors",
        "is_lead_inventor", "verification_link", "status",
    ],
    "books": [
        "record_id", "candidate_id", "title", "publisher", "year",
        "isbn", "authors", "authorship_role", "online_link",
    ],
    "awards": [
        "record_id", "candidate_id", "award_type", "detail", "year",
        "issuing_body", "is_hec_scholarship", "is_international",
    ],
    "supervision": [
        "record_id", "candidate_id", "student_name", "degree_supervised",
        "supervision_role", "year_graduated", "joint_publication",
    ],
    "references": [
        "record_id", "candidate_id", "ref_name", "designation", "organization",
        "address", "country", "phone", "email", "relationship",
    ],
}

EXTRACTION_SYSTEM_PROMPT = """You are an expert HR data extraction assistant for the TALASH recruitment system.
Extract structured information from candidate CVs and return ONLY valid JSON.
Do not add any explanation, markdown, or text outside the JSON object.
Extract every field you can find. Use null for fields not present in the CV."""

EXTRACTION_USER_TEMPLATE = """Extract all candidate data from CV file: {filename}

Return ONLY a valid JSON object with this exact structure (no extra text):
{{
    "personal_info": {{
        "full_name": "string",
        "father_guardian_name": "string or null",
        "date_of_birth": "YYYY-MM-DD or null",
        "nationality": "string or null",
        "gender": "Male/Female or null",
        "marital_status": "string or null",
        "current_salary_pkr": null,
        "expected_salary_pkr": null,
        "present_employment": "string or null",
        "current_employer": "string or null",
        "apply_date": "YYYY-MM-DD or null",
        "post_applied_for": "string or null",
        "department": "string or null"
    }},
    "education": [
        {{
            "degree_level": "SSC/HSSC/Bachelor/Master/PhD/Other",
            "degree_name": "string",
            "specialization": "string or null",
            "institution": "string",
            "grade_gpa_percentage": "string or null",
            "passing_year": null,
            "board_university": "string or null",
            "country": "string or null"
        }}
    ],
    "experience": [
        {{
            "job_title": "string",
            "organization": "string",
            "location": "string or null",
            "country": "string or null",
            "employment_type": "Academic/Industry/Research/Other",
            "start_date": "YYYY-MM or null",
            "end_date": "YYYY-MM or Present or null",
            "is_current": false
        }}
    ],
    "publications": [
        {{
            "title": "string",
            "pub_type": "Journal/Conference/Workshop/Other",
            "first_author": "string or null",
            "co_authors": "string or null",
            "venue_name": "string or null",
            "year": null,
            "impact_factor_claimed": null
        }}
    ],
    "skills": [{{"skill_name": "string", "skill_category": "string or null"}}],
    "patents": [
        {{
            "patent_title": "string",
            "patent_number": "string or null",
            "filing_date": "string or null",
            "grant_date": "string or null",
            "country": "string or null",
            "inventors": "string or null",
            "is_lead_inventor": false,
            "status": "Granted/Pending/Other"
        }}
    ],
    "books": [
        {{
            "title": "string",
            "publisher": "string or null",
            "year": null,
            "isbn": "string or null",
            "authors": "string or null",
            "authorship_role": "Sole/Lead/Co-author",
            "online_link": "string or null"
        }}
    ],
    "awards": [
        {{
            "award_type": "string",
            "detail": "string or null",
            "year": null,
            "issuing_body": "string or null",
            "is_hec_scholarship": false,
            "is_international": false
        }}
    ],
    "supervision": {{
        "ms_main_supervisor": 0,
        "ms_co_supervisor": 0,
        "phd_main_supervisor": 0,
        "phd_co_supervisor": 0,
        "publications_with_students": 0,
        "student_names": []
    }},
    "references": [
        {{
            "ref_name": "string",
            "designation": "string or null",
            "organization": "string or null",
            "address": "string or null",
            "country": "string or null",
            "phone": "string or null",
            "email": "string or null",
            "relationship": "string or null"
        }}
    ]
}}

CV TEXT:
{cv_text}"""

# Keep old single-prompt variable so nothing else breaks
EXTRACTION_PROMPT = EXTRACTION_SYSTEM_PROMPT + "\n\n" + EXTRACTION_USER_TEMPLATE
