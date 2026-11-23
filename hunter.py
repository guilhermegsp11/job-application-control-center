"""Daily public job discovery for the Job Application Control Center.

No login scraping. Match scores are heuristic, not AI/CV-based assessments.
"""
import datetime as dt
import html
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'data' / 'jobs.json'
HEADERS = {'User-Agent': 'Mozilla/5.0 (compatible; PersonalJobDiscovery/1.0)', 'Accept': 'application/json'}
TITLE_TERMS = (
    'marketing', 'partnership', 'partner', 'brand', 'campaign', 'go-to-market',
    'growth', 'community', 'activation', 'sponsorship', 'communications',
    'enablement', 'education', 'training', 'events', 'experiential', 'channel'
)
STRONG_TITLES = (
    'partner marketing', 'channel marketing', 'integrated marketing',
    'field marketing', 'brand marketing', 'regional marketing', 'emea marketing',
    'go-to-market', 'product marketing', 'strategic partnership',
    'sports marketing', 'lifestyle marketing', 'marketing manager',
    'campaign manager', 'partnerships manager', 'marketing lead',
    'training manager', 'education manager', 'community manager'
)
SKILLS = (
    'partnership', 'go-to-market', 'brand', 'campaign', 'field marketing',
    'channel', 'product launch', 'stakeholder', 'budget', 'agency', 'event',
    'sports', 'consumer', 'b2b', 'training', 'education', 'enablement',
    'international', 'emea', 'analytics', 'content', 'creative', 'community',
    'creator', 'retail', 'activation', 'sponsorship', 'product marketing'
)
JUNIOR = re.compile(r'\b(intern(ship)?|werkstudent|working student|graduate trainee|junior|assistant|praktikant|apprentice|ausbildung)\b', re.I)
GERMAN_STRONG = re.compile(
    r'\b(?:german|deutsch(?:e|en|er|es)?)\b.{0,55}\b(?:c1|c2|native|fluent|business fluent|muttersprach\w*|verhandlungssicher)\b'
    r'|\b(?:c1|c2|native|fluent|business fluent|muttersprach\w*|verhandlungssicher)\b.{0,55}\b(?:german|deutsch(?:e|en|er|es)?)\b', re.I)
GERMANY = ('germany', 'deutschland', 'munich', 'münchen', 'bavaria', 'bayern', 'berlin', 'hamburg', 'frankfurt', 'stuttgart', 'köln', 'cologne', 'düsseldorf', 'leipzig', 'nürnberg', 'nuremberg')
REMOTE = ('remote', 'europe', 'eu ', 'eu/', 'emea', 'worldwide', 'anywhere', 'global')
OTHER_ONLY = ('united states', 'usa only', 'us only', 'canada only', 'united kingdom only', 'uk only', 'australia only', 'india only')
STATS = Counter()

def get(url):
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=25) as response:
            return json.load(response)
    except (urllib.error.URLError, TimeoutError, ValueError, OSError) as exc:
        print(f'SOURCE ERROR {url}: {type(exc).__name__}: {exc}', flush=True)
        STATS['source_errors'] += 1
        return {}

def clean(value):
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]*>', ' ', str(value or '')))).strip()

def remotive():
    data = get('https://remotive.com/api/remote-jobs?category=marketing')
    rows = data.get('jobs', [])
    print('Remotive fetched:', len(rows), flush=True)
    for x in rows:
        yield {
            'title': x.get('title') or '', 'company': x.get('company_name') or '',
            'location': x.get('candidate_required_location') or '',
            'url': x.get('url') or '', 'postedAt': str(x.get('publication_date') or '')[:10],
            'description': clean(x.get('description')), 'source': 'Remotive',
            'salary': x.get('salary') or '', 'remote': True
        }

def arbeitnow():
    total = 0
    for page in range(1, 11):
        data = get(f'https://www.arbeitnow.com/api/job-board-api?page={page}')
        rows = data.get('data') or []
        if not rows:
            break
        total += len(rows)
        for x in rows:
            timestamp = x.get('created_at')
            try:
                date = dt.datetime.fromtimestamp(int(timestamp), dt.timezone.utc).date().isoformat() if timestamp else ''
            except (ValueError, TypeError, OverflowError):
                date = ''
            yield {
                'title': x.get('title') or '', 'company': x.get('company_name') or '',
                'location': x.get('location') or '', 'url': x.get('url') or '',
                'postedAt': date, 'description': clean(x.get('description')),
                'source': 'Arbeitnow', 'salary': '', 'remote': bool(x.get('remote'))
            }
    print('Arbeitnow fetched:', total, flush=True)

