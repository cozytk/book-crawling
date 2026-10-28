# 민음사 세계문학전집 20개 작품 검색 검증

확인일: 2026-10-29 KST. 민음사 전집에 포함된 20개 작품을 사용했다. 분권은 작품 1개로 세었으며, 원점수와 수치의 종류를 보존했다. 숫자 평점 수집, 올바른 작품 식별, 대표 판본 선정은 서로 다른 검증 항목이다.

## 결과

8개 소스 × 20개 입력 = 160칸 중 숫자 평점은 **132 → 159칸**, 한 번의 조회에서 8개 소스가 모두 완료된 작품은 **2 → 19/20개**다. 분권 일부 누락은 완료에서 제외한다. 실패·미확인 값을 0점이나 0건으로 채우지 않았다.

별도 재조회 1개 입력을 포함한 최종 확인은 **160/160칸 · 20/20개 작품**이다. 최초 조회와 재조회는 JSON에 각각 남기고 아래 최종 표에는 재조회한 행을 사용한다. 시간·요청 수 비교는 첫 20개 전체 실행 기준이다.

| 소스 | 변경 전 숫자 평점 | 최종 숫자 평점 | 비교 수치의 의미 |
| --- | ---: | ---: | --- |
| 교보 | 19/20 | 20/20 | 사이트가 표시하는 리뷰/평가 수 |
| 알라딘 | 19/20 | 20/20 | 별점 참여 수; 글 리뷰·100자평 별도 |
| Yes24 | 19/20 | 20/20 | 글 리뷰 수; 한줄평 별도 |
| 사락 | 19/20 | 20/20 | 별점 참여 수; 글 리뷰 별도 |
| 왓챠 | 19/20 | 20/20 | 별점 참여 수 |
| Goodreads | 17/20 | 20/20 | 별점 참여 수; 글 리뷰 별도 |
| LibraryThing | 18/20 | 20/20 | API reviews / 작품 헤더 글 리뷰 수; members와 구분 |
| Amazon | 2/20 | 20/20 | 현재 선택한 상품의 별점 참여 수 |

변경 전 숫자 중 Goodreads의 카라마조프 39명은 다른 저자의 책이었고, LibraryThing의 베르테르는 다른 작품으로 연결되어 있었다. 위 변경 전 숫자 합계는 이 오탐 2개를 포함한다. 올바른 작품으로 확인된 결과 수와 단순 숫자 개수를 혼동하지 않는다. 이 20개 입력을 사용해 결함을 수정한 회귀 검증이며, 보지 못한 전체 검색어에 대한 정확도 추정은 아니다.

## 실제 사이트 대조와 대표 상품

