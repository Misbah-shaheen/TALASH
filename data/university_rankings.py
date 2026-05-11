"""
University Rankings from QS and THE
Sources: topuniversities.com, timeshighereducation.com
"""

UNIVERSITY_RANKINGS = {
    'mit': {'qs': 1, 'the': 2},
    'massachusetts institute of technology': {'qs': 1, 'the': 2},
    'cambridge': {'qs': 2, 'the': 5},
    'university of cambridge': {'qs': 2, 'the': 5},
    'oxford': {'qs': 3, 'the': 1},
    'university of oxford': {'qs': 3, 'the': 1},
    'stanford': {'qs': 5, 'the': 3},
    'harvard': {'qs': 4, 'the': 4},
    'imperial college': {'qs': 8, 'the': 8},
    'eth zurich': {'qs': 7, 'the': 11},
    'ucl': {'qs': 9, 'the': 22},
    'carnegie mellon': {'qs': 52, 'the': 24},
    'university of toronto': {'qs': 21, 'the': 21},
    'tsinghua university': {'qs': 25, 'the': 12},
    'peking university': {'qs': 17, 'the': 14},
    'national university of singapore': {'qs': 8, 'the': 19},
    'nus': {'qs': 8, 'the': 19},
    'nust': {'qs': 334, 'the': None},
    'national university of sciences and technology': {'qs': 334, 'the': None},
    'lums': {'qs': 651, 'the': None},
    'fast': {'qs': 1001, 'the': None},
    'comsats': {'qs': 751, 'the': None},
    'uet lahore': {'qs': 601, 'the': None},
    'punjab university': {'qs': 801, 'the': None},
    'quaid-i-azam university': {'qs': 801, 'the': None},
    'pieas': {'qs': 701, 'the': None},
}

def get_university_rank(institution_name):
    """Returns QS and THE rankings — local DB first, then OpenAlex live lookup."""
    default = {'qs_rank': None, 'the_rank': None, 'source': 'Not in Dataset'}
    if not institution_name:
        return default
    name_lower = str(institution_name).lower().strip()
    if name_lower in UNIVERSITY_RANKINGS:
        r = UNIVERSITY_RANKINGS[name_lower]
        return {'qs_rank': r['qs'], 'the_rank': r['the'], 'source': 'QS/THE Dataset'}
    # Partial matching
    for key, r in UNIVERSITY_RANKINGS.items():
        if key in name_lower or name_lower in key:
            return {'qs_rank': r['qs'], 'the_rank': r['the'], 'source': 'Partial Match'}

    # Live OpenAlex institution lookup
    try:
        import requests, urllib.parse, time
        query = urllib.parse.quote(institution_name)
        url = f"https://api.openalex.org/institutions?search={query}&per-page=1"
        r = requests.get(url, timeout=10, headers={"User-Agent": "TALASH-NUST/2.0"})
        if r.status_code == 200:
            results = r.json().get("results", [])
            if results:
                inst = results[0]
                works = inst.get("works_count", 0)
                cited = inst.get("cited_by_count", 0)
                country = inst.get("country_code", "")
                time.sleep(0.3)
                return {
                    'qs_rank': None,
                    'the_rank': None,
                    'source': 'OpenAlex Live',
                    'openalex_works': works,
                    'openalex_citations': cited,
                    'country': country,
                    'openalex_name': inst.get("display_name", ""),
                }
    except Exception:
        pass

    return default

def get_institution_quality(institution_name):
    """Get human-readable institution quality assessment."""
    ranks = get_university_rank(institution_name)
    qs = ranks['qs_rank']
    if qs and qs <= 100:
        return "World Top 100 University"
    elif qs and qs <= 500:
        return "World Top 500 University"
    elif qs and qs <= 1000:
        return "World Top 1000 University"
    elif institution_name:
        return "Regional/National University"
    return "Unknown"