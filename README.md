# Book Crawler

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

## 2026-10-27 복구 상태

코드, 로컬 실행, SQLite 기록 저장을 복구했습니다. 기존 Vercel 팀 접근도 복구했습니다. 외부 배포는 GCP 결제 계정 종료와 Supabase DNS 조회 실패로 복구가 남아 있습니다. 새 Supabase 무료 DB 생성은 약관 동의가 필요해 보류 중입니다. 세부 검증과 제한은 [복구 보고서](docs/recovery-20261027.md)를 참고하세요.
