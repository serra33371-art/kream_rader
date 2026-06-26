import requests
import json
import os
from datetime import datetime, timezone

API_KEY = os.environ.get('NEWS_API_KEY', '')

QUERIES = [
    {'q': 'sneaker collab limited edition', 'tags': ['collab', 'sneakers']},
    {'q': 'limited edition drop exclusive sneaker', 'tags': ['limited', 'sneakers']},
    {'q': '콜라보 한정판', 'tags': ['collab', 'limited']},
    {'q': '한정판 발매 스니커즈', 'tags': ['limited', 'sneakers']},
    {'q': 'fashion collaboration exclusive', 'tags': ['fashion', 'collab']},
    {'q': '패션 콜라보 컬렉션', 'tags': ['fashion', 'collab']},
    {'q': 'pokemon collab limited', 'tags': ['kidult', 'collab']},
    {'q': '키덜트 피규어 콜라보 한정', 'tags': ['kidult', 'collab']},
    {'q': 'Nike Jordan collab release', 'tags': ['sneakers', 'collab']},
    {'q': 'Adidas collaboration limited', 'tags': ['sneakers', 'collab']},
]

seen = set()
items = []

for qobj in QUERIES:
    try:
        url = 'https://newsapi.org/v2/everything'
        params = {
            'q': qobj['q'],
            'sortBy': 'publishedAt',
            'pageSize': 20,
            'apiKey': API_KEY,
        }
        res = requests.get(url, params=params, timeout=10)
        data = res.json()
        articles = data.get('articles', [])
        for a in articles:
            link = a.get('url', '')
            title = a.get('title', '')
            if not link or not title or title == '[Removed]' or link in seen:
                continue
            seen.add(link)
            items.append({
                'id': link,
                'title': title,
                'desc': a.get('description') or '',
                'link': link,
                'image': a.get('urlToImage') or '',
                'date': a.get('publishedAt') or '',
                'source': (a.get('source') or {}).get('name') or '',
                'tags': qobj['tags'],
            })
    except Exception as e:
        print(f"오류 ({qobj['q']}): {e}")

output = {
    'updated': datetime.now(timezone.utc).isoformat(),
    'count': len(items),
    'items': items,
}

with open('data.json', 'w', encoding='utf-8') as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print(f"완료: {len(items)}개 저장")
