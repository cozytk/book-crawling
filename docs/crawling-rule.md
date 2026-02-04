# 크롤링 방식 가이드

## 크롤링 방식 선택 플로우

```
[시작] requests로 던져본다. (Tier 1)
   ↓
[차단 발생?] 헤더(User-Agent)를 넣는다. (Tier 2)
   ↓
[데이터 없음?] JS 렌더링 문제다. → Playwright를 쓴다. (Tier 3)
   ↓
[너무 느림/대용량?] Network 탭을 분석해서 API 주소를 딴다. (Tier 4)
   ↓
[강력 차단?] curl_cffi나 playwright-stealth 같은 고급 회피 기술을 쓴다. (Tier 5)
```

---

## 플랫폼별 크롤링 방식

| 플랫폼 | 베이스 클래스 | 방식 | Tier | 이유 |
|--------|---------------|------|------|------|
| 교보문고 | `BasePlatformCrawler` | Playwright | 3 | 검색 결과가 JavaScript로 동적 로딩 |
| Yes24 | `BaseHttpCrawler` | HTTP (urllib) | 2 | 서버 사이드 렌더링, User-Agent만으로 우회 |
| 알라딘 | `BasePlatformCrawler` | Playwright | 3 | 리뷰 수가 동적 로딩 (API 전환 권장) |

---

## 베이스 클래스

### 1. BasePlatformCrawler (Playwright 기반)

**파일**: `crawlers/base.py`

```python
class BasePlatformCrawler(ABC):
    """Playwright 브라우저 기반 크롤러"""
```

**특징**:
- Headless Chromium 브라우저 사용
- JavaScript 렌더링 지원
- 메모리 사용량: ~200MB per instance
- 초기화 시간: 2-3초

**사용 시점**:
- 검색 결과나 리뷰가 JavaScript로 동적 로딩되는 경우
- AJAX 요청을 기다려야 하는 경우

### 2. BaseHttpCrawler (HTTP 기반)

**파일**: `crawlers/base_http.py`

```python
class BaseHttpCrawler(ABC):
    """HTTP 전용 크롤러 - 브라우저 없음"""
```

**특징**:
- urllib로 직접 HTTP 요청
- 브라우저 없이 HTML 파싱
- 메모리 사용량: ~20MB
- 즉시 실행 가능

**사용 시점**:
- 서버 사이드 렌더링 페이지
- JavaScript 없이 모든 데이터 접근 가능
- 자동화 감지를 우회해야 하는 경우 (Yes24)

---

## 플랫폼별 상세

### 교보문고 (Kyobo)

**방식**: Playwright (Tier 3)

**이유**: 검색 결과 목록이 JavaScript로 렌더링됨

**주요 셀렉터**:
- 검색 결과: `.prod_item`
- 책 제목: `input.result_checkbox[data-name]`
- 평점: `.review_score`
- 리뷰 수: 정규식 `\((\d[\d,]*)\s*개의\s*리뷰\)`

### Yes24

**방식**: HTTP/urllib (Tier 2)

**이유**:
- Playwright 사용 시 자동화 감지로 리다이렉트됨
- 서버 사이드 렌더링으로 모든 데이터 접근 가능

**주의사항**:
- User-Agent는 단순하게: `"Mozilla/5.0"`
- 매 요청마다 새로운 opener 생성
- UTF-8/EUC-KR 인코딩 폴백 처리

**주요 셀렉터**:
- 검색 결과 링크: `a.gd_name`
- 평점: `.gd_rating em`
- 리뷰 수: 정규식 `회원리뷰\s*\(\s*(\d[\d,]*)\s*건?\s*\)`

### 알라딘

**방식**: 현재 Playwright (Tier 3), API 권장 (Tier 4)

**권장 방안**: 알라딘 Open API
- TTBKey 발급 필요 (무료, 1-2일 승인)
- 일일 5,000회 무료 호출
- 더 정확하고 안정적인 데이터

---

## 성능 비교

| 항목 | Playwright | HTTP |
|------|------------|------|
| 메모리 | ~200MB | ~20MB |
| 초기화 시간 | 2-3초 | 없음 |
| 요청당 시간 | 3-5초 | 1-2초 |
| JavaScript 지원 | O | X |

---

## 새 크롤러 추가 시

1. 먼저 개발자 도구로 네트워크 탭 확인
2. JavaScript 비활성화 후 페이지 로드 테스트
3. 필요한 데이터가 초기 HTML에 있는지 확인
4. 적절한 Tier/베이스 클래스 선택
