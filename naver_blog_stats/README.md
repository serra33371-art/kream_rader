# 네이버 블로그 통계 스크래퍼

크리에이터 어드바이저(`creator-advisor.naver.com`) 화면은 React 앱이라 HTML(Elements 탭)에는 숫자가 없습니다.
화면이 내부 **API(JSON)** 를 호출해서 그리는 구조라, 그 API 요청을 그대로 복사해 파이썬으로 다시 호출합니다.

## 1. 개발자도구에서 할 일

1. 크리에이터 어드바이저 > 블로그 > 통합 데이터(원하는 탭: 방문 분석 / 조회수 순위 등) 화면을 연다
2. `F12` → **Network** 탭 → 필터에서 **Fetch/XHR** 선택
3. `Ctrl+R`(새로고침) 또는 날짜/탭을 한 번 바꿔서 요청이 새로 찍히게 한다
4. 목록에서 `api` 가 들어간 요청을 하나씩 클릭 → 오른쪽 **Preview / Response** 에서
   화면의 숫자(예: 156)가 들어있는 요청을 찾는다
   - 검색창(`Ctrl+F`, Network 탭 안)에 화면 숫자를 쳐도 해당 요청이 찾아진다
5. 그 요청을 우클릭 → **Copy → Copy as cURL (bash)**
   - 윈도우라면 `(cmd)` 말고 꼭 **(bash)** 를 고르세요
6. 이 폴더에 `curl.txt` 파일을 만들어 붙여넣고 저장

> 확인해두면 좋은 것: **Headers → Request URL** 의 파라미터 이름
> (예: `startDate`, `endDate`, `date`, `metric`, `contentType` …). 날짜 파라미터 이름을 알면 `--start-key` 로 지정 가능.

⚠️ `curl.txt` 에는 로그인 쿠키(`NID_AUT`, `NID_SES`)가 들어있습니다. **절대 커밋/공유하지 마세요** (.gitignore 처리됨).
쿠키가 만료되면(401/403) 5번을 다시 하면 됩니다.

## 2. 실행

```bash
pip install -r requirements.txt

# 복사한 요청 그대로 1번 호출 + 원본 JSON 확인
python scrape_stats.py --dump

# 날짜별로 반복 호출 (URL 안의 YYYY-MM-DD 값을 자동으로 바꿔가며)
python scrape_stats.py --start 2026-09-01 --end 2026-09-22

# 날짜 파라미터 이름을 직접 지정
python scrape_stats.py --start 2026-09-01 --end 2026-09-22 --start-key startDate --end-key endDate
```

결과: `blog_stats.csv` (한글 안 깨지는 UTF-8 BOM). 구글 시트에서 **파일 → 가져오기** 하거나 그냥 복붙.

팁: 화면에서 기간을 "15일"처럼 길게 잡고 복사하면 한 번 호출로 여러 날짜가 오는 경우가 많습니다.
그땐 `--start` 없이 그냥 실행하는 게 제일 간단합니다.

## 3. (선택) 구글 시트에 바로 올리기

1. Google Cloud Console → 서비스 계정 생성 → JSON 키 다운로드 → 이 폴더에 `service_account.json`
2. Google Sheets API / Drive API 사용 설정
3. 대상 시트를 서비스 계정 이메일(`...@...iam.gserviceaccount.com`)에 **편집자**로 공유
4. 실행:

```bash
python scrape_stats.py --start 2026-09-01 --end 2026-09-22 --sheet-id <시트ID> --worksheet 방문분석
```

지정한 탭을 비우고 새로 씁니다.
