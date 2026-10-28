# 검색 소스 전반 개선 및 실제 요청 검증 — 2026-10-28

## 확인 방법

Aside의 실제 로그인 세션과 별도의 Chrome DevTools 백그라운드 컨텍스트에서 검색 화면, 상품 페이지, DOM 및 Network 요청을 조사했다. 사용자 브라우저의 쿠키나 Cloudflare 통과 상태를 운영 서버에 복사하지 않았다. 정상 브라우저 접근, 별도 브라우저 접근, 서버 HTTP 수집은 별도로 확인했다.

운영 API의 이전 버전과 검증 배포에 같은 10개 검색을 수행한다. `scripts/benchmark_live_sources.py`는 강제 새로 조회, 첫 결과 시간, 전체 완료 시간, 소스별 상태·실제 상품·저자·ISBN, HTTP 요청 수를 기록한다. 실제 사이트 소수 실측이며 통계적인 전체 정확도로 해석하지 않는다. 모의 회귀 테스트와 실검색 결과를 구분한다.

## 조사한 소스별 요청과 반영

| 소스 | 실제 확인한 요청·응답 | 반영 |
|---|---|---|
| 알라딘 | `/ttb/api/ItemSearch.aspx?Query=…&QueryType=Keyword&SearchTarget=Book`, ItemLookUp의 원제·ISBN·저자·ratingInfo. 웹 검색은 `/search/wsearchresult.aspx?SearchTarget=Book&SearchWord=…` | 제목·저자·상품 종류를 검증한 후보에서 공통 작품과 판본 ISBN을 정함. 제목 뒤 1·2권을 작품 검색에서 허용. 청소년 분류에 숨은 축약판보다 일반 판본을 우선하되 어린이 원작 자체를 일괄 배제하지 않음. |
| 교보 | `https://search.kyobobook.co.kr/search?keyword=…&gbCode=TOT&target=total`. 목록의 대표 저자는 `.prod_author_group .author.rep`, 상품 식별자는 상품의 구조화된 ISBN 속성 | 공유 ISBN을 우선 사용. 실패하면 같은 저자 아래에서 제목으로 재탐색. 목록의 집계 점수가 있으면 별도 오래된 통계 API를 호출하지 않음. |
| Yes24 | `/Product/Search?domain=ALL&query=…`, 상품 `/product/goods/{id}`. `domain=BOOK`은 실제 브라우저에서 홈으로 이동하므로 채택하지 않음. 목록 `.gd_res`는 도서·전자책·CD 등을 구분함 | 실제 도서 상품만 선택. 검증한 ISBN의 Book 메타데이터와 상품 번호를 확인. 명시적인 저자·판본을 공유하고, 제목 검색에서는 원저·각색 및 다른 저자의 동명 도서를 거름. |
| 사락 | Network에서 `/api24/v1/reading-note/book/{id}/book-info`, `/book-statistics-summary` 확인 | Yes24에서 검증한 동일 상품 번호와 ISBN을 재사용. 평가 참여 수와 글 리뷰 수를 혼동하지 않음. |
| 왓챠피디아 | 실제 화면은 `/ko/search?query=…`, 상세는 `/ko/contents/{code}`. Network에는 `/api/searches`, `/api/contents/{code}`도 있으나 일반 API 요청은 허용된 클라이언트 헤더가 없으면 거부됨 | 잘못된 이전 검색 경로를 교체. 브라우저 호환 HTTP와 연결 재사용을 적용. 공개 HTML의 책 결과와 Book JSON-LD를 사용하며 영화·시리즈·추천 영역을 제외. 임시 search_id를 결과 URL에서 제거. |
| Goodreads | `/search?q=…`, `/book/isbn/{isbn}`, `/book/show/{id}`. 실제 UI에 기존 테이블과 새 `[data-testid=book-item-title]` 카드 구조가 공존 | 두 구조 지원. 목록에 저자가 없으면 상세에서 확인. 검증한 작품의 긴 설명 부제는 다른 판본의 필수 제목으로 강제하지 않음. 정확한 Book ISBN 및 상세 저자를 재확인. |
| Amazon | `/s?k=…&i=stripbooks`, `/dp/{ASIN}`. 실제 검색 첫 항목에 오디오북이 섞임. 서버 요청에는 일시적인 503도 관측 | 도서 카테고리, 제목·저자와 상품 식별자를 함께 확인. 요청하지 않은 오디오북을 걸러낸 뒤 일반 링크 폴백으로 다시 채택하지 않음. 집계 평가만 사용. 서버 제한은 성공으로 처리하지 않음. |
| LibraryThing | 실제 검색은 `/search.php?search=…&searchtype=newwork_titles&sortchoice=0`. 상세는 `/work/{id}/t/{slug}`. 현재 평점은 작품 헤더 `.pagecard .lt_scoreboard`에 있음 | `term` 대신 확인한 `search` 인자를 사용. 작품 헤더의 점수·Reviews만 추출하고 Members는 별점 참여 수로 바꾸지 않음. 차단된 같은 호스트 요청을 반복하지 않음. 상세 수집 제한 시 점수를 채워 넣지 않음. |

