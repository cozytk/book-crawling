"""AI service for generating book descriptions using Brave Search and Gemini."""
import os
import logging
from typing import Optional
import httpx
from google import genai

logger = logging.getLogger(__name__)

# Configure Gemini API
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
BRAVE_SEARCH_API_KEY = os.getenv("BRAVE_SEARCH_API_KEY")

if GEMINI_API_KEY:
    client = genai.Client(api_key=GEMINI_API_KEY)


async def generate_book_description(
    book_title: str, author: Optional[str] = None
) -> Optional[str]:
    """
    Generate a book description using Brave Search and Gemini Flash 3.

    Args:
        book_title: The title of the book
        author: Optional author name

    Returns:
        A 2-3 sentence description of the book and author, or None if generation fails
    """
    try:
        # Step 1: Search using Brave Search API
        search_query = f"{book_title}"
        if author:
            search_query += f" {author}"

        search_results = await _brave_search(search_query)
        if not search_results:
            logger.warning(f"No search results found for: {search_query}")
            return None

        # Step 2: Generate description using Gemini
        description = await _generate_with_gemini(book_title, search_results)
        return description

    except Exception as e:
        logger.error(f"Error generating book description: {e}", exc_info=True)
        return None


async def _brave_search(query: str) -> Optional[str]:
    """
    Search using Brave Search API.

    Args:
        query: Search query string

    Returns:
        Formatted search results as string, or None if search fails
    """
    if not BRAVE_SEARCH_API_KEY:
        logger.error("BRAVE_SEARCH_API_KEY not configured")
        return None

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://api.search.brave.com/res/v1/web/search",
                headers={
                    "X-Subscription-Token": BRAVE_SEARCH_API_KEY,
                    "Accept": "application/json"
                },
                params={
                    "q": query,
                    "count": 10,
                    "search_lang": "en"
                },
                timeout=10.0
            )
            response.raise_for_status()

            data = response.json()
            results = data.get("web", {}).get("results", [])

            if not results:
                return None

            # Format top 5 results
            formatted_results = []
            for i, result in enumerate(results[:5], 1):
                title = result.get("title", "")
                description = result.get("description", "")
                formatted_results.append(f"{i}. {title}\n{description}")

            return "\n\n".join(formatted_results)

    except httpx.HTTPError as e:
        logger.error(f"Brave Search API error: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error during search: {e}")
        return None


async def _generate_with_gemini(book_title: str, search_results: str) -> Optional[str]:
    """
    Generate book description using Gemini Flash 3.

    Args:
        book_title: The title of the book
        search_results: Formatted search results

    Returns:
        Generated description, or None if generation fails
    """
    if not GEMINI_API_KEY:
        logger.error("GEMINI_API_KEY not configured")
        return None

    try:
        prompt = f"""다음은 '{book_title}'에 대한 웹 검색 결과입니다. 이 책과 작가에 대해 자세히 소개해주세요.

검색 결과:
{search_results}

다음 내용을 포함하여 상세히 소개해주세요:
1. 작가 소개 (국적, 대표작, 특징 등)
2. 책의 주요 내용과 주제
3. 책의 특징과 의의
4. 독자 반응이나 평가 (있다면)

상세한 소개:"""

        response = await client.aio.models.generate_content(
            model="gemini-3-flash-preview",
            contents=prompt
        )

        if response and response.text:
            return response.text.strip()

        return None

    except Exception as e:
        logger.error(f"Gemini API error: {e}")
        return None
