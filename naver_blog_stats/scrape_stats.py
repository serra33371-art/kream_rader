"""네이버 크리에이터 어드바이저(블로그 통계) 데이터를 긁어서 CSV / 구글 시트로 저장.

사용법 요약 (자세한 건 README.md):
  1. 크롬 개발자도구 > Network > Fetch/XHR 에서 통계 API 요청을
     우클릭 > Copy > Copy as cURL (bash) 로 복사해 curl.txt 에 붙여넣기
  2. python scrape_stats.py --start 2026-09-01 --end 2026-09-22
  3. (선택) --sheet-id 를 주면 구글 시트에도 바로 붙여넣음
"""
import argparse
import csv
import json
import re
import shlex
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import requests

DATE_RE = re.compile(r'^\d{4}-\d{2}-\d{2}$')
# 이 헤더들은 requests 가 알아서 처리하므로 복사본에서 제외
SKIP_HEADERS = {'content-length', 'accept-encoding', 'host'}


def parse_curl(text):
    """'Copy as cURL (bash)' 문자열에서 url / headers / cookies 를 뽑아낸다."""
    text = text.replace('\\\n', ' ').replace('\\\r\n', ' ')
    tokens = shlex.split(text)
    url, headers, cookies = None, {}, {}
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok in ('-H', '--header'):
            key, _, value = tokens[i + 1].partition(':')
            key, value = key.strip(), value.strip()
            if key.lower() == 'cookie':
                cookies.update(_parse_cookie(value))
            elif key.lower() not in SKIP_HEADERS:
                headers[key] = value
            i += 2
        elif tok in ('-b', '--cookie'):
            cookies.update(_parse_cookie(tokens[i + 1]))
            i += 2
        elif tok in ('-X', '--request', '--data', '--data-raw', '--data-binary', '-d'):
            i += 2
        elif tok.startswith('http'):
            url = tok
            i += 1
        else:
            i += 1
    if not url:
        sys.exit('curl.txt 에서 URL 을 찾지 못했습니다. "Copy as cURL (bash)" 로 복사했는지 확인하세요.')
    return url, headers, cookies


def _parse_cookie(raw):
    out = {}
    for part in raw.split(';'):
        if '=' in part:
            k, v = part.strip().split('=', 1)
            out[k] = v
    return out


def with_date(url, day, start_key, end_key):
    """URL 의 날짜 파라미터를 day 로 바꾼다.

    --start-key/--end-key 를 주면 그 파라미터만, 아니면 YYYY-MM-DD 형태인
    모든 파라미터를 바꾼다.
    """
    parts = urlsplit(url)
    params = parse_qsl(parts.query, keep_blank_values=True)
    ds = day.isoformat()
    new = []
    for k, v in params:
        if start_key or end_key:
            if k in (start_key, end_key):
                v = ds
        elif DATE_RE.match(v):
            v = ds
        new.append((k, v))
    return urlunsplit(parts._replace(query=urlencode(new)))


def find_rows(obj):
    """응답 JSON 안에서 가장 큰 'dict 리스트'를 찾아 표 데이터로 사용."""
    best = []

    def walk(o):
        nonlocal best
        if isinstance(o, list):
            if o and all(isinstance(x, dict) for x in o) and len(o) > len(best):
                best = o
            for x in o:
                walk(x)
        elif isinstance(o, dict):
            for v in o.values():
                walk(v)

    walk(obj)
    if not best and isinstance(obj, dict):
        best = [obj]
    return best


def flatten(d, prefix=''):
    out = {}
    for k, v in d.items():
        key = f'{prefix}{k}'
        if isinstance(v, dict):
            out.update(flatten(v, key + '.'))
        elif isinstance(v, list):
            out[key] = json.dumps(v, ensure_ascii=False)
        else:
            out[key] = v
    return out


def daterange(start, end, step='day'):
    if step == 'month':
        d = start.replace(day=1)
        while d <= end:
            yield d
            d = (d + timedelta(days=32)).replace(day=1)
        return
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


