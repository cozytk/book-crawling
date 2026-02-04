import asyncio
import argparse
import pandas as pd
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
import re


async def search_and_get_book_url(page, query, search_type="title"):
    """
    검색어로 책을 찾고 첫 번째 결과의 상세 페이지 URL 반환
    search_type: 'title' 또는 'isbn'
    """
    if search_type == "isbn":
        # ISBN 검색은 직접 상품 조회 가능
        url = f"https://search.kyobobook.co.kr/search?keyword={query}&gbCode=TOT&target=total"
    else:
        url = f"https://search.kyobobook.co.kr/search?keyword={query}"

    print(f"검색 중: {query} ({search_type})")
    await page.goto(url)

    try:
        await page.wait_for_selector(".prod_list", timeout=10000)
    except:
        print("검색 결과를 찾을 수 없습니다.")
        return None, None

    content = await page.content()
    soup = BeautifulSoup(content, "html.parser")

    # 첫 번째 검색 결과 찾기
    first_item = soup.select_one(".prod_item")
    if not first_item:
        print("검색 결과가 없습니다.")
        return None, None

    # 책 링크 추출
    link_elem = first_item.select_one("a.prod_info")
    if not link_elem:
        link_elem = first_item.select_one("a[href*='/product/']")

    if not link_elem:
        print("책 링크를 찾을 수 없습니다.")
        return None, None

    book_url = link_elem.get("href")
    if not book_url.startswith("http"):
        book_url = "https://product.kyobobook.co.kr" + book_url

    # 책 제목 추출
    title_elem = first_item.select_one(".prod_info")
    book_title = title_elem.get_text(strip=True) if title_elem else "Unknown"

    print(f"찾은 책: {book_title}")
    return book_url, book_title


async def get_book_info(page, soup):
    """책 기본 정보 추출"""
    info = {}

    # 제목
    title_elem = soup.select_one(".prod_title, h1.title")
    info["title"] = title_elem.get_text(strip=True) if title_elem else "N/A"

    # 저자
    author_elem = soup.select_one(".author, .prod_author")
    info["author"] = author_elem.get_text(strip=True) if author_elem else "N/A"

    # 출판사
    publisher_elem = soup.select_one(".publisher, .prod_publish")
    info["publisher"] = publisher_elem.get_text(strip=True) if publisher_elem else "N/A"

    # 평점
    rating_elem = soup.select_one(".rating_grade .score, .review_rating .score")
    if rating_elem:
        rating_text = rating_elem.get_text(strip=True)
        info["rating"] = rating_text
    else:
        info["rating"] = "N/A"

    # 리뷰 수
    review_count_elem = soup.select_one(".review_count, .rating_count")
    if review_count_elem:
        count_text = review_count_elem.get_text(strip=True)
        numbers = re.findall(r'\d+', count_text)
        info["review_count"] = numbers[0] if numbers else "0"
    else:
        info["review_count"] = "0"

    return info


async def crawl_reviews(page, book_url, max_reviews=50):
    """
    책 상세 페이지에서 리뷰 수집
    """
    print(f"상세 페이지 접속: {book_url}")
    await page.goto(book_url)
    await asyncio.sleep(2)

    reviews = []

    # 페이지 스크롤하여 리뷰 섹션 로드
    for i in range(5):
        await page.evaluate(f"window.scrollTo(0, {(i + 1) * 1000})")
        await asyncio.sleep(0.5)

    page_num = 1
    while len(reviews) < max_reviews:
        content = await page.content()
        soup = BeautifulSoup(content, "html.parser")

        # 교보문고 리뷰 아이템 셀렉터
        review_items = soup.select("div.comment_item")

        if not review_items:
            print("리뷰를 찾을 수 없습니다.")
            break

        new_reviews_found = False
        for item in review_items:
            if len(reviews) >= max_reviews:
                break

            review = extract_review_data(item)
            # 실제 리뷰 내용이 있는 것만 수집
            if review and review.get("content") and len(review["content"]) > 5:
                # 중복 체크
                if not any(r["content"] == review["content"] for r in reviews):
                    reviews.append(review)
                    new_reviews_found = True
                    content_preview = review["content"][:30].replace("\n", " ")
                    print(f"리뷰 {len(reviews)} 수집: {content_preview}...")

        if not new_reviews_found:
            # 새 리뷰가 없으면 다음 페이지 시도
            pass

        # 다음 페이지 버튼 찾기
        try:
            # 교보문고 페이지네이션: button.btn_page.next 또는 다음 페이지 번호
            next_btn = page.locator("button.btn_page.next:not([disabled])")
            if await next_btn.count() > 0 and page_num < 20 and len(reviews) < max_reviews:
                await next_btn.first.click()
                await asyncio.sleep(1.5)
                page_num += 1
                print(f"페이지 {page_num}로 이동...")
            else:
                # 다음 페이지 번호 직접 클릭
                next_page_num = page_num + 1
                next_page_link = page.locator(f"a.btn_page_num:has-text('{next_page_num}')")
                if await next_page_link.count() > 0 and len(reviews) < max_reviews:
                    await next_page_link.first.click()
                    await asyncio.sleep(1.5)
                    page_num += 1
                    print(f"페이지 {page_num}로 이동...")
                else:
                    break
        except Exception as e:
            print(f"페이지네이션 오류: {e}")
            break

    return reviews


