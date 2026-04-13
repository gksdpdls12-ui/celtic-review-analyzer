"""
네이버 검색 API — 블로그/뉴스 리뷰 수집
공식 API: https://developers.naver.com/docs/serviceapi/search/

리뷰 분석 전략:
- 쿠팡/네이버쇼핑 직접 리뷰는 API 제한 → 네이버 블로그에 실제 구매 후기 다수 존재
- 네이버 블로그: 실사용 리뷰, 설치 후기, 비교 후기
- 네이버 뉴스: 업계 동향, 제품 출시 소식
"""
import requests
import re
from html import unescape


BLOG_URL  = "https://openapi.naver.com/v1/search/blog"
NEWS_URL  = "https://openapi.naver.com/v1/search/news"


def _headers(client_id: str, client_secret: str) -> dict:
    return {
        "X-Naver-Client-Id": client_id,
        "X-Naver-Client-Secret": client_secret,
    }


def clean_html(text: str) -> str:
    """HTML 태그 및 특수문자 제거"""
    text = re.sub(r"<[^>]+>", "", text)
    return unescape(text).strip()


def search_blog(
    client_id: str,
    client_secret: str,
    query: str,
    display: int = 20,
    sort: str = "sim",  # sim(정확도) | date(최신순)
) -> list[dict]:
    """
    네이버 블로그 검색 (실사용 리뷰 수집 핵심)

    Returns: [{title, description, link, bloggername, postdate}, ...]
    """
    params = {"query": query, "display": display, "sort": sort}
    resp = requests.get(
        BLOG_URL,
        headers=_headers(client_id, client_secret),
        params=params,
        timeout=10,
    )
    resp.raise_for_status()
    items = resp.json().get("items", [])
    return [
        {
            "title": clean_html(item.get("title", "")),
            "description": clean_html(item.get("description", "")),
            "link": item.get("link", ""),
            "author": item.get("bloggername", ""),
            "date": item.get("postdate", ""),
            "source": "naver_blog",
        }
        for item in items
    ]


def search_news(
    client_id: str,
    client_secret: str,
    query: str,
    display: int = 10,
    sort: str = "date",
) -> list[dict]:
    """
    네이버 뉴스 검색 (업계 동향 파악)
    """
    params = {"query": query, "display": display, "sort": sort}
    resp = requests.get(
        NEWS_URL,
        headers=_headers(client_id, client_secret),
        params=params,
        timeout=10,
    )
    resp.raise_for_status()
    items = resp.json().get("items", [])
    return [
        {
            "title": clean_html(item.get("title", "")),
            "description": clean_html(item.get("description", "")),
            "link": item.get("originallink", item.get("link", "")),
            "date": item.get("pubDate", ""),
            "source": "naver_news",
        }
        for item in items
    ]


def collect_reviews(
    client_id: str,
    client_secret: str,
    keywords: list[str],
    display_per_keyword: int = 10,
) -> list[dict]:
    """
    여러 키워드에 대해 블로그 리뷰를 수집합니다.

    keywords 예시: ["대성쎌틱 후기", "대성보일러 리뷰", "셀틱보일러 사용기"]
    """
    all_reviews = []
    seen_links = set()

    for keyword in keywords:
        try:
            items = search_blog(
                client_id, client_secret,
                query=keyword,
                display=display_per_keyword,
                sort="date",  # 최신 리뷰 우선
            )
            for item in items:
                if item["link"] not in seen_links:
                    seen_links.add(item["link"])
                    item["search_keyword"] = keyword
                    all_reviews.append(item)
        except Exception as e:
            print(f"  [경고] '{keyword}' 검색 실패: {e}")

    return all_reviews
