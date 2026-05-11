"""
LLM Extractor - Gemini with dual-key fallback for TALASH CV extraction
"""

import json
import re
import time
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path

import google.generativeai as genai

from config import (
    GEMINI_API_KEYS, MODEL, MAX_TOKENS,
    EXTRACTION_SYSTEM_PROMPT, EXTRACTION_USER_TEMPLATE,
    SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM, SMTP_ENABLED,
)

# ── Dual-key Gemini caller ────────────────────────────────────────────────────

_current_key_idx = 0   # tracks which key is active this session


def _call_gemini_with_fallback(system_prompt: str, user_prompt: str,
                                temperature: float = 0.0,
                                max_output_tokens: int = MAX_TOKENS) -> str:
    """
    Try GEMINI_API_KEYS[0]; on quota / 429 / ResourceExhausted rotate to [1].
    Returns raw response text, or '' on total failure.
    """
    global _current_key_idx
    keys = GEMINI_API_KEYS
    tried = set()

    for attempt in range(len(keys)):
        key_idx = _current_key_idx % len(keys)
        if key_idx in tried:
            break
        tried.add(key_idx)
        api_key = keys[key_idx]

        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(
                MODEL,
                generation_config={
                    "temperature": temperature,
                    "max_output_tokens": max_output_tokens,
                },
            )
            response = model.generate_content([system_prompt, user_prompt])
            text = response.text
            return text.strip() if isinstance(text, str) else ""

        except Exception as e:
            err_str = str(e).lower()
            is_quota = any(kw in err_str for kw in (
                "quota", "429", "resource_exhausted", "rate", "limit",
                "resourceexhausted", "per_day", "per_minute",
            ))
            if is_quota:
                print(f"  [LLM] Key #{key_idx+1} quota/rate-limit hit — rotating to next key")
                _current_key_idx = (key_idx + 1) % len(keys)
                time.sleep(2)
            else:
                print(f"  [LLM] Key #{key_idx+1} error: {e}")
                _current_key_idx = (key_idx + 1) % len(keys)

    print("  [LLM] All API keys exhausted or failed.")
    return ""


# ── Public helper (used by analysis_engine etc.) ──────────────────────────────

def call_llm(prompt: str, temperature: float = 0.0, max_tokens: int = 2000) -> str:
    """Single-prompt LLM call with dual-key fallback. Returns raw text."""
    return _call_gemini_with_fallback(
        "You are a helpful academic HR analysis assistant.",
        prompt,
        temperature=temperature,
        max_output_tokens=max_tokens,
    )


# ── CV Extraction ─────────────────────────────────────────────────────────────

def extract_candidate_data(cv_text: str, filename: str) -> dict:
    """Extract structured candidate data from CV text using Gemini."""
    user_prompt = EXTRACTION_USER_TEMPLATE.format(
        filename=filename,
        cv_text=cv_text[:35000],
    )

    response_text = _call_gemini_with_fallback(
        EXTRACTION_SYSTEM_PROMPT,
        user_prompt,
        temperature=0.0,
        max_output_tokens=MAX_TOKENS,
    )

    if not response_text:
        return _get_empty_extraction()

    # Clean markdown fences
    response_text = re.sub(r'```json\s*', '', response_text)
    response_text = re.sub(r'```\s*',     '', response_text)
    response_text = response_text.strip()

    try:
        data = json.loads(response_text)
    except json.JSONDecodeError:
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group())
            except json.JSONDecodeError:
                print(f"  JSON parse failed. Response: {response_text[:300]}")
                data = _get_empty_extraction()
        else:
            print(f"  No JSON found. Response: {response_text[:300]}")
            data = _get_empty_extraction()

    required_keys = ["personal_info", "education", "experience", "publications",
                     "skills", "patents", "books", "awards", "references"]
    for key in required_keys:
        if key not in data:
            data[key] = [] if key != "personal_info" else {}

    return data


def _get_empty_extraction() -> dict:
    return {
        "personal_info": {},
        "education": [],
        "experience": [],
        "publications": [],
        "skills": [],
        "patents": [],
        "books": [],
        "awards": [],
        "references": [],
    }


# ── LLM-generated missing-info email ─────────────────────────────────────────

def build_missing_info_email(candidate_name: str, missing_fields: list,
                              candidate_email: str = None) -> str:
    """Use LLM to generate a professional, personalised missing-info email."""
    fields_str = "\n".join(f"- {f}" for f in missing_fields)
    prompt = f"""You are an HR assistant for TALASH (NUST recruitment system).
Write a professional, polite, and personalized email to the candidate asking them
to provide the following missing information from their application.

Candidate name: {candidate_name}
Missing fields:
{fields_str}

Requirements:
- Use a warm, professional tone
- Explain WHY each piece of information is important for evaluation
- Give them a 5-business-day deadline
- Sign off as "TALASH Recruitment Team, NUST"
- Include a Subject line at the very top in format: Subject: <subject text>
- Do NOT use placeholder brackets like [date] or [email address]

Write only the email (subject + body), nothing else."""

    email_text = _call_gemini_with_fallback(
        "You are a professional HR communication specialist.",
        prompt,
        temperature=0.4,
        max_output_tokens=1000,
    )

    if not email_text:
        # Fallback to template
        subject = f"Missing Information Request – {candidate_name} | TALASH Recruitment"
        body = (
            f"Dear {candidate_name},\n\n"
            f"Thank you for your interest in joining NUST. While reviewing your application, "
            f"we found the following information missing or incomplete:\n\n"
            f"{fields_str}\n\n"
            f"Kindly provide the above details within 5 business days so we may complete "
            f"your evaluation accurately.\n\n"
            f"Best regards,\n"
            f"TALASH Recruitment Team – NUST"
        )
        email_text = f"Subject: {subject}\n\n{body}"

    return email_text


