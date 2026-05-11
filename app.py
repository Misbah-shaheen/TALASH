"""
TALASH Web Application — Flask + SQLite backend
"""

from flask import Flask, render_template, request, jsonify, send_file
from flask_cors import CORS
import os
import json
from pathlib import Path
from werkzeug.utils import secure_filename
import threading
from dotenv import load_dotenv

load_dotenv()

# LLM helpers (imported lazily to avoid circular import at module level)
def _llm_email():
    from core.llm_extractor import build_missing_info_email, generate_candidate_summary, send_email_smtp
    return build_missing_info_email, generate_candidate_summary, send_email_smtp

app = Flask(__name__)
CORS(app)

app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'talash-secret')
app.config['UPLOAD_FOLDER'] = './cvs'
app.config['OUTPUT_FOLDER'] = './output'
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50 MB upload limit

Path(app.config['UPLOAD_FOLDER']).mkdir(parents=True, exist_ok=True)
Path(app.config['OUTPUT_FOLDER']).mkdir(parents=True, exist_ok=True)

# ── SQLite bootstrap ──────────────────────────────────────────────────────────
import database as db
db.init_db()

# In-memory cache (sorted by score, rebuilt after each pipeline run)
candidates_cache = []

_pipeline_status = {"running": False, "message": "Idle", "progress": 0}


# ─────────────────────────────────────────────────────────────────────────────
# Startup: load from DB first; fall back to JSON cache migration if DB empty
# ─────────────────────────────────────────────────────────────────────────────

def load_candidates():
    """Reload in-memory cache from SQLite (fast path)."""
    global candidates_cache
    rows = db.get_all_candidates()

    if not rows:
        # First run — migrate existing JSON cache into DB
        cache_dir = Path(app.config['OUTPUT_FOLDER']) / 'raw_json'
        if cache_dir.exists():
            print("[app] No DB rows found — migrating JSON cache to SQLite…")
            db.bulk_load_from_json_cache(str(cache_dir), app.config['OUTPUT_FOLDER'])
            rows = db.get_all_candidates()

    # Build cache from DB rows with full JSON blobs
    result = []
    for row in rows:
        try:
            if row.get('raw_json'):
                data = json.loads(row['raw_json'])
                if row.get('evaluation_json'):
                    data['evaluation'] = json.loads(row['evaluation_json'])
                result.append(data)
        except Exception as e:
            print(f"[app] Cache build error for {row.get('candidate_id')}: {e}")

    candidates_cache = result
    print(f"[app] Cache ready: {len(candidates_cache)} candidates.")


def _save_gap_email(data: dict, output_dir: Path):
    gap_email = (
        data.get('evaluation', {})
            .get('experience_analysis', {})
            .get('gap_email')
    )
    if not gap_email:
        return
    cid = data.get('candidate_id', 'unknown')
    email_path = output_dir / f"gap_email_{cid}.txt"
    if not email_path.exists():
        email_path.write_text(gap_email, encoding='utf-8')


load_candidates()


# ─────────────────────────────────────────────────────────────────────────────
# Routes — Pages
# ─────────────────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('index.html')


# ─────────────────────────────────────────────────────────────────────────────
# Routes — Dashboard
# ─────────────────────────────────────────────────────────────────────────────

@app.route('/api/dashboard')
def dashboard():
    try:
        stats = db.get_dashboard_stats()
    except Exception:
        # Fallback to cache if DB unavailable
        stats = {
            'total': len(candidates_cache),
            'avg_score': 0,
            'top_candidates': [],
            'publications_total': 0,
            'phd_count': 0,
            'score_distribution': {'hire': 0, 'shortlist': 0, 'reject': 0, 'pending': 0},
            'pub_types': [],
        }
        if candidates_cache:
            scores = [c.get('evaluation', {}).get('overall_score', 0) for c in candidates_cache]
            stats['avg_score'] = round(sum(scores) / len(scores), 1)
    return jsonify(stats)


# ─────────────────────────────────────────────────────────────────────────────
# Routes — Candidates
# ─────────────────────────────────────────────────────────────────────────────