## 공통 탐색·식별 흐름

1. 공통 카탈로그의 제목·저자로 한 작품을 먼저 선택한다. 국내 소스가 제각각 첫 결과를 고르지 않도록 ISBN을 공유한다.
2. ISBN이 있는 국내 소스는 그 판본을 먼저 찾는다. 해당 판본이 없으면 알려진 저자를 유지한 채 제목 검색을 재시도한다. 사용자가 직접 입력한 ISBN은 다른 판본으로 완화하지 않는다.
3. 제목 검색은 작품 기준이므로 권수가 명시되지 않았을 때 여러 권으로 나뉜 판본을 찾을 수 있다. 권수를 입력하면 기존 권수 불일치 차단을 유지한다. 가능하면 첫 권을 우선한다.
4. `제목 저자`, `저자 제목` 입력에서 실제 후보의 저자 메타데이터로 확인한 단어만 분리한다. 임의 단어를 삭제해 유사한 책을 만들지 않는다.
5. 원어 저자명은 ISBN을 검증한 Yes24 판본의 ‘저’ 소개 영역에서 얻는다. 번역자나 관련 추천 작가의 영문 이름을 사용하지 않는다. 동명 저자를 막으면서 여러 언어의 표기를 연결한다.
6. Open Library의 Work → matching Edition → ISBN 연결과 author key의 대체 이름을 활용한다. 원제와 영문 제목이 다르더라도 같은 작품의 판본 연결이 확인되어야 사용한다. 작품·평점의 고정 검색어별 정답 분기는 두지 않았다. 관측한 일부 저자명 표기 차이는 명시적인 인명 별칭으로만 보관한다.

Open Library는 `editions.key`를 포함해야 이번 조사에서 실제 matching edition 문서가 반환되었다. `fields`에 작품과 판본의 식별자·제목·ISBN을 함께 요청한다. [Search API](https://openlibrary.org/dev/docs/api/search), [Authors API](https://openlibrary.org/dev/docs/api/authors)의 구조를 실제 응답과 대조했다.

이전 식별 규칙의 검색·소스 캐시는 버전 5에서 재사용하지 않는다. 과거 검색 기록은 남기고 기존처럼 재검증 안내를 표시한다.

## 실검색에서 드러난 기존 문제

- ‘인간의 굴레에서’는 모든 국내 소스에서 정상 분권 제목을 제외했고 해외 검색도 시작하지 못했다.
- ‘전쟁과 평화’는 Yes24·사락에서 아자 가트의 동명 도서를 골랐다.
- ‘죄와 벌’도 Yes24·사락에서 김동인 작품을 골랐고, 알라딘은 청소년 판본을 우선했다.
- `Clean Code`는 국내 일부 소스에서 Kameron Hussain의 다른 책을 골랐다.
- `1984`의 LibraryThing 검색은 그래픽노블 후보를 채택했다. 평점은 없었지만 작품 정보 자체도 잘못될 수 있었다.

이 사례들은 제목 몇 개에 대한 URL·평점을 고정하는 방식으로 수정하지 않았다.

## 검증 및 배포 결과

회귀 검사와 최종 운영 배포, 10개 검색 비교 결과는 아래에 추가한다. LibraryThing의 일반 브라우저 세션은 열렸지만 깨끗한 별도 Chrome 컨텍스트와 서버 HTTP는 Cloudflare 검증 페이지를 받았다. 브라우저에서 열린다는 사실을 운영 크롤러의 수집 성공으로 간주하지 않는다.
