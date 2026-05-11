"""
Normalization utilities for candidate data
"""

import re
from datetime import datetime
from dateutil import parser


def make_candidate_id(index: int) -> str:
    """Generate candidate ID like cand_001"""
    return f"cand_{index:03d}"


def make_record_id(prefix: str, candidate_id: str, seq: int) -> str:
    """Generate record ID like edu_cand_001_01"""
    return f"{prefix}_{candidate_id}_{seq:02d}"


def normalize_date(date_str) -> str:
    """Normalize date to YYYY-MM-DD format"""
    if not date_str or date_str in [None, "", "null", "Present"]:
        return None
    
    date_str = str(date_str).strip()
    
    if date_str.lower() == "present":
        return "Present"
    
    # Try parsing with dateutil
    try:
        dt = parser.parse(date_str, fuzzy=True)
        return dt.strftime("%Y-%m-%d")
    except:
        pass
    
    # Manual patterns
    patterns = [
        (r'(\d{4})', lambda m: f"{m.group(1)}-01-01"),
        (r'(\d{2})-(\d{2})-(\d{4})', lambda m: f"{m.group(3)}-{m.group(2)}-{m.group(1)}"),
        (r'(\d{2})/(\d{2})/(\d{4})', lambda m: f"{m.group(3)}-{m.group(2)}-{m.group(1)}"),
        (r'([A-Za-z]{3})-(\d{4})', lambda m: f"{m.group(2)}-{_month_to_num(m.group(1))}-01"),
        (r'([A-Za-z]+)[\s-](\d{4})', lambda m: f"{m.group(2)}-{_month_to_num(m.group(1)[:3])}-01"),
    ]
    
    for pattern, formatter in patterns:
        match = re.search(pattern, date_str, re.IGNORECASE)
        if match:
            try:
                return formatter(match)
            except:
                continue
    
    return date_str


def _month_to_num(month: str) -> str:
    months = {
        "jan": "01", "feb": "02", "mar": "03", "apr": "04",
        "may": "05", "jun": "06", "jul": "07", "aug": "08",
        "sep": "09", "oct": "10", "nov": "11", "dec": "12"
    }
    return months.get(month.lower()[:3], "01")


def normalize_salary(salary) -> int:
    """Normalize salary - if value < 5000, multiply by 1000"""
    if not salary:
        return None
    
    if isinstance(salary, (int, float)):
        val = salary
    else:
        # Extract numbers from string
        match = re.search(r'(\d+(?:,\d+)?)', str(salary))
        if not match:
            return None
        val = int(match.group(1).replace(',', ''))
    
    if val < 5000 and val > 0:
        val = val * 1000
    
    return val


def compute_duration_months(start_date, end_date) -> int:
    """Compute duration in months between two dates"""
    if not start_date:
        return None
    
    start = normalize_date(start_date)
    if not start:
        return None
    
    end = normalize_date(end_date) if end_date else None
    
    try:
        start_dt = datetime.strptime(start, "%Y-%m-%d")
        if end and end != "Present":
            end_dt = datetime.strptime(end, "%Y-%m-%d")
        else:
            end_dt = datetime.now()
        
        months = (end_dt.year - start_dt.year) * 12 + (end_dt.month - start_dt.month)
        return max(0, months)
    except:
        return None


def classify_degree_level(degree_text) -> str:
    """Classify degree level from degree name/text"""
    if not degree_text:
        return None
    
    text = str(degree_text).upper()
    
    if "PHD" in text or "DOCTOR" in text:
        return "PhD"
    elif "MS" in text or "MSC" in text or "MASTER" in text or "MPHIL" in text:
        return "Master"
    elif "BS" in text or "BSC" in text or "BACHELOR" in text or "BE" in text:
        return "Bachelor"
    elif "HSSC" in text or "INTERMEDIATE" in text or "FSC" in text or "A-LEVEL" in text:
        return "HSSC"
    elif "SSC" in text or "MATRIC" in text or "O-LEVEL" in text:
        return "SSC"
    else:
        return "Other"