@app.route('/api/candidates')
def get_candidates():
    search_q = request.args.get('q', '').strip()
    if search_q:
        rows = db.search_candidates(search_q)
        # Re-attach evaluation JSON
        result = []
        for row in rows:
            try:
                data = json.loads(row['raw_json']) if row.get('raw_json') else {}
                eval_data = json.loads(row['evaluation_json']) if row.get('evaluation_json') else {}
                result.append(_candidate_summary(data, eval_data))
            except Exception:
                pass
        return jsonify(result)

    result = [_candidate_summary(c, c.get('evaluation', {})) for c in candidates_cache]
    return jsonify(result)


def _candidate_summary(c: dict, eval_data: dict) -> dict:
    pi = c.get('personal_info', {}) if isinstance(c.get('personal_info'), dict) else {}
    return {
        'id':                c.get('candidate_id'),
        'name':              pi.get('full_name', 'Unknown'),
        'post':              pi.get('post_applied_for', 'N/A'),
        'department':        pi.get('department', ''),
        'overall_score':     eval_data.get('overall_score', 0),
        'education_score':   eval_data.get('educational_analysis', {}).get('score', 0),
        'research_score':    round(eval_data.get('research_analysis', {}).get('overall_quality_score', 0), 1),
        'experience_years':  eval_data.get('experience_analysis', {}).get('experience_years', 0),
        'experience_score':  eval_data.get('experience_analysis', {}).get('score', 0),
        'publications':      len(c.get('publications', [])),
        'patents_total':     eval_data.get('patents_analysis', {}).get('total', 0),
        'dominant_topic':    eval_data.get('topic_analysis', {}).get('dominant_topic'),
        'diversity_score':   eval_data.get('topic_analysis', {}).get('diversity_score', 0),
        'research_breadth':  eval_data.get('topic_analysis', {}).get('breadth'),
        'unique_coauthors':  eval_data.get('coauthor_analysis', {}).get('unique_coauthors', 0),
        'collab_diversity':  eval_data.get('coauthor_analysis', {}).get('collaboration_diversity_score', 0),
        'exp_gaps':          len(eval_data.get('experience_analysis', {}).get('gaps', [])),
        'exp_overlaps':      len(eval_data.get('experience_analysis', {}).get('overlaps', [])),
        'career_progression':eval_data.get('experience_analysis', {}).get('career_progression', {}).get('assessment'),
        'has_gap_email':     bool(eval_data.get('experience_analysis', {}).get('gap_email')),
        'skill_score':       round(eval_data.get('skill_analysis', {}).get('alignment_score', 0), 1),
        'skills_strong':     eval_data.get('skill_analysis', {}).get('strong', 0),
        'skills_unsupported':eval_data.get('skill_analysis', {}).get('unsupported', 0),
        'recommendation':    _recommend(eval_data.get('overall_score', 0)),
        'phd':               any(e.get('degree_level') in ('PhD', 'PHD') for e in c.get('education', [])),
    }


def _recommend(score):
    if score >= 60: return 'Hire'
    if score >= 45: return 'Shortlist'
    if score >= 30: return 'Review'
    return 'Reject'


@app.route('/api/candidate/<candidate_id>')
def get_candidate(candidate_id):
    # Try DB first (returns full JSON blob)
    data = db.get_candidate_full(candidate_id)
    if data:
        return jsonify(data)
    # Fallback to cache
    for c in candidates_cache:
        if c.get('candidate_id') == candidate_id:
            return jsonify(c)
    return jsonify({'error': 'Not found'}), 404


@app.route('/api/candidate/<candidate_id>', methods=['DELETE'])
def delete_candidate(candidate_id):
    """Remove a candidate from DB and JSON cache."""
    db.delete_candidate(candidate_id)
    # Remove JSON file
    cache_file = Path(app.config['OUTPUT_FOLDER']) / 'raw_json' / f"{candidate_id}.json"
    if cache_file.exists():
        cache_file.unlink()
    load_candidates()
    return jsonify({'success': True})


@app.route('/api/candidate/<candidate_id>/gap_email')
def get_gap_email(candidate_id):
    data = db.get_candidate_full(candidate_id)
    if not data:
        for c in candidates_cache:
            if c.get('candidate_id') == candidate_id:
                data = c
                break
    if not data:
        return jsonify({'error': 'Not found'}), 404

    gap_email = (
        data.get('evaluation', {})
            .get('experience_analysis', {})
            .get('gap_email')
    )
    if gap_email:
        return jsonify({'candidate_id': candidate_id, 'email': gap_email})
    return jsonify({'candidate_id': candidate_id, 'email': None,
                    'message': 'No gaps or overlaps detected'})


