"""
TALASH Analysis Engine - All 9 Functional Modules
3.1 Educational Profile Analysis
3.2 Research Profile Analysis (Journals + Conferences)
3.3 Student Supervision
3.4 Books Authored
3.5 Patents (enhanced: number, inventors, verification link, role analysis)
3.6 Topic Variability (LLM-based clustering)
3.7 Co-author Analysis (recurring collaborators, team size, diversity)
3.8 Professional Experience (overlap/gap detection, career progression, email draft)
3.9 Skill Alignment (LLM-based evidence verification)
"""

from core.ranking_verifier import RankingVerifier
import re
import json
from collections import Counter
from datetime import datetime


# ── Gemini LLM helper (shared by 3.6 and 3.9) ────────────────────────────────

def _call_gemini(prompt: str) -> str:
    """Call Gemini with dual-key fallback. Returns '' on total failure."""
    try:
        from core.llm_extractor import call_llm
        return call_llm(prompt, temperature=0.0, max_tokens=2000)
    except Exception as e:
        print(f"  [LLM] Gemini call failed: {e}")
        return ""


def _parse_llm_json(text):
    """Strip markdown fences and parse JSON from LLM response."""
    if not isinstance(text, str):
        return None
    text = re.sub(r"```json\s*", "", text)
    text = re.sub(r"```\s*", "", text)
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"[\[{].*[\]}]", text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group())
            except json.JSONDecodeError:
                pass
    return None


# ─────────────────────────────────────────────────────────────────────────────