def upload_to_sheet(rows, columns, sheet_id, worksheet, creds_path):
    import gspread  # pip install gspread

    gc = gspread.service_account(filename=creds_path)
    sh = gc.open_by_key(sheet_id)
    try:
        ws = sh.worksheet(worksheet)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=worksheet, rows=1000, cols=len(columns))
    values = [columns] + [[r.get(c, '') for c in columns] for r in rows]
    ws.clear()
    ws.update(values, 'A1')
    print(f'구글 시트 "{worksheet}" 탭에 {len(rows)}행 업로드 완료')


def main():
    p = argparse.ArgumentParser(description='네이버 블로그 통계 스크래퍼')
    p.add_argument('--curl', default='curl.txt', help='Copy as cURL(bash) 내용을 저장한 파일')
    p.add_argument('--start', help='시작일 YYYY-MM-DD (생략하면 복사한 URL 그대로 1번만 호출)')
    p.add_argument('--end', help='종료일 YYYY-MM-DD (기본: 어제)')
    p.add_argument('--start-key', help='시작일 파라미터 이름 (예: startDate). 생략 시 자동 감지')
    p.add_argument('--end-key', help='종료일 파라미터 이름 (예: endDate)')
    p.add_argument('--step', choices=['day', 'month'], default='day',
                   help='day: 하루씩 / month: 매월 1일로 (조회수 순위 같은 월간 화면)')
    p.add_argument('--out', default='blog_stats.csv', help='저장할 CSV 경로')
    p.add_argument('--dump', action='store_true', help='원본 JSON 을 raw/ 폴더에 저장 (구조 확인용)')
    p.add_argument('--delay', type=float, default=1.0, help='요청 간 대기(초)')
    p.add_argument('--sheet-id', help='구글 시트 ID (URL 의 /d/<ID>/edit 부분)')
    p.add_argument('--worksheet', default='blog_stats', help='구글 시트 탭 이름')
    p.add_argument('--creds', default='service_account.json', help='구글 서비스계정 키 파일')
    args = p.parse_args()

    url, headers, cookies = parse_curl(Path(args.curl).read_text(encoding='utf-8'))
    session = requests.Session()
    session.headers.update(headers)
    session.cookies.update(cookies)

    if args.start:
        start = date.fromisoformat(args.start)
        end = date.fromisoformat(args.end) if args.end else date.today() - timedelta(days=1)
        targets = [(d.isoformat(), with_date(url, d, args.start_key, args.end_key))
                   for d in daterange(start, end, args.step)]
    else:
        targets = [('', url)]

    all_rows = []
    for label, target in targets:
        resp = session.get(target, timeout=20)
        if resp.status_code in (401, 403):
            sys.exit(f'[{resp.status_code}] 인증 실패 - 쿠키가 만료됐습니다. 개발자도구에서 cURL 을 다시 복사하세요.')
        resp.raise_for_status()
        try:
            data = resp.json()
        except ValueError:
            sys.exit('JSON 이 아닌 응답입니다. Fetch/XHR 요청(api 주소)을 복사했는지 확인하세요.\n'
                     + resp.text[:300])

        if args.dump:
            Path('raw').mkdir(exist_ok=True)
            name = label or datetime.now().strftime('%Y%m%d_%H%M%S')
            Path(f'raw/{name}.json').write_text(
                json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')

        rows = [flatten(r) for r in find_rows(data)]
        for r in rows:
            if label:
                r = {'request_date': label, **r}
            all_rows.append(r)
        print(f'{label or "요청"}: {len(rows)}행')
        if len(targets) > 1:
            time.sleep(args.delay)

    if not all_rows:
        sys.exit('가져온 데이터가 없습니다. --dump 로 원본 JSON 을 확인하세요.')

    columns = []
    for r in all_rows:
        for k in r:
            if k not in columns:
                columns.append(k)

    # utf-8-sig: 엑셀/구글시트에서 한글 안 깨지게
    with open(args.out, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=columns)
        w.writeheader()
        w.writerows(all_rows)
    print(f'{args.out} 저장 완료 ({len(all_rows)}행, {len(columns)}열)')

    if args.sheet_id:
        upload_to_sheet(all_rows, columns, args.sheet_id, args.worksheet, args.creds)


if __name__ == '__main__':
    main()