- Aside로 교보·알라딘·Yes24의 20개 검색 목록, 왓챠·사락·LibraryThing의 20개 상세, Goodreads의 20개 검색과 20개 상세, Amazon의 20개 검색을 확인했다. Yes24는 20개 대표권 상세에서 정보 더 보기를 열어 종이책/eBook 리뷰·한줄평 소계까지 확인했다. 검색 목록은 노출된 후보 범위이며 전체 카탈로그의 모든 페이지를 망라하지 않았다.
- Yes24 브라우저 탐색은 초기 전체 로딩 대기가 반복해서 멈췄으나 domcontentloaded 기준 이동으로 해결했다. 탐색 실패 기록을 성공한 관측으로 간주하지 않았으며, 실제 상품 헤더와 집계 펼침을 다시 캡처했다.
- 교보는 올바른 원저자의 종이책 후보 중 출판사·번역자·분권 묶음의 관측 수치를 비교한다. 분권은 같은 판본 ISBN을 국내 네 소스에 공유한다. 따라서 분권 결과는 각 사이트의 모든 출판사 중 독립적인 전역 최댓값을 주장하지 않는다.
- 알라딘 단권은 실제 `리뷰순` 버튼의 `SortOrder=4`를 사용해 검증한 후보 사이에서 관측 평가 수가 큰 상품을 선택한다. 이방인 88 → 222, 참을 수 없는 존재의 가벼움 93 → 209의 대표 상품 변경을 실제 목록·상세/API로 확인했다. 절판 구판도 포함한다.
- Yes24 단권은 실제 리뷰순 링크의 order=REVIEW_CNT를 사용하고 종이책+eBook 글 리뷰 소계를 우선하여 후보를 비교한다. 상세의 Book/상품 번호·저자·ISBN을 확인한다. 페스트는 민음사 162개보다 문예출판사 상품의 412개(종이책 8+eBook 404)가 컸다. 이는 해당 사이트가 상품에 연결해 표시하는 합계다.
- 사락은 Yes24의 검증된 검색 후보를 공유하되 상위 최대 3개의 사락 API 집계를 직접 비교한다. 선택한 상품의 Yes24 Book 노드로 제목·저자·상품 번호를 다시 확인한다. Yes24의 페스트 412개 상품은 사락에서는 14명/글 리뷰 12개였으므로, Yes24의 최다 리뷰 상품을 사락의 최다 참여 상품으로 간주하지 않는다. 전체 카탈로그의 전역 최댓값을 보장하지 않는다.
- Goodreads는 공개 헤더 자동완성의 Book ID·작품 ID·제목·저자를 확인하고 정확한 ratingsCount와 avgRating을 읽는다. 상위 5개에서 원작이 누락되면 실제 검색 목록에서 관측한 전체 제목으로 최대 두 번 보완하고 저자를 다시 검증한다. 제목 검색만 허용하며 명시 ISBN 검색은 이 작품 집계로 대체하지 않는다. 응답에 없는 글 리뷰 수는 미확인이다. 상세 HTML 경로도 남겨 두었다.
- Amazon은 Aside의 실제 제목·저자·형식·정확한 평가 라벨을 대조했다. 오디오북·다른 저자·해설서 등을 제외한 노출 후보 중 규모가 큰 상품 및 최대 두 개 대안을 상품 식별자 저장소에 등록했다. 종이책의 문고판·가죽 제본과 Kindle을 포함하며, 다른 언어 판본은 상품 제목에 표시한다.
- 우선 상품이 현재 서버에서 차단되면 등록된 검증 대안을 사용한다. 따라서 최종 숫자는 그 시점에 접근 가능한 검증 상품의 집계이며, 브라우저에서 관측한 최대 참여 수와 항상 같다고 주장하지 않는다. 원점수·선택된 상품 URL·시점을 함께 남긴다.
- 최종 Amazon 검증은 **상품 식별자 캐시가 채워진 상태**이며 `force_refresh=true`로 별점은 매번 공개 별점 팝업 또는 상세에서 새로 읽었다. 상품 번호·제목·저자·관측 시각만 등록했고 평점 숫자는 입력하지 않았다. 성공한 일반 서버 검색도 이후에 같은 식별자를 자동 학습한다. 제목/판본 메타데이터가 있는 20권의 회귀 검증으로서, 모든 미검색 도서의 차단 해소를 뜻하지 않는다.
- Amazon 공개 팝업은 제목·저자가 없으므로 사전 검증 상품과 현재 국내 작품 저자가 일치한 경우에만 사용한다. 집계 영역의 원점수·global ratings를 읽고 모든 상품/리뷰 링크의 ASIN이 일치해야 한다. 백년의 고독은 종이책 4,580개로, 오디오북 9,729개를 섞지 않았다.
- 현재 선택한 ASIN과 상세의 ASIN이 다르면 종이책 ISBN이 페이지에 남아 있더라도 다른 상품의 집계 평점을 사용하지 않는다. 검증 상품 조회가 모두 막히면 작은 임의 ISBN 판본으로 덮어 성공 처리하지 않는다.

## 수정한 식별·집계 결함

