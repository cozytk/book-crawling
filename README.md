# 갈피 · Book Crawler

책 제목으로 알라딘·교보문고·Yes24·사락·왓챠·Goodreads·Amazon·LibraryThing의 평점과 평가 수를 비교합니다. 각 사이트가 고른 판본과 집계 방식이 다르므로, 카드의 제목과 원문 링크를 함께 확인하세요. 평균은 수집된 플랫폼의 10점 환산 평점을 단순 평균한 값입니다. ‘리뷰 수’에는 사이트에 따라 별점 참여자 수가 포함됩니다.

## 로컬 실행

Python 3.11 이상, uv, Node.js 22.7 이상이 필요합니다.

```sh
uv sync --frozen
cp .env.example .env
```

`.env`에 `ALADIN_TTB_KEY`를 설정하면 알라딘과 한국어 제목의 원서 연결을 사용할 수 있습니다. API 키는 커밋하지 않습니다. 별도 DB 설정 없이 로컬 SQLite에 검색 기록을 보존합니다.

저장소 루트에서 API 실행:

```sh
uv run uvicorn api.app:app --host 127.0.0.1 --port 8000
```

`web/` 디렉터리에서 웹 실행:

```sh
npm ci
npm run dev -- --hostname 127.0.0.1
```

접속: http://localhost:3000 · API 문서: http://127.0.0.1:8000/docs

`BOOK_CRAWLER_DB`가 설정되면 Supabase보다 우선합니다. Supabase를 쓰려면 이 변수를 제거하고 `SUPABASE_URL`과 `SUPABASE_KEY`를 함께 설정하세요. 로컬 DB 파일은 `data/searches.sqlite3`이며 Git에서 제외됩니다. SQLite 파일은 지속 가능한 디스크가 있는 로컬 환경용입니다.

## 검증

```sh
uv run pytest -q
```

`web/`에서:

```sh
npm test
npm run build
npm audit
```

검색은 제목 일치도를 먼저 확인하고, 확인된 원서 제목 또는 Edition → Work 연결을 이용합니다. 같은 저자라는 이유만으로 다른 작품을 연결하지 않습니다. 로컬 캐시는 검색한 플랫폼 범위를 기억하며, 일부 플랫폼 검색이 전체 검색의 캐시로 사용되지 않습니다. 기존 Supabase 레코드는 범위 정보가 없으므로 실제 결과에 포함된 플랫폼에만 재사용합니다.

사이트 차단이나 원서 정보 부족으로 결과가 누락될 수 있습니다. 누락 플랫폼은 검색 완료 화면에 표시합니다. 모든 플랫폼의 수집을 보장하지 않습니다.

## Vercel 배포

웹과 Python API를 Vercel의 별도 프로젝트로 실행하고, 검색 기록은 비공개 Vercel Blob에 저장합니다. 운영에 GCP·Supabase가 필요하지 않습니다. 기존 외부 자원과 과거 DB 데이터는 변경하거나 자동 이전하지 않습니다.

- 웹: `book-crawling`, 루트 `web/`, 서울 `icn1`.
- API: `book-crawling-api`, `scripts/prepare-vercel-api.py`로 `.deploy/api/`에 생성, 서울 `icn1`.
- 저장소: API에 연결한 비공개 Blob. UUID별 불변 기록과 검색어별 24시간 캐시를 분리합니다. 기록 화면은 최근 500개를 표시합니다. 읽을 책 목록은 기존처럼 브라우저에 보관합니다.
- 브라우저는 같은 출처의 `/api/*`를 호출합니다. Next.js가 서버 전용 `API_SERVICE_TOKEN`으로 API에 연결하며, API 주소·키를 클라이언트 번들에 넣지 않습니다. 기존 웹 `ACCESS_TOKEN` 인증을 유지합니다.

웹 환경 변수: `API_BACKEND_URL`, `API_SERVICE_TOKEN`, 기존 `ACCESS_TOKEN`.
API 환경 변수: `API_SERVICE_TOKEN`, 연결된 Blob 자격 증명, `ALADIN_TTB_KEY` 및 선택적인 Google Books/AI 키. **운영 API에 `BOOK_CRAWLER_DB`나 Supabase 변수를 설정하지 않습니다.**

```sh
python3 scripts/prepare-vercel-api.py
vercel project inspect --cwd .deploy/api --scope cozytks-projects
vercel deploy --prod --cwd .deploy/api --scope cozytks-projects
vercel project inspect --scope cozytks-projects
vercel deploy --prod --skip-domain --scope cozytks-projects
# 생성된 웹 배포를 검증한 뒤:
vercel promote <검증한-웹-배포-URL> --scope cozytks-projects
```

최초 준비 시 API 프로젝트를 생성하고 `.deploy/api/`에 명시적으로 연결합니다. 비공개 Blob을 API 프로젝트에 연결하고, 두 프로젝트에 같은 API 서비스 토큰을 Secret으로 설정하세요. 로그인은 원래 `cozytk` 팀을 사용할 수 있는 계정이어야 합니다. 키나 `.env`를 저장소에 추가하지 않습니다.

API는 HTTP 크롤러만 패키징하므로 Playwright 브라우저·pandas·Docker가 필요하지 않습니다. 사이트별 조회는 동시 실행하고, 플랫폼 조회 18초·원서 해석 12초·선택적 AI 소개 20초의 제한을 둡니다. 차단되거나 일치하는 책이 없는 사이트는 결과를 대체하지 않고 누락 상태로 표시합니다.

검증 결과와 저장소 선택의 제한은 [Vercel 전환 보고서](docs/vercel-migration-20261028.md), 이전 복구 과정은 [복구 보고서](docs/recovery-20261027.md)를 참고하세요.
