"""
경쟁사 리뷰 수집기
- 네이버 스마트스토어: .env NAVER_COOKIES 사용 (브라우저 불필요)
- 쿠팡: 공개 API 직접 호출
"""

from __future__ import annotations

import os
import re
import time
import random
from urllib.parse import urlparse

import requests

from .models import ProductInfo, Review


# ─────────────────────────────────────────────
# 공통 HTTP 설정
# ─────────────────────────────────────────────

_UA_LIST = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
]

PAGE_SIZE = 20


def _session(referer: str = "") -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "User-Agent": random.choice(_UA_LIST),
        "Accept-Language": "ko-KR,ko;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
    })
    if referer:
        s.headers["Referer"] = referer
    return s


def _sleep():
    time.sleep(random.uniform(0.8, 1.5))


# ─────────────────────────────────────────────
# URL 파싱
# ─────────────────────────────────────────────

def detect_platform(url: str) -> str:
    host = urlparse(url).netloc.lower()
    if "smartstore.naver.com" in host:
        return "naver_smartstore"
    if "coupang.com" in host:
        return "coupang"
    return "unknown"


def _parse_naver_url(url: str) -> tuple[str, str]:
    """store_id, product_no 반환"""
    m = re.search(r"smartstore\.naver\.com/([^/?#]+)/products/(\d+)", url)
    if not m:
        raise ValueError(f"스마트스토어 URL 형식이 아닙니다: {url}")
    return m.group(1), m.group(2)


def _parse_coupang_url(url: str) -> str:
    """product_id 반환"""
    m = re.search(r"/vp/products/(\d+)", url)
    if not m:
        raise ValueError(f"쿠팡 URL 형식이 아닙니다: {url}")
    return m.group(1)


# ─────────────────────────────────────────────
# 네이버 스마트스토어
# ─────────────────────────────────────────────

def _naver_cookies() -> dict:
    raw = os.environ.get("NAVER_COOKIES", "")
    if not raw:
        return {}
    result = {}
    for part in raw.split(";"):
        part = part.strip()
        if "=" in part:
            k, _, v = part.partition("=")
            result[k.strip()] = v.strip()
    return result


def _naver_get_ids(session: requests.Session, store_id: str, product_no: str) -> tuple[str, str]:
    """제품 페이지 HTML에서 channelNo, originProductNo 추출"""
    url = f"https://smartstore.naver.com/{store_id}/products/{product_no}"
    resp = session.get(url, timeout=15)
    if resp.status_code != 200:
        raise RuntimeError(f"제품 페이지 로드 실패: HTTP {resp.status_code}")

    html = resp.text
    m1 = re.search(r'"channelNo"\s*:\s*["\']?(\d+)', html)
    m2 = re.search(r'"originProductNo"\s*:\s*["\']?(\d+)', html)

    channel_no = m1.group(1) if m1 else ""
    origin_no  = m2.group(1) if m2 else product_no

    if not channel_no:
        # __PRELOADED_STATE__ JSON fallback
        m3 = re.search(r'window\.__PRELOADED_STATE__\s*=\s*({.+?});\s*\n', html, re.DOTALL)
        if m3:
            try:
                import json
                state = json.loads(m3.group(1))
                def _find(obj, key):
                    if isinstance(obj, dict):
                        for k, v in obj.items():
                            if k == key and v:
                                return str(v)
                            found = _find(v, key)
                            if found:
                                return found
                    elif isinstance(obj, list):
                        for item in obj:
                            found = _find(item, key)
                            if found:
                                return found
                    return ""
                channel_no = _find(state, "channelNo") or channel_no
                origin_no  = _find(state, "originProductNo") or origin_no
            except Exception:
                pass

    print(f"[naver] channelNo={channel_no or '(미확인)'}  originNo={origin_no}")
    return channel_no or store_id, origin_no


