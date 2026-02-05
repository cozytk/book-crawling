# version 0.0.1
- 책 제목을 입력하면 해당 책의 평점, 리뷰수를 플랫폼 별로 수집
    - 수집할 플랫폼
        - 국내
            - 교보문고
            - yes24
            - 알라딘
            - 왓챠피디아
            - 리디북스
            - 밀리의 서재
            - 사락
        - 해외
            - amazon books
            - goodreads
- 사실 평점은 구글 검색만 해도 상단에 나오기 때문에, 플랫폼 별 크롤링 보안이 강하다면 구글 검색으로 대체하는 것도 고려

### 고민
- 모든 플랫폼을 통틀어 고유한 책을 식별할 수 있는 방법
    - 첫번째 접근: 책제목을 통해 ISBN을 찾고, ISBN을 통해 각 플랫폼에서 책을 찾기
        - 한계: 번역된 책의 경우 ISBN이 다를 수 있음 

---

# 문제 분석 로그

## [2026-02-04] 교보문고 검색 결과 불일치 문제

### 현상
```
검색어: "밝은밤 최은영"
- kyobo: [국내도서] 최은영 3종 특별 한정 에디션 (X)
- yes24: 밝은 밤 (O)
- aladin: 밝은 밤 (O)
```

### 원인 분석
1. **검색 결과 우선순위 문제**: 교보문고 검색 결과에서 "3종 특별 한정 에디션"이 상위에 노출
2. **매칭 로직 한계**: 현재 로직은 `query_lower in book_name.lower()`로 체크하는데, "밝은밤"이 "[국내도서] 최은영 3종 특별 한정 에디션"에 포함되지 않음
3. **폴백 동작**: 정확한 매칭이 없으면 첫 번째 유효한 결과를 반환

### 해결 방안 (우선순위)
1. **[P1] 제목 매칭 개선**: 검색어의 각 단어가 제목에 포함되는지 개별 체크
   - "밝은밤" → "밝은 밤" 공백 처리
   - "최은영" → 저자명으로 분리하여 저자 필드에서 매칭
2. **[P2] 세트/에디션 제외**: "[세트]", "에디션", "3종" 등 키워드가 포함된 결과 제외
3. **[P3] 저자명 활용**: 검색어에서 저자명 추출하여 별도 검증

### 테스트 케이스
- "밝은밤 최은영" → "밝은 밤" 찾아야 함
- "클린 코드" → "Clean Code(클린 코드)" 찾아야 함 (현재 정상)
- "해리 포터" → 세트 상품 아닌 개별 권 우선

---

## [2026-02-04] 교보문고 Playwright 연결 오류 (해결됨)

### 현상
```
[kyobo] 에러 발생: Connection closed while reading from the driver
```

### 원인 분석
- **핵심 원인**: Python 3.14 + asyncio + urllib 사용 후 subprocess/Playwright 실행 시 SIGSEGV (-11) 발생
- urllib.request.build_opener() 사용 후 새 Python 프로세스에서 Playwright 초기화 시 크래시
- 교보문고 검색 결과는 HTTP로 가져올 수 있으나, 평점/리뷰는 JavaScript 동적 로딩 필요 → Playwright 유지

### 테스트 결과
| 테스트 케이스 | 결과 |
|--------------|------|
| Kyobo 단독 실행 | 정상 |
| HTTP 크롤러 후 Kyobo 실행 | SIGSEGV |
| Kyobo 먼저 실행 후 HTTP | **정상** |

### 해결 방법
**실행 순서 변경**: Playwright 기반 크롤러를 HTTP 크롤러보다 먼저 실행

```python
# main.py 수정
# 1. Playwright 기반 크롤러 먼저 실행 (HTTP 전에)
for p in browser_platforms:
    result = await crawl_platform(CRAWLERS[p], query)

# 2. HTTP 기반 크롤러 나중에 실행
http_results = await asyncio.gather(*http_tasks)

---

## [2026-02-04] 알라딘 API 전환 완료

### 변경 내용
- Playwright 기반 크롤러 → API 기반 크롤러
- `ItemSearch` API로 검색, `ItemLookUp` API로 평점/리뷰 조회

### 개선 효과
| 항목 | 크롤링 | API |
|------|--------|-----|
| 속도 | 5-7초 | 0.5-1초 |
| 메모리 | ~200MB | ~20MB |
| 리뷰 수 정확도 | 6건 (파싱 오류) | 234건 (정확) |
| 안정성 | HTML 변경에 취약 | 안정적 |

---

## [2026-02-04] 교보문고 HTTP 전환 완료

### 정적 렌더링 테스트 결과

| 소스 | 정적 HTML에 평점? | 정적 HTML에 리뷰수? | HTTP 가능? |
|------|------------------|-------------------|-----------|
| **검색 페이지** | ✅ 예 | ✅ 예 | **가능** |
| **상세 페이지** | ✅ 예 (JSON-LD) | ✅ 예 | **가능** (Referer 헤더 필요) |
| 구글 검색 | ❌ (JS 필요) | ❌ | 불가 |

### 발견된 HTML 구조
```html
<span class="review_klover_box">
    <span class="review_klover_text font_size_xxs">9.8</span>
    <span class="review_desc">(127건)</span>