# ─────────────────────────────────────────────────────────────────────────────
# Routes — Rankings
# ─────────────────────────────────────────────────────────────────────────────

@app.route('/api/rankings')
def get_rankings():
    rankings = []
    for i, c in enumerate(candidates_cache, 1):
        eval_data = c.get('evaluation', {})
        score = eval_data.get('overall_score', 0)
        rankings.append({
            'rank':               i,
            'id':                 c.get('candidate_id'),
            'name':               c.get('personal_info', {}).get('full_name', 'Unknown'),
            'score':              score,
            'recommendation':     _recommend(score),
            'strength':           str(eval_data.get('educational_analysis', {}).get('overall_strength', ''))[:60],
            'dominant_topic':     eval_data.get('topic_analysis', {}).get('dominant_topic'),
            'skill_score':        eval_data.get('skill_analysis', {}).get('alignment_score', 0),
            'patents':            eval_data.get('patents_analysis', {}).get('total', 0),
            'career_progression': eval_data.get('experience_analysis', {}).get('career_progression', {}).get('assessment'),
            'research_score':     round(eval_data.get('research_analysis', {}).get('overall_quality_score', 0), 1),
            'education_score':    eval_data.get('educational_analysis', {}).get('score', 0),
            'publications':       len(c.get('publications', [])),
            'phd':                any(e.get('degree_level') in ('PhD', 'PHD') for e in c.get('education', [])),
        })
    return jsonify(rankings)


# ─────────────────────────────────────────────────────────────────────────────
# Routes — Upload & Processing
# ─────────────────────────────────────────────────────────────────────────────

@app.route('/api/upload', methods=['POST'])
def upload_cv():
    """Accept one or more PDF uploads into the cvs/ folder."""
    if 'files' not in request.files:
        return jsonify({'error': 'No files part in request'}), 400

    uploaded = []
    errors = []
    for file in request.files.getlist('files'):
        if file.filename == '':
            continue
        if not file.filename.lower().endswith('.pdf'):
            errors.append(f"{file.filename} is not a PDF")
            continue
        filename = secure_filename(file.filename)
        dest = Path(app.config['UPLOAD_FOLDER']) / filename
        file.save(str(dest))
        uploaded.append(filename)

    return jsonify({'uploaded': uploaded, 'errors': errors,
                    'message': f"{len(uploaded)} file(s) uploaded successfully."})


@app.route('/api/process', methods=['POST'])
def process_cvs():
    """Kick off the pipeline in a background thread."""
    global _pipeline_status
    if _pipeline_status['running']:
        return jsonify({'success': False, 'message': 'Pipeline already running'}), 409

    resume = request.json.get('resume', False) if request.is_json else False

    def run():
        global _pipeline_status
        _pipeline_status = {'running': True, 'message': 'Pipeline started…', 'progress': 0}
        try:
            from pipeline import run_pipeline
            run_pipeline(
                input_dir=app.config['UPLOAD_FOLDER'],
                output_dir=app.config['OUTPUT_FOLDER'],
                generate_emails=True,
                resume=resume,
            )
            # Sync new JSON files into SQLite
            cache_dir = Path(app.config['OUTPUT_FOLDER']) / 'raw_json'
            db.bulk_load_from_json_cache(str(cache_dir))
            load_candidates()
            _pipeline_status = {'running': False, 'message': 'Done', 'progress': 100}
        except Exception as e:
            _pipeline_status = {'running': False, 'message': f'Error: {e}', 'progress': 0}

    threading.Thread(target=run, daemon=True).start()
    return jsonify({'success': True, 'message': 'Processing started in background'})


@app.route('/api/process/status')
def process_status():
    return jsonify(_pipeline_status)



