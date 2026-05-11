"""
Ranking Verifier - Integrates all external ranking sources
Per spec: "Do not take journal ranking information from CV, verify it from the sources"

Now includes:
  - Local DB (fast, offline)
  - Crossref DOI/title lookup (paper existence)
  - Semantic Scholar (citation count, existence)
  - OpenAlex (live impact factor)
  - Beall's predatory list (full embedded)
  - HEC journal list (Pakistan)
  - Lens.org patent lookup
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.conference_rankings import get_core_rank, is_a_star, get_conference_maturity
from data.journal_database import lookup_journal
from data.university_rankings import get_university_rank, get_institution_quality

# Import new verifiers
try:
    from core.verifiers import (
        verify_paper_doi,
        verify_paper_semantic_scholar,
        get_live_impact_factor,
        check_predatory,
        check_hec_journal,
        check_hec_university,
        verify_patent,
    )
    _VERIFIERS_AVAILABLE = True
except ImportError:
    _VERIFIERS_AVAILABLE = False
    print("[RankingVerifier] WARNING: core/verifiers.py not found — online verification disabled")


class RankingVerifier:
    """
    Verifies rankings from local DB + live APIs.
    fast=True  -> local DB + offline checks only (used during bulk pipeline)
    fast=False -> also calls Crossref, Semantic Scholar, OpenAlex (deep verify)
    """

    def __init__(self, fast: bool = True):
        self.fast = fast

    # ── Journal ───────────────────────────────────────────────────────────────

    def verify_journal(self, journal_name, claimed_if=None):
        result = lookup_journal(journal_name)

        # Predatory check (offline, Beall's list embedded)
        if _VERIFIERS_AVAILABLE:
            pred = check_predatory(journal_name)
            result['predatory']        = pred['is_predatory']
            result['predatory_detail'] = pred
            if pred['is_predatory']:
                result['quality_assessment'] = "PREDATORY - Do not count"
            elif pred.get('warning'):
                result['predatory_warning'] = pred['warning']

        # HEC check (offline, embedded list)
        if _VERIFIERS_AVAILABLE:
            hec = check_hec_journal(journal_name)
            result['hec_recognized']  = hec['hec_recognized']
            result['hec_category']    = hec['hec_category']
            result['hec_description'] = hec['hec_description']

        # Quality label from local DB
        if not result.get('predatory'):
            if result['wos_indexed'] and result.get('quartile') == 'Q1':
                result['quality_assessment'] = "Excellent - Top Tier Journal"
            elif result['wos_indexed'] and result.get('quartile') == 'Q2':
                result['quality_assessment'] = "Good - Well Respected Journal"
            elif result['scopus_indexed']:
                result['quality_assessment'] = "Acceptable - Scopus Indexed"
            elif result.get('hec_recognized'):
                result['quality_assessment'] = f"HEC Recognized ({result.get('hec_category','')})"
            else:
                result['quality_assessment'] = "Unverified - Needs Manual Check"

        # IF mismatch vs local DB
        if claimed_if and result.get('impact_factor'):
            try:
                if abs(float(claimed_if) - float(result['impact_factor'])) > 1.0:
                    result['if_mismatch'] = True
                    result['quality_assessment'] += " (IF discrepancy detected)"
            except (TypeError, ValueError):
                pass

        # Online enrichment (slow — only when fast=False)
        if not self.fast and _VERIFIERS_AVAILABLE:
            try:
                oa = get_live_impact_factor(journal_name, issn=result.get('issn'))
                result['openalex'] = oa
                if oa.get('found'):
                    live_if = oa.get('2yr_mean_citedness')
                    result['live_impact_factor'] = live_if
                    result['h_index']   = oa.get('h_index')
                    result['is_in_doaj'] = oa.get('is_in_doaj')
                    if claimed_if and live_if:
                        diff = abs(float(claimed_if) - float(live_if))
                        if diff > 1.5:
                            result['if_mismatch'] = True
                            result['quality_assessment'] += f" (Live IF={round(live_if,2)} vs claimed {claimed_if})"
            except Exception as e:
                result['openalex_error'] = str(e)

        return result

    # ── Paper existence ───────────────────────────────────────────────────────

    def verify_paper_exists(self, title, doi=None, year=None):
        """Crossref + Semantic Scholar check. Only runs when fast=False."""
        result = {'overall_exists': False, 'crossref': None,
                  'semantic_scholar': None, 'flags': [], 'citation_count': 0}
        if not _VERIFIERS_AVAILABLE or self.fast:
            return result
        try:
            cr = verify_paper_doi(title, doi, year)
            result['crossref'] = cr
            if cr.get('exists'):
                result['overall_exists'] = True
            if cr.get('flag'):
                result['flags'].append(cr['flag'])
        except Exception as e:
            result['flags'].append(f'Crossref error: {e}')
        try:
            ss = verify_paper_semantic_scholar(title, year)
            result['semantic_scholar'] = ss
            if ss.get('found'):
                result['overall_exists'] = True
                result['citation_count'] = ss.get('citation_count', 0)
            if ss.get('flag') and '❌' in ss.get('flag', ''):
                result['flags'].append(ss['flag'])
        except Exception as e:
            result['flags'].append(f'Semantic Scholar error: {e}')
        return result

    # ── Conference ────────────────────────────────────────────────────────────

    def verify_conference(self, conference_name):
        result = {
            'core_rank': get_core_rank(conference_name),
            'is_a_star': is_a_star(conference_name),
            'maturity':  get_conference_maturity(conference_name),
        }
        if result['is_a_star']:
            result['quality_assessment'] = "Excellent - A* Conference"
        elif result['core_rank'] == 'A':
            result['quality_assessment'] = "Very Good - A Rank Conference"
        elif result['core_rank'] == 'B':
            result['quality_assessment'] = "Good - B Rank Conference"
        elif result['core_rank'] == 'C':
            result['quality_assessment'] = "Average - C Rank Conference"
        else:
            result['quality_assessment'] = "Unverified - Not in CORE Rankings"
        if result['maturity'].get('is_mature'):
            result['quality_assessment'] += " (Mature Conference Series)"
        return result

    # ── Institution ───────────────────────────────────────────────────────────

    def verify_institution(self, institution_name):
        result = get_university_rank(institution_name)
        result['quality_label'] = get_institution_quality(institution_name)
        if _VERIFIERS_AVAILABLE:
            hec_uni = check_hec_university(institution_name)
            result['hec_recognized'] = hec_uni['hec_recognized']
            if hec_uni['hec_recognized'] and not result.get('qs_rank'):
                result['quality_label'] = 'HEC Recognized Pakistani University'

        # If not in local DB and fast=False, try live OpenAlex institution lookup
        if not self.fast and not result.get('qs_rank'):
            try:
                import urllib.parse, requests, time
                query = urllib.parse.quote(institution_name)
                url = f"https://api.openalex.org/institutions?search={query}&per-page=1"
                r = requests.get(url, timeout=10,
                                 headers={'User-Agent': 'TALASH-NUST/2.0'})
                if r.status_code == 200:
                    data = r.json()
                    results = data.get('results', [])
                    if results:
                        inst = results[0]
                        ror = inst.get('ror', '')
                        country = inst.get('country_code', '')
                        works_count = inst.get('works_count', 0)
                        cited_count = inst.get('cited_by_count', 0)
                        result['openalex_found'] = True
                        result['openalex_country'] = country
                        result['openalex_works'] = works_count
                        result['openalex_citations'] = cited_count
                        result['openalex_ror'] = ror
                        if not result.get('quality_label'):
                            result['quality_label'] = (
                                'Verified Institution (OpenAlex)' if works_count > 100
                                else 'Small/Emerging Institution'
                            )
                time.sleep(0.3)
            except Exception as e:
                result['openalex_error'] = str(e)

        return result

    # ── Patent ────────────────────────────────────────────────────────────────

    def verify_patent(self, patent: dict) -> dict:
        """
        fast=True  -> format validation + Google Patents URL only
        fast=False -> Lens.org lookup for real existence check
        """
        import re, urllib.parse
        patent_number = str(patent.get('patent_number', '')).strip().upper().replace(' ', '')
        title = patent.get('patent_title') or patent.get('title', '')

        valid_patterns = [
            r'^[A-Z]{2}\d{5,}[A-Z]?\d?$',
            r'^[A-Z]{2}\d{4}/\d+$',
            r'^\d{5,}$',
            r'^GE\d{6}[A-Z]?$',
        ]
        is_valid_fmt = bool(patent_number and any(
            re.match(p, patent_number) for p in valid_patterns
        ))
        gp_url = (
            f'https://patents.google.com/patent/{urllib.parse.quote(patent_number)}'
            if patent_number else None
        )

        if self.fast or not _VERIFIERS_AVAILABLE:
            return {
                'found': None,
                'patent_number': patent_number,
                'number_valid_format': is_valid_fmt,
                'google_patents_url': gp_url,
                'flag': None if is_valid_fmt else f'Non-standard format: {patent_number}',
                'method': 'Format check only',
            }

        result = verify_patent(patent_number=patent_number, title=title,
                               inventor=patent.get('inventors', ''))
        result['number_valid_format'] = is_valid_fmt
        if gp_url and not result.get('google_patents_url'):
            result['google_patents_url'] = gp_url
        return result
