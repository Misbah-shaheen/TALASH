import sys
import os
import json
import argparse
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from tqdm import tqdm
from core.pdf_parser import extract_text_from_pdf, get_pdf_metadata
from core.llm_extractor import extract_candidate_data, build_missing_info_email
from core.excel_writer import write_excel
from utils.normalizer import (
    make_candidate_id,
    make_record_id,
    normalize_date,
    normalize_salary,
    compute_duration_months,
    classify_degree_level,
    detect_missing_fields,
    infer_authorship_role,
)
from config import TABLE_SCHEMAS



# ── Per-record post-processing ────────────────────────────────────────────────

def _post_process(candidate_data: dict, candidate_id: str, filename: str) -> dict:
    """
    Apply normalization to all fields after LLM extraction.
    Adds IDs, normalizes dates/salaries, computes durations.
    """
    result = {"candidate_id": candidate_id, "source_pdf": filename}

    # ── personal_info ──────────────────────────────────────────────────────────
    pi = candidate_data.get("personal_info") or {}
    pi["candidate_id"] = candidate_id
    pi["source_pdf"] = filename

    # Fix key mismatches — Gemini returns different names than our schema
    pi["full_name"] = (
        pi.get("full_name") or pi.get("name") or pi.get("candidate_name") or ""
    )
    pi["father_guardian_name"] = (
        pi.get("father_guardian_name")
        or pi.get("father_name")
        or pi.get("fathers_name")
        or pi.get("father")
        or pi.get("guardian_name")
        or None
    )
    pi["fathers_occupation"] = (
        pi.get("fathers_occupation") or pi.get("father_occupation") or None
    )
    pi["current_salary_pkr"] = normalize_salary(
        pi.get("current_salary_pkr") or pi.get("current_salary")
    )
    pi["expected_salary_pkr"] = normalize_salary(
        pi.get("expected_salary_pkr") or pi.get("expected_salary")
    )
    pi["date_of_birth"] = normalize_date(pi.get("date_of_birth"))
    result["personal_info"] = pi

    candidate_name = pi.get("full_name", "")

    # ── education ──────────────────────────────────────────────────────────────
    edu_records = []
    for seq, edu in enumerate(candidate_data.get("education") or [], 1):
        if not isinstance(edu, dict):
            continue
        edu["record_id"] = make_record_id("edu", candidate_id, seq)
        edu["candidate_id"] = candidate_id
        edu["degree_level"] = classify_degree_level(
            edu.get("degree_level") or edu.get("degree_name")
        )
        edu["education_gap_flag"] = False  # filled by analysis module
        edu_records.append(edu)
    result["education"] = edu_records

    # ── experience ─────────────────────────────────────────────────────────────
    exp_records = []
    prev_end = None
    for seq, exp in enumerate(candidate_data.get("experience") or [], 1):
        if not isinstance(exp, dict):
            continue
        exp["record_id"] = make_record_id("exp", candidate_id, seq)
        exp["candidate_id"] = candidate_id

        # FIX-3: if LLM left start_date/end_date null but gave a duration string,
        # parse it now so compute_duration_months and gap detection work correctly.
        # Duration format examples: "Sep-2017 - Aug-2023", "Jan-2025 - Present"
        if not exp.get("start_date") and not exp.get("end_date"):
            duration_str = str(exp.get("duration", "") or "").strip()
            if duration_str:
                import re as _re
                parts = _re.split(r"\s*-\s*", duration_str, maxsplit=1)
                if len(parts) == 2:
                    exp["start_date"] = parts[0].strip()
                    exp["end_date"] = parts[1].strip()
                elif len(parts) == 1 and parts[0].strip():
                    exp["start_date"] = parts[0].strip()
                    exp["end_date"] = None

        start = normalize_date(exp.get("start_date"))
        end_raw = exp.get("end_date")
        is_current = str(end_raw).lower() in ("present", "current", "") if end_raw else False
        end = None if is_current else normalize_date(end_raw)

        exp["start_date"] = start
        exp["end_date"] = "Present" if is_current else end
        exp["is_current"] = is_current
        exp["duration_months"] = compute_duration_months(start, end_raw)

        # Gap detection (will be used by analysis module)
        exp["gap_before_months"] = (
            compute_duration_months(prev_end, start)
            if prev_end and start else None
        )
        exp["overlap_flag"] = False  # filled by analysis module

        prev_end = end if not is_current else None
        exp_records.append(exp)
    result["experience"] = exp_records

    # ── publications ───────────────────────────────────────────────────────────
    pub_records = []
    for seq, pub in enumerate(candidate_data.get("publications") or [], 1):
        if not isinstance(pub, dict):
            continue
        pub["record_id"] = make_record_id("pub", candidate_id, seq)
        pub["candidate_id"] = candidate_id

        # FIX-2: classify pub_type using venue string, not just the pub_type field.
        # LLM sometimes sets pub_type="Journal" for everything — override when
        # the venue name clearly signals a conference/symposium/proceedings.
        CONF_SIGNALS = (
            "conference", "symposium", "proceedings", "workshop",
            "congress", "convention", "colloquium", "inmic", "ibcast",
            "icosst", "icet", "bhurban", "multitopic",
        )
        venue_str = str(
            pub.get("venue_name") or pub.get("published_in") or pub.get("venue") or ""
        ).lower()
        if any(sig in venue_str for sig in CONF_SIGNALS):
            pub["pub_type"] = "Conference"
        elif not pub.get("pub_type"):
            pub["pub_type"] = "Journal"
        # else: keep what LLM already set (Journal/Workshop/Other)

        # Infer authorship role
        if not pub.get("authorship_role"):
            pub["authorship_role"] = infer_authorship_role(
                candidate_name,
                pub.get("first_author"),
                pub.get("co_authors"),
            )

        # Normalize publication date
        pub_date = pub.get("month") or pub.get("year")
        pub["year"] = pub.get("year")

        pub_records.append(pub)
    result["publications"] = pub_records

    # ── skills ─────────────────────────────────────────────────────────────────
    skill_records = []
    for seq, skill in enumerate(candidate_data.get("skills") or [], 1):
        if isinstance(skill, str):
            skill = {"skill_name": skill, "skill_category": None, "proficiency_claimed": None}
        if not isinstance(skill, dict):
            continue
        skill["record_id"] = make_record_id("skl", candidate_id, seq)
        skill["candidate_id"] = candidate_id
        skill["evidence_level"] = None  # filled by skill-alignment module
        skill_records.append(skill)
    result["skills"] = skill_records

    # ── patents, books, awards, references ────────────────────────────────────
    for table, prefix in [("patents", "pat"), ("books", "bk"), ("awards", "awd"), ("references", "ref")]:
        records = []
        for seq, rec in enumerate(candidate_data.get(table) or [], 1):
            if not isinstance(rec, dict):
                continue
            rec["record_id"] = make_record_id(prefix, candidate_id, seq)
            rec["candidate_id"] = candidate_id
            records.append(rec)
        result[table] = records

    # FIX-1: supervision — the NUST form has no supervision section so the LLM
    # always returns null. Default to the empty structure so db.save_candidate()
    # never calls .get() on None and downstream analysis gets zero counts instead
    # of a crash.
    raw_sup = candidate_data.get("supervision")
    result["supervision"] = {
        "ms_main_supervisor":        int(raw_sup.get("ms_main_supervisor")  or 0) if raw_sup else 0,
        "ms_co_supervisor":          int(raw_sup.get("ms_co_supervisor")    or 0) if raw_sup else 0,
        "phd_main_supervisor":       int(raw_sup.get("phd_main_supervisor") or 0) if raw_sup else 0,
        "phd_co_supervisor":         int(raw_sup.get("phd_co_supervisor")   or 0) if raw_sup else 0,
        "publications_with_students": int(raw_sup.get("publications_with_students") or 0) if raw_sup else 0,
        "student_names":             (raw_sup.get("student_names") or [])   if raw_sup else [],
    }

    return result