def extract_review_data(item):
    """리뷰 항목에서 데이터 추출 (교보문고 구조)"""
    review = {}

    # 작성자 - .user_info_box 내 첫 번째 .info_item
    info_items = item.select(".user_info_box .info_item")
    if len(info_items) >= 1:
        # 첫 번째 info_item이 작성자 (버튼이 아닌 경우)
        writer_elem = info_items[0]
        if not writer_elem.select_one("button"):
            review["writer"] = writer_elem.get_text(strip=True)
        else:
            review["writer"] = "익명"
    else:
        review["writer"] = "익명"

    # 날짜 - 두 번째 .info_item (보통 날짜 형식)
    if len(info_items) >= 2:
        date_text = info_items[1].get_text(strip=True)
        # 날짜 형식 확인 (YYYY.MM.DD)
        if re.match(r'\d{4}\.\d{2}\.\d{2}', date_text):
            review["date"] = date_text
        else:
            review["date"] = "N/A"
    else:
        review["date"] = "N/A"

    # 평점 - input.form_rating의 value 또는 .caption-badge 텍스트
    rating_input = item.select_one("input.form_rating")
    if rating_input and rating_input.get("value"):
        review["rating"] = rating_input.get("value")
    else:
        caption = item.select_one(".caption-badge")
        if caption:
            rating_text = caption.get_text(strip=True)
            numbers = re.findall(r'(\d+)점', rating_text)
            review["rating"] = numbers[0] if numbers else "N/A"
        else:
            review["rating"] = "N/A"

    # 평가 태그 (쉬웠어요, 추천해요 등)
    quote_elem = item.select_one(".review_quotes_text")
    review["tag"] = quote_elem.get_text(strip=True) if quote_elem else ""

    # 리뷰 내용 - .comment_text
    content_elem = item.select_one(".comment_text")
    if content_elem:
        # br 태그를 줄바꿈으로 변환
        for br in content_elem.find_all("br"):
            br.replace_with("\n")
        review["content"] = content_elem.get_text(strip=True)
    else:
        review["content"] = ""

    # 좋아요 수 - .btn_like .text
    like_elem = item.select_one(".btn_like .text")
    if like_elem:
        like_text = like_elem.get_text(strip=True)
        numbers = re.findall(r'\d+', like_text)
        review["likes"] = numbers[0] if numbers else "0"
    else:
        review["likes"] = "0"

    # 구매 타입 (종이책, eBook 등)
    badge_elem = item.select_one(".badge_kyobo .text")
    review["purchase_type"] = badge_elem.get_text(strip=True) if badge_elem else ""

    return review


async def crawl_book_reviews(query, search_type="title", max_reviews=50):
    """
    메인 크롤링 함수
    query: ISBN 또는 책 제목
    search_type: 'isbn' 또는 'title'
    max_reviews: 최대 수집할 리뷰 수
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        # 1. 책 검색
        book_url, book_title = await search_and_get_book_url(page, query, search_type)

        if not book_url:
            await browser.close()
            return None, []

        # 2. 상세 페이지에서 책 정보 및 리뷰 수집
        await page.goto(book_url)
        await asyncio.sleep(2)

        content = await page.content()
        soup = BeautifulSoup(content, "html.parser")

        book_info = await get_book_info(page, soup)
        book_info["search_query"] = query
        book_info["url"] = book_url

        # 3. 리뷰 수집
        reviews = await crawl_reviews(page, book_url, max_reviews)

        await browser.close()

        return book_info, reviews


def main():
    parser = argparse.ArgumentParser(description="교보문고 책 리뷰 크롤러")
    parser.add_argument("--query", type=str, required=True,
                        help="검색할 ISBN 또는 책 제목")
    parser.add_argument("--type", type=str, default="title", choices=["title", "isbn"],
                        help="검색 타입 (title 또는 isbn)")
    parser.add_argument("--max-reviews", type=int, default=50,
                        help="최대 수집할 리뷰 수")
    parser.add_argument("--output", type=str, default="reviews.csv",
                        help="출력 CSV 파일명")

    args = parser.parse_args()

    print(f"'{args.query}' ({args.type}) 리뷰 수집 시작...")

    book_info, reviews = asyncio.run(
        crawl_book_reviews(args.query, args.type, args.max_reviews)
    )

    if not book_info:
        print("책을 찾을 수 없습니다.")
        return

    print(f"\n=== 책 정보 ===")
    print(f"제목: {book_info.get('title', 'N/A')}")
    print(f"저자: {book_info.get('author', 'N/A')}")
    print(f"출판사: {book_info.get('publisher', 'N/A')}")
    print(f"평점: {book_info.get('rating', 'N/A')}")
    print(f"URL: {book_info.get('url', 'N/A')}")

    if reviews:
        print(f"\n=== 수집된 리뷰: {len(reviews)}개 ===")

        # 리뷰 데이터에 책 정보 추가
        for review in reviews:
            review["book_title"] = book_info.get("title", "")
            review["book_author"] = book_info.get("author", "")

        df = pd.DataFrame(reviews)
        df.to_csv(args.output, index=False, encoding="utf-8-sig")
        print(f"리뷰가 {args.output}에 저장되었습니다.")

        # 샘플 출력
        print(f"\n--- 샘플 리뷰 ---")
        for i, review in enumerate(reviews[:3]):
            print(f"\n[리뷰 {i+1}]")
            print(f"  작성자: {review.get('writer', 'N/A')}")
            print(f"  평점: {review.get('rating', 'N/A')}")
            print(f"  내용: {review.get('content', 'N/A')[:100]}...")
    else:
        print("\n수집된 리뷰가 없습니다.")


if __name__ == "__main__":
    main()