def _naver_product_info(session: requests.Session, store_id: str, product_no: str, url: str) -> ProductInfo:
    page_url = f"https://smartstore.naver.com/{store_id}/products/{product_no}"
    resp = session.get(page_url, timeout=15)
    html = resp.text if resp.status_code == 200 else ""

    product_name = ""
    rating = None
    total_reviews = 0

    # og:title
    m = re.search(r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)', html)
    if m:
        product_name = m.group(1).strip()

    # aggregateRating
    m2 = re.search(r'"ratingValue"\s*:\s*"?([\d.]+)"?', html)
    m3 = re.search(r'"reviewCount"\s*:\s*"?(\d+)"?', html)
    if m2:
        try:
            rating = float(m2.group(1))
        except ValueError:
            pass
    if m3:
        try:
            total_reviews = int(m3.group(1))
        except ValueError:
            pass

    return ProductInfo(
        product_name=product_name,
        brand=store_id,
        platform="naver_smartstore",
        rating=rating,
        total_reviews=total_reviews,
    )


def scrape_naver(url: str, max_reviews: int = 100) -> tuple[ProductInfo, list[Review]]:
    store_id, product_no = _parse_naver_url(url)
    cookies = _naver_cookies()

    if not cookies:
        raise RuntimeError(
            "NAVER_COOKIES가 설정되지 않았습니다.\n"
            ".env 파일에 NAVER_COOKIES=... 를 추가하세요.\n"
            "(브라우저 개발자도구 → Application → Cookies에서 복사)"
        )

    session = _session(referer=f"https://smartstore.naver.com/{store_id}/products/{product_no}")
    session.cookies.update(cookies)

    # 제품 정보 + ID 추출
    info = _naver_product_info(session, store_id, product_no, url)
    _sleep()
    channel_no, origin_no = _naver_get_ids(session, store_id, product_no)

    # 리뷰 수집
    reviews: list[Review] = []
    page = 1

    while len(reviews) < max_reviews:
        api_url = (
            f"https://smartstore.naver.com/i/v1/stores/{channel_no}/products/{origin_no}"
            f"/reviews?reviewType=PURCHASE&sortType=RECENT&page={page}&pageSize={PAGE_SIZE}"
        )
        resp = session.get(api_url, headers={"Accept": "application/json"}, timeout=15)

        if resp.status_code == 401:
            raise RuntimeError("쿠키가 만료됐습니다. .env의 NAVER_COOKIES를 갱신해주세요.")
        if resp.status_code == 403:
            raise RuntimeError("접근이 차단됐습니다. 잠시 후 다시 시도하세요.")
        if resp.status_code != 200:
            print(f"[naver] API 오류: HTTP {resp.status_code}")
            break

        data = resp.json()
        items = data.get("reviews") or data.get("contents") or data.get("list") or []
        if not items:
            break

        for item in items:
            content = (item.get("reviewContent") or item.get("content") or "").strip()
            if not content:
                continue

            rating_raw = item.get("reviewScore") or item.get("starScore") or item.get("score")
            try:
                rating = float(rating_raw) if rating_raw is not None else None
            except (ValueError, TypeError):
                rating = None

            reviews.append(Review(
                product_name=info.product_name,
                rating=rating,
                content=content,
                date=str(item.get("createDate") or item.get("reviewDate") or "")[:10],
                helpful_count=int(item.get("recommenderCount") or item.get("recommendCount") or 0),
                is_photo_review=bool(item.get("attachedImageCount") or item.get("imageUrls")),
                purchase_option=item.get("optionContent") or item.get("productOptionContent") or "",
            ))

        total = int(data.get("totalCount") or data.get("total") or 0)
        print(f"[naver] page={page}  수집={len(reviews)}개 / 전체={total}개")

        if not total or len(reviews) >= min(max_reviews, total):
            break

        page += 1
        _sleep()

    info.total_reviews = info.total_reviews or len(reviews)
    return info, reviews[:max_reviews]


# ─────────────────────────────────────────────
# 쿠팡
# ─────────────────────────────────────────────

