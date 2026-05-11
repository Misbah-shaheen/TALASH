"""
Free public APIs for supplementary journal verification.
Sources: DOAJ, Crossref, OpenAlex - No authentication required.
"""

import time
import requests

_session = requests.Session()
_session.headers.update({'User-Agent': 'TALASH-AcademicProject/1.0'})
_cache = {}

def _get(url, params=None):
    key = str(url) + str(sorted((params or {}).items()))
    if key in _cache:
        return _cache[key]
    try:
        r = _session.get(url, params=params, timeout=10)
        if r.status_code == 200:
            data = r.json()
            _cache[key] = data
            time.sleep(0.5)
            return data
    except Exception:
        pass
    return None

def check_doaj(journal_name, issn=None):
    """Check DOAJ for open access journals."""
    query = f'issn:{issn}' if issn else f'title:"{journal_name}"'
    data = _get('https://doaj.org/api/v2/search/journals', {'q': query, 'page_size': 1})
    if data and data.get('results'):
        bib = data['results'][0].get('bibjson', {})
        issns = bib.get('identifier', [])
        issn_val = next((i.get('id') for i in issns if i.get('type') == 'pissn'), None)
        return {'found': True, 'publisher': bib.get('publisher', {}).get('name'), 'issn': issn_val}
    return {'found': False}

def check_crossref(journal_name, issn=None):
    """Check Crossref for publisher metadata."""
    params = {'query': journal_name, 'rows': 1, 'select': 'publisher,ISSN'}
    if issn:
        params['filter'] = f'issn:{issn}'
    data = _get('https://api.crossref.org/works', params)
    if data and data.get('message', {}).get('items'):
        item = data['message']['items'][0]
        issns = item.get('ISSN', [])
        return {'found': True, 'publisher': item.get('publisher'), 'issn': issns[0] if issns else None}
    return {'found': False}

def verify_journal_apis(journal_name, issn=None):
    """Verify journal using free APIs."""
    result = {'doaj_indexed': False, 'crossref_found': False, 'publisher': None}
    doaj = check_doaj(journal_name, issn)
    if doaj['found']:
        result['doaj_indexed'] = True
        result['publisher'] = doaj.get('publisher')
    cr = check_crossref(journal_name, issn)
    if cr['found']:
        result['crossref_found'] = True
        if not result['publisher']:
            result['publisher'] = cr.get('publisher')
    return result