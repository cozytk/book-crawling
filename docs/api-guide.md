# 도서 검색 API 가이드

## 개요

| API | 제공사 | 평점 제공 | 리뷰 수 | 일일 한도 | 인증 방식 |
|-----|--------|----------|---------|-----------|-----------|
| 알라딘 | 알라딘 | O (10점) | O | 5,000회 | TTBKey |
| 네이버 | 네이버 | X | X | 25,000회 | Client ID/Secret |
| 카카오 | 카카오(다음) | X | X | 월간 쿼터 | REST API Key |

**결론**: 평점/리뷰 데이터가 필요하면 **알라딘 API**가 유일한 선택

---

## 1. 알라딘 Open API

### 기본 정보
- **공식 문서**: https://blog.aladin.co.kr/openapi
- **API 키 발급**: https://www.aladin.co.kr/ttb/apiintro.aspx
- **일일 한도**: 5,000회 (프리미엄: 100,000회)

### 제공 API
| API | 용도 | 엔드포인트 |
|-----|------|------------|
| ItemSearch | 책 검색 | `/ttb/api/ItemSearch.aspx` |
| ItemLookUp | 상세 조회 | `/ttb/api/ItemLookUp.aspx` |
| ItemList | 리스트 조회 | `/ttb/api/ItemList.aspx` |

### ItemSearch (검색)

```bash
curl "http://www.aladin.co.kr/ttb/api/ItemSearch.aspx?\
ttbkey=YOUR_TTB_KEY&\
Query=클린코드&\
QueryType=Title&\
MaxResults=10&\
SearchTarget=Book&\
output=js&\
Version=20131101"
```

**주요 파라미터**:
| 파라미터 | 설명 | 값 |
|----------|------|-----|
| ttbkey | API 키 | 필수 |
| Query | 검색어 | 필수 |
| QueryType | 검색 타입 | Keyword, Title, Author, Publisher |
| MaxResults | 결과 수 | 1-50 (기본 10) |
| SearchTarget | 대상 | Book, Foreign, eBook, All |
| output | 출력 형식 | xml, js (JSON) |

**응답 필드**:
```json
{
  "item": [{
    "title": "클린 코드 Clean Code",
    "author": "로버트 C. 마틴",
    "isbn13": "9788966260959",
    "itemId": 34083680,
    "customerReviewRank": 10,  // 평점 (10점 만점)
    "priceSales": 29700,
    "cover": "https://image.aladin.co.kr/..."
  }]
}
```

### ItemLookUp (상세 조회) - 평점/리뷰 포함

```bash
curl "http://www.aladin.co.kr/ttb/api/ItemLookUp.aspx?\
ttbkey=YOUR_TTB_KEY&\
itemIdType=ItemId&\
ItemId=34083680&\
output=js&\
Version=20131101&\
OptResult=ratingInfo,reviewList"
```

**OptResult 옵션**:
| 옵션 | 설명 |
|------|------|
| ratingInfo | 평점 정보 |
| reviewList | 리뷰 목록 |
| fulldescription | 전체 소개 |
| Toc | 목차 |

**ratingInfo 응답**:
```json
{
  "subInfo": {
    "ratingInfo": {
      "ratingScore": 9.6,        // 평균 평점 (10점 만점)
      "ratingCount": 10,         // 평가 참여자 수
      "commentReviewCount": 6,   // 텍스트 리뷰 수
      "myReviewCount": 6         // 마이리뷰 수
    }
  }
}
```

---

## 2. 네이버 책 검색 API

### 기본 정보
- **공식 문서**: https://developers.naver.com/docs/serviceapi/search/book/book.md
- **일일 한도**: 25,000회
- **특징**: 평점/리뷰 정보 없음, 검색만 지원

### 인증
```
X-Naver-Client-Id: YOUR_CLIENT_ID
X-Naver-Client-Secret: YOUR_CLIENT_SECRET
```

### API 호출

```bash
curl -H "X-Naver-Client-Id: YOUR_ID" \
     -H "X-Naver-Client-Secret: YOUR_SECRET" \
     "https://openapi.naver.com/v1/search/book.json?query=%ED%81%B4%EB%A6%B0%EC%BD%94%EB%93%9C&display=10"
```