def detect_missing_fields(candidate_data: dict) -> list:
    """Detect missing critical fields in candidate data"""
    missing = []

    pi = candidate_data.get("personal_info", {}) or {}

    # ── Personal info fields ──────────────────────────────────────────────────
    # Original critical fields (kept as-is for consistency)
    critical_fields = ["full_name", "date_of_birth", "current_salary_pkr"]
    for field in critical_fields:
        if not pi.get(field):
            missing.append(field)

    # Additional personal info fields needed for evaluation
    _EMPTY = ("", "none", "null", "n/a", "unknown", "not provided", "not mentioned")

    def _blank(val) -> bool:
        """Return True if val is effectively empty."""
        return not val or str(val).strip().lower() in _EMPTY

    if _blank(pi.get("email")):
        missing.append("email")

    if _blank(pi.get("phone")) and _blank(pi.get("contact_number")):
        missing.append("phone")

    if _blank(pi.get("cnic")) and _blank(pi.get("national_id")):
        missing.append("cnic")

    if _blank(pi.get("post_applied_for")):
        missing.append("post_applied_for")

    # ── Education ─────────────────────────────────────────────────────────────
    # Original check (kept as-is)
    if not candidate_data.get("education"):
        missing.append("education")
    else:
        # Flag individual education records that are missing key sub-fields
        for i, edu in enumerate(candidate_data["education"]):
            if _blank(edu.get("degree_name")):
                missing.append(f"education[{i}].degree_name")
            if _blank(edu.get("institution")):
                missing.append(f"education[{i}].institution")
            if _blank(edu.get("passing_year")):
                missing.append(f"education[{i}].passing_year")

    # ── Experience ────────────────────────────────────────────────────────────
    if not candidate_data.get("experience"):
        missing.append("experience")
    else:
        for i, exp in enumerate(candidate_data["experience"]):
            if _blank(exp.get("start_date")):
                missing.append(f"experience[{i}].start_date")
            if _blank(exp.get("organization")):
                missing.append(f"experience[{i}].organization")

    # ── Publications ──────────────────────────────────────────────────────────
    # Only flag as missing if the candidate claims publications but none were extracted
    claims_pubs = not _blank(pi.get("publications_count")) or not _blank(pi.get("google_scholar"))
    if claims_pubs and not candidate_data.get("publications"):
        missing.append("publications")
    else:
        for i, pub in enumerate(candidate_data.get("publications", [])):
            if _blank(pub.get("title")):
                missing.append(f"publications[{i}].title")
            if _blank(pub.get("venue_name")) and _blank(pub.get("published_in")):
                missing.append(f"publications[{i}].venue_name")
            if _blank(pub.get("year")):
                missing.append(f"publications[{i}].year")

    return missing


def infer_authorship_role(candidate_name: str, first_author: str, co_authors: str) -> str:
    """Infer authorship role based on candidate name position"""
    if not candidate_name:
        return "Co-author"
    
    candidate_name_clean = candidate_name.lower().strip()
    
    if first_author and candidate_name_clean in first_author.lower():
        return "First"
    
    if co_authors and candidate_name_clean in co_authors.lower():
        # Check if candidate is first among co-authors
        co_list = co_authors.split(",")
        if co_list and candidate_name_clean in co_list[0].lower():
            return "First"
        return "Co-author"
    
    return "Co-author"


def clean_json_response(response_text: str) -> str:
    """Clean JSON response from LLM"""
    # Remove markdown code blocks
    response_text = re.sub(r'```json\s*', '', response_text)
    response_text = re.sub(r'```\s*', '', response_text)
    
    # Remove trailing commas in objects/arrays
    response_text = re.sub(r',\s*}', '}', response_text)
    response_text = re.sub(r',\s*]', ']', response_text)
    
    return response_text.strip()
