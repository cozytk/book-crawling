# OpenObserve 대시보드 가이드

크롤러 검색 결과 분석 및 실행 단위 모니터링을 위한 OpenObserve 대시보드 구성 가이드입니다.

## 접속 정보

- URL: http://localhost:5080
- 로그인: admin@example.com / admin123
- 스트림: `crawler`

---

## 1단계: 대시보드 변수(Variable) 설정 가이드

변수를 설정하면 대시보드 상단에서 특정 `execution_id`(검색 실행 단위)를 선택하여 데이터를 필터링할 수 있습니다.

1.  **Dashboards** 메뉴에서 생성한 대시보드로 이동합니다.
2.  우측 상단 **Settings** (톱니바퀴 아이콘) → **Variables** 메뉴를 클릭합니다.
3.  **Add Variable** 버튼을 클릭하고 아래와 같이 입력합니다:
    -   **Name**: `execution_id`
    -   **Label**: 검색 실행 ID
    -   **Type**: `Query`
    -   **Query**:
        ```sql
        SELECT DISTINCT execution_id
        FROM crawler
        WHERE execution_id IS NOT NULL
        ORDER BY _timestamp DESC
        LIMIT 100
        ```
4.  **Save** 버튼을 눌러 저장합니다. 이제 대시보드 상단에 드롭다운 메뉴가 나타납니다.

---

## 패널 1: 검색 실행 히스토리 (종합 요약)

각 검색 실행(`execution_id`)별로 어떤 책을 찾았고, 주요 플랫폼별 평점이 어떠했는지 한 줄로 요약하여 보여줍니다.

### SQL 쿼리
```sql
SELECT
  execution_id,
  query as searched_book,
  -- ratings
  res_kyobo_rating as ky_r,
  res_yes24_rating as y24_r,
  res_aladin_rating as al_r,
  res_sarak_rating as sr_r,
  res_goodreads_rating as gr_r,
  res_amazon_rating as am_r,
  res_librarything_rating as lt_r,
  -- reviews
  res_kyobo_reviews as ky_cnt,
  res_yes24_reviews as y24_cnt,
  res_aladin_reviews as al_cnt,
  res_sarak_reviews as sr_cnt,
  res_goodreads_reviews as gr_cnt,
  res_amazon_reviews as am_cnt,
  res_librarything_reviews as lt_cnt,
  elapsed_ms as time_ms,
  ts
FROM crawler
WHERE event = 'search_summary'
ORDER BY _timestamp DESC
LIMIT 50
```

### 설정
-   **Chart Type**: Table (표)
-   **Title**: "검색 실행별 평점 요약"
-   **Interaction**: `execution_id` 컬럼 클릭 시 Dashboard 변수(`$execution_id`)가 업데이트되도록 설정하면 편리합니다.

---

## 패널 2: 플랫폼별 상세 결과 (상세 보기)

상단 드롭다운에서 선택된 `execution_id`에 속한 플랫폼들의 상세 정보(리뷰 수, 정규화된 평점 등)를 보여줍니다.

### SQL 쿼리
```sql
SELECT
  crawler as platform,
  title as book_title,
  rating,
  review_count,
  elapsed_ms,
  url
FROM crawler
WHERE execution_id = '$execution_id'
  AND event = 'crawl_complete'
  AND crawler != 'main'
ORDER BY rating DESC
```

### 설정
-   **Chart Type**: Table (표)
-   **Title**: "선택된 실행($execution_id)의 플랫폼별 결과"

---

## 패널 3: 시도 및 에러 현황

크롤링 과정에서 발생한 에러나 재시도 내역을 확인합니다.

### SQL 쿼리 (에러 로그)
```sql
SELECT
  ts,
  crawler,
  error,
  query
FROM crawler
WHERE level = 'ERROR' 
  AND (execution_id = '$execution_id' OR '$execution_id' = '')
ORDER BY _timestamp DESC
LIMIT 20
```

---

## 로그 필드 참조

| 필드 명 | 설명 |
| :--- | :--- |
| `execution_id` | **유저의 한 번의 검색 단위**를 묶어주는 고유 ID |
| `event` | 로그 종류 (`crawl_start`, `search_summary`, `crawl_complete` 등) |
| `res_{platform}_rating` | 요약 로그(`search_summary`)에 포함된 각 플랫폼별 평점 |
| `elapsed_ms` | 소요 시간 (밀리초) |
| `success` | 크롤링 성공 여부 |
