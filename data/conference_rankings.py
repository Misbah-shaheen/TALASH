"""
CORE Conference Rankings
Source: https://portal.core.edu.au/conf-ranks/
"""
import re

CORE_RANKINGS = {
    'cvpr': 'A*', 'iccv': 'A*', 'eccv': 'A', 'bmvc': 'B', 'wacv': 'B',
    'neurips': 'A*', 'nips': 'A*', 'icml': 'A*', 'iclr': 'A*',
    'aistats': 'A', 'ecml': 'A', 'pakdd': 'A',
    'aaai': 'A*', 'ijcai': 'A*', 'uai': 'A',
    'acl': 'A*', 'emnlp': 'A*', 'naacl': 'A', 'coling': 'A', 'eacl': 'A',
    'icra': 'A', 'iros': 'A', 'rss': 'A*',
    'sigcomm': 'A*', 'mobicom': 'A*', 'infocom': 'A', 'nsdi': 'A*',
    'sigmod': 'A*', 'vldb': 'A*', 'icde': 'A', 'edbt': 'A',
    'chi': 'A*', 'uist': 'A', 'cscw': 'A*',
    'www': 'A*', 'sigir': 'A*', 'cikm': 'A', 'wsdm': 'A',
    'stoc': 'A*', 'focs': 'A*', 'soda': 'A*',
    'ccs': 'A*', 'usenix security': 'A*', 'ndss': 'A',
    'icse': 'A*', 'fse': 'A*', 'esec': 'A*', 'ase': 'A', 'issta': 'A',
    'osdi': 'A*', 'sosp': 'A*', 'eurosys': 'A',
    'kdd': 'A*', 'icdm': 'A', 'sdm': 'A',
    'icip': 'B', 'icassp': 'B',
    'inmic': 'C', 'ibcast': 'C', 'icosst': 'C', 'icet': 'C',
}

def get_core_rank(conference_name):
    """Returns CORE ranking (A*, A, B, C) for a conference."""
    if not conference_name:
        return 'Not Found'
    name_lower = str(conference_name).lower().strip()
    direct = CORE_RANKINGS.get(name_lower)
    if direct:
        return direct
    for key, rank in CORE_RANKINGS.items():
        if re.search(r'\b' + re.escape(key) + r'\b', name_lower):
            return rank
    return 'Not in CORE'

def is_a_star(conference_name):
    """Returns True if conference is A* ranked."""
    rank = get_core_rank(conference_name)
    return rank == 'A*'

def get_conference_maturity(conference_name):
    """Extract conference edition/maturity from name."""
    if not conference_name:
        return {'edition': None, 'is_mature': False}
    match = re.search(r'(\d+)(?:st|nd|rd|th)\s+(?:international|annual)', 
                      str(conference_name).lower())
    if match:
        edition = int(match.group(1))
        return {'edition': edition, 'is_mature': edition >= 10}
    return {'edition': None, 'is_mature': False}