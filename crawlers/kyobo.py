import re

from bs4 import BeautifulSoup

from .base import BasePlatformCrawler


class KyoboCrawler(BasePlatformCrawler):
    """교보문고 크롤러"""

    name = "kyobo"
    base_url = "https://www.kyobobook.co.kr"
    rating_scale = 10

    async def search_book(self, query: str) -> tuple[str | None, str]:
        """책 검색 후 가장 관련 있는 결과의 상세 페이지 URL 반환"""
        search_url = f"https://search.kyobobook.co.kr/search?keyword={query}"

        print(f"[{self.name}] 검색 중: {query}")
        await self.page.goto(search_url)

        try:
            await self.page.wait_for_selector(".prod_list", timeout=10000)
        except Exception:
            print(f"[{self.name}] 검색 결과를 찾을 수 없습니다.")
            return None, ""

        content = await self.page.content()
        soup = BeautifulSoup(content, "html.parser")

        # 모든 검색 결과에서 가장 관련 있는 것 선택
        items = soup.select(".prod_item")
        if not items:
            return None, ""

        query_lower = query.lower()
        best_match = None
        best_title = ""
        best_url = ""

        for item in items:
            # data-name 속성에서 책 제목 추출 (가장 정확)
            checkbox = item.select_one("input.result_checkbox")
            if checkbox:
                book_name = checkbox.get("data-name", "")
            else:
                title_elem = item.select_one(".prod_info")
                book_name = title_elem.get_text(strip=True) if title_elem else ""

            # 링크 추출
            link_elem = item.select_one("a.prod_link")
            if not link_elem:
                link_elem = item.select_one("a[href*='/detail/']")
            if not link_elem:
                continue

            book_url = link_elem.get("href", "")
            if not book_url.startswith("http"):
                book_url = "https://product.kyobobook.co.kr" + book_url

            # ebook 제외 (종이책 우선)
            if "ebook" in book_url.lower():
                continue

            # 첫 번째 유효한 결과를 기본으로 저장
            if best_match is None:
                best_match = item
                best_title = book_name
                best_url = book_url

            # 검색어가 제목에 포함된 경우 우선
            if query_lower in book_name.lower():
                best_match = item
                best_title = book_name
                best_url = book_url
                break

        if not best_url:
            return None, ""

        print(f"[{self.name}] 찾은 책: {best_title}")
        return best_url, best_title

    async def get_rating(self, url: str) -> tuple[float | None, int]:
        """상세 페이지에서 평점/리뷰수 추출"""
        await self.page.goto(url)
        await self.delay(1, 2)

        content = await self.page.content()
        soup = BeautifulSoup(content, "html.parser")

        # 평점 추출 (교보문고는 10점 만점)
        rating = None
        # .review_score 또는 .feel_lucky 내의 점수
        rating_selectors = [
            ".review_score",
            ".feel_lucky .review_score",
            ".col_review .review_score",
        ]
        for selector in rating_selectors:
            rating_elem = soup.select_one(selector)
            if rating_elem:
                rating_text = rating_elem.get_text(strip=True)
                try:
                    rating = float(rating_text)
                    break
                except ValueError:
                    continue

        # 리뷰 수 추출 - "(N개의 리뷰)" 패턴에서 추출
        review_count = 0

        # prod_review_box 또는 col_review에서 찾기
        review_sections = soup.select(".prod_review_box, .col_review, .tab_content")
        for section in review_sections:
            text = section.get_text()
            # "(117개의 리뷰)" 또는 "Klover 리뷰 (117)" 패턴
            patterns = [
                r"\((\d[\d,]*)\s*개의\s*리뷰\)",
                r"리뷰\s*\((\d[\d,]*)\)",
                r"Klover\s*리뷰\s*\((\d[\d,]*)\)",
            ]
            for pattern in patterns:
                match = re.search(pattern, text)
                if match:
                    review_count = int(match.group(1).replace(",", ""))
                    break
            if review_count > 0:
                break

        return rating, review_count