def evaluate(x):
    title = x['title'].lower()
    desc = x['description'].lower()
    loc = x['location'].lower()
    if not any(term in title for term in TITLE_TERMS):
        return None, 'unrelated_title'
    if JUNIOR.search(title):
        return None, 'junior_role'
    # Exclude explicit C1/C2/native/fluent German requirements, but don't mistake
    # English fluency for German fluency.
    if GERMAN_STRONG.search(desc):
        return None, 'advanced_german'
    in_germany = any(term in loc for term in GERMANY)
    remote_scope = any(term in loc for term in REMOTE)
    if not in_germany and not remote_scope:
        return None, 'outside_target_location'
    if not in_germany and any(term in loc for term in OTHER_ONLY):
        return None, 'restricted_remote_location'
    # Remote listings with unspecified country eligibility remain provisional.
    uncertain_remote = not in_germany and ('remote' in loc or 'anywhere' in loc or 'worldwide' in loc)
    combined = title + ' ' + desc
    hits = [term for term in SKILLS if term in combined]
    strong = [term for term in STRONG_TITLES if term in title]
    # Ranking estimate only: don't label keyword overlap as actual ATS match.
    score = min(94, 60 + min(len(hits), 12) * 2 + (8 if strong else 0) + (4 if in_germany else 0))
    if 'senior' in title or 'lead' in title or 'head of' in title:
        score = min(96, score + 3)
    if score < 70:
        return None, 'low_preliminary_score'
    return (score, hits, uncertain_remote), 'accepted'

def main():
    today = dt.datetime.now(dt.timezone.utc).date()
    old = {}
    if OUT.exists():
        try:
            old = {j['url']: j for j in json.loads(OUT.read_text(encoding='utf-8')).get('jobs', []) if j.get('url')}
        except (OSError, ValueError, KeyError, TypeError):
            print('Existing feed unreadable; starting fresh', flush=True)
    found = {}
    sources = [remotive, arbeitnow]
    for source in sources:
        for x in source():
            STATS['fetched'] += 1
            if not x['url'] or not x['company'] or not x['title']:
                STATS['missing_fields'] += 1
                continue
            if x['postedAt']:
                try:
                    age = (today - dt.date.fromisoformat(x['postedAt'])).days
                    if age > 30 or age < -1:
                        STATS['outside_30_days'] += 1
                        continue
                except ValueError:
                    STATS['invalid_date'] += 1
            result, reason = evaluate(x)
            STATS[reason] += 1
            if result is None:
                continue
            score, hits, uncertain = result
            job = {key: x[key] for key in ('title', 'company', 'location', 'url', 'postedAt', 'source', 'salary')}
            job.update(
                match=score,
                reason='Keyword evidence: ' + ', '.join(hits[:8]) + '. Preliminary estimate, not an AI/CV assessment.',
                gaps=('Confirm remote eligibility for Germany. ' if uncertain else '') +
                     'Verify salary (target €85k+), German requirements and seniority.',
                status=old.get(x['url'], {}).get('status', 'new')
            )
            found[x['url']] = job
    for url, job in old.items():
        found.setdefault(url, job)
    jobs = sorted(found.values(), key=lambda j: (j.get('postedAt') or '', j.get('match') or 0), reverse=True)[:300]
    OUT.parent.mkdir(exist_ok=True, parents=True)
    OUT.write_text(json.dumps({
        'updated': dt.datetime.now(dt.timezone.utc).isoformat(),
        'jobs': jobs, 'sources': ['Remotive', 'Arbeitnow'],
        'notice': 'Public-source coverage only. Match scores are heuristic; check German language, salary and Germany eligibility.'
    }, ensure_ascii=False, indent=2), encoding='utf-8')
    print('FILTER DIAGNOSTICS:', dict(STATS), flush=True)
    print('Jobs in feed:', len(jobs), flush=True)
    if not jobs:
        print('No matches. Review source counts and filter diagnostics above.', flush=True)

if __name__ == '__main__':
    main()