def scrape_coupang(url: str, max_reviews: int = 100) -> tuple[ProductInfo, list[Review]]:
    product_id = _parse_coupang_url(url)
    session = _session(referer=url)
    session.headers.update({
        "Accept": "application/json, text/plain, */*",
        "Referer": url,
    })

    # 제품 정보
    info = _coupang_product_info(session, product_id, url)

    # 리뷰 수집
    reviews: list[Review] = []
    page = 1

    while len(reviews) < max_reviews:
        api_url = (
            f"https://www.coupang.com/vp/products/{product_id}/reviews"
            f"?page={page}&per_page={PAGE_SIZE}&sortBy=DATE_DESC&ratings=&q=&viRoleCode=2&ratingSummary=true"
        )
        resp = session.get(api_url, timeout=15)

        if resp.status_code == 403:
            print("[coupang] 접근 차단됨. 잠시 후 다시 시도하세요.")
            break
        if resp.status_code != 200:
            print(f"[coupang] API 오류: HTTP {resp.status_code}")
            break

        try:
            data = resp.json()
        except Exception:
            print("[coupang] JSON 파싱 오류")
            break

        items = (data.get("data") or {}).get("reviews") or data.get("reviews") or []
        if not items:
            break

        for item in items:
            content = (item.get("reviewText") or item.get("content") or "").strip()
            if not content:
                continue

            rating_raw = item.get("rating") or item.get("reviewRating")
            try:
                rating = float(rating_raw) if rating_raw is not None else None
            except (ValueError, TypeError):
                rating = None

            reviews.append(Review(
                product_name=info.product_name,
                rating=rating,
                content=content,
                date=str(item.get("reviewDate") or item.get("date") or "")[:10],
                helpful_count=int(item.get("helpfulCount") or item.get("helpful") or 0),
                is_photo_review=bool(item.get("photoReview") or item.get("hasImage")),
                purchase_option=item.get("productOptionName") or item.get("optionName") or "",
            ))

        total = (data.get("data") or {}).get("totalCount") or data.get("totalCount") or 0
        print(f"[coupang] page={page}  수집={len(reviews)}개 / 전체={total}개")

        if not total or len(reviews) >= min(max_reviews, total):
            break

        page += 1
        _sleep()

    info.total_reviews = info.total_reviews or len(reviews)
    return info, reviews[:max_reviews]


def _coupang_product_info(session: requests.Session, product_id: str, url: str) -> ProductInfo:
    resp = session.get(url, timeout=15)
    html = resp.text if resp.status_code == 200 else ""

    product_name = ""
    rating = None
    total_reviews = 0

    m = re.search(r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)', html)
    if m:
        product_name = m.group(1).strip()

    m2 = re.search(r'"ratingValue"\s*:\s*"?([\d.]+)"?', html)
    m3 = re.search(r'"reviewCount"\s*:\s*"?(\d+)"?', html)
    if m2:
        try:
            rating = float(m2.group(1))
        except ValueError:
            pass
    if m3:
        try:
            total_reviews = int(m3.group(1))
        except ValueError:
            pass

    return ProductInfo(
        product_name=product_name,
        platform="coupang",
        rating=rating,
        total_reviews=total_reviews,
    )


# ─────────────────────────────────────────────
# 공개 API
# ─────────────────────────────────────────────

def scrape(url: str, max_reviews: int = 100) -> tuple[ProductInfo, list[Review]]:
    """URL을 보고 자동으로 플랫폼 감지 후 수집"""
    platform = detect_platform(url)

    if platform == "naver_smartstore":
        print(f"[scraper] 네이버 스마트스토어 → 쿠키 모드")
        return scrape_naver(url, max_reviews)

    if platform == "coupang":
        print(f"[scraper] 쿠팡 → requests 모드")
        return scrape_coupang(url, max_reviews)

    raise ValueError(
        f"지원하지 않는 URL입니다.\n"
        f"지원: 네이버 스마트스토어, 쿠팡\n"
        f"입력: {url}"
    )
