"""
Journal Database - WoS/Scopus indexed journals with quartile and impact factor data.
Sources: mjl.clarivate.com, scopus, scimago
Note: Per spec - do NOT trust IF from CV, verify from this source.
"""

import re

# Journal database: key = lowercase journal name / common abbreviation
# Fields: wos_indexed, scopus_indexed, quartile, impact_factor, predatory, issn
JOURNAL_DB = {
    # ── IEEE Journals ──────────────────────────────────────────────────────────
    "ieee transactions on neural networks and learning systems": {
        "wos_indexed": True, "scopus_indexed": True, "quartile": "Q1", "impact_factor": 10.4, "predatory": False, "issn": "2162-237X"
    },
    "ieee transactions on image processing": {
        "wos_indexed": True, "scopus_indexed": True, "quartile": "Q1", "impact_factor": 10.6, "predatory": False, "issn": "1057-7149"
    },
    "ieee transactions on pattern analysis and machine intelligence": {
        "wos_indexed": True, "scopus_indexed": True, "quartile": "Q1", "impact_factor": 23.6, "predatory": False, "issn": "0162-8828"
    },
    "ieee transactions on signal processing": {
        "wos_indexed": True, "scopus_indexed": True, "quartile": "Q1", "impact_factor": 4.9, "predatory": False, "issn": "1053-587X"
    },
    "ieee transactions on communications": {
        "wos_indexed": True, "scopus_indexed": True, "quartile": "Q1", "impact_factor": 5.6, "predatory": False, "issn": "0090-6778"
    },
    "ieee transactions on wireless communications": {
        "wos_indexed": True, "scopus_indexed": True, "quartile": "Q1", "impact_factor": 8.9, "predatory": False, "issn": "1536-1276"
    },
    "ieee transactions on vehicular technology": {
        "wos_indexed": True, "scopus_indexed": True, "quartile": "Q1", "impact_factor": 6.5, "predatory": False, "issn": "0018-9545"
    },
    "ieee transactions on industrial electronics": {
        "wos_indexed": True, "scopus_indexed": True, "quartile": "Q1", "impact_factor": 7.7, "predatory": False, "issn": "0278-0046"
    },
    "ieee transactions on power electronics": {
        "wos_indexed": True, "scopus_indexed": True, "quartile": "Q1", "impact_factor": 6.7, "predatory": False, "issn": "0885-8993"
    },
    "ieee transactions on smart grid": {
        "wos_indexed": True, "scopus_indexed": True, "quartile": "Q1", "impact_factor": 9.6, "predatory": False, "issn": "1949-3053"
    },
    "ieee transactions on cybernetics": {
        "wos_indexed": True, "scopus_indexed": True, "quartile": "Q1", "impact_factor": 11.8, "predatory": False, "issn": "2168-2267"
    },
    "ieee transactions on knowledge and data engineering": {
        "wos_indexed": True, "scopus_indexed": True, "quartile": "Q1", "impact_factor": 8.9, "predatory": False, "issn": "1041-4347"
    },
    "ieee transactions on information forensics and security": {
        "wos_indexed": True, "scopus_indexed": True, "quartile": "Q1", "impact_factor": 6.8, "predatory": False, "issn": "1556-6013"
    },
    "ieee access": {
        "wos_indexed": True, "scopus_indexed": True, "quartile": "Q2", "impact_factor": 3.9, "predatory": False, "issn": "2169-3536"
    },
    "ieee internet of things journal": {
        "wos_indexed": True, "scopus_indexed": True, "quartile": "Q1", "impact_factor": 10.6, "predatory": False, "issn": "2327-4662"
    },
    "ieee communications letters": {
        "wos_indexed": True, "scopus_indexed": True, "quartile": "Q2", "impact_factor": 3.7, "predatory": False, "issn": "1089-7798"
    },
    "ieee signal processing letters": {
        "wos_indexed": True, "scopus_indexed": True, "quartile": "Q2", "impact_factor": 3.9, "predatory": False, "issn": "1070-9908"
    },
    "ieee sensors journal": {
        "wos_indexed": True, "scopus_indexed": True, "quartile": "Q2", "impact_factor": 4.3, "predatory": False, "issn": "1530-437X"
    },
    "ieee geoscience and remote sensing letters": {
        "wos_indexed": True, "scopus_indexed": True, "quartile": "Q2", "impact_factor": 4.0, "predatory": False, "issn": "1545-598X"
    },
    "ieee transactions on geoscience and remote sensing": {
        "wos_indexed": True, "scopus_indexed": True, "quartile": "Q1", "impact_factor": 8.2, "predatory": False, "issn": "0196-2892"
    },
    "ieee transactions on antennas and propagation": {
        "wos_indexed": True, "scopus_indexed": True, "quartile": "Q1", "impact_factor": 5.7, "predatory": False, "issn": "0018-926X"
    },
    "ieee transactions on microwave theory and techniques": {
        "wos_indexed": True, "scopus_indexed": True, "quartile": "Q1", "impact_factor": 4.3, "predatory": False, "issn": "0018-9480"
    },
    "ieee communications magazine": {
        "wos_indexed": True, "scopus_indexed": True, "quartile": "Q1", "impact_factor": 9.0, "predatory": False, "issn": "0163-6804"
    },
    "ieee network": {
        "wos_indexed": True, "scopus_indexed": True, "quartile": "Q1", "impact_factor": 9.3, "predatory": False, "issn": "0890-8044"
    },

    # ── Elsevier Journals ──────────────────────────────────────────────────────
    "expert systems with applications": {
        "wos_indexed": True, "scopus_indexed": True, "quartile": "Q1", "impact_factor": 8.5, "predatory": False, "issn": "0957-4174"
    },
    "pattern recognition": {
        "wos_indexed": True, "scopus_indexed": True, "quartile": "Q1", "impact_factor": 8.0, "predatory": False, "issn": "0031-3203"
    },
    "pattern recognition letters": {
        "wos_indexed": True, "scopus_indexed": True, "quartile": "Q2", "impact_factor": 3.9, "predatory": False, "issn": "0167-8655"
    },
    "neural networks": {
        "wos_indexed": True, "scopus_indexed": True, "quartile": "Q1", "impact_factor": 7.8, "predatory": False, "issn": "0893-6080"
    },
    "neurocomputing": {
        "wos_indexed": True, "scopus_indexed": True, "quartile": "Q1", "impact_factor": 6.0, "predatory": False, "issn": "0925-2312"
    },
    "computers and electrical engineering": {
        "wos_indexed": True, "scopus_indexed": True, "quartile": "Q2", "impact_factor": 4.0, "predatory": False, "issn": "0045-7906"
    },
    "applied soft computing": {
        "wos_indexed": True, "scopus_indexed": True, "quartile": "Q1", "impact_factor": 8.7, "predatory": False, "issn": "1568-4946"
    },
    "knowledge-based systems": {
        "wos_indexed": True, "scopus_indexed": True, "quartile": "Q1", "impact_factor": 8.8, "predatory": False, "issn": "0950-7051"
    },
    "information sciences": {
        "wos_indexed": True, "scopus_indexed": True, "quartile": "Q1", "impact_factor": 8.1, "predatory": False, "issn": "0020-0255"
    },
    "future generation computer systems": {
        "wos_indexed": True, "scopus_indexed": True, "quartile": "Q1", "impact_factor": 7.5, "predatory": False, "issn": "0167-739X"
    },
    "computer networks": {
        "wos_indexed": True, "scopus_indexed": True, "quartile": "Q1", "impact_factor": 5.6, "predatory": False, "issn": "1389-1286"
    },
    "signal processing": {
        "wos_indexed": True, "scopus_indexed": True, "quartile": "Q2", "impact_factor": 4.4, "predatory": False, "issn": "0165-1684"
    },
    "biomedical signal processing and control": {
        "wos_indexed": True, "scopus_indexed": True, "quartile": "Q2", "impact_factor": 5.1, "predatory": False, "issn": "1746-8094"
    },
    "electric power systems research": {
        "wos_indexed": True, "scopus_indexed": True, "quartile": "Q2", "impact_factor": 3.9, "predatory": False, "issn": "0378-7796"
    },
    "renewable energy": {
        "wos_indexed": True, "scopus_indexed": True, "quartile": "Q1", "impact_factor": 9.0, "predatory": False, "issn": "0960-1481"
    },
    "energy conversion and management": {
        "wos_indexed": True, "scopus_indexed": True, "quartile": "Q1", "impact_factor": 11.5, "predatory": False, "issn": "0196-8904"
    },
    "measurement": {
        "wos_indexed": True, "scopus_indexed": True, "quartile": "Q2", "impact_factor": 5.6, "predatory": False, "issn": "0263-2241"
    },

    # ── Springer / Nature Journals ─────────────────────────────────────────────
    "machine learning": {
        "wos_indexed": True, "scopus_indexed": True, "quartile": "Q2", "impact_factor": 4.9, "predatory": False, "issn": "0885-6125"
    },
    "neural computing and applications": {
        "wos_indexed": True, "scopus_indexed": True, "quartile": "Q2", "impact_factor": 6.0, "predatory": False, "issn": "0941-0643"
    },
    "soft computing": {
        "wos_indexed": True, "scopus_indexed": True, "quartile": "Q2", "impact_factor": 3.9, "predatory": False, "issn": "1432-7643"
    },
    "wireless networks": {
        "wos_indexed": True, "scopus_indexed": True, "quartile": "Q2", "impact_factor": 3.0, "predatory": False, "issn": "1022-0038"
    },
    "wireless personal communications": {
        "wos_indexed": True, "scopus_indexed": True, "quartile": "Q3", "impact_factor": 1.9, "predatory": False, "issn": "0929-6212"
    },
    "journal of network and computer applications": {
        "wos_indexed": True, "scopus_indexed": True, "quartile": "Q1", "impact_factor": 8.7, "predatory": False, "issn": "1084-8045"
    },
    "cluster computing": {
        "wos_indexed": True, "scopus_indexed": True, "quartile": "Q2", "impact_factor": 4.4, "predatory": False, "issn": "1386-7857"
    },
    "multimedia tools and applications": {
        "wos_indexed": True, "scopus_indexed": True, "quartile": "Q2", "impact_factor": 3.6, "predatory": False, "issn": "1380-7501"
    },
    "journal of supercomputing": {
        "wos_indexed": True, "scopus_indexed": True, "quartile": "Q2", "impact_factor": 3.3, "predatory": False, "issn": "0920-8542"
    },

    # ── MDPI Journals ──────────────────────────────────────────────────────────
    "sensors": {
        "wos_indexed": True, "scopus_indexed": True, "quartile": "Q2", "impact_factor": 3.9, "predatory": False, "issn": "1424-8220"
    },
    "electronics": {
        "wos_indexed": True, "scopus_indexed": True, "quartile": "Q2", "impact_factor": 2.9, "predatory": False, "issn": "2079-9292"
    },
    "applied sciences": {
        "wos_indexed": True, "scopus_indexed": True, "quartile": "Q2", "impact_factor": 2.7, "predatory": False, "issn": "2076-3417"
    },
    "mathematics": {
        "wos_indexed": True, "scopus_indexed": True, "quartile": "Q1", "impact_factor": 2.4, "predatory": False, "issn": "2227-7390"
    },
    "energies": {
        "wos_indexed": True, "scopus_indexed": True, "quartile": "Q3", "impact_factor": 3.2, "predatory": False, "issn": "1996-1073"
    },
    "remote sensing": {
        "wos_indexed": True, "scopus_indexed": True, "quartile": "Q1", "impact_factor": 5.0, "predatory": False, "issn": "2072-4292"
    },
    "symmetry": {
        "wos_indexed": True, "scopus_indexed": True, "quartile": "Q2", "impact_factor": 2.7, "predatory": False, "issn": "2073-8994"
    },

    # ── Other Major Journals ───────────────────────────────────────────────────
    "nature": {
        "wos_indexed": True, "scopus_indexed": True, "quartile": "Q1", "impact_factor": 64.8, "predatory": False, "issn": "0028-0836"
    },
    "science": {
        "wos_indexed": True, "scopus_indexed": True, "quartile": "Q1", "impact_factor": 56.9, "predatory": False, "issn": "0036-8075"
    },
    "nature communications": {
        "wos_indexed": True, "scopus_indexed": True, "quartile": "Q1", "impact_factor": 16.6, "predatory": False, "issn": "2041-1723"
    },
    "plos one": {
        "wos_indexed": True, "scopus_indexed": True, "quartile": "Q2", "impact_factor": 3.7, "predatory": False, "issn": "1932-6203"
    },
    "scientific reports": {
        "wos_indexed": True, "scopus_indexed": True, "quartile": "Q2", "impact_factor": 4.6, "predatory": False, "issn": "2045-2322"
    },
    "journal of cleaner production": {
        "wos_indexed": True, "scopus_indexed": True, "quartile": "Q1", "impact_factor": 11.1, "predatory": False, "issn": "0959-6526"
    },
    "acm computing surveys": {
        "wos_indexed": True, "scopus_indexed": True, "quartile": "Q1", "impact_factor": 16.6, "predatory": False, "issn": "0360-0300"
    },

    # ── Known Predatory / Low Quality ─────────────────────────────────────────
    "international journal of advanced computer science and applications": {
        "wos_indexed": False, "scopus_indexed": False, "quartile": None, "impact_factor": None, "predatory": True, "issn": "2158-107X"
    },
    "international journal of engineering and technology": {
        "wos_indexed": False, "scopus_indexed": False, "quartile": None, "impact_factor": None, "predatory": True, "issn": None
    },
    "world applied sciences journal": {
        "wos_indexed": False, "scopus_indexed": False, "quartile": None, "impact_factor": None, "predatory": True, "issn": "1818-4952"
    },
}