@app.route('/api/db/reanalyze', methods=['POST'])
def reanalyze_all():
    """Re-run analysis engine on all cached JSON files and update DB scores."""
    from core.analysis_engine import AnalysisEngine
    from core.llm_extractor import generate_candidate_summary
    cache_dir = Path(app.config['OUTPUT_FOLDER']) / 'raw_json'
    if not cache_dir.exists():
        return jsonify({'error': 'No raw_json cache found. Process CVs first.'}), 404

    engine = AnalysisEngine()
    updated = 0
    errors = []

    for json_file in sorted(cache_dir.glob('*.json')):
        try:
            import json as _json
            candidate = _json.loads(json_file.read_text(encoding='utf-8'))
            evaluation = engine.evaluate_candidate(candidate)
            summary = generate_candidate_summary(candidate, evaluation)
            evaluation['llm_summary'] = summary
            candidate['evaluation'] = evaluation
            # Save updated JSON back
            json_file.write_text(_json.dumps(candidate, indent=2, default=str), encoding='utf-8')
            # Update DB
            cid = candidate.get('candidate_id')
            if cid:
                db.update_evaluation(cid, evaluation)
            updated += 1
        except Exception as e:
            errors.append(f"{json_file.name}: {e}")

    load_candidates()
    return jsonify({'success': True, 'reanalyzed': updated, 'errors': errors})

@app.route('/api/db/migrate', methods=['POST'])
def migrate_db():
    """Manually trigger JSON cache → SQLite migration."""
    cache_dir = Path(app.config['OUTPUT_FOLDER']) / 'raw_json'
    if not cache_dir.exists():
        return jsonify({'error': 'No raw_json cache found'}), 404
    n = db.bulk_load_from_json_cache(str(cache_dir))
    load_candidates()
    return jsonify({'success': True, 'imported': n})


# ─────────────────────────────────────────────────────────────────────────────
# Routes — Export
# ─────────────────────────────────────────────────────────────────────────────

@app.route('/api/export')
def export():
    excel_path = Path(app.config['OUTPUT_FOLDER']) / 'TALASH_Candidates.xlsx'
    if excel_path.exists():
        return send_file(str(excel_path), as_attachment=True,
                         download_name='TALASH_Candidates.xlsx')
    return jsonify({'error': 'No export file found. Run the pipeline first.'}), 404


@app.route('/api/export/csv')
def export_csv():
    """Quick CSV export of candidate summary from DB."""
    import csv, io
    rows = db.get_all_candidates()
    fields = ['candidate_id', 'full_name', 'post_applied_for', 'department',
              'overall_score', 'education_score', 'research_score',
              'experience_score', 'skill_score', 'recommendation', 'created_at']
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fields, extrasaction='ignore')
    writer.writeheader()
    writer.writerows(rows)
    buf.seek(0)
    from flask import Response
    return Response(buf.getvalue(), mimetype='text/csv',
                    headers={'Content-Disposition': 'attachment; filename=TALASH_Summary.csv'})


# ─────────────────────────────────────────────────────────────────────────────
# Routes — Uploaded files listing
# ─────────────────────────────────────────────────────────────────────────────

@app.route('/api/uploads')
def list_uploads():
    upload_dir = Path(app.config['UPLOAD_FOLDER'])
    files = []
    for f in sorted(upload_dir.glob('*.pdf')):
        files.append({
            'name': f.name,
            'size_kb': round(f.stat().st_size / 1024, 1),
        })
    return jsonify(files)


@app.route('/api/uploads/<filename>', methods=['DELETE'])
def delete_upload(filename):
    path = Path(app.config['UPLOAD_FOLDER']) / secure_filename(filename)
    if path.exists():
        path.unlink()
        return jsonify({'success': True})
    return jsonify({'error': 'File not found'}), 404




# ─────────────────────────────────────────────────────────────────────────────
# Routes — Missing Information Emails (LLM-generated, SMTP-sendable)
# ─────────────────────────────────────────────────────────────────────────────

