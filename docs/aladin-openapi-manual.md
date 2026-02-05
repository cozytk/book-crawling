

[1\. 요청 (Request)](#1.-요청-\(request\))

[1\) 상품 검색 API](#1\)-상품-검색-api)

[2\) 상품 리스트 API](#2\)-상품-리스트-api)

[3\) 상품 조회 API](#3\)-상품-조회-api)

[4\) 중고상품 보유 매장 검색 API](#4\)-중고상품-보유-매장-검색-api)

[2\. 응답 (Response)](#2.-응답-\(response\))

[1\) 상품 검색/상품 리스트/상품 조회 API](#1\)-상품-검색/상품-리스트/상품-조회-api)

[2\) 상품 조회 API : 부가정보](#2\)-상품-조회-api-:-부가정보)

[3\) 중고상품 보유 매장 검색 API](#3\)-중고상품-보유-매장-검색-api)

**\*  최종업데이트 : 2022-07-13**

# **1\. 요청 (Request)** {#1.-요청-(request)}

## **1\) 상품 검색 API** {#1)-상품-검색-api}

\- 요청 방법

* 요청 URL : http://www.aladin.co.kr/ttb/api/ItemSearch.aspx  
* 요청 URL샘플 : http://www.aladin.co.kr/ttb/api/ItemSearch.aspx?ttbkey=\[TTBKey\]\&Query=aladdin\&QueryType=Title\&MaxResults=10\&start=1\&SearchTarget=Book\&output=xml\&Version=20131101  
* 결과샘플  
  * XML형식 : http://www.aladin.co.kr/ttb/api/test/ItemSearch\_20131101.xml  
  * javascript형식 : http://www.aladin.co.kr/ttb/api/test/ItemSearch\_20131101.js  
* 한 페이지에 최대 50개, 총 결과는 200개까지만 검색 가능

\- 상품 검색 API 요청(Request) 파라미터

| 구분 | 요청변수 | 변수종류 | 설명 |
| ----- | ----- | ----- | ----- |
| 필수 | TTBKey | 문자열 | 부여받은 TTBKey값 |
|  | Query | 문자열 | 검색어 |
| 옵션 (옵션 조정 변수가 없을 경우에는 기본값으로 검색) | QueryType | Keyword (기본값) : 제목+저자 Title : 제목검색 Author : 저자검색 Publisher : 출판사검색 | 검색어 종류 |
|  | SearchTarget | Book(기본값) : 도서 Foreign : 외국도서 Music : 음반 DVD : DVD Used : 중고샵(도서/음반/DVD 등) eBook: 전자책 All : 위의 모든 타겟(몰) | 검색 대상 Mall |
|  | Start | 1이상, 양의 정수(기본값:1) | 검색결과 시작페이지 |
|  | MaxResults | 1이상 100이하, 양의 정수(기본값:10) | 검색결과 한 페이지당 최대 출력 개수 |
|  | Sort | Accuracy(기본값): 관련도 PublishTime : 출간일 Title : 제목 SalesPoint : 판매량 CustomerRating 고객평점 MyReviewCount :마이리뷰갯수 | 정렬순서 |
|  | Cover | Big : 큰 크기 : 너비 200px MidBig : 중간 큰 크기 : 너비 150px Mid(기본값) : 중간 크기 : 너비 85px Small : 작은 크기 : 너비 75px Mini : 매우 작은 크기 : 너비 65px None : 없음 | 표지 이미지 크기 |
|  | CategoryId | 양의정수 \- 분야의 고유 번호(기본값:0, 전체) ([참고 : 알라딘 모든 분야 카테고리](https://image.aladin.co.kr/img/files/aladin_Category_CID_20210927.xls)) | 특정 분야로 검색결과를 제한함 |
|  | Output | XML(기본값) : REST XML형식 JS : JSON방식 | 출력방법 |
|  | Partner | 문자 | 제휴와 관련한 파트너코드.제휴사의 경우 파트너코드 입력으로 제휴사 유효성 체크. |
|  | includeKey | 양의정수(기본값:0) | includeKey가 1인 경우 결과의 상품페이지 링크값에 TTBKey가 포함됨. |
|  | InputEncoding | 문자열(인코딩의 영문이름 \- 기본값:utf-8) | 검색어의 인코딩 값을 설정. "utf-8"이나 "euc-kr"과 같은 인코딩의 영문이름. |
|  | Version | 정수형 날짜 (기본값: 20070901\) | 검색API의 Version(날짜형식)을 설정. (최신버젼: 20131101\) |
|  | outofStockfilter | 양의정수(기본값:0) | 품절/절판 등 재고 없는 상품 필터링("1"이 제외 필터) |
|  | RecentPublishFilter | 0\~60 사이 양의정수 (기본값:0) | 출간일(월단위) 제한 필터링.  값이 1인 경우, 최근 한 달내 출간된 상품만 검색됨.  0인 경우, 전체 기간 출간 상품이 검색. |
|  | OptResult |  | *부가 정보 ※ 요청시 OptResult=ebookList,usedList,reviewList 와 같은 Array 형태로 요청* |
|  |  | ebookList  | 해당 종이책의 전자책 정보 |
|  |  | usedList | 해당 상품에 등록된 중고상품 정보 |
|  |  | fileFormatList  | 전자책의 포맷 및 용량 |

## **2\) 상품 리스트 API** {#2)-상품-리스트-api}

\- 요청 방법

* 요청 URL : http://www.aladin.co.kr/ttb/api/ItemList.aspx  
* 요청 URL샘플 : http://www.aladin.co.kr/ttb/api/ItemList.aspx?ttbkey=\[TTBKey\]\&QueryType=ItemNewAll\&MaxResults=10\&start=1\&SearchTarget=Book\&output=xml\&Version=20131101  
* 결과샘플  
  * XML형식 : http://www.aladin.co.kr/ttb/api/test/ItemList\_20131101.xml  
  * javascript형식 : http://www.aladin.co.kr/ttb/api/test/ItemList\_20131101.js  
* 한 페이지에 최대 50개, 총 결과는 200개까지만 조회 가능

\- 상품 리스트 API 요청(Request) 파라미터

| 구분 | 요청변수 | 변수종류 | 설명 |
| ----- | ----- | ----- | ----- |
| 필수 | TTBKey | 문자열 | 부여받은 TTBKey값 |
|  | QueryType | ItemNewAll : 신간 전체 리스트 ItemNewSpecial : 주목할 만한 신간 리스트 ItemEditorChoice : 편집자 추천 리스트(카테고리로만 조회 가능 \- 국내도서/음반/외서만 지원) Bestseller : 베스트셀러 BlogBest : 블로거 베스트셀러 (국내도서만 조회 가능) | 리스트 종류 |
| 옵션 (옵션 조정 변수가 없을 경우에는 기본값으로 검색) | SearchTarget | Book(기본값) : 도서 Foreign : 외국도서 Music : 음반 DVD : DVD Used : 중고샵(도서/음반/DVD 등) eBook: 전자책 All : 위의 모든 타겟(몰) | 조회 대상 Mall |
|  | SubSearchTarget | Book : 도서 Music : 음반 DVD : DVD | SearchTarget이 중고(Used)인 경우, 서브 Mall 지정 |
|  | Start | 1이상, 양의 정수(기본값:1) | 검색결과 시작페이지 |
|  | MaxResults | 1이상 100이하, 양의 정수(기본값:10) | 검색결과 한 페이지당 최대 출력 개수 |
|  | Cover | Big : 큰 크기 : 너비 200px MidBig : 중간 큰 크기 : 너비 150px Mid(기본값) : 중간 크기 : 너비 85px Small : 작은 크기 : 너비 75px Mini : 매우 작은 크기 : 너비 65px None : 없음 | 표지크기 |
|  | CategoryId | 양의정수 \- 분야의 고유 번호(기본값:0, 전체) ([참고 : 알라딘 모든 분야 카테고리](https://image.aladin.co.kr/img/files/aladin_Category_CID_20210927.xls)) | 특정 분야로 검색결과를 제한함 |
|  | Output | XML(기본값) : REST XML형식 JS : JSON방식 | 출력방법 |
|  | Partner | 문자 | 제휴와 관련한 파트너코드.제휴사의 경우 파트너코드 입력으로 제휴사 유효성 체크. |
|  | includeKey | 양의정수(기본값:0) | includeKey가 1인 경우 결과의 상품페이지 링크값에 TTBKey가 포함됨. |
|  | InputEncoding | 문자열(인코딩의 영문이름 \- 기본값:utf-8) | 검색어의 인코딩 값을 설정. "utf-8"이나 "euc-kr"과 같은 인코딩의 영문이름. |
|  | Version | 정수형 날짜 (기본값: 20070901\) | 검색API의 Version(날짜형식)을 설정. (최신버젼: 20131101\) |
|  | outofStockfilter | 양의정수(기본값:0) | 품절/절판 등 재고 없는 상품 필터링 ("1"이 제외 필터) |
|  | Year, Month, Week | 베스트셀러를 조회할 주간 (기본값:0) | QueryType=Bestseller인 경우, 베스트셀러를 조회할 주간 “Year=2022\&Month=5\&Week=3”형식으로 요청. 생략하면 현재 주간의 정보 제공. |
|  | OptResult |  | *부가 정보 ※ 요청시 OptResult=ebookList,usedList,reviewList 와 같은 Array 형태로 요청* |
|  |  | ebookList  | 해당 종이책의 전자책 정보 |
|  |  | usedList | 해당 상품에 등록된 중고상품 정보 |
|  |  | fileFormatList  | 전자책의 포맷 및 용량 |

## **3\) 상품 조회 API** {#3)-상품-조회-api}

\- 요청 방법

* 요청 URL : http://www.aladin.co.kr/ttb/api/ItemLookUp.aspx  
* 요청 URL샘플 : http://www.aladin.co.kr/ttb/api/ItemLookUp.aspx?ttbkey=\[TTBKey\]\&itemIdType=ISBN\&ItemId=\[도서의ISBN\]\&output=xml\&Version=20131101\&OptResult=ebookList,usedList,reviewList  
* "상품 조회 응답(Reponse) 결과값"의 스펙은 "검색 응답(Reponse) 결과값"과 동일한 결과에 단순히 부가정보가 추가되어지는 것임.  
* 분류 ID값은 [**알라딘 모든 분야 카테고리 엑셀문서**](https://image.aladin.co.kr/img/files/aladin_Category_CID_20210927.xls)를 참고하십시오.  
* 결과샘플  
  * XML형식 : http://www.aladin.co.kr/ttb/api/test/ItemLookUp\_20131101.xml  
  * javascript형식 : http://www.aladin.co.kr/ttb/api/test/ItemLookUp\_20131101.js

\- 상품 조회 API 요청(Request) 파라미터  
※ 주황색 정보의 경우, 일반적인 스펙에는 포함되지 않고, 별도로 협의 후 제공

| 구분 | 요청변수 | 변수종류 | 설명 |
| ----- | ----- | ----- | ----- |
| 필수 | TTBKey | 문자열 | 부여받은 TTBKey값 |
|  | ItemId | 문자열/숫자 | 상품을 구분짓는 유일한 값 (ItemIdType으로 정수값과 ISBN중에 택일) |
| 옵션 (옵션 조정 변수가 없을 경우에는 기본값으로 조회) | ItemIdType | ISBN(기본값) : ISBN 10자리 ISBN13 : ISBN 13자리 ItemId | 조회용 파라미터인 ItemId가 ISBN으로 입력되었는지, 알라딘고유의"ItemId"값으로 입력되었는지 선택 **가급적 13자리 ISBN을 이용해주세요** |
|  | Cover | Big : 큰 크기 MidBig : 중간 큰 크기 Mid(기본값) : 중간 크기 Small : 작은 크기 Mini : 매우 작은 크기 None : 없음 | 표지크기 |
|  | Output | XML(기본값) : REST XML형식 JS : JSON방식 | 출력방법 |
|  | Partner | 문자 | 제휴와 관련한 파트너코드.제휴사의 경우 파트너코드 입력으로 제휴사 유효성 체크. |
|  | Version | 정수형 날짜(기본값: 20070901\) | 검색API의 Version(날짜형식)을 설정 (최신버젼: 20131101\) |
|  | includeKey | 양의정수(기본값:0) | includeKey가 1인 경우 결과의 상품페이지 링크값에 TTBKey가 포함됨. |
|  | offCode | 문자열 | 중고상품 보유 매장 검색 API에서 얻어낸 중고매장의 offCode값 |
|  | OptResult |  | *부가 정보 ※ 요청시 OptResult=ebookList,usedList,reviewList 와 같은 Array 형태로 요청* |
|  |  | ebookList  | 해당 종이책의 전자책 정보 |
|  |  | usedList | 해당 상품에 등록된 중고상품 정보 |
|  |  | fileFormatList  | 전자책의 포맷 및 용량 |
|  |  | c2binfo | 중고C2B(알라딘이 고객에게 매입하는 중고) 매입여부 및 매입가 조회. |
|  |  | packing | 판형 정보, 포장 관련 정보 |
|  |  | b2bSupply | 전자책 B2B 납품가능 여부 |
|  |  | subbarcode | 부가기호 |
|  |  | cardReviewImgList | 카드리뷰 일부 이미지 경로 |
|  |  | ratingInfo | 상품의 별 평점,100자평 개수, 마이리뷰 개수 |
|  |  | bestSellerRank | 상품의 주간베스트셀러 순위 |
|  |  | previewImgList | 미리보기 이미지 경로 (추가 요청시 가능) |
|  |  | eventList  | 관련 이벤트 정보 (추가 요청시 가능) |
|  |  | authors  | 상품의 저자/아티스트 정보 목록 (추가 요청시 가능) |
|  |  | reviewList  | 상품에 등록된 리뷰 목록 (추가 요청시 가능) |
|  |  | fulldescription  | 상품의 설명 및 출판사 상품소개. DVD는 줄거리도 포함 (추가 요청시 가능) |
|  |  | fulldescription2 | 출판사(제작사) 제공 상폼소개 |
|  |  | Toc  | 상품의 목차 (추가 요청시 가능) |
|  |  | Story | 줄거리 (추가 요청시 가능) |
|  |  | categoryIdList | 전체 분야 (추가 요청시 가능)  |
|  |  | mdrecommend | 편집장의 선택 (추가 요청시 가능) |
|  |  | phraseList | 책속에서 (추가 요청시 가능, 최대 3개까지 노출) |

## **4\) 중고상품 보유 매장 검색 API** {#4)-중고상품-보유-매장-검색-api}

\- 요청 방법

* 요청 URL : http://www.aladin.co.kr/ttb/api/ItemOffStoreList.aspx  
* 요청 URL샘플 : http://www.aladin.co.kr/ttb/api/ItemOffStoreList.aspx?ttbkey=\[TTBKey\]\&itemIdType=ISBN\&ItemId=\[도서의ISBN\]\&output=xml  
* 결과샘플  
  * XML형식 : http://www.aladin.co.kr/ttb/api/test/ItemOffStoreList\_20131101.xml  
  * javascript형식 : http://www.aladin.co.kr/ttb/api/test/ItemOffStoreList\_20131101.js

\- 중고상품 보유 매장 검색 API 요청(Request) 파라미터

| 구분 | 요청변수 | 변수종류 | 설명 |
| ----- | ----- | ----- | ----- |
| 필수 | TTBKey | 문자열 | 부여받은 TTBKey값 |
|  | ItemId | 문자열/숫자 | 상품을 구분짓는 유일한 값 (ItemIdType으로 정수값과 ISBN중에 택일) |
| 옵션  | ItemIdType | ISBN(기본값) : ISBN 10자리 ISBN13 : ISBN 13자리 ItemId | 조회용 파라미터인 ItemId가 ISBN으로 입력되었는지, 알라딘고유의"ItemId"값으로 입력되었는지 선택 |

# **2\. 응답 (Response)** {#2.-응답-(response)}

## **1\) 상품 검색/상품 리스트/상품 조회 API** {#1)-상품-검색/상품-리스트/상품-조회-api}

| 필드명 | 설명 | 자료형 |
| ----- | ----- | ----- |
| version | API Version | 정수형 날짜 |
| tile | API 결과의 제목 | 문자열 |
| link | API 결과와 관련된 알라딘 페이지 URL 주소 | 문자열(URL) |
| pubDate | API 출력일 | 문자형 날짜 |
| totalResults | API의 총 결과수 | 정수 |
| startIndex | Page수 | 정수 |
| itemsPerPage | 한 페이지에 출력될 상품 수 | 정수 |
| query | API로 조회한 쿼리 | 문자열 |
| searchCategoryId | 분야로 조회한 경우 해당 분야의 ID | 정수 |
| searchCategoryName | 분야로 조회한 경우 해당 분야의 분야명 | 문자열 |
| item \<\< | 상품정보 (이하 결과값은 모두 item의 하위 정보) |   |
| title | 상품명 | 문자열 |
| link | 상품 링크 URL | 문자열(URL) |
| author | 저자/아티스트 | 문자열 |
| pubdate | 출간일(출시일) | 날짜 |
| description | 상품설명 (요약) | 문자열 |
| isbn | 10자리 ISBN | 문자열 |
| isbn13 | 13자리 ISBN | 문자열 |
| pricesales | 판매가 | 정수 |
| pricestandard | 정가 | 정수 |
| mallType | 상품의 몰타입(국내도서:BOOK, 음반:MUSIC, Dvd:DVD, 외서:FOREIGN, 전자책:EBOOK, 중고상품:USED) | 문자열 |
| stockstatus | 재고상태(정상유통일 경우 비어있음, 품절/절판 등) | 문자열  |
| mileage | 마일리지 | 정수 |
| cover | 커버(표지) | 문자열(URL)  |
| publisher | 출판사(제작사/출시사) | 문자열  |
| salesPoint | 판매지수 | 정수 |
| adult | 성인 등급 여부 (true인 경우 성인 등급 도서) | bool |
| fixedPrice | (종이책/전자책인 경우) 정가제 여부 (true인 경우 정가제 해당 도서) | bool |
| subbarcode | 부가기호 |  |
| customerReviewRank | 회원 리뷰 평점(별점 평균) : 0\~10점(별0.5개당 1점) | 정수 |
| bestDuration | (베스트셀러인 경우만 노출) 베스트셀러 순위 관련 추가 정보 | 문자열 |
| bestRank | (베스트셀러인 경우만 노출) 베스트셀러 순위 정보 | 정수 |
| seriesInfo \< seriesId | 시리즈 ID | 정수 |
| seriesInfo \< seriesLink | 해당 시리즈의 조회 URL | 문자열(URL)   |
| seriesInfo \< seriesName | 시리즈 이름 | 문자열  |
| subInfo \<\< | 부가정보(이하 결과값은 모두 subInfo의 하위 정보) |   |
| ebookList | 해당 종이책의 전자책 리스트 정보 |   |
| ebookList \< itemId | 해당 종이책의 전자책 ItemId | 정수 |
| ebookList \< ISBN | 해당 종이책의 전자책 ISBN | 문자열 |
| ebookList \< isbn13 | 해당 종이책의 전자책 13자리 ISBN | 문자열 |
| ebookList \< priceSales | 해당 종이책의 전자책 판매가 | 정수 |
| ebookList \< link | 해당 종이책의 전자책 상품페이지 링크 | 문자열(URL) |
| usedList | 해당 상품에 등록된 중고상품 정보 |   |
| usedList \< aladinUsed | 알라딘 직접 배송 중고의 정보 |   |
| usedList \< aladinUsed \< itemCount | 알라딘 직접 배송 중고의 보유 상품수 | 정수 |
| usedList \< aladinUsed \< minPrice | 알라딘 직접 배송 중고의 보유 상품중 최저가 상품 판매가격 | 정수 |
| usedList \< aladinUsed \< link | 알라딘 직접 배송 중고의 리스트 페이지 URL | 문자열(URL) |
| usedList \< userUsed | 회원 직접 배송 중고의 정보 |   |
| usedList \< userUsed\< itemCount | 회원 직접 배송 중고의 보유 상품수 | 정수 |
| usedList \< userUsed\< minPrice | 회원 직접 배송 중고의 보유 상품중 최저가 상품 판매가격 | 정수 |
| usedList \< userUsed\< link | 회원 직접 배송 중고의 리스트 페이지 URL | 문자열(URL) |
| usedList \< spaceUsed | 광활한 우주점(매장 배송) 중고의 정보 |   |
| usedList \< spaceUsed\< itemCount | 광활한 우주점(매장 배송) 중고의 보유 상품수 | 정수 |
| usedList \< spaceUsed\< minPrice | 광활한 우주점(매장 배송) 중고의 보유 상품중 최저가 상품 판매가격 | 정수 |
| usedList \< spaceUsed\< link | 광활한 우주점(매장 배송) 중고의 리스트 페이지 URL | 문자열(URL) |
| usedType | 중고상품의 알라딘,회원 직접 배송 여부 (userUsed: 회원 직접 배송, aladinUsed: 알라딘 직접 배송,   spaceUsed: 광활한 우주점) | 문자열 |
| newBookList | 중고상품의 새책 정보 |   |
| newBookList \< itemId | 중고상품의 새책 itemId | 정수 |
| newBookList \< isbn | 중고상품의 새책 isbn | 문자열 |
| newBookList \< isbn13 | 중고상품의 새책 13자리 isbn | 문자열 |
| newBookList \< priceSales | 중고상품의 새책 판매가격 | 정수 |
| newBookList \< link | 중고상품의 새책 상품페이지 URL | 문자열(URL) |
| paperBookList | 전자책에 해당하는 종이책 정보 |   |
| paperBookList \< itemId | 전자책에 해당하는 종이책 itemId | 정수 |
| paperBookList \< isbn | 전자책에 해당하는 종이책 isbn | 문자열 |
| paperBookList \< priceSales | 전자책에 해당하는 종이책 판매가격 | 정수 |
| paperBookList \< link | 전자책에 해당하는 종이책 상품페이지 URL | 문자열(URL) |
| fileFormatList \< fileType | 전자책의 포맷정보 (ex: EPUB, PDF) | 문자열 |
| fileFormatList \< fileSize | 전자책의 용량정보 (byte단위) | 정수 |

## **2\) 상품 조회 API : 부가정보** {#2)-상품-조회-api-:-부가정보}

※ 주황색 정보의 경우, 일반적인 스펙에는 포함되지 않고, 별도로 협의 후 제공

| 필드명 | 설명 | 자료형 |
| ----- | ----- | ----- |
| item \<\< | 상품정보 (이하 결과값은 모두 item의 하위 정보) |   |
| fullDescription | 책소개 | 문자열  |
| fullDescription2 | 출판사 제공 책소개 | 문자열 |
| categoryIdList \< categoryInfo \< categoryId | 전체 분야 정보 \- 카테고리 ID | 정수 |
| categoryIdList \< categoryInfo \< categoryName | 전체 분야 정보 \- 카테고리 명 | 문자열 |
| subInfo \<\< | 부가정보(이하 결과값은 모두 subInfo의 하위 정보) |   |
| subTitle | 부제 | 문자열 |
| originalTitle | 원제 | 문자열 |
| itemPage | 상품의 쪽수 | 숫자 |
| subbarcode | 부가기호 |  |
| taxFree | 비과세 여부(True의 경우 비과세) | bool |
| toc | 목차 | 문자열 |
| previewImgList | Let's Look(미리보기) 이미지 경로 | 문자열(URL) |
| cardReviewImgList  | 카드리뷰 이미지 경로 | 문자열(URL) |
| ratingInfo | 상품의 별 평점,100자평 개수, 마이리뷰 개수 |  |
| ratingInfo \< ratingScore | 상품의 별 평점 | 숫자 (실수) |
| ratingInfo \< ratingCount | 상품에 별을 남긴 개수 | 정수 |
| ratingInfo \< commentReviewCount | 100자평 남긴 개수 | 정수 |
| ratingInfo \< myReviewCount | 마이리뷰 남긴 개수 | 정수 |
| bestSellerRank | 상품의 주간베스트셀러 순위 정보 | 문자열 |
| authors | 참여 작가/아티스트들의 정보 |   |
| authors \< authorId | 참여 작가/아티스트의 ID | 정수 |
| authors \< authorName | 참여 작가/아티스트의 이름 | 문자열 |
| authors \< authorType | 참여 작가/아티스트의 참여 타입 | 문자열 |
| authors \< authorTypeDesc | 참여 작가/아티스트의 참여 타입 설명 | 문자열 |
| authors \< authorInfo | 참여 작가/아티스트의 정보 및 소개 | 문자열 |
| authors \< authorInfoLink | 참여 작가/아티스트의 정보 및 소개 페이지 URL | 문자열(URL) |
| c2bsales | 중고 C2B 매입 여부. 1이면 매입가능. 2면 매입불가 상태.(매입 여부는 수시로 변동되는 정보) | 숫자 |
| c2bsales\_price | 중고 C2B 매입가. AA는 최상급 상태일 경우, A는 상급, B는 중급, C는 균일가매입으로 1천원(C가 0인 경우에는 균일가매입도 불가) | 숫자(금액 원) |
| b2bSupply | 전자책 B2B 납품가능 여부 | bool |
| catno | 음반 고유의 번호 | 문자열 |
| recommendationComment | 음반 추천글 | 문자열 |
| specialFeature | DVD의 Special Feature | 문자열 |
| story | 도서/DVD의 줄거리 | 문자열 |
| disc | DVD의 Disc장수 | 정수 |
| playtime | DVD의 상영시간 | 문자열 |
| language | DVD의 언어 | 문자열 |
| caption | DVD의 자막 | 문자열 |
| screenrate | DVD의 화면비율 | 문자열 |
| recordingtype | DVD의 오디오 | 문자열 |
| areacode | DVD의 지역코드 | 숫자 |
| eventList | 상품과 연관된 이벤트 정보 |   |
| eventList \< link | 상품과 연관된 이벤트 페이지 URL | 문자열(URL) |
| eventList \< title | 상품과 연관된 이벤트 제목 | 문자열 |
| reviewList | 상품에 등록된 리뷰 목록 |   |
| reviewList \< reviewRank | 상품에 등록된 리뷰 평점 (10점 만점) | 정수 |
| reviewList \< writer | 상품에 등록된 리뷰 작성자(닉네임) | 문자열 |
| reviewList \< link | 상품에 등록된 리뷰 연결 URL | 문자열(URL) |
| reviewList \< title | 상품에 등록된 리뷰 제목 | 문자열 |
| offStoreInfo | 중고 매장 정보 |  |
| offStoreInfo \< offCode | 중고 매장의 offCode 값 | 문자열 |
| offStoreInfo \< offName | 중고 매장의 매장명 | 문자열 |
| offStoreInfo \< link | 중고 매장 상품페이지 링크 URL | 문자열(URL) |
| offStoreInfo \< hasStock | 중고 매장내 상품 보유 여부 (1:보유, 0:보유하지 않음) | 정수(bool) |
| offStoreInfo \< maxPrice | 중고 매장내 상품 중 최고가 금액 | 정수 |
| offStoreInfo \< minPrice | 중고 매장내 상품 중 최저가 금액 | 정수 |
| offStoreInfo \< location | 중고 매장내 상품의 위치 정보 | 문자열 |
| packing  | 판형 정보, 포장 관련 정보 |  |
| packing \< styleDesc | 판형 정보 (예: 양장본, 반양장본 등등) | 문자열 |
| packing \< weight | 무게 (그램 기준) | 정수 |
| packing \< sizeDepth | 깊이 (mm 기준) | 정수 |
| packing \< sizeHeight | 세로 (mm 기준) | 정수 |
| packing \< sizeWidth | 가로 (mm 기준) | 정수 |
| phraseList  | 책속에서(책 본문 인용구) 코너 정보 |  |
| phraseList \< pageNo | 책속에서 코너의 페이지 범위 정보 | 문자열 |
| phraseList \< phrase | 책속에서 코너의 문구 정보, 혹은 이미지 정보 (HTML) | 문자열 |
| mdRecommendList | 편집장의 선택 코너 정보 |  |
| mdRecommendList \< title | 편집장의 선택 코너의 제목 | 문자열 |
| mdRecommendList \< comment | 편집장의 선택 코너의 내용 (HTML) | 문자열 |
| mdRecommendList \< mdName | 편집장의 선택 코너의 MD이름/선택 날짜 | 문자열 |

## **3\) 중고상품 보유 매장 검색 API** {#3)-중고상품-보유-매장-검색-api}

| 필드명 | 설명 | 자료형 |
| ----- | ----- | ----- |
| version | API Version | 정수형 날짜 |
| link | API 결과와 관련된 알라딘 페이지 URL 주소 | 문자열(URL) |
| pubDate | API 출력일 | 문자형 날짜 |
| query | API로 조회한 쿼리 | 문자열 |
| itemOffStoreList \<\< | 중고 매장 정보 (이하 결과값은 모두 itemOffStoreList 의 하위 정보) |   |
| offCode | 중고 매장의 offCode 값 | 문자열 |
| offName | 중고 매장의 매장 명 | 문자열 |
| link | 중고 매장 상품 링크 URL | 문자열(URL) |