def lookup_journal(journal_name: str) -> dict:
    """
    Look up a journal by name and return its indexing/quality info.
    Returns a dict with: wos_indexed, scopus_indexed, quartile,
    impact_factor, predatory, issn, source, quality_assessment
    """
    default = {
        "wos_indexed": False,
        "scopus_indexed": False,
        "quartile": None,
        "impact_factor": None,
        "predatory": False,
        "issn": None,
        "source": "Not in Local DB",
        "quality_assessment": "Unverified - Needs Manual Check",
        "doaj_indexed": False,
        "crossref_found": False,
    }

    if not journal_name:
        return default

    name_lower = str(journal_name).lower().strip()
    # Remove common noise
    name_lower = re.sub(r'\(.*?\)', '', name_lower).strip()

    # Exact match
    if name_lower in JOURNAL_DB:
        entry = dict(JOURNAL_DB[name_lower])
        entry["source"] = "Local DB - Exact Match"
        entry.setdefault("doaj_indexed", False)
        entry.setdefault("crossref_found", False)
        return entry

    # Partial match — journal name is contained in key or vice versa
    for key, data in JOURNAL_DB.items():
        if key in name_lower or name_lower in key:
            entry = dict(data)
            entry["source"] = "Local DB - Partial Match"
            entry.setdefault("doaj_indexed", False)
            entry.setdefault("crossref_found", False)
            return entry

    # Keyword-based heuristics — record baseline but still try OpenAlex for live IF
    heuristic_result = None
    if "ieee transactions on" in name_lower or "ieee journal" in name_lower:
        heuristic_result = {**default,
                "wos_indexed": True, "scopus_indexed": True,
                "quartile": "Q1", "source": "Heuristic - IEEE Transactions"}
    elif "ieee" in name_lower:
        heuristic_result = {**default,
                "wos_indexed": True, "scopus_indexed": True,
                "quartile": "Q2", "source": "Heuristic - IEEE"}
    elif any(k in name_lower for k in ["elsevier", "springer", "wiley", "taylor & francis", "sage"]):
        heuristic_result = {**default,
                "wos_indexed": True, "scopus_indexed": True,
                "quartile": "Q2", "source": "Heuristic - Major Publisher"}
    elif "mdpi" in name_lower:
        heuristic_result = {**default,
                "scopus_indexed": True,
                "quartile": "Q3", "source": "Heuristic - MDPI"}

    # ── Live OpenAlex lookup — runs for ALL journals (enriches heuristic hits too) ────
    try:
        import requests, time
        url = "https://api.openalex.org/sources"
        params = {"search": journal_name, "per_page": 3}
        r = requests.get(url, params=params, timeout=10,
                         headers={"User-Agent": "TALASH-NUST/2.0"})
        if r.status_code == 200:
            items = r.json().get("results", [])
            if items:
                item = items[0]
                stats = item.get("summary_stats", {})
                live_if = stats.get("2yr_mean_citedness")
                is_oa = item.get("is_in_doaj", False)
                works = item.get("works_count", 0)
                # Start from heuristic baseline if available, else default
                oa_result = {**(heuristic_result if heuristic_result else default)}
                oa_result["source"] = (
                    (heuristic_result["source"] + " + OpenAlex Live IF")
                    if heuristic_result else "OpenAlex Live Lookup"
                )
                oa_result["issn"] = item.get("issn_l")
                oa_result["impact_factor"] = round(live_if, 3) if live_if else oa_result.get("impact_factor")
                oa_result["doaj_indexed"] = is_oa
                if works > 50:
                    oa_result["scopus_indexed"] = True
                # Refine quartile from live IF (overrides heuristic estimate)
                if live_if:
                    if live_if >= 10:
                        oa_result["quartile"] = "Q1"
                        oa_result["wos_indexed"] = True
                        oa_result["quality_assessment"] = "Excellent - Top Tier Journal (OpenAlex)"
                    elif live_if >= 4:
                        oa_result["quartile"] = "Q1"
                        oa_result["wos_indexed"] = True
                        oa_result["quality_assessment"] = "Good - Q1 Journal (OpenAlex)"
                    elif live_if >= 2:
                        oa_result["quartile"] = "Q2"
                        oa_result["scopus_indexed"] = True
                        oa_result["quality_assessment"] = "Acceptable - Q2 Journal (OpenAlex)"
                    elif live_if >= 0.5:
                        oa_result["quartile"] = "Q3"
                        oa_result["quality_assessment"] = "Below Average - Q3 Journal (OpenAlex)"
                    else:
                        oa_result["quartile"] = "Q4"
                        oa_result["quality_assessment"] = "Low - Q4 Journal (OpenAlex)"
                elif is_oa:
                    oa_result["quality_assessment"] = "Open Access - DOAJ Indexed (OpenAlex)"
                elif not heuristic_result:
                    oa_result["quality_assessment"] = "Found in OpenAlex - Ranking Unclear"
                time.sleep(0.3)
                return oa_result
    except Exception:
        pass

    # OpenAlex failed — return heuristic baseline if we have one
    if heuristic_result:
        return heuristic_result

    return default