# ── LLM-generated candidate summary ──────────────────────────────────────────

def generate_candidate_summary(candidate_data: dict, evaluation: dict) -> str:
    """Use LLM to generate a concise HR narrative summary for the candidate."""
    name       = candidate_data.get("personal_info", {}).get("full_name", "Candidate")
    post       = candidate_data.get("personal_info", {}).get("post_applied_for", "Unknown Position")
    edu_str    = "; ".join(
        f"{e.get('degree_name','')} from {e.get('institution','')}"
        for e in (candidate_data.get("education") or [])[:4]
    ) or "Not available"
    pub_count  = len(candidate_data.get("publications") or [])
    skills_str = ", ".join(
        (s.get("skill_name","") if isinstance(s,dict) else str(s))
        for s in (candidate_data.get("skills") or [])[:15]
    ) or "Not listed"
    exp_str    = "; ".join(
        f"{e.get('job_title','')} at {e.get('organization','')}"
        for e in (candidate_data.get("experience") or [])[:4]
    ) or "Not available"

    overall_score  = evaluation.get("overall_score", 0)
    edu_score      = evaluation.get("educational_analysis", {}).get("score", 0)
    research_score = evaluation.get("research_analysis", {}).get("overall_quality_score", 0)
    exp_score      = evaluation.get("experience_analysis", {}).get("score", 0)
    skill_score    = evaluation.get("skill_analysis", {}).get("alignment_score", 0)
    gaps           = len(evaluation.get("experience_analysis", {}).get("gaps", []))
    overlaps       = len(evaluation.get("experience_analysis", {}).get("overlaps", []))

    prompt = f"""You are an HR evaluation expert. Generate a concise, factual, and balanced
narrative summary of this academic job candidate for a NUST recruitment panel.

Candidate: {name}
Post Applied: {post}
Overall TALASH Score: {overall_score}/100
Education Score: {edu_score}/100 — Degrees: {edu_str}
Research Score: {research_score}/100 — Publications: {pub_count}
Experience Score: {exp_score}/100 — Roles: {exp_str}
Skill Score: {skill_score}/100 — Skills: {skills_str}
Employment gaps detected: {gaps} | Overlaps: {overlaps}

Write a 150–200 word summary that:
1. Highlights the candidate's key strengths
2. Notes any concerns (gaps, low scores, weak research, etc.)
3. States overall suitability for the applied post
4. Ends with a clear recommendation: Hire / Shortlist / Reject
Use professional, evidence-based language. Do not fabricate details."""

    summary = _call_gemini_with_fallback(
        "You are a senior HR evaluation expert writing candidate assessment summaries.",
        prompt,
        temperature=0.3,
        max_output_tokens=600,
    )

    if not summary:
        rec = "Hire" if overall_score >= 70 else "Shortlist" if overall_score >= 45 else "Reject"
        summary = (
            f"{name} applied for {post} with an overall TALASH score of {overall_score}/100. "
            f"Education score: {edu_score}/100. Research score: {research_score}/100 across "
            f"{pub_count} publications. Experience score: {exp_score}/100. "
            f"Recommendation: {rec}."
        )
    return summary


# ── SMTP Email Sender ─────────────────────────────────────────────────────────

def send_email_smtp(to_address: str, email_text: str,
                    candidate_name: str = "Candidate") -> dict:
    """
    Actually send an email via SMTP.
    email_text must start with 'Subject: <subject line>' on first line.

    Returns: {'success': bool, 'message': str}
    """
    if not SMTP_ENABLED:
        return {
            "success": False,
            "message": (
                "SMTP not configured. Set SMTP_USER and SMTP_PASSWORD in your .env file. "
                "The email draft has been saved and can be sent manually."
            ),
        }

    if not to_address or "@" not in to_address:
        return {"success": False, "message": "Invalid or missing recipient email address."}

    # Parse subject from first line
    lines = email_text.strip().splitlines()
    subject = f"Application Follow-up – {candidate_name}"
    body_lines = lines

    if lines and lines[0].lower().startswith("subject:"):
        subject = lines[0][len("subject:"):].strip()
        body_lines = lines[1:]
        # Skip blank lines after subject
        while body_lines and not body_lines[0].strip():
            body_lines = body_lines[1:]

    body = "\n".join(body_lines)

    try:
        msg = MIMEMultipart("alternative")
        msg["From"]    = SMTP_FROM
        msg["To"]      = to_address
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as server:
            server.ehlo()
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_FROM, [to_address], msg.as_string())

        return {"success": True, "message": f"Email sent to {to_address}"}

    except smtplib.SMTPAuthenticationError:
        return {
            "success": False,
            "message": "SMTP authentication failed. Check SMTP_USER and SMTP_PASSWORD in .env.",
        }
    except Exception as e:
        return {"success": False, "message": f"Email send failed: {e}"}