# ── Missing info email writer ─────────────────────────────────────────────────

def _write_email_draft(candidate_data: dict, output_dir: Path, generate: bool):
    if not generate:
        return

    missing = detect_missing_fields(candidate_data)
    if not missing:
        return

    name = candidate_data.get("personal_info", {}).get("full_name", "Candidate")
    cid  = candidate_data.get("candidate_id", "unknown")
    candidate_email = candidate_data.get("personal_info", {}).get("email", "")

    print(f"  Generating LLM missing-info email for {name} ({len(missing)} fields)")
    try:
        from core.llm_extractor import build_missing_info_email
        email_body = build_missing_info_email(name, missing, candidate_email)
        email_path = output_dir / f"missing_email_{cid}.txt"
        email_path.write_text(email_body, encoding="utf-8")
        print(f"  Email saved → {email_path.name}")
    except Exception as e:
        print(f"  Email generation failed: {e}")


# ── Progress checkpoint ────────────────────────────────────────────────────────

def _load_checkpoint(checkpoint_path: Path) -> set:
    if checkpoint_path.exists():
        return set(json.loads(checkpoint_path.read_text()))
    return set()


def _save_checkpoint(checkpoint_path: Path, done: set):
    checkpoint_path.write_text(json.dumps(list(done)))


# ── Main pipeline ──────────────────────────────────────────────────────────────