</span>
```

### 변경 내용
- `BasePlatformCrawler` (Playwright) → `BaseHttpCrawler` (urllib)
- 검색 페이지에서 평점/리뷰 수 직접 추출 (1회 HTTP 요청)
- 상세 페이지 접근 불필요 → 속도 대폭 개선

### 개선 효과
| 항목 | Before (Playwright) | After (HTTP) |
|------|---------------------|--------------|
| 메모리 | ~200MB | ~20MB |
| 속도 | 5-7초 | 1-2초 |
| 실행 순서 | 반드시 먼저 실행 | 병렬 실행 가능 |

### 테스트 결과
```
검색어: 돈의 방정식
- aladin: 10/10 (2건) - 돈의 방정식
- kyobo:  9.8/10 (127건) - 돈의 방정식
- yes24:  9.5/10 (59건) - 돈의 방정식
평균: 9.77/10, 총 188개
```

### 미해결 이슈: 교보문고 검색어 처리
- "밝은밤 최은영" 검색 시 교보문고 검색 엔진이 세트 상품을 우선 노출
- "밝은 밤" (공백 포함) 검색 시에는 정상 결과
- 원인: 교보문고 검색 엔진의 토큰화 방식 차이
- 향후 대응: 검색 실패 시 공백 변형 재검색 로직 추가 고려

### 향후 확장성
리뷰 텍스트 크롤링 필요 시:
```python
# crawlers/kyobo_review.py (향후 생성)
class KyoboReviewCrawler(BasePlatformCrawler):
    """Playwright 기반 리뷰 텍스트 크롤러"""
    async def get_reviews(self, url: str) -> list[dict]:
        # 상세 페이지 접근 → 리뷰 탭 → 페이지네이션
```

---

## [2026-02-04] CloudFront 차단 우회 방법 발견

### 테스트 결과

| 방법 | 응답 크기 | 결과 |
|------|----------|------|
| 기본 User-Agent | 0 bytes | ❌ 차단 |
| 전체 브라우저 헤더 | 50KB | ⚠️ 부분 성공 |
| **Referer 헤더 추가** | 273KB | ✅ **성공** |

### 해결 방법
```python
headers = {
    "User-Agent": "Mozilla/5.0 ...",
    "Referer": "https://search.kyobobook.co.kr/",  # 핵심!
}
```

### 상세 페이지 JSON-LD 데이터
```json
{
  "@type": "AggregateRating",
  "ratingValue": "9.8",
  "ratingCount": "127",
  "bestRating": "10"
}
```

### 구현
`KyoboCrawler.get_rating_from_detail(url)` 메서드 추가:
- 기본 동작: 검색 페이지에서 추출 (1회 요청, 빠름)
- 대안: `get_rating_from_detail()`로 상세 페이지에서 JSON-LD 추출 (2회 요청, 정확)

---

## [2026-02-04] Goodreads 크롤러 추가 (해외 플랫폼 첫 연동)

### 책 식별 방법 리서치

| 방법 | 한국어 책 지원 | 번역본 연결 | 결론 |
|------|-------------|-----------|------|
| Open Library | ❌ 0건 | ✅ Work ID | 한국어 미지원 |
| Google Books | ✅ 좋음 | ❌ 없음 | 연결 불가 |
| **알라딘 API** | ✅ 사용 중 | - | **채택** |

### Goodreads 크롤링 분석

| 페이지 | 데이터 위치 | HTTP 가능? |
|--------|-----------|-----------|
| **상세 페이지** | JSON-LD `aggregateRating` | ✅ **가능** |
| 검색 페이지 | 텍스트 파싱 필요 | ⚠️ JS 의존적 |

### 구현 방식
- **상세 페이지 JSON-LD 추출** (교보문고와 동일 방식)
- ISBN 검색 시 상세 페이지로 직접 리다이렉트
- 5점 만점 → 10점 만점으로 정규화

### JSON-LD 구조
```json
{
  "@type": "AggregateRating",
  "ratingValue": 4.38,
  "ratingCount": 32072,
  "reviewCount": 3238
}
```

### 테스트 결과
```
검색어: Clean Code
플랫폼: aladin, kyobo, yes24, goodreads
============================================================

플랫폼       평점          리뷰 수     책 제목
----------------------------------------------------------------------
aladin     9.6/10       6          클린 코드 Clean Code
kyobo      9.8/10       117        Clean Code(클린 코드)
yes24      9.5/10       101        Clean Code 클린 코드
goodreads  4.35/5       1471       Clean Code: A Handbook of Agile...
----------------------------------------------------------------------

평균 평점 (10점 만점): 9.40
총 리뷰 수: 1,695개
```

### 파일 변경
| 파일 | 변경 내용 |
|------|----------|
| `crawlers/goodreads.py` | **신규** - HTTP 기반 Goodreads 크롤러 |
| `crawlers/__init__.py` | GoodreadsCrawler export 추가 |
| `main.py` | goodreads 플랫폼 등록 |

### 향후 확장
- **원서-번역본 연결**: 알라딘 API에서 원서 ISBN 조회 → Goodreads 검색
- **Amazon Books 추가**: Goodreads와 유사한 구조