@app.route('/api/candidate/<candidate_id>/missing_email', methods=['GET'])
def get_missing_email(candidate_id):
    """Generate (or return cached) personalised missing-info email via LLM."""
    data = None
    for c in candidates_cache:
        if c.get('candidate_id') == candidate_id:
            data = c
            break
    if not data:
        raw = db.get_candidate_full(candidate_id)
        if raw:
            data = raw

    if not data:
        return jsonify({'error': 'Candidate not found'}), 404

    from utils.normalizer import detect_missing_fields
    missing = detect_missing_fields(data)
    name = data.get('personal_info', {}).get('full_name', 'Candidate')
    candidate_email = data.get('personal_info', {}).get('email') or ''

    if not missing:
        return jsonify({
            'candidate_id': candidate_id,
            'name': name,
            'missing_fields': [],
            'email_text': None,
            'message': 'No missing fields detected — profile appears complete.',
        })

    # Check cached email file
    output_dir = Path(app.config['OUTPUT_FOLDER'])
    email_file = output_dir / f"missing_email_{candidate_id}.txt"
    if email_file.exists():
        email_text = email_file.read_text(encoding='utf-8')
    else:
        build_fn, _, _ = _llm_email()
        email_text = build_fn(name, missing, candidate_email)
        email_file.write_text(email_text, encoding='utf-8')

    return jsonify({
        'candidate_id': candidate_id,
        'name': name,
        'candidate_email': candidate_email,
        'missing_fields': missing,
        'email_text': email_text,
    })


@app.route('/api/candidate/<candidate_id>/send_missing_email', methods=['POST'])
def send_missing_email(candidate_id):
    """Send the missing-info email via SMTP, or return draft if SMTP not set up."""
    body = request.get_json(silent=True) or {}
    to_address = body.get('to_email', '').strip()

    # Get candidate
    data = None
    for c in candidates_cache:
        if c.get('candidate_id') == candidate_id:
            data = c
            break
    if not data:
        raw = db.get_candidate_full(candidate_id)
        if raw:
            data = raw
    if not data:
        return jsonify({'error': 'Candidate not found'}), 404

    name = data.get('personal_info', {}).get('full_name', 'Candidate')
    if not to_address:
        to_address = data.get('personal_info', {}).get('email', '')

    # Get or generate email text
    output_dir = Path(app.config['OUTPUT_FOLDER'])
    email_file = output_dir / f"missing_email_{candidate_id}.txt"
    if email_file.exists():
        email_text = email_file.read_text(encoding='utf-8')
    else:
        from utils.normalizer import detect_missing_fields
        missing = detect_missing_fields(data)
        build_fn, _, _ = _llm_email()
        email_text = build_fn(name, missing, to_address)
        email_file.write_text(email_text, encoding='utf-8')

    _, _, send_fn = _llm_email()
    result = send_fn(to_address, email_text, name)
    return jsonify(result)


@app.route('/api/candidate/<candidate_id>/send_gap_email', methods=['POST'])
def send_gap_email_smtp(candidate_id):
    """Send the employment-gap clarification email via SMTP."""
    body = request.get_json(silent=True) or {}
    to_address = body.get('to_email', '').strip()

    data = None
    for c in candidates_cache:
        if c.get('candidate_id') == candidate_id:
            data = c
            break
    if not data:
        raw = db.get_candidate_full(candidate_id)
        if raw:
            data = raw
    if not data:
        return jsonify({'error': 'Candidate not found'}), 404

    name = data.get('personal_info', {}).get('full_name', 'Candidate')
    if not to_address:
        to_address = data.get('personal_info', {}).get('email', '')

    gap_email = (
        data.get('evaluation', {})
            .get('experience_analysis', {})
            .get('gap_email')
    )
    if not gap_email:
        return jsonify({'error': 'No gap email available for this candidate'}), 404

    _, _, send_fn = _llm_email()
    result = send_fn(to_address, gap_email, name)
    return jsonify(result)


# ─────────────────────────────────────────────────────────────────────────────
# Routes — LLM Candidate Summary
# ─────────────────────────────────────────────────────────────────────────────