def run_pipeline(
    input_dir: str,
    output_dir: str,
    generate_emails: bool = False,
    resume: bool = False,
    delay_between_calls: float = 1.5,
):
    input_path = Path(input_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    pdf_files = sorted(input_path.glob("*.pdf"))
    if not pdf_files:
        print(f" No PDF files found in {input_dir}")
        return

    print(f"\n{'='*60}")
    print(f"  TALASH Pre-Processing Pipeline")
    print(f"  Input : {input_dir}  ({len(pdf_files)} PDFs)")
    print(f"  Output: {output_dir}")
    print(f"{'='*60}\n")

    checkpoint_path = output_path / ".checkpoint.json"
    done_files = _load_checkpoint(checkpoint_path) if resume else set()

    # Always skip files already in DB (avoids reprocessing on fresh pipeline run)
    try:
        import database as db
        existing = db.get_all_candidates()
        for cand in existing:
            fname = cand.get("source_pdf", "")
            if fname:
                done_files.add(fname)
    except Exception:
        pass

    # Raw JSON cache dir (for debugging / reruns)
    cache_dir = output_path / "raw_json"
    cache_dir.mkdir(exist_ok=True)

    all_candidates = []
    failed = []

    for idx, pdf_path in enumerate(tqdm(pdf_files, desc="Processing CVs"), 1):
        if resume and pdf_path.name in done_files:
            # Load from cache
            cache_file = cache_dir / f"{pdf_path.stem}.json"
            if cache_file.exists():
                cand = json.loads(cache_file.read_text())
                all_candidates.append(cand)
                continue

        print(f"\n[{idx:02d}/{len(pdf_files)}] {pdf_path.name}")

        try:
            # Step 1: Extract text from PDF
            meta = get_pdf_metadata(pdf_path)
            print(f"  {meta['page_count']} pages, {meta['file_size_kb']} KB")
            cv_text = extract_text_from_pdf(pdf_path)

            if len(cv_text.strip()) < 100:
                raise ValueError("Extracted text too short — likely scanned/image PDF")

            print(f"   Extracted {len(cv_text):,} chars")

            # Step 2: LLM extraction
            print(f"  Sending to Gemini for extraction…")
            raw_data = extract_candidate_data(cv_text, pdf_path.name)

            # Step 3: Post-process & normalize
            candidate_id = make_candidate_id(idx)
            processed = _post_process(raw_data, candidate_id, pdf_path.name)

            # Cache raw + processed JSON (initial save before evaluation)
            cache_file = cache_dir / f"{pdf_path.stem}.json"
            cache_file.write_text(json.dumps(processed, indent=2, default=str), encoding="utf-8")

            # Step 4: Run full analysis + LLM evaluation
            print(f"  Running TALASH analysis engine…")
            try:
                from core.analysis_engine import AnalysisEngine
                from core.llm_extractor import generate_candidate_summary
                engine = AnalysisEngine()
                evaluation = engine.evaluate_candidate(processed)
                processed["evaluation"] = evaluation
                # Generate LLM narrative summary
                summary_text = generate_candidate_summary(processed, evaluation)
                processed["evaluation"]["llm_summary"] = summary_text
                # Save with evaluation
                cache_file.write_text(json.dumps(processed, indent=2, default=str), encoding="utf-8")
                print(f"  Score: {evaluation.get('overall_score', 0):.1f}/100")
            except Exception as eval_err:
                print(f"  Analysis failed (non-fatal): {eval_err}")

            all_candidates.append(processed)
            done_files.add(pdf_path.name)
            _save_checkpoint(checkpoint_path, done_files)

            # Step 5: Missing info email
            _write_email_draft(processed, output_path, generate_emails)

            name = processed.get("personal_info", {}).get("full_name", "?")
            edu_count = len(processed.get("education", []))
            pub_count = len(processed.get("publications", []))
            exp_count = len(processed.get("experience", []))
            print(f"  {name} — {edu_count} degrees, {exp_count} jobs, {pub_count} publications")

            # Polite delay between API calls
            if idx < len(pdf_files):
                time.sleep(delay_between_calls)

        except Exception as e:
            print(f"  ✗ FAILED: {e}")
            failed.append((pdf_path.name, str(e)))
            continue

    if not all_candidates:
        print("\nNo candidates processed successfully.")
        return

    # Step 5: Write consolidated Excel
    print(f"\n Writing Excel output ({len(all_candidates)} candidates)…")
    excel_path = output_path / "TALASH_Candidates.xlsx"
    write_excel(all_candidates, str(excel_path))

    # Step 6: Summary report
    _print_summary(all_candidates, failed, str(excel_path))


def _print_summary(candidates: list, failed: list, excel_path: str):
    print(f"\n{'='*60}")
    print(f"  PIPELINE COMPLETE")
    print(f"{'='*60}")
    print(f"  Processed : {len(candidates)} candidates")
    print(f"  Failed    : {len(failed)}")
    if failed:
        for fname, err in failed:
            print(f"      • {fname}: {err}")

    total_pubs = sum(len(c.get("publications", [])) for c in candidates)
    total_exp = sum(len(c.get("experience", [])) for c in candidates)
    phd_count = sum(
        1 for c in candidates
        if any(e.get("degree_level") == "PhD" for e in c.get("education", []))
    )

    print(f"\n  Dataset stats:")
    print(f"     PhD holders   : {phd_count}/{len(candidates)}")
    print(f"     Total pubs    : {total_pubs} ({total_pubs/len(candidates):.1f} avg)")
    print(f"     Total exp rows: {total_exp}")
    print(f"\n  Output: {excel_path}")
    print(f"{'='*60}\n")


# ── CLI ────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="TALASH Pre-Processing Pipeline")
    parser.add_argument("--input",   required=True,  help="Folder containing PDF CVs")
    parser.add_argument("--output",  required=True,  help="Output folder")
    parser.add_argument("--emails",  action="store_true", help="Generate missing-info emails")
    parser.add_argument("--resume",  action="store_true", help="Skip already-processed PDFs")
    parser.add_argument("--delay",   type=float, default=1.5, help="Delay (s) between API calls")
    args = parser.parse_args()

    run_pipeline(
        input_dir=args.input,
        output_dir=args.output,
        generate_emails=args.emails,
        resume=args.resume,
        delay_between_calls=args.delay,
    )