"""
스크레이퍼 추상 베이스 클래스 + 공통 HTTP 유틸
"""

from __future__ import annotations

import random
import time
from abc import ABC, abstractmethod

import requests
from requests import Response, Session

from ..models import CrawledReview, ProductInfo
from ..router import ParsedURL


# ─────────────────────────────────────────────
# 공통 HTTP 설정
# ─────────────────────────────────────────────

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
]

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

JSON_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "ko-KR,ko;q=0.9",
    "Content-Type": "application/json",
}


def make_session(referer: str = "") -> Session:
    """랜덤 User-Agent + 공통 헤더가 설정된 세션 생성"""
    s = requests.Session()
    headers = {**DEFAULT_HEADERS, "User-Agent": random.choice(USER_AGENTS)}
    if referer:
        headers["Referer"] = referer
    s.headers.update(headers)
    return s


def polite_sleep(min_sec: float = 0.8, max_sec: float = 2.0) -> None:
    """크롤링 간 대기 (서버 부하 방지)"""
    time.sleep(random.uniform(min_sec, max_sec))


def safe_get(
    session: Session,
    url: str,
    params: dict | None = None,
    timeout: int = 15,
    retries: int = 2,
) -> Response | None:
    """재시도 포함 안전한 GET 요청"""
    for attempt in range(retries + 1):
        try:
            resp = session.get(url, params=params, timeout=timeout)
            resp.raise_for_status()
            return resp
        except requests.exceptions.HTTPError as e:
            if resp.status_code in (403, 429):
                wait = (attempt + 1) * 3
                print(f"[scraper] {resp.status_code} 응답 — {wait}초 대기 후 재시도")
                time.sleep(wait)
            else:
                print(f"[scraper] HTTP 오류 {resp.status_code}: {url}")
                return None
        except requests.exceptions.RequestException as e:
            print(f"[scraper] 요청 실패 (시도 {attempt + 1}): {e}")
            if attempt < retries:
                time.sleep(2)
    return None


# ─────────────────────────────────────────────
# 추상 베이스 스크레이퍼
# ─────────────────────────────────────────────

class BaseScraper(ABC):
    """모든 플랫폼 스크레이퍼의 공통 인터페이스"""

    platform: str = "unknown"
    MAX_REVIEWS: int = 100          # 기본 최대 수집량
    PAGE_SIZE: int = 20             # 페이지당 리뷰 수

    def __init__(self):
        self.session = make_session()

    @abstractmethod
    def get_product_info(self, parsed: ParsedURL) -> ProductInfo:
        """제품 기본 정보 추출"""
        ...

    @abstractmethod
    def get_reviews(
        self, parsed: ParsedURL, max_reviews: int = 100
    ) -> list[CrawledReview]:
        """리뷰 수집 (최신순 우선)"""
        ...

    def scrape(
        self, parsed: ParsedURL, max_reviews: int = 100
    ) -> tuple[ProductInfo, list[CrawledReview]]:
        """제품 정보 + 리뷰를 함께 수집"""
        print(f"[{self.platform}] 제품 정보 수집 중...")
        product_info = self.get_product_info(parsed)

        print(f"[{self.platform}] 리뷰 수집 중 (최대 {max_reviews}개)...")
        reviews = self.get_reviews(parsed, max_reviews=max_reviews)

        product_info.crawled_reviews = len(reviews)
        print(f"[{self.platform}] 수집 완료: {len(reviews)}개 리뷰")
        return product_info, reviews