class AnalysisEngine:
    def __init__(self):
        self.verifier = RankingVerifier()

    # ==================== 3.1 EDUCATIONAL PROFILE ANALYSIS ====================

    def analyze_education(self, education_records, experience_records):
        """Complete educational profile analysis per spec sections i-ix."""
        result = {
            'sse': None, 'hssc': None, 'ug': None, 'pg': None, 'phd': None,
            'sse_percentage': None, 'hssc_percentage': None,
            'ug_cgpa': None, 'pg_cgpa': None, 'phd_completed': False,
            'degree_sequence': [], 'institution_rankings': [],
            'educational_gaps': [], 'justified_gaps': [],
            'academic_performance': [], 'overall_strength': 'Unknown',
            'score': 0
        }

        sorted_edu = sorted(education_records, key=lambda x: x.get('passing_year', 0) or 0)

        for i, edu in enumerate(sorted_edu):
            level = edu.get('degree_level', '').upper()
            grade = edu.get('grade_gpa_percentage')
            inst = edu.get('institution', '')

            if level == 'SSC':
                result['sse'] = edu
                result['sse_percentage'] = self._normalize_grade(grade)
            elif level == 'HSSC':
                result['hssc'] = edu
                result['hssc_percentage'] = self._normalize_grade(grade)
            elif level == 'BACHELOR':
                result['ug'] = edu
                result['ug_cgpa'] = self._normalize_grade(grade)
            elif level == 'MASTER':
                result['pg'] = edu
                result['pg_cgpa'] = self._normalize_grade(grade)
            elif level == 'PHD':
                result['phd'] = edu
                result['phd_completed'] = True

            if inst:
                rank = self.verifier.verify_institution(inst)
                result['institution_rankings'].append({
                    'degree': edu.get('degree_name'), 'institution': inst,
                    'qs_rank': rank.get('qs_rank'), 'the_rank': rank.get('the_rank'),
                    'quality': rank.get('quality_label')
                })

            if grade:
                result['academic_performance'].append({
                    'level': level, 'grade': grade, 'normalized': self._normalize_grade(grade)
                })

            result['degree_sequence'].append(edu.get('degree_name'))

        result['progression_score'] = self._calculate_progression(result['academic_performance'])
        result['educational_gaps'] = self._detect_gaps(sorted_edu)
        result['justified_gaps'] = self._justify_gaps(result['educational_gaps'], experience_records)
        result['overall_strength'], result['score'] = self._interpret_educational_strength(result)

        return result

    def _normalize_grade(self, grade):
        if not grade:
            return None
        try:
            grade_str = str(grade).strip()
            if '%' in grade_str:
                return round(float(grade_str.replace('%', '')) / 25, 2)
            if '/' in grade_str:
                num, den = map(float, grade_str.split('/'))
                return round(num / den * 4.0, 2)
            num = float(grade_str)
            if num <= 4.5:
                return round(num, 2)
            elif num <= 100:
                return round(num / 25, 2)
        except:
            pass
        return None

    def _detect_gaps(self, sorted_edu):
        gaps = []
        for i in range(len(sorted_edu) - 1):
            current_end = sorted_edu[i].get('passing_year')
            next_start = sorted_edu[i + 1].get('passing_year')
            if current_end and next_start and next_start - current_end > 2:
                gaps.append({
                    'from': sorted_edu[i].get('degree_level'),
                    'to': sorted_edu[i+1].get('degree_level'),
                    'gap_years': next_start - current_end
                })
        return gaps

    def _justify_gaps(self, gaps, experience_records):
        justified = []
        for gap in gaps:
            if experience_records:
                gap['justified'] = True
                gap['justification'] = 'Professional experience documented'
                justified.append(gap)
            else:
                gap['justified'] = False
                gap['justification'] = 'No professional experience found'
        return justified

    def _calculate_progression(self, performance):
        if len(performance) < 2:
            return 'Insufficient data'
        grades = [p['normalized'] for p in performance if p['normalized']]
        if len(grades) >= 2 and grades[-1] > grades[0]:
            return 'Improving'
        elif len(grades) >= 2 and grades[-1] < grades[0]:
            return 'Declining'
        return 'Consistent'

    def _interpret_educational_strength(self, result):
        score = 40  # base score — having any degree qualifies candidate

        # PhD is the primary qualification for academic recruitment
        if result['phd_completed']:
            score += 30  # PhD = strong positive signal
        elif result.get('highest_degree') in ('MS', 'MPhil', 'Masters'):
            score += 15

        # CGPA bonuses (optional — many CVs don't state CGPA)
        if result['ug_cgpa'] and result['ug_cgpa'] >= 3.5:
            score += 10
        elif result['ug_cgpa'] and result['ug_cgpa'] >= 3.0:
            score += 5
        if result['pg_cgpa'] and result['pg_cgpa'] >= 3.5:
            score += 10
        elif result['pg_cgpa'] and result['pg_cgpa'] >= 3.0:
            score += 5

        # No unexplained gaps = small bonus
        if len(result['educational_gaps']) == 0:
            score += 5

        # Top-ranked institution bonus
        for inst in result['institution_rankings']:
            if inst.get('qs_rank') and inst['qs_rank'] <= 500:
                score += 5
                break

        if score >= 80:
            strength = "Excellent - Strong academic background"
        elif score >= 65:
            strength = "Good - Solid educational foundation"
        elif score >= 50:
            strength = "Average - Meets basic requirements"
        else:
            strength = "Needs improvement - Educational gaps or low scores"
        return strength, min(100, score)

    # ==================== 3.2 RESEARCH PROFILE ANALYSIS ====================

    def analyze_research_profile(self, publications):
        result = {
            'journal_papers': [], 'conference_papers': [],
            'total': len(publications), 'q1_count': 0, 'q2_count': 0,
            'a_star_count': 0, 'first_author_count': 0, 'predatory_count': 0,
            'overall_quality_score': 0, 'detailed_analysis': []
        }

        for pub in publications:
            pub_type = pub.get('pub_type', 'Journal')
            venue = pub.get('venue_name', '')

            if pub_type == 'Journal':
                analysis = self.verifier.verify_journal(venue, pub.get('impact_factor_claimed'))
                analysis.update({
                    'title': pub.get('title'), 'year': pub.get('year'),
                    'authorship': pub.get('authorship_role', 'Unknown')
                })
                result['journal_papers'].append(analysis)
                if analysis.get('quartile') == 'Q1':
                    result['q1_count'] += 1
                elif analysis.get('quartile') == 'Q2':
                    result['q2_count'] += 1
                if analysis.get('predatory'):
                    result['predatory_count'] += 1
            else:
                analysis = self.verifier.verify_conference(venue)
                analysis.update({
                    'title': pub.get('title'), 'year': pub.get('year'),
                    'authorship': pub.get('authorship_role', 'Unknown')
                })
                result['conference_papers'].append(analysis)
                if analysis.get('is_a_star'):
                    result['a_star_count'] += 1

            if pub.get('authorship_role') == 'First':
                result['first_author_count'] += 1

            result['detailed_analysis'].append(analysis)

        total = len(publications)
        if total > 0:
            # Base: publication count matters even if venues unverified
            base = min(50, total * 5)
            q1_bonus   = min(30, result['q1_count'] * 10)
            q2_bonus   = min(15, result['q2_count'] * 5)
            astar_bonus= min(20, result['a_star_count'] * 10)
            # Count scopus-indexed journal papers
            scopus_count = sum(
                1 for p in result['journal_papers']
                if p.get('scopus_indexed') or p.get('wos_indexed')
            )
            scopus_bonus = min(20, scopus_count * 4)
            quality_score = base + q1_bonus + q2_bonus + astar_bonus + scopus_bonus
            result['overall_quality_score'] = min(100, round(quality_score, 1))
            result['scopus_indexed_count'] = scopus_count

        return result

    # ==================== 3.3 STUDENT SUPERVISION ====================

    def analyze_supervision(self, supervision_records):
        result = {
            'ms_main': 0, 'ms_co': 0, 'phd_main': 0, 'phd_co': 0,
            'total_supervised': 0, 'students': [], 'score': 0
        }

        if isinstance(supervision_records, dict):
            result['ms_main']  = int(supervision_records.get('ms_main_supervisor', 0) or 0)
            result['ms_co']    = int(supervision_records.get('ms_co_supervisor', 0) or 0)
            result['phd_main'] = int(supervision_records.get('phd_main_supervisor', 0) or 0)
            result['phd_co']   = int(supervision_records.get('phd_co_supervisor', 0) or 0)
            result['students'] = supervision_records.get('student_names', []) or []
            result['total_supervised'] = result['phd_main'] + result['ms_main']
            result['score'] = min(100, result['phd_main'] * 15 + result['ms_main'] * 5)
            return result

        if not isinstance(supervision_records, list):
            return result

        for sup in supervision_records:
            if not isinstance(sup, dict):
                continue
            degree = sup.get('degree_supervised', '').upper()
            role = sup.get('supervision_role', '').lower()
            if 'PHD' in degree:
                if 'main' in role:
                    result['phd_main'] += 1
                else:
                    result['phd_co'] += 1
            else:
                if 'main' in role:
                    result['ms_main'] += 1
                else:
                    result['ms_co'] += 1
            result['students'].append(sup.get('student_name'))

        result['total_supervised'] = result['phd_main'] + result['ms_main']
        result['score'] = min(100, result['phd_main'] * 15 + result['ms_main'] * 5)
        return result

    # ==================== 3.4 BOOKS AUTHORED ====================

    def analyze_books(self, book_records):
        result = {'total': 0, 'books': [], 'score': 0}

        for book in book_records:
            authorship = book.get('authorship_role', 'co-author')
            publisher = book.get('publisher', '')
            credible_publishers = ['Springer', 'Elsevier', 'Wiley', 'Cambridge', 'Oxford', 'IEEE', 'ACM']
            is_credible = any(pub in publisher for pub in credible_publishers)
            result['books'].append({
                'title': book.get('title'), 'year': book.get('year'),
                'authorship': authorship, 'publisher': publisher,
                'is_credible_publisher': is_credible
            })
            result['total'] += 1

        result['score'] = min(100, result['total'] * 20)
        return result

    # ==================== 3.5 PATENTS ====================

    def analyze_patents(self, patent_records):
        """
        Analyze patents per spec 3.5:
          a. Extract: patent_number, title, date, inventors, country, verification_link
          b. Determine inventor role: lead / co-inventor / contributing
          c. Assess verification credibility
        """
        result = {
            'total': 0,
            'lead_inventor_count': 0,
            'co_inventor_count': 0,
            'contributing_count': 0,
            'unique_countries': [],
            'verifiable_count': 0,
            'patents': [],
            'score': 0,
            'summary': ''
        }

        OFFICIAL_PATENT_DOMAINS = [
            'patents.google.com', 'patentscope.wipo.int', 'espacenet.com',
            'uspto.gov', 'epo.org', 'ipindia.gov.in', 'ipos.gov.sg',
            'sipo.gov.cn', 'j-platpat.inpit.go.jp', 'lens.org'
        ]

        countries_seen = []

        for patent in patent_records:
            title       = patent.get('patent_title') or patent.get('title', '')
            number      = patent.get('patent_number', '')
            filing_date = patent.get('filing_date') or patent.get('date', '')
            grant_date  = patent.get('grant_date', '')
            inventors   = patent.get('inventors', '')
            country     = patent.get('country', 'Unknown')
            verify_link = patent.get('verification_link', '')
            status      = patent.get('status', 'Granted')
            is_lead     = patent.get('is_lead_inventor', False)

            # b. Inventor role
            inventors_str = str(inventors) if inventors else ''
            role = self._determine_inventor_role(is_lead, inventors_str)

            if role == 'Lead Inventor':
                result['lead_inventor_count'] += 1
            elif role == 'Co-Inventor':
                result['co_inventor_count'] += 1
            else:
                result['contributing_count'] += 1

            # c. Verification credibility
            link_verified = False
            link_quality  = 'No link provided'
            if verify_link:
                link_lower = verify_link.lower()
                if any(domain in link_lower for domain in OFFICIAL_PATENT_DOMAINS):
                    link_verified = True
                    link_quality  = 'Official patent database link'
                    result['verifiable_count'] += 1
                else:
                    link_quality = 'Non-standard link – manual verification recommended'

            # Patent number sanity check
            number_looks_valid = bool(re.search(r'[A-Z]{0,3}\d{5,}', str(number).upper()))

            if country and country != 'Unknown':
                countries_seen.append(country)

            result['patents'].append({
                'patent_number':      number,
                'patent_title':       title,
                'filing_date':        filing_date,
                'grant_date':         grant_date,
                'inventors':          inventors_str,
                'country':            country,
                'status':             status,
                'inventor_role':      role,
                'verification_link':  verify_link,
                'link_quality':       link_quality,
                'link_verified':      link_verified,
                'number_looks_valid': number_looks_valid,
            })
            result['total'] += 1

        result['unique_countries'] = list(set(countries_seen))

        # Scoring: lead > co > contributing, bonus for verifiable
        score = (
            result['lead_inventor_count'] * 25 +
            result['co_inventor_count'] * 15 +
            result['contributing_count'] * 10 +
            result['verifiable_count'] * 5
        )
        result['score'] = min(100, score)

        result['summary'] = (
            f"{result['total']} patent(s) — "
            f"{result['lead_inventor_count']} as lead inventor, "
            f"{result['co_inventor_count']} as co-inventor. "
            f"Countries: {', '.join(result['unique_countries']) or 'N/A'}. "
            f"{result['verifiable_count']} officially verifiable."
        )

        return result

    def _determine_inventor_role(self, is_lead_flag, inventors_str: str) -> str:
        """Determine inventor role from flag + inventor list position."""
        if is_lead_flag:
            return 'Lead Inventor'
        if not inventors_str:
            return 'Contributing Inventor'
        parts = [p.strip() for p in re.split(r',|;|and', inventors_str) if p.strip()]
        if len(parts) <= 1:
            return 'Lead Inventor'
        return 'Co-Inventor'

    # ==================== 3.6 TOPIC VARIABILITY (LLM-based) ====================

    def analyze_topic_variability(self, publications):
        """
        Measure topic variability via LLM clustering.

        Per spec 3.6: group into thematic clusters, measure diversity,
        identify dominant area and temporal trend.
        """
        if not publications:
            return {
                'topics': {}, 'topic_percentages': {}, 'diversity_score': 0,
                'dominant_topic': None, 'is_specialist': True,
                'breadth': 'No publications', 'trend': 'N/A',
                'major_themes': [], 'llm_used': False
            }

        pub_summaries = []
        for i, pub in enumerate(publications):
            pub_summaries.append(
                f"{i+1}. Title: {pub.get('title','?')} | "
                f"Venue: {pub.get('venue_name','?')} | "
                f"Year: {pub.get('year','?')} | "
                f"Keywords: {pub.get('keywords','')}"
            )

        pub_text = "\n".join(pub_summaries)

        prompt = f"""You are a research analyst. Given the following publications, 
cluster them into broad research themes (e.g. Machine Learning, Computer Vision, NLP,
Cybersecurity, IoT, Networks, Software Engineering, HR Analytics, etc.).

Publications:
{pub_text}

Respond ONLY with this JSON (no preamble, no markdown):
{{
  "clusters": {{
    "Theme Name": [1, 2, 3],
    ...
  }},
  "dominant_topic": "Theme Name",
  "diversity_score": <0-100 float>,
  "is_specialist": <true/false>,
  "temporal_trend": "one sentence about how topics changed over time",
  "major_themes": ["Theme1", "Theme2"]
}}"""

        llm_response = _call_gemini(prompt)
        parsed = _parse_llm_json(llm_response) if llm_response else None

        if parsed and isinstance(parsed, dict) and 'clusters' in parsed:
            clusters     = parsed.get('clusters', {})
            topic_counts = {t: len(papers) for t, papers in clusters.items()}
            total        = len(publications)
            topic_pcts   = {t: round(c / total * 100, 1) for t, c in topic_counts.items()}
            dominant     = parsed.get('dominant_topic') or (
                max(topic_counts, key=topic_counts.get) if topic_counts else 'Unknown'
            )
            diversity    = float(parsed.get('diversity_score', 0))
            is_spec      = parsed.get('is_specialist', diversity < 40)

            return {
                'topics':            topic_counts,
                'topic_percentages': topic_pcts,
                'diversity_score':   round(diversity, 1),
                'dominant_topic':    dominant,
                'is_specialist':     is_spec,
                'breadth':           'Specialist' if is_spec else 'Interdisciplinary',
                'trend':             parsed.get('temporal_trend', 'N/A'),
                'major_themes':      parsed.get('major_themes', list(topic_counts.keys())),
                'llm_used':          True
            }

        # Fallback: keyword-based
        topics = Counter()
        for pub in publications:
            topics[self._infer_topic(pub.get('title', ''))] += 1

        total    = len(publications)
        dominant = topics.most_common(1)[0][0]
        max_pct  = topics.most_common(1)[0][1] / total
        diversity = round((1 - max_pct) * 100, 1)

        return {
            'topics':            dict(topics),
            'topic_percentages': {t: round(c/total*100, 1) for t, c in topics.items()},
            'diversity_score':   diversity,
            'dominant_topic':    dominant,
            'is_specialist':     diversity < 40,
            'breadth':           'Specialist' if diversity < 40 else 'Interdisciplinary',
            'trend':             'N/A (LLM unavailable)',
            'major_themes':      [t for t, _ in topics.most_common()],
            'llm_used':          False
        }

    def _infer_topic(self, title):
        """Fallback keyword-based topic inference."""
        title_lower = title.lower()
        topics = {
            'Machine Learning': ['ml', 'machine learning', 'deep learning', 'neural', 'transformer'],
            'Computer Vision':  ['vision', 'image', 'object detection', 'segmentation', 'cnn'],
            'NLP':              ['nlp', 'text', 'language', 'sentiment', 'bert', 'gpt', 'llm'],
            'Cybersecurity':    ['security', 'cyber', 'encryption', 'malware'],
            'IoT':              ['iot', 'internet of things', 'sensor'],
            'Networks':         ['network', 'routing', '5g', 'wireless', 'communication'],
            'Software Eng.':    ['software', 'agile', 'testing', 'devops'],
        }
        for topic, keywords in topics.items():
            if any(kw in title_lower for kw in keywords):
                return topic
        return 'Other'

    # ==================== 3.7 CO-AUTHOR ANALYSIS ====================

    def analyze_coauthors(self, publications):
        """
        Analyze collaboration patterns per spec 3.7:
          - Unique co-authors, recurring vs one-time
          - Team size analysis
          - Collaboration diversity score
          - Student-supervisor pattern heuristic
          - Yearly network evolution
        """
        coauthor_counts = Counter()
        paper_sizes     = []
        yearly_collabs  = {}

        for pub in publications:
            co_authors_raw = pub.get('co_authors', '') or ''
            year           = pub.get('year')

            authors = [
                a.strip() for a in re.split(r',|;\s*|\s+and\s+', co_authors_raw)
                if a.strip() and len(a.strip()) > 2
            ]
            paper_sizes.append(len(authors))

            for author in authors:
                coauthor_counts[author] += 1

            if year:
                yearly_collabs.setdefault(str(year), set()).update(authors)

        total_pubs    = max(1, len(publications))
        unique_authors = len(coauthor_counts)
        recurring      = {a: c for a, c in coauthor_counts.items() if c > 1}
        one_time       = {a: c for a, c in coauthor_counts.items() if c == 1}
        top5           = coauthor_counts.most_common(5)

        avg_coauthors = round(sum(paper_sizes) / total_pubs, 1)
        if avg_coauthors <= 2:
            team_style = 'Small teams (1-3 authors typical)'
        elif avg_coauthors <= 4:
            team_style = 'Medium teams (3-5 authors typical)'
        else:
            team_style = 'Large collaborative groups (5+ authors typical)'

        diversity_score = min(100, round((unique_authors / total_pubs) * 20, 1))

        # Student-supervisor heuristic: same co-author in 3+ papers
        strong_ties = [(a, c) for a, c in top5 if c >= 3]
        supervision_hint = (
            "Strong repeated collaboration (possible supervision): "
            + ", ".join(f"{a} ({c} papers)" for a, c in strong_ties)
        ) if strong_ties else "No obvious student-supervisor pattern detected"

        papers_with_recurring = sum(
            1 for pub in publications
            if any(
                a.strip() in recurring
                for a in re.split(r',|;\s*|\s+and\s+', pub.get('co_authors', '') or '')
                if a.strip()
            )
        )
        recurring_ratio = round(papers_with_recurring / total_pubs * 100, 1)

        return {
            'unique_coauthors':              unique_authors,
            'total_collaboration_slots':     sum(coauthor_counts.values()),
            'avg_coauthors_per_paper':       avg_coauthors,
            'team_style':                    team_style,
            'top_collaborators':             [{'name': a, 'papers': c} for a, c in top5],
            'recurring_collaborators':       len(recurring),
            'one_time_collaborators':        len(one_time),
            'recurring_ratio_pct':           recurring_ratio,
            'collaboration_diversity_score': diversity_score,
            'supervision_hint':              supervision_hint,
            'yearly_network_size':           {yr: len(s) for yr, s in sorted(yearly_collabs.items())},
        }

    # ==================== 3.8 PROFESSIONAL EXPERIENCE ====================

    def analyze_experience(self, experience_records, education_records=None, candidate_name='Candidate'):
        """
        Analyze professional experience per spec 3.8:
          i.   Timeline consistency: edu-job overlaps, job-job overlaps, gaps
          ii.  Gap justification
          iii. Career continuity and progression
          iv.  Missing-info email draft when unexplained gaps/overlaps exist
        """
        result = {
            'total_months': 0, 'academic_months': 0, 'industry_months': 0,
            'jobs': [], 'gaps': [], 'overlaps': [], 'edu_job_overlaps': [],
            'career_progression': {}, 'timeline_consistent': True,
            'score': 0, 'experience_years': 0,
            'gap_email': None
        }

        education_records = education_records or []

        def _parse_date(d):
            if not d:
                return None
            s = str(d).strip()
            if s.lower() in ('present', 'current', 'now', 'till date'):
                return datetime.now()
            for fmt in ('%Y-%m-%d', '%Y-%m', '%m/%Y', '%m-%Y', '%b-%Y', '%B %Y', '%Y'):
                try:
                    return datetime.strptime(s[:len(fmt.replace('%Y','0000').replace('%m','00').replace('%d','00').replace('%b','Jan').replace('%B','January'))], fmt)
                except (ValueError, TypeError):
                    pass
            m = re.search(r'(\d{4})', s)
            if m:
                return datetime(int(m.group(1)), 1, 1)
            return None

        # Parse all jobs
        parsed_jobs = []
        for exp in experience_records:
            start = _parse_date(exp.get('start_date'))
            end   = _parse_date(exp.get('end_date')) or datetime.now()
            if not start:
                continue
            duration = max(0, round((end - start).days / 30.44))
            is_current = str(exp.get('end_date', '')).lower() in ('present', 'current', 'now', '', 'till date')
            parsed_jobs.append({
                'title':      exp.get('job_title', 'Unknown'),
                'org':        exp.get('organization', ''),
                'type':       exp.get('employment_type', 'Other'),
                'start':      start,
                'end':        end,
                'duration':   duration,
                'is_current': is_current
            })

        parsed_jobs.sort(key=lambda x: x['start'])

        for job in parsed_jobs:
            result['total_months'] += job['duration']
            if job['type'] == 'Academic':
                result['academic_months'] += job['duration']
            elif job['type'] == 'Industry':
                result['industry_months'] += job['duration']
            result['jobs'].append({
                'title':           job['title'],
                'org':             job['org'],
                'type':            job['type'],
                'start':           job['start'].strftime('%Y-%m'),
                'end':             'Present' if job['is_current'] else job['end'].strftime('%Y-%m'),
                'duration_months': job['duration']
            })

        result['experience_years'] = round(result['total_months'] / 12, 1)

        # i-a. Job-Job overlaps
        for i in range(len(parsed_jobs)):
            for j in range(i + 1, len(parsed_jobs)):
                a, b = parsed_jobs[i], parsed_jobs[j]
                overlap_start = max(a['start'], b['start'])
                overlap_end   = min(a['end'],   b['end'])
                if overlap_start < overlap_end:
                    overlap_months = round((overlap_end - overlap_start).days / 30.44)
                    result['overlaps'].append({
                        'job_a':          f"{a['title']} @ {a['org']}",
                        'job_b':          f"{b['title']} @ {b['org']}",
                        'overlap_months': overlap_months,
                        'note':           'Concurrent roles detected – verify (part-time/consulting may be valid)'
                    })
                    result['timeline_consistent'] = False

        # Parse education periods for overlap/gap cross-check
        parsed_edu_periods = []
        for edu in education_records:
            end_yr = edu.get('passing_year')
            if not end_yr:
                continue
            level = edu.get('degree_level', '').upper()
            dur_yrs = {'SSC': 10, 'HSSC': 2, 'BACHELOR': 4, 'MASTER': 2, 'PHD': 4}.get(level, 3)
            parsed_edu_periods.append({
                'degree': edu.get('degree_name', level),
                'start':  datetime(max(1950, int(end_yr) - dur_yrs), 1, 1),
                'end':    datetime(int(end_yr), 12, 31)
            })

        # i-b. Education-Job overlaps
        for edu_p in parsed_edu_periods:
            for job in parsed_jobs:
                ov_start = max(edu_p['start'], job['start'])
                ov_end   = min(edu_p['end'],   job['end'])
                if ov_start < ov_end:
                    ov_months = round((ov_end - ov_start).days / 30.44)
                    result['edu_job_overlaps'].append({
                        'education':      edu_p['degree'],
                        'job':            f"{job['title']} @ {job['org']}",
                        'overlap_months': ov_months,
                        'note':           'Edu-job overlap – acceptable if RA/part-time; flag if full-time'
                    })

        # i-c. Professional gaps (>=3 months between consecutive jobs)
        unexplained_gaps = []
        for i in range(len(parsed_jobs) - 1):
            gap_start = parsed_jobs[i]['end']
            gap_end   = parsed_jobs[i + 1]['start']
            if gap_end > gap_start:
                gap_months = round((gap_end - gap_start).days / 30.44)
                if gap_months >= 3:
                    bridged = any(
                        e['start'] <= gap_start and e['end'] >= gap_end
                        for e in parsed_edu_periods
                    )
                    unexplained_gaps.append({
                        'after_job':              f"{parsed_jobs[i]['title']} @ {parsed_jobs[i]['org']}",
                        'before_job':             f"{parsed_jobs[i+1]['title']} @ {parsed_jobs[i+1]['org']}",
                        'gap_months':             gap_months,
                        'bridged_by_education':   bridged,
                        'justification':          'Covered by education period' if bridged else 'Unexplained – requires clarification'
                    })

        result['gaps'] = unexplained_gaps

        # iii. Career progression
        seniority_ladder = [
            'intern', 'trainee', 'assistant', 'junior', 'associate', 'lecturer',
            'engineer', 'developer', 'analyst', 'researcher', 'officer',
            'senior', 'lead', 'principal', 'manager', 'head', 'coordinator',
            'director', 'dean', 'professor', 'vp', 'cto', 'ceo', 'president'
        ]

        def _seniority(title):
            t = title.lower()
            for idx, kw in enumerate(seniority_ladder):
                if kw in t:
                    return idx
            return -1

        if len(parsed_jobs) >= 2:
            first_level = _seniority(parsed_jobs[0]['title'])
            last_level  = _seniority(parsed_jobs[-1]['title'])
            if last_level > first_level:
                progression = 'Upward – clear career growth detected'
            elif last_level == first_level:
                progression = 'Lateral – similar seniority maintained'
            else:
                progression = 'Unclear or declining seniority'
        else:
            progression = 'Insufficient data (single role or no parsed dates)'

        result['career_progression'] = {
            'assessment':         progression,
            'roles_chronological': [f"{j['title']} @ {j['org']}" for j in parsed_jobs]
        }

        # iv. Email draft for unexplained gaps/overlaps
        truly_unexplained = [g for g in unexplained_gaps if not g['bridged_by_education']]
        if truly_unexplained or result['overlaps']:
            result['gap_email'] = self._draft_gap_email(
                candidate_name, truly_unexplained, result['overlaps']
            )

        # Scoring
        months = result['total_months']
        if months >= 60:
            base_score = 100
        elif months >= 36:
            base_score = 75
        elif months >= 12:
            base_score = 50
        else:
            base_score = 25

        deduction = len(truly_unexplained) * 5 + len(result['overlaps']) * 3
        result['score'] = max(0, base_score - deduction)

        return result

    def _draft_gap_email(self, name, gaps, overlaps):
        """Use LLM to draft a professional, personalised gap-clarification email."""
        issues = []
        for g in gaps:
            issues.append(
                f"  - A gap of approximately {g['gap_months']} month(s) between "
                f"'{g['after_job']}' and '{g['before_job']}' (no reason stated in CV)"
            )
        for o in overlaps:
            issues.append(
                f"  - Overlapping positions: '{o['job_a']}' and '{o['job_b']}' "
                f"(overlap: ~{o['overlap_months']} month(s))"
            )

        if not issues:
            return None

        prompt = f"""You are an HR assistant for TALASH (NUST recruitment system).
Write a professional, polite email to candidate '{name}' asking them to clarify
the following employment history issues:

{chr(10).join(issues)}

Requirements:
- Warm and professional tone — not accusatory
- Explain that clarification is needed for complete evaluation
- Give a 5-business-day response deadline
- Sign off as: TALASH Recruitment Team, NUST
- Start with Subject: line

Write ONLY the email. No preamble."""

        try:
            from core.llm_extractor import call_llm
            email = call_llm(prompt, temperature=0.3, max_tokens=800)
        except Exception:
            email = ""

        if not email:
            # Template fallback
            email = (
                f"Subject: Clarification Required – Employment History | TALASH Recruitment\n\n"
                f"Dear {name},\n\n"
                f"Thank you for applying to NUST. While reviewing your CV, we noticed the "
                f"following points in your employment history that require clarification:\n\n"
                + "\n".join(issues) +
                f"\n\nKindly provide a brief explanation within 5 business days so we may "
                f"complete your evaluation accurately.\n\n"
                f"Best regards,\nTALASH Recruitment Team – NUST"
            )
        return email

    # ==================== 3.9 SKILL ALIGNMENT (LLM-based) ====================

    def analyze_skills(self, skills, publications, experience, job_description=''):
        """
        Verify claimed skills via LLM cross-referencing against publications
        and experience per spec 3.9.

        Evidence levels: Strong / Partial / Weak / Unsupported
        """
        skill_list = [
            (s.get('skill_name', '') if isinstance(s, dict) else str(s)).strip()
            for s in skills
        ]
        skill_list = [s for s in skill_list if s]

        if not skill_list:
            return {
                'skills_list': [], 'total': 0,
                'strong': 0, 'partial': 0, 'weak': 0, 'unsupported': 0,
                'skill_evidence': {}, 'alignment_score': 0,
                'job_relevance': [], 'llm_used': False
            }

        pub_titles = [p.get('title', '') for p in publications]
        exp_titles = [
            f"{e.get('job_title','')} at {e.get('organization','')}"
            for e in experience
        ]

        pub_text = "\n".join(f"- {t}" for t in pub_titles[:30]) or "None"
        exp_text = "\n".join(f"- {t}" for t in exp_titles[:20])  or "None"
        jd_text  = job_description.strip() if job_description else "Not provided"

        prompt = f"""You are an HR analyst verifying CV skill claims.

Claimed Skills:
{', '.join(skill_list)}

Publication titles:
{pub_text}

Work experience roles:
{exp_text}

Target job description:
{jd_text}

For EACH claimed skill classify evidence:
- "Strong"      : appears clearly in BOTH publications AND experience
- "Partial"     : appears in ONE of publications OR experience
- "Weak"        : mentioned tangentially, minimal support
- "Unsupported" : no evidence in publications or experience

Also classify job relevance as "High", "Medium", or "Low" for each skill.

Respond ONLY with this JSON (no preamble, no markdown):
{{
  "skill_evidence": {{
    "<skill_name>": {{"evidence": "Strong|Partial|Weak|Unsupported", "reason": "one sentence", "job_relevance": "High|Medium|Low"}}
  }}
}}"""

        llm_response = _call_gemini(prompt)
        parsed       = _parse_llm_json(llm_response) if llm_response else None

        if parsed and isinstance(parsed, dict) and 'skill_evidence' in parsed:
            skill_evidence = {}
            job_relevance  = []

            for skill in skill_list:
                # Case-insensitive key match
                matched_key = next(
                    (k for k in parsed['skill_evidence'] if k.lower() == skill.lower()),
                    None
                )
                if matched_key:
                    info = parsed['skill_evidence'][matched_key]
                    ev   = info.get('evidence', 'Unsupported')
                    skill_evidence[skill] = {
                        'evidence':      ev,
                        'reason':        info.get('reason', ''),
                        'job_relevance': info.get('job_relevance', 'Medium')
                    }
                else:
                    ev = self._fallback_skill_evidence(skill, pub_titles, exp_titles)
                    skill_evidence[skill] = {
                        'evidence':      ev,
                        'reason':        'Keyword-based fallback (LLM did not return this skill)',
                        'job_relevance': 'Medium'
                    }
                job_relevance.append({
                    'skill':     skill,
                    'relevance': skill_evidence[skill]['job_relevance']
                })

            counts    = Counter(v['evidence'] for v in skill_evidence.values())
            evidenced = counts.get('Strong', 0) + counts.get('Partial', 0)

            return {
                'skills_list':     skill_list,
                'total':           len(skill_list),
                'strong':          counts.get('Strong', 0),
                'partial':         counts.get('Partial', 0),
                'weak':            counts.get('Weak', 0),
                'unsupported':     counts.get('Unsupported', 0),
                'skill_evidence':  skill_evidence,
                'alignment_score': round(evidenced / max(1, len(skill_list)) * 100, 1),
                'job_relevance':   job_relevance,
                'llm_used':        True
            }

        # Fallback: keyword matching
        skill_evidence = {}
        for skill in skill_list:
            ev = self._fallback_skill_evidence(skill, pub_titles, exp_titles)
            skill_evidence[skill] = {
                'evidence':      ev,
                'reason':        'Keyword match in titles/roles',
                'job_relevance': 'Medium'
            }

        counts    = Counter(v['evidence'] for v in skill_evidence.values())
        evidenced = counts.get('Strong', 0) + counts.get('Partial', 0)

        return {
            'skills_list':     skill_list,
            'total':           len(skill_list),
            'strong':          counts.get('Strong', 0),
            'partial':         counts.get('Partial', 0),
            'weak':            counts.get('Weak', 0),
            'unsupported':     counts.get('Unsupported', 0),
            'skill_evidence':  skill_evidence,
            'alignment_score': round(evidenced / max(1, len(skill_list)) * 100, 1),
            'job_relevance':   [{'skill': s, 'relevance': 'Medium'} for s in skill_list],
            'llm_used':        False
        }

    def _fallback_skill_evidence(self, skill: str, pub_titles: list, exp_titles: list) -> str:
        skill_l = skill.lower()
        in_pub  = any(skill_l in t.lower() for t in pub_titles)
        in_exp  = any(skill_l in t.lower() for t in exp_titles)
        if in_pub and in_exp:
            return 'Strong'
        elif in_pub or in_exp:
            return 'Partial'
        return 'Unsupported'

    # ==================== COMPLETE EVALUATION ====================

    def evaluate_candidate(self, candidate_data):
        """Complete evaluation using all 9 modules."""
        personal     = candidate_data.get('personal_info', {})
        education    = candidate_data.get('education', [])
        experience   = candidate_data.get('experience', [])
        publications = candidate_data.get('publications', [])
        skills       = candidate_data.get('skills', [])
        supervision  = candidate_data.get('supervision', [])
        books        = candidate_data.get('books', [])
        patents      = candidate_data.get('patents', [])
        name         = personal.get('full_name', 'Candidate')

        edu_analysis         = self.analyze_education(education, experience)
        research_analysis    = self.analyze_research_profile(publications)
        supervision_analysis = self.analyze_supervision(supervision)
        books_analysis       = self.analyze_books(books)
        patents_analysis     = self.analyze_patents(patents)
        topic_analysis       = self.analyze_topic_variability(publications)
        coauthor_analysis    = self.analyze_coauthors(publications)
        exp_analysis         = self.analyze_experience(experience, education, name)
        skill_analysis       = self.analyze_skills(
            skills, publications, experience,
            job_description=personal.get('post_applied_for', '')
        )

        # ── TALASH Scoring Formula ───────────────────────────────────────────
        #
        # 6 modules, weights:
        #   Education                              25%
        #   Research output                        35%
        #   Experience + skill alignment combined  20%
        #   Topic variability + co-author          10%
        #   (supervision/books/patents bonus        up to +8 pts)
        #
        # Skill alignment: most CVs have no skills section.
        # We infer skill evidence from publication titles + job titles instead.
        # This makes skill scoring fair across all candidates.

        pub_count = len(publications)

        # 1. EDUCATION — 25%
        edu_score = edu_analysis.get('score', 0) or 0

        # 2. RESEARCH OUTPUT — 35%
        # 0 publications = 0 research score. No free points.
        research_score = round(research_analysis.get('overall_quality_score', 0) or 0, 1)
        if pub_count == 0:
            research_score = 0

        # 3. EXPERIENCE — 15% of the combined 20%
        exp_score = exp_analysis.get('score', 0) or 0

        # 4. SKILL ALIGNMENT — 5% of the combined 20%
        # If CV had explicit skills → use alignment_score from LLM
        # If CV had no skills section → infer from pub titles + job titles
        raw_skill_score = round(skill_analysis.get('alignment_score', 0) or 0, 1)
        if raw_skill_score == 0 and pub_count > 0:
            # Infer: each publication is evidence of a technical skill
            # More pubs with indexed venues = stronger skill evidence
            scopus_count = research_analysis.get('scopus_indexed_count', 0) or 0
            raw_skill_score = min(100, 40 + pub_count * 3 + scopus_count * 5)
        elif raw_skill_score == 0 and pub_count == 0:
            # No pubs, no skills section — infer from experience richness only
            exp_years = (exp_analysis.get('total_months', 0) or 0) / 12
            raw_skill_score = min(60, 20 + exp_years * 3)

        # 5. TOPIC VARIABILITY + CO-AUTHOR — 10%
        topic_score  = float(topic_analysis.get('diversity_score', 0) or 0)
        coauth_score = float(coauthor_analysis.get('collaboration_score', 0) or 0)
        if topic_score == 0 and pub_count > 0:
            topic_score = min(50 + pub_count * 2, 80)
        if coauth_score == 0 and pub_count > 0:
            coauth_score = min(40 + pub_count * 1.5, 75)
        breadth_score = (topic_score + coauth_score) / 2 if pub_count > 0 else 0

        # 6. SUPERVISION / BOOKS / PATENTS — bonus up to +8 pts
        supervision_score = supervision_analysis.get('score', 0) or 0
        books_score       = books_analysis.get('score', 0) or 0
        patents_score     = patents_analysis.get('score', 0) or 0
        sbp_parts = [s for s in [supervision_score, books_score, patents_score] if s > 0]
        sbp_avg   = sum(sbp_parts) / len(sbp_parts) if sbp_parts else 0
        sbp_bonus = round(sbp_avg * 0.08, 2)   # max +8 points

        # Weighted sum
        overall_score = (
            edu_score      * 0.25 +
            research_score * 0.38 +
            exp_score      * 0.15 +
            raw_skill_score * 0.02 +
            breadth_score  * 0.10 +
            sbp_bonus
        )

        # No PhD penalty (-10): AP role requires PhD
        if not edu_analysis.get('phd_completed'):
            overall_score -= 10

        overall_score = min(max(round(overall_score, 1), 0.0), 100.0)

        return {
            'candidate_id':          candidate_data.get('candidate_id'),
            'full_name':             personal.get('full_name'),
            'post_applied':          personal.get('post_applied_for'),
            'overall_score':         round(overall_score, 1),
            'educational_analysis':  edu_analysis,
            'research_analysis':     research_analysis,
            'supervision_analysis':  supervision_analysis,
            'books_analysis':        books_analysis,
            'patents_analysis':      patents_analysis,
            'topic_analysis':        topic_analysis,
            'coauthor_analysis':     coauthor_analysis,
            'experience_analysis':   exp_analysis,
            'skill_analysis':        skill_analysis,
        }