@app.route('/api/candidate/<candidate_id>/summary', methods=['GET'])
def get_candidate_summary(candidate_id):
    """Generate an LLM narrative summary for the candidate."""
    data = None
    for c in candidates_cache:
        if c.get('candidate_id') == candidate_id:
            data = c
            break
    if not data:
        raw = db.get_candidate_full(candidate_id)
        if raw:
            data = raw
    if not data:
        return jsonify({'error': 'Candidate not found'}), 404

    evaluation = data.get('evaluation', {})
    output_dir = Path(app.config['OUTPUT_FOLDER'])
    summary_file = output_dir / f"summary_{candidate_id}.txt"

    force = request.args.get('refresh', 'false').lower() == 'true'
    if summary_file.exists() and not force:
        summary = summary_file.read_text(encoding='utf-8')
    else:
        _, gen_fn, _ = _llm_email()
        summary = gen_fn(data, evaluation)
        summary_file.write_text(summary, encoding='utf-8')

    return jsonify({
        'candidate_id': candidate_id,
        'name': data.get('personal_info', {}).get('full_name'),
        'overall_score': evaluation.get('overall_score', 0),
        'summary': summary,
    })


@app.route('/api/candidate/<candidate_id>/skills', methods=['GET'])
def get_candidate_skills(candidate_id):
    """Return detailed skill analysis for a candidate."""
    data = None
    for c in candidates_cache:
        if c.get('candidate_id') == candidate_id:
            data = c
            break
    if not data:
        raw = db.get_candidate_full(candidate_id)
        if raw:
            data = raw
    if not data:
        return jsonify({'error': 'Candidate not found'}), 404

    skill_analysis = data.get('evaluation', {}).get('skill_analysis', {})
    raw_skills = data.get('skills', [])
    return jsonify({
        'candidate_id': candidate_id,
        'raw_skills': raw_skills,
        'analysis': skill_analysis,
    })


# ─────────────────────────────────────────────────────────────────────────────
# Routes — Live Journal/Conference Verification
# ─────────────────────────────────────────────────────────────────────────────

@app.route('/api/verify/journal', methods=['POST'])
def verify_journal_live():
    """Live journal verification using Crossref + OpenAlex."""
    body = request.get_json(silent=True) or {}
    journal_name = body.get('journal_name', '').strip()
    issn = body.get('issn', '').strip()
    if not journal_name and not issn:
        return jsonify({'error': 'journal_name or issn required'}), 400

    try:
        from core.ranking_verifier import RankingVerifier
        rv = RankingVerifier(fast=False)   # live mode
        result = rv.verify_journal(journal_name or issn)
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/verify/university', methods=['POST'])
def verify_university_live():
    """Live university ranking lookup using QS/THE data from OpenAlex."""
    body = request.get_json(silent=True) or {}
    name = body.get('name', '').strip()
    if not name:
        return jsonify({'error': 'name required'}), 400

    try:
        from core.ranking_verifier import RankingVerifier
        rv = RankingVerifier(fast=False)
        result = rv.verify_institution(name)
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/verify/paper', methods=['POST'])
def verify_paper_live():
    """Verify paper existence via Crossref and Semantic Scholar."""
    body = request.get_json(silent=True) or {}
    title = body.get('title', '').strip()
    doi   = body.get('doi', '').strip()
    year  = body.get('year')
    if not title and not doi:
        return jsonify({'error': 'title or doi required'}), 400

    try:
        from core.verifiers import verify_paper_doi, verify_paper_semantic_scholar
        result = verify_paper_doi(title, doi, year)
        if not result.get('exists'):
            ss = verify_paper_semantic_scholar(title, year)
            result['semantic_scholar'] = ss
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/bulk_missing_emails', methods=['POST'])
def bulk_missing_emails():
    """Generate personalised missing-info emails for ALL candidates with missing data."""
    results = []
    output_dir = Path(app.config['OUTPUT_FOLDER'])
    build_fn, _, _ = _llm_email()

    from utils.normalizer import detect_missing_fields

    for c in candidates_cache:
        cid   = c.get('candidate_id', '')
        name  = c.get('personal_info', {}).get('full_name', 'Candidate')
        missing = detect_missing_fields(c)
        if not missing:
            results.append({'candidate_id': cid, 'name': name, 'status': 'complete'})
            continue

        email_file = output_dir / f"missing_email_{cid}.txt"
        if not email_file.exists():
            email_text = build_fn(name, missing)
            email_file.write_text(email_text, encoding='utf-8')

        results.append({
            'candidate_id': cid,
            'name': name,
            'missing_count': len(missing),
            'missing_fields': missing,
            'email_file': str(email_file),
            'status': 'generated',
        })

    return jsonify({'generated': len([r for r in results if r['status']=='generated']),
                    'results': results})


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)