- 키릴 문자 저자명을 라틴 문자 토큰으로만 비교해 둘 다 빈 집합이면 일치하던 오류를 수정했다. 카라마조프는 다른 저자의 39명 결과를 제외하고 도스토예프스키의 약 42만 명 작품을 선택한다.
- 악센트·강세 부호 및 아래/아래서 표기를 제한적으로 정규화한다. 독일어 소유격 Werther/Werthers를 구별하지 않되 해설서·다른 권 검사는 유지한다. Goodreads의 Band I 같은 부분 권을 작품 전체로 선택하지 않는다.
- LibraryThing은 같은 카탈로그 작품의 ISBN 연결 지지를 먼저 비교한다. 베르테르는 32개 ISBN이 지지한 work/28158을 선택하여, 1개 잘못 연결된 ISBN의 work/3493(아버지와 아들)을 배제했다. 전역 작품 메타데이터 오류를 모두 해결한 것은 아니며 HTML 제목·저자는 별도로 대조했다.
- 알라딘의 `ratingCount`, `myReviewCount`, `commentReviewCount`를 각각 별점 참여·글 리뷰·100자평으로 분리했다. 이방인의 실제 예는 222명 / 글 리뷰 86개 / 100자평 131개다.
- 사락의 `userWhoDidVoteThisBookCount`와 `reviewCount`를 별도로 보존한다. 베르테르는 평가 803명 / 글 리뷰 164개다. Yes24의 글 리뷰와 한줄평도 나눠 표시한다.
- LibraryThing 수레바퀴 아래서의 글 리뷰 42개는 실제 작품 헤더와 일치했다. 적은 글 리뷰를 평점 참여 수로 바꾸거나 실패로 간주하지 않는다. Amazon의 일부 ISBN fallback에서 보인 7·10·13·21명짜리 판본은 대표 판본 선정 문제로 다뤘다.
- 여러 권의 점수는 사용자가 선택한 권별 단순 평균이다. 같은 소스의 작품 평점을 권수만큼 복제하지 않으며 누락 권과 미확인 수치는 별도로 남긴다.

## 20개 작품의 최종 결과

각 칸은 `원점수 · 수치`이고 상품 링크를 포함한다. 교보·알라딘·Yes24·사락은 10점, 나머지는 5점이다. 분권 수치는 권별 합계이며 고유 인원 수가 아니다. 실패 상태는 해당 조회 시점의 결과다.

| 작품(민음사 전집 번호) | 교보 | 알라딘 | Yes24 | 사락 | 왓챠 | Goodreads | LibraryThing | Amazon |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 햄릿 (3) | [9.5 · 223](https://product.kyobobook.co.kr/detail/S000000620140) | [8.5 · 124](https://www.aladin.co.kr/shop/wproduct.aspx?ItemId=168036) | [9.2 · 124](https://www.yes24.com/product/goods/57197) | [8.4 · 1,110](https://sarak.yes24.com/reading-note/book/57197) | [3.8 · 10,074](https://pedia.watcha.com/ko/contents/byKmNZ4) | [4.03 · 1,096,351](https://www.goodreads.com/book/show/1420) | [4.15 · 339](https://www.librarything.com/work/2199) | [4.5 · 11,502](https://www.amazon.com/dp/1451669410) |
| 오만과 편견 (88) | [9.6 · 761](https://product.kyobobook.co.kr/detail/S000000620225) | [9 · 404](https://www.aladin.co.kr/shop/wproduct.aspx?ItemId=436838) | [9.3 · 377](https://www.yes24.com/product/goods/402246) | [8.8 · 2,316](https://sarak.yes24.com/reading-note/book/402246) | [4 · 27,643](https://pedia.watcha.com/ko/contents/boOn8n4) | [4.3 · 5,041,490](https://www.goodreads.com/book/show/129915654) | [4.395 · 1,531](https://www.librarything.com/work/2773690) | [4.6 · 39,380](https://www.amazon.com/dp/1481274953) |
| 레 미제라블 (301–305) | [9.84 · 159](https://product.kyobobook.co.kr/detail/S000000620438) | [9.44 · 37](https://www.aladin.co.kr/shop/wproduct.aspx?ItemId=20671313) | [9.38 · 75](https://www.yes24.com/product/goods/7929047) | [9.3 · 86](https://sarak.yes24.com/reading-note/book/7929047) | [4.1 · 9,681](https://pedia.watcha.com/ko/contents/b4eY5X4) | [4.22 · 868,927](https://www.goodreads.com/book/show/36377471) | [4.265 · 385](https://www.librarything.com/work/19485) | [4.6 · 3,689](https://www.amazon.com/dp/1626864640) |
| 죄와 벌 (284–285) | [9.9 · 672](https://product.kyobobook.co.kr/detail/S000000620421) | [9.3 · 70](https://www.aladin.co.kr/shop/wproduct.aspx?ItemId=16211750) | [9.55 · 217](https://www.yes24.com/product/goods/6712992) | [9.2 · 436](https://sarak.yes24.com/reading-note/book/6712992) | [4.1 · 8,996](https://pedia.watcha.com/ko/contents/byzL8k4) | [4.29 · 1,171,647](https://www.goodreads.com/book/show/7144) | [4.25 · 584](https://www.librarything.com/work/10072) | [4.4 · 16,256](https://www.amazon.com/dp/B074W9WW4S) |
| 동물농장 (5) | [9.8 · 1,133](https://product.kyobobook.co.kr/detail/S000000620142) | [9.3 · 452](https://www.aladin.co.kr/shop/wproduct.aspx?ItemId=40674) | [9.5 · 418](https://www.yes24.com/product/goods/17352) | [8.9 · 2,332](https://sarak.yes24.com/reading-note/book/17352) | [4.1 · 42,414](https://pedia.watcha.com/ko/contents/bWyPWNo) | [4.03 · 4,849,654](https://www.goodreads.com/book/show/170448) | [4.005 · 1,027](https://www.librarything.com/work/1477) | [4.6 · 95,282](https://www.amazon.com/dp/0451526341) |
| 1984 (77) | [9.8 · 1,027](https://product.kyobobook.co.kr/detail/S000000620214) | [9.3 · 446](https://www.aladin.co.kr/shop/wproduct.aspx?ItemId=418906) | [9.5 · 344](https://www.yes24.com/product/goods/372300) | [8.9 · 1,971](https://sarak.yes24.com/reading-note/book/372300) | [4.2 · 48,357](https://pedia.watcha.com/ko/contents/bopPDwo) | [4.21 · 5,811,605](https://www.goodreads.com/book/show/61439040) | [4.22 · 1,470](https://www.librarything.com/work/1472) | [4.6 · 15,242](https://www.amazon.com/dp/0241453518) |
| 이방인 (266) | [9.8 · 941](https://product.kyobobook.co.kr/detail/S000000619973) | [9 · 222](https://www.aladin.co.kr/shop/wproduct.aspx?ItemId=11267296) | [9.3 · 307](https://www.yes24.com/product/goods/4827613) | [8.8 · 1,265](https://sarak.yes24.com/reading-note/book/4827613) | [4 · 47,918](https://pedia.watcha.com/ko/contents/bokPREy) | [4.03 · 1,548,683](https://www.goodreads.com/book/show/49552) | [3.945 · 597](https://www.librarything.com/work/2150) | [4.3 · 5,593](https://www.amazon.com/dp/B008QLXSG8) |
| 페스트 (267) | [9.6 · 816](https://product.kyobobook.co.kr/detail/S000000620404) | [8.5 · 132](https://www.aladin.co.kr/shop/wproduct.aspx?ItemId=11267326) | [9.8 · 412](https://www.yes24.com/product/goods/7381053) | [9.1 · 251](https://sarak.yes24.com/reading-note/book/4827619) | [3.9 · 12,855](https://pedia.watcha.com/ko/contents/boNLPM9) | [4.02 · 336,576](https://www.goodreads.com/book/show/11989) | [3.945 · 288](https://www.librarything.com/work/2147) | [4.2 · 3,874](https://www.amazon.com/dp/B09MCQ82Q2) |
| 위대한 개츠비 (75) | [9.6 · 536](https://product.kyobobook.co.kr/detail/S000000620212) | [8.6 · 296](https://www.aladin.co.kr/shop/wproduct.aspx?ItemId=417997) | [9 · 319](https://www.yes24.com/product/goods/370331) | [8.4 · 1,163](https://sarak.yes24.com/reading-note/book/370331) | [3.8 · 37,939](https://pedia.watcha.com/ko/contents/boYQ8Mo) | [3.92 · 6,175,477](https://www.goodreads.com/book/show/41733839) | [3.84 · 1,318](https://www.librarything.com/work/2964) | [4.4 · 16,393](https://www.amazon.com/dp/B000FC0PDA) |
| 호밀밭의 파수꾼 (47) | [9.5 · 945](https://product.kyobobook.co.kr/detail/S000000620184) | [8.2 · 662](https://www.aladin.co.kr/shop/wproduct.aspx?ItemId=308822243) | [8.7 · 571](https://www.yes24.com/product/goods/204300) | [8.4 · 1,962](https://sarak.yes24.com/reading-note/book/204300) | [3.8 · 30,318](https://pedia.watcha.com/ko/contents/boAr1Ay) | [3.8 · 4,030,470](https://www.goodreads.com/book/show/5107) | [3.78 · 1,209](https://www.librarything.com/work/4053418) | [4.4 · 48,321](https://www.amazon.com/dp/0316769177) |
| 데미안 (44) | [9.7 · 2,031](https://product.kyobobook.co.kr/detail/S000000620181) | [8.8 · 456](https://www.aladin.co.kr/shop/wproduct.aspx?ItemId=260084) | [9.3 · 566](https://www.yes24.com/product/goods/176787) | [8.7 · 2,698](https://sarak.yes24.com/reading-note/book/176787) | [4 · 51,803](https://pedia.watcha.com/ko/contents/b4ex329) | [4.13 · 213,627](https://www.goodreads.com/book/show/43609577) | [3.925 · 128](https://www.librarything.com/work/8422) | [4.7 · 3,675](https://www.amazon.com/dp/B0191ZQ9U4) |
| 인간의 굴레에서 (11–12) | [9.9 · 352](https://product.kyobobook.co.kr/detail/S000000620148) | [9.2 · 96](https://www.aladin.co.kr/shop/wproduct.aspx?ItemId=118702) | [9.45 · 92](https://www.yes24.com/product/goods/17378) | [8 · 463](https://sarak.yes24.com/reading-note/book/17378) | [4.2 · 1,676](https://pedia.watcha.com/ko/contents/bokZdE4) | [4.16 · 63,603](https://www.goodreads.com/book/show/31548) | [4.06 · 171](https://www.librarything.com/work/7701) | [4.3 · 3,712](https://www.amazon.com/dp/1089248474) |
| 참을 수 없는 존재의 가벼움 (234) | [9.6 · 1,308](https://product.kyobobook.co.kr/detail/S000000619722) | [8.9 · 209](https://www.aladin.co.kr/shop/wproduct.aspx?ItemId=6103061) | [9.4 · 237](https://www.yes24.com/product/goods/61933303) | [8.7 · 1,143](https://sarak.yes24.com/reading-note/book/61933303) | [4 · 34,354](https://pedia.watcha.com/ko/contents/byPNN04) | [4.1 · 572,970](https://www.goodreads.com/book/show/835810) | [4 · 312](https://www.librarything.com/work/5068) | [4.3 · 6,611](https://www.amazon.com/dp/0061148520) |
| 노인과 바다 (278) | [9.8 · 758](https://product.kyobobook.co.kr/detail/S000000620415) | [9 · 126](https://www.aladin.co.kr/shop/wproduct.aspx?ItemId=14522431) | [9.4 · 184](https://www.yes24.com/product/goods/6157159) | [8.8 · 937](https://sarak.yes24.com/reading-note/book/6157159) | [3.8 · 21,083](https://pedia.watcha.com/ko/contents/boAL1Y4) | [3.82 · 1,386,254](https://www.goodreads.com/book/show/2165) | [3.77 · 576](https://www.librarything.com/work/4933) | [4.7 · 10,850](https://www.amazon.com/dp/0684801221) |
| 카라마조프가의 형제들 (154–156) | [9.4 · 145](https://product.kyobobook.co.kr/detail/S000000620291) | [8.7 · 88](https://www.aladin.co.kr/shop/wproduct.aspx?ItemId=988088) | [9.567 · 96](https://www.yes24.com/product/goods/2710341) | [9.3 · 122](https://sarak.yes24.com/reading-note/book/2710341) | [4.1 · 5,811](https://pedia.watcha.com/ko/contents/boqepMo) | [4.4 · 420,282](https://www.goodreads.com/book/show/4934) | [4.37 · 408](https://www.librarything.com/work/7856) | [4.4 · 3,397](https://www.amazon.com/dp/B0918B6C6J) |
| 안나 카레니나 (219–221) | [9.9 · 184](https://product.kyobobook.co.kr/detail/S000000620356) | [9.167 · 92](https://www.aladin.co.kr/shop/wproduct.aspx?ItemId=4615730) | [9.267 · 73](https://www.yes24.com/product/goods/3530515) | [9.267 · 121](https://sarak.yes24.com/reading-note/book/3530515) | [4 · 5,130](https://pedia.watcha.com/ko/contents/boOEpn9) | [4.11 · 974,169](https://www.goodreads.com/book/show/15823480) | [4.145 · 710](https://www.librarything.com/work/2340) | [4.6 · 3,563](https://www.amazon.com/dp/1853262714) |
| 수레바퀴 아래 (50) | [9.8 · 423](https://product.kyobobook.co.kr/detail/S000000620187) | [8.7 · 168](https://www.aladin.co.kr/shop/wproduct.aspx?ItemId=292110) | [9.2 · 210](https://www.yes24.com/product/goods/221158) | [8.7 · 622](https://sarak.yes24.com/reading-note/book/221158) | [3.9 · 12,705](https://pedia.watcha.com/ko/contents/bo5Q5Go) | [3.89 · 23,752](https://www.goodreads.com/book/show/2419713.The_Prodigy) | [3.79 · 42](https://www.librarything.com/work/8406) | [4.4 · 349](https://www.amazon.com/dp/B0DDX4RL3W) |
| 싯다르타 (58) | [9.8 · 1,860](https://product.kyobobook.co.kr/detail/S000000620195) | [9.1 · 177](https://www.aladin.co.kr/shop/wproduct.aspx?ItemId=329596) | [9.4 · 428](https://www.yes24.com/product/goods/257435) | [8.7 · 1,516](https://sarak.yes24.com/reading-note/book/257435) | [4 · 16,828](https://pedia.watcha.com/ko/contents/byd5kW9) | [4.09 · 923,023](https://www.goodreads.com/book/show/52036) | [3.95 · 426](https://www.librarything.com/work/10128) | [4.6 · 18,247](https://www.amazon.com/dp/0553208845) |
| 백년의 고독 (34–35) | [9.75 · 450](https://product.kyobobook.co.kr/detail/S000000620171) | [9.1 · 164](https://www.aladin.co.kr/shop/wproduct.aspx?ItemId=217600) | [9.35 · 151](https://www.yes24.com/product/goods/96378) | [8.3 · 529](https://sarak.yes24.com/reading-note/book/96378) | [4.1 · 5,071](https://pedia.watcha.com/ko/contents/byzqK7o) | [4.13 · 1,159,954](https://www.goodreads.com/book/show/320) | [4.17 · 798](https://www.librarything.com/work/5864) | [4.6 · 4,580](https://www.amazon.com/dp/0060883286) |
| 젊은 베르테르의 슬픔 (25) | [9.5 · 372](https://product.kyobobook.co.kr/detail/S000000620162) | [8.3 · 166](https://www.aladin.co.kr/shop/wproduct.aspx?ItemId=187464) | [8.8 · 171](https://www.yes24.com/product/goods/17386) | [8.3 · 803](https://sarak.yes24.com/reading-note/book/17386) | [3.6 · 14,917](https://pedia.watcha.com/ko/contents/b4Q5ZB4) | [3.7 · 165,180](https://www.goodreads.com/book/show/705790) | [3.615 · 155](https://www.librarything.com/work/28158) | [4.2 · 1,967](https://www.amazon.com/dp/014044503X) |

## 요청 수와 시간

| 측정 | 변경 전 | 최종 |
| --- | ---: | ---: |
| HTTP 요청 합계 | 364 | 425 |
| 첫 평점 중앙값 | 0.861초 | 1.007초 |
| 전체 완료 중앙값 | 13.512초 | 10.726초 |

모두 순차 입력·강제 재조회이며 실행 위치/차단/응답 시점이 달랐다. 수집 범위도 바뀌었으므로 이 한 쌍의 실행으로 속도 우위를 일반화하지 않는다. 캐시·연결 재사용·동일 요청 합치기·추가 HTTP가 없는 경우의 대기 생략은 별도 로직과 회귀 테스트로 검증했다.

마지막 베르테르 조회에서는 원서 카탈로그가 한국어판 ISBN을 영어 제목으로 반환하여 Goodreads 식별 검증에서 거절됐다. 재조회 결과는 따로 보존했다. 이처럼 외부 카탈로그 오류·시간 초과와 차단은 여전히 재발할 수 있다. 식별 불일치를 작은 임의 판본이나 0점으로 메우지 않는다.

## 재현과 증거

- 입력: [scripts/minumsa_audit_cases.json](../scripts/minumsa_audit_cases.json)
- 공개 사실·서버 결과·Aside 관측: [evidence/minumsa-20-audit-20261029.json](evidence/minumsa-20-audit-20261029.json)
- 등록한 상품 메타데이터: [evidence/minumsa-20-amazon-identities-20261029.json](evidence/minumsa-20-amazon-identities-20261029.json)
- `API_SERVICE_TOKEN`을 환경에 설정한 뒤 `uv run python scripts/benchmark_live_sources.py --base-url https://book-crawling-api.vercel.app --cases-file scripts/minumsa_audit_cases.json --concurrency 1 --output audit.json`으로 다시 수집할 수 있다. 인증 정보는 결과 파일에 쓰지 않는다.
- 상품 식별자는 `scripts/import_source_identities.py`의 dry run으로 검증하고 `--apply`일 때만 현재 저장소에 등록한다. 평점 필드가 들어 있는 파일은 거절한다. 식별자는 30일 유효하고, 강제 재조회에서도 집계 HTTP 요청을 생략하지 않는다.
- Python 3.12 회귀 테스트 310개, 웹 SSE 테스트 2개와 production 빌드·GitHub 검사를 통과했다. 모의 응답 테스트 통과와 위 실제 서버 수집 성공을 구분한다. 중간 20권 실측 통계도 JSON에 남겨 시간대·배포별 수집 차이를 숨기지 않았다.

## 운영 화면과 저장 검증

- Aside에서 운영 웹의 새로 조회를 실행하여 레 미제라블 8개 소스 완료를 확인했다. 402×681 CSS px에서 문서 너비는 402px이고, 카드 8개·펼친 교보 1~5권 상품 링크 5개를 확인했다. 기존 사용자 탭은 변경하지 않았다. 실제 iPhone Safari 검증은 아니다.
- 웹 프록시 → API → Private Blob 기록을 다시 읽어 schema 25·평점 8개와 네 국내 소스의 5권 단순 평균이 동일함을 확인했다. ISBN 9788937463037 강제 재조회는 네 소스 모두 3권 ISBN으로 고정되며 분권 평균을 만들지 않았다.
- 화면: [모바일 검색](evidence/galpi-mobile-home-402.png) · [권별 점수 펼침](evidence/galpi-mobile-volumes-402.png)

## 배포

- 운영: https://book-crawling.vercel.app · API: https://book-crawling-api.vercel.app
- 최종 검증 API production 빌드: `dpl_8V2wumQyNXvcFjyhgg4i2zRvy2kR`, 코드 `7492f66`, 스키마 25.
- 웹 production 빌드: `dpl_J4ESsTTXSuovJEBKXcCipggNciM2`, 코드 `c5c9b2e`.
- 위 검증한 production 빌드를 운영으로 승격했다. Vercel Functions·Private Blob을 사용하며 GCP·Supabase는 운영 요청에 사용하지 않는다. 기존 원격 자료를 삭제하거나 이전하지 않았다.
