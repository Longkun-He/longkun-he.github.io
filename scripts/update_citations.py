"""Update the site data using the SerpApi Google Scholar author endpoint."""
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

AUTHOR = 'cuvYdUwAAAAJ'
key = os.environ.get('SERPAPI_KEY')
if not key:
    sys.exit('SERPAPI_KEY is not configured.')

items, annual, total = [], None, None
start = 0
while True:
    query = urllib.parse.urlencode({'engine': 'google_scholar_author', 'author_id': AUTHOR,
        'hl': 'en', 'num': 100, 'start': start, 'api_key': key, 'no_cache': 'true'})
    request = urllib.request.Request('https://serpapi.com/search.json?' + query, headers={'User-Agent': 'academic-homepage/1.0'})
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            data = json.load(response)
    except Exception as exc:
        # URLs include the API key; never print the exception.
        sys.exit('Scholar synchronization failed (network or API error).')
    if data.get('error') or data.get('search_metadata', {}).get('status') != 'Success':
        sys.exit('Scholar synchronization failed (service returned an error).')
    if start == 0:
        cited = data.get('cited_by', {})
        annual = cited.get('graph')
        table = cited.get('table') or []
        total = next((row.get('citations', {}).get('all') for row in table if 'citations' in row), None)
        if not isinstance(annual, list) or total is None:
            sys.exit('Scholar synchronization failed (missing citation history).')
    page = data.get('articles')
    if not isinstance(page, list):
        sys.exit('Scholar synchronization failed (missing publications).')
    for row in page:
        year = row.get('year')
        count = row.get('cited_by', {}).get('value', 0) or 0
        items.append({'title': row.get('title', ''), 'authors': row.get('authors', ''),
            'publication': row.get('publication', ''), 'year': int(year) if str(year).isdigit() else None,
            'citations': int(count), 'link': row.get('link', '')})
    pagination = data.get('serpapi_pagination') or {}
    if not pagination.get('next'):
        break
    if len(page) == 0 or start >= 10000:
        sys.exit('Scholar synchronization failed (invalid pagination).')
    start += len(page)
if not items or any(not p['title'] for p in items):
    sys.exit('Scholar synchronization failed (incomplete publication data).')
annual = sorted(({'year': int(x['year']), 'citations': int(x['citations'])} for x in annual), key=lambda x: x['year'])
if len({x['year'] for x in annual}) != len(annual) or any(x['citations'] < 0 for x in annual):
    sys.exit('Scholar synchronization failed (invalid citation history).')
result = {'updated_at': datetime.now(timezone.utc).isoformat(timespec='seconds'), 'source': 'Google Scholar via SerpApi',
          'total_citations': int(total), 'annual': annual, 'publications': items}
path = Path('data/citations.json')
path.parent.mkdir(exist_ok=True)
path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(f'Updated {len(items)} publications and {len(annual)} citation years.')