**주요 파라미터**:
| 파라미터 | 설명 | 값 |
|----------|------|-----|
| query | 검색어 (URL 인코딩 필수) | 필수 |
| display | 결과 수 | 1-100 (기본 10) |
| start | 시작 위치 | 1-1000 |
| sort | 정렬 | sim (정확도), date (출간일) |

**응답 필드**:
```json
{
  "items": [{
    "title": "클린 코드",
    "author": "로버트 C. 마틴",
    "isbn": "9788966260959",
    "publisher": "인사이트",
    "pubdate": "20131224",
    "discount": "29700",
    "image": "https://shopping-phinf.pstatic.net/...",
    "link": "https://search.shopping.naver.com/..."
  }]
}
```

---

## 3. 카카오 책 검색 API (다음)

### 기본 정보
- **공식 문서**: https://developers.kakao.com/docs/latest/ko/daum-search/dev-guide
- **한도**: 월간 쿼터 (앱별 상이)
- **특징**: 평점/리뷰 정보 없음, 검색만 지원

### 인증
```
Authorization: KakaoAK YOUR_REST_API_KEY
```

### API 호출

```bash
curl -H "Authorization: KakaoAK YOUR_KEY" \
     "https://dapi.kakao.com/v3/search/book?query=%ED%81%B4%EB%A6%B0%EC%BD%94%EB%93%9C&size=10"
```

**주요 파라미터**:
| 파라미터 | 설명 | 값 |
|----------|------|-----|
| query | 검색어 (URL 인코딩 필수) | 필수 |
| sort | 정렬 | accuracy, latest |
| page | 페이지 | 1-50 |
| size | 결과 수 | 1-50 (기본 10) |
| target | 검색 필드 | title, isbn, publisher, person |

**응답 필드**:
```json
{
  "documents": [{
    "title": "Clean Code(클린 코드)",
    "authors": ["로버트 C. 마틴"],
    "isbn": "8966260950 9788966260959",
    "publisher": "인사이트",
    "datetime": "2013-12-24T00:00:00.000+09:00",
    "price": 33000,
    "sale_price": 29700,
    "thumbnail": "https://search1.kakaocdn.net/...",
    "status": "정상판매"
  }],
  "meta": {
    "total_count": 40,
    "is_end": false
  }
}
```

---

## API 비교 및 활용 전략

### 데이터 비교

| 필드 | 알라딘 | 네이버 | 카카오 |
|------|--------|--------|--------|
| 제목 | O | O | O |
| 저자 | O | O | O |
| ISBN | O | O | O |
| 출판사 | O | O | O |
| 가격 | O | O | O |
| 커버 이미지 | O | O | O |
| **평점** | **O** | X | X |
| **리뷰 수** | **O** | X | X |
| 판매 상태 | O | X | O |

### 권장 활용 전략

1. **평점/리뷰 수집**: 알라딘 API (유일하게 제공)
2. **ISBN으로 책 검색**: 알라딘 또는 카카오 (정확도 높음)
3. **제목 검색**: 네이버 (결과 다양)
4. **백업/크로스체크**: 여러 API 병행 사용

### 크롤링 vs API

| 항목 | 크롤링 | API |
|------|--------|-----|
| 안정성 | 낮음 (HTML 변경 시 깨짐) | 높음 |
| 속도 | 느림 (3-7초) | 빠름 (0.5-1초) |
| 데이터 정확도 | 파싱 오류 가능 | 정확 |
| 리뷰 전체 내용 | 가능 | 일부 API만 지원 |
| 법적 리스크 | 있음 | 없음 |

**권장**: 평점/리뷰 수는 알라딘 API 사용, 리뷰 전체 내용 필요 시 크롤링 병행

---

## 환경 변수

`.env` 파일:
```
ALADIN_TTB_KEY=your_ttb_key
NAVER_CLIENT_ID=your_client_id
NAVER_CLIENT_SECRET=your_client_secret
KAKAO_REST_API_KEY=your_rest_api_key
```

---

## 참고 링크

- [알라딘 Open API](https://blog.aladin.co.kr/openapi)
- [네이버 책 검색 API](https://developers.naver.com/docs/serviceapi/search/book/book.md)
- [카카오 다음 검색 API](https://developers.kakao.com/docs/latest/ko/daum-search/dev-guide)
