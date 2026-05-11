"""
rescore_fast.py  —  Re-score all candidates locally (no LLM calls).
Place this file inside your talash_out folder, then run from ANYWHERE:

    python path/to/talash_out/rescore_fast.py
    OR (from inside talash_out):
    python rescore_fast.py

"""

import sys
import os

# ── Locate the folder that contains core/ ────────────────────────────────────
_HERE = os.path.dirname(os.path.abspath(__file__))

if os.path.isdir(os.path.join(_HERE, "core")):
    # Script is sitting right next to core/ (e.g. inside talash_out/)
    TALASH_OUT = _HERE
elif os.path.isdir(os.path.join(_HERE, "talash_out", "core")):
    # Script is one level above talash_out/ (e.g. inside output/)
    TALASH_OUT = os.path.join(_HERE, "talash_out")
else:
    print("ERROR: Cannot find the 'core' package.\n"
          f"  Searched: {_HERE}  and  {os.path.join(_HERE, 'talash_out')}\n"
          "  Move rescore_fast.py into the folder that contains core/")
    sys.exit(1)

if TALASH_OUT not in sys.path:
    sys.path.insert(0, TALASH_OUT)

os.environ.setdefault("TALASH_DB", os.path.join(TALASH_OUT, "talash.db"))
# ─────────────────────────────────────────────────────────────────────────────

import json
import time

# ── Kill ALL Gemini/LLM calls so rescoring is instant ────────────────────────
import core.llm_extractor as _llm
import core.analysis_engine as _ae

def _noop(*args, **kwargs):
    return ""

_llm.call_llm      = _noop   # used by analyze_skills & _draft_gap_email
_ae._call_gemini   = _noop   # used by analyze_topic_variability & analyze_skills
# ─────────────────────────────────────────────────────────────────────────────

from core.analysis_engine import AnalysisEngine
import database as db


def rescore_all():
    engine = AnalysisEngine()

    # Load every candidate from SQLite
    with db.get_conn() as conn:
        rows = conn.execute("SELECT candidate_id, raw_json FROM candidates").fetchall()

    if not rows:
        print("No candidates found in the database. Run the pipeline first.")
        return

    total   = len(rows)
    updated = 0
    failed  = 0

    print(f"Re-scoring {total} candidates (no LLM calls)…\n")

    for i, row in enumerate(rows, 1):
        cid = row["candidate_id"]
        raw = row["raw_json"]

        if not raw:
            print(f"  [{i}/{total}] {cid} — SKIP (no raw JSON)")
            failed += 1
            continue

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            print(f"  [{i}/{total}] {cid} — SKIP (bad JSON: {e})")
            failed += 1
            continue

        try:
            t0         = time.time()
            evaluation = engine.evaluate_candidate(data)
            elapsed    = time.time() - t0

            db.update_evaluation(cid, evaluation)
            score = evaluation.get("overall_score", 0)
            name  = evaluation.get("full_name") or cid
            print(f"  [{i}/{total}] {name:<35} score={score:5.1f}  ({elapsed:.2f}s)")
            updated += 1

        except Exception as e:
            print(f"  [{i}/{total}] {cid} — ERROR: {e}")
            failed += 1

    print(f"\nDone. Updated: {updated}  |  Failed/Skipped: {failed}  |  Total: {total}")
    print("Refresh your browser — scores are live.")


if __name__ == "__main__":
    rescore_all()