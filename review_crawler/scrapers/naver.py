"""
네이버 스마트스토어 & 네이버 쇼핑 스크레이퍼 (2025 최신)

핵심 변경사항:
  - 제품 페이지 HTML 에서 __PRELOADED_STATE__ / window.__STORE__ 직접 파싱
  - channelNo(숫자 ID) 추출 — 문자열 alias 가 아닌 숫자를 사용해야 리뷰 API 응답
  - 리뷰 API 호출 전 제품 페이지 방문으로 NNB 쿠키 선취득
  - 여러 패턴 fallback 체인으로 페이지 구조 변경에 대응
"""

from __future__ import annotations

import json
import re
import time

from bs4 import BeautifulSoup

from ..models import CrawledReview, ProductInfo
from ..router import ParsedURL
from .base import BaseScraper, JSON_HEADERS, polite_sleep, safe_get

# ─────────────────────────────────────────────
# 공통 상수
# ─────────────────────────────────────────────

_PRODUCT_PAGE  = "https://smartstore.naver.com/{store_id}/products/{product_no}"
_REVIEW_API    = (
    "https://smartstore.naver.com/i/v1/stores/{channel_no}"
    "/products/{origin_product_no}/reviews"
)
_CHANNEL_API   = "https://smartstore.naver.com/i/v1/channels/{store_id}"


class NaverSmartStoreScraper(BaseScraper):
    platform = "naver_smartstore"
    PAGE_SIZE = 20

    # ── 페이지 HTML 가져오기 ─────────────────────

    def _fetch_product_page(self, store_id: str, product_no: str) -> str:
        """제품 페이지 HTML 반환 + 세션 쿠키(NNB 등) 자동 획득"""
        url = _PRODUCT_PAGE.format(store_id=store_id, product_no=product_no)
        self.session.headers.update({
            "Referer": f"https://smartstore.naver.com/{store_id}",
            "Accept": (
                "text/html,application/xhtml+xml,application/xml;"
                "q=0.9,image/avif,image/webp,*/*;q=0.8"
            ),
            "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "same-origin",
        })
        resp = safe_get(self.session, url, timeout=20)
        return resp.text if resp else ""

    # ── __PRELOADED_STATE__ / 스크립트 JSON 파싱 ─

    def _extract_preloaded(self, html: str) -> dict:
        """
        네이버 스마트스토어 페이지에서 서버사이드 렌더링 데이터를 추출.
        시도 순서:
          1) window.__PRELOADED_STATE__ = JSON.parse('...')
          2) window.__PRELOADED_STATE__ = {...}
          3) <script id="__NEXT_DATA__"> {...} </script>   (Next.js)
          4) application/json 스크립트 태그
        """
        # ── 패턴 1: JSON.parse(문자열)
        m = re.search(
            r'__PRELOADED_STATE__\s*=\s*JSON\.parse\((["\'])(.+?)\1\)',
            html, re.DOTALL
        )
        if m:
            try:
                raw = m.group(2).encode().decode("unicode_escape")
                return json.loads(raw)
            except Exception:
                pass

        # ── 패턴 2: 직접 객체 할당 (가장 흔한 형태)
        m = re.search(
            r'__PRELOADED_STATE__\s*=\s*(\{.+?\})\s*;?\s*(?:</script>|window\.)',
            html, re.DOTALL
        )
        if m:
            try:
                return json.loads(m.group(1))
            except Exception:
                pass

        # ── 패턴 3: Next.js __NEXT_DATA__
        m = re.search(
            r'<script[^>]+id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>',
            html, re.DOTALL
        )
        if m:
            try:
                return json.loads(m.group(1))
            except Exception:
                pass

        # ── 패턴 4: 스크립트 태그에 포함된 JSON 블록들 순차 탐색
        for script_content in re.findall(
            r'<script[^>]*>(.*?)</script>', html, re.DOTALL
        ):
            if "channelNo" in script_content or "originProductNo" in script_content:
                # JSON 블록 추출 시도
                for m in re.finditer(r'(\{[^{}]{200,}\})', script_content, re.DOTALL):
                    try:
                        obj = json.loads(m.group(1))
                        if isinstance(obj, dict) and (
                            "channelNo" in str(obj) or "originProductNo" in str(obj)
                        ):
                            return obj
                    except Exception:
                        continue

        return {}

    def _find_value(self, data: dict | list | str, *keys: str) -> str:
        """
        중첩 dict/list 에서 key 이름으로 값을 재귀 탐색.
        숫자도 문자열로 반환.
        """
        if isinstance(data, dict):
            for k, v in data.items():
                if k in keys and v:
                    return str(v)
                result = self._find_value(v, *keys)
                if result:
                    return result
        elif isinstance(data, list):
            for item in data:
                result = self._find_value(item, *keys)
                if result:
                    return result
        return ""

    # ── channel_no / origin_product_no 추출 ─────

    def _get_ids_from_page(
        self, html: str, store_id: str, product_no: str
    ) -> tuple[str, str]:
        """
        HTML 에서 (channel_no, origin_product_no) 추출.
        channel_no 는 숫자 ID, origin_product_no 는 원본 상품 번호.
        """
        state = self._extract_preloaded(html)

        channel_no = self._find_value(state, "channelNo")
        origin_no  = self._find_value(state, "originProductNo", "originNo")

        # ── 정규식 fallback (state 파싱 실패 시) ──
        if not channel_no:
            patterns = [
                r'"channelNo"\s*:\s*(\d+)',
                r'channelNo["\s:]+(\d+)',
                r'"channel"[^}]*"no"\s*:\s*(\d+)',
            ]
            for pat in patterns:
                m = re.search(pat, html)
                if m:
                    channel_no = m.group(1)
                    break

        if not origin_no:
            patterns = [
                r'"originProductNo"\s*:\s*(\d+)',
                r'originProductNo["\s:]+(\d+)',
            ]
            for pat in patterns:
                m = re.search(pat, html)
                if m:
                    origin_no = m.group(1)
                    break

        # ── API fallback (HTML 에 없을 때) ────────
        if not channel_no:
            channel_no = self._get_channel_no_via_api(store_id)

        return channel_no or store_id, origin_no or product_no

    def _get_channel_no_via_api(self, store_id: str) -> str:
        """채널 API 로 숫자형 channelNo 획득"""
        self.session.headers.update({
            "Referer": f"https://smartstore.naver.com/{store_id}",
            **JSON_HEADERS,
        })
        resp = safe_get(
            self.session,
            _CHANNEL_API.format(store_id=store_id),
            timeout=10,
        )
        if not resp:
            return ""
        try:
            data = resp.json()
            return str(
                data.get("channelNo")
                or data.get("channel", {}).get("channelNo")
                or data.get("id")
                or ""
            )
        except Exception:
            return ""

    # ── 제품 정보 ────────────────────────────────

    def get_product_info(self, parsed: ParsedURL) -> ProductInfo:
        info = ProductInfo(url=parsed.original, platform=self.platform)
        if not parsed.product_id:
            return info

        html = self._fetch_product_page(parsed.store_id, parsed.product_id)
        if not html:
            return info

        soup = BeautifulSoup(html, "html.parser")
        state = self._extract_preloaded(html)

        # 상품명
        info.product_name = (
            self._find_value(state, "name", "productName")
            or self._meta(soup, "og:title")
            or ""
        )
        # 브랜드
        info.brand = (
            self._find_value(state, "brandName", "mallName", "storeName")
            or parsed.store_id
        )
        # 카테고리
        info.category = self._find_value(state, "categoryName", "wholeCategory")

        # 별점 / 리뷰 수
        rating_str = self._find_value(state, "averageRating", "starScore", "avgRating")
        try:
            info.rating = float(rating_str) if rating_str else None
        except ValueError:
            pass

        review_count_str = self._find_value(
            state, "totalReviewCount", "reviewCount", "count"
        )
        try:
            info.total_reviews = int(review_count_str) if review_count_str else 0
        except ValueError:
            pass

        # 가격
        price_str = self._find_value(
            state, "salePrice", "minPrice", "benefitPrice", "price"
        )
        try:
            price_int = int(float(price_str.replace(",", ""))) if price_str else 0
            if price_int:
                info.price_min = price_int
                info.price_display = f"{price_int:,}원"
        except (ValueError, AttributeError):
            pass

        # JSON-LD fallback
        if not info.product_name or not info.rating:
            for script in soup.find_all("script", type="application/ld+json"):
                try:
                    ld = json.loads(script.string or "")
                    if ld.get("@type") == "Product":
                        info.product_name = info.product_name or ld.get("name", "")
                        info.brand = info.brand or ld.get("brand", {}).get("name", "")
                        if not info.price_min:
                            price = (
                                ld.get("offers", {}).get("price")
                                or ld.get("offers", {}).get("lowPrice")
                            )
                            if price:
                                info.price_min = int(float(price))
                                info.price_display = f"{info.price_min:,}원"
                        if not info.rating:
                            agg = ld.get("aggregateRating", {})
                            if agg:
                                info.rating = float(agg.get("ratingValue", 0) or 0)
                                info.total_reviews = int(agg.get("reviewCount", 0) or 0)
                        break
                except Exception:
                    continue

        return info

    @staticmethod
    def _meta(soup: BeautifulSoup, prop: str) -> str:
        el = soup.find("meta", property=prop) or soup.find("meta", attrs={"name": prop})
        return (el.get("content", "") if el else "") or ""

    # ── 리뷰 수집 ────────────────────────────────

    def get_reviews(self, parsed: ParsedURL, max_reviews: int = 100) -> list[CrawledReview]:
        store_id   = parsed.store_id
        product_no = parsed.product_id

        if not store_id or not product_no:
            print("[naver] store_id 또는 product_no 없음")
            return []

        # ① 제품 페이지 방문 → 쿠키 획득 + IDs 추출
        print(f"[naver] 제품 페이지 로드 중 ({store_id}/{product_no})...")
        html = self._fetch_product_page(store_id, product_no)
        if not html:
            print("[naver] 페이지 로드 실패")
            return []

        channel_no, origin_no = self._get_ids_from_page(html, store_id, product_no)
        print(f"[naver] channelNo={channel_no}  originProductNo={origin_no}")
        polite_sleep(0.8, 1.5)

        # ② 리뷰 API 헤더 설정
        review_url = _REVIEW_API.format(
            channel_no=channel_no,
            origin_product_no=origin_no,
        )
        self.session.headers.update({
            "Referer": _PRODUCT_PAGE.format(
                store_id=store_id, product_no=product_no
            ),
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "ko-KR,ko;q=0.9",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "X-Requested-With": "XMLHttpRequest",
        })
        # Content-Type 제거 (GET 요청에 Content-Type 있으면 일부 서버에서 거부)
        self.session.headers.pop("Content-Type", None)

        reviews: list[CrawledReview] = []
        page = 1

        while len(reviews) < max_reviews:
            params = {
                "reviewType": "PURCHASE",
                "sortType":   "RECENT",
                "page":       page,
                "pageSize":   self.PAGE_SIZE,
            }
            resp = safe_get(self.session, review_url, params=params, timeout=20)
            if not resp:
                print(f"[naver] 리뷰 API 응답 없음 (page={page})")
                break

            # ── 응답 파싱 ──────────────────────
            try:
                data = resp.json()
            except Exception:
                print(f"[naver] JSON 파싱 실패 — status={resp.status_code}")
                if resp.status_code == 403:
                    print("[naver] 403: 잠시 후 재시도 (rate limit 가능성)")
                    time.sleep(5)
                break

            # 리뷰 목록 key 탐색 (구조가 달라질 수 있어 여러 key 시도)
            items: list[dict] = (
                data.get("reviews")
                or data.get("contents")
                or data.get("list")
                or data.get("data", {}).get("reviews")
                or []
            )

            if not items:
                print(f"[naver] 리뷰 없음 (page={page}) — 응답 keys: {list(data.keys())}")
                break

            for item in items:
                content = (
                    item.get("reviewContent")
                    or item.get("content")
                    or item.get("body")
                    or ""
                ).strip()
                if not content:
                    continue

                # 별점
                rating_raw = (
                    item.get("reviewScore")
                    or item.get("starScore")
                    or item.get("score")
                )
                try:
                    rating = float(rating_raw) if rating_raw is not None else None
                except (ValueError, TypeError):
                    rating = None

                # 날짜 (ISO 형식 앞 10자리만)
                date_str = str(
                    item.get("createDate")
                    or item.get("reviewDate")
                    or item.get("createdAt")
                    or ""
                )[:10]

                helpful = (
                    item.get("recommenderCount")
                    or item.get("recommendCount")
                    or item.get("helpful")
                    or 0
                )

                reviews.append(CrawledReview(
                    platform=self.platform,
                    product_name=item.get("productName", ""),
                    rating=rating,
                    content=content,
                    date=date_str,
                    helpful_count=int(helpful or 0),
                    is_photo_review=bool(
                        item.get("attachedImageCount")
                        or item.get("hasPhotos")
                        or item.get("imageUrls")
                    ),
                    purchase_option=(
                        item.get("optionContent")
                        or item.get("productOptionContent")
                        or ""
                    ),
                    user_profile=item.get("reviewerGrade", ""),
                ))

            # 전체 리뷰 수 확인
            total = int(
                data.get("totalCount")
                or data.get("total")
                or data.get("data", {}).get("totalCount")
                or 0
            )
            print(
                f"[naver] page={page}  수집={len(reviews)}개 / 전체={total}개"
            )

            if not total or len(reviews) >= min(max_reviews, total):
                break

            page += 1
            polite_sleep(1.0, 2.0)

        return reviews[:max_reviews]


# ─────────────────────────────────────────────
# 네이버 쇼핑 카탈로그 스크레이퍼
# ─────────────────────────────────────────────

class NaverShoppingScraper(BaseScraper):
    """네이버 쇼핑 카탈로그 통합 리뷰 스크레이퍼"""
    platform = "naver_shopping"

    # 최신 카탈로그 리뷰 API (2025)
    _REVIEW_ENDPOINTS = [
        "https://shopping.naver.com/api/reviews/v2/list?nvMid={nvmid}&page={page}&pageSize={size}&sort=RECENT",
        "https://shopping.naver.com/v1/catalog-reviews?nvMid={nvmid}&page={page}&pageSize={size}&sort=DATE",
    ]

    def _get_page_html(self, url: str) -> BeautifulSoup | None:
        resp = safe_get(self.session, url, timeout=20)
        return BeautifulSoup(resp.text, "html.parser") if resp else None

    def get_product_info(self, parsed: ParsedURL) -> ProductInfo:
        info = ProductInfo(url=parsed.original, platform=self.platform)
        if not parsed.product_id:
            return info

        url = f"https://shopping.naver.com/catalog/{parsed.product_id}"
        self.session.headers.update({"Referer": "https://shopping.naver.com"})
        soup = self._get_page_html(url)
        if not soup:
            return info

        for script in soup.find_all("script", type="application/ld+json"):
            try:
                ld = json.loads(script.string or "")
                if ld.get("@type") == "Product":
                    info.product_name = ld.get("name", "")
                    info.brand        = ld.get("brand", {}).get("name", "")
                    offers = ld.get("offers", {})
                    low = offers.get("lowPrice") or offers.get("price")
                    if low:
                        info.price_min     = int(float(low))
                        info.price_display = f"{info.price_min:,}원~"
                    agg = ld.get("aggregateRating", {})
                    if agg:
                        info.rating        = float(agg.get("ratingValue", 0) or 0)
                        info.total_reviews = int(agg.get("reviewCount", 0) or 0)
                    break
            except Exception:
                continue
        return info

    def get_reviews(self, parsed: ParsedURL, max_reviews: int = 100) -> list[CrawledReview]:
        nvmid = parsed.product_id
        if not nvmid:
            return []

        # 카탈로그 페이지 방문 → 쿠키 획득
        safe_get(
            self.session,
            f"https://shopping.naver.com/catalog/{nvmid}",
            timeout=15,
        )
        polite_sleep(0.8, 1.5)

        self.session.headers.update({
            "Referer": f"https://shopping.naver.com/catalog/{nvmid}",
            "Accept": "application/json, text/plain, */*",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
        })
        self.session.headers.pop("Content-Type", None)

        reviews: list[CrawledReview] = []

        for endpoint_tmpl in self._REVIEW_ENDPOINTS:
            page = 1
            while len(reviews) < max_reviews:
                url = endpoint_tmpl.format(
                    nvmid=nvmid, page=page, size=self.PAGE_SIZE
                )
                resp = safe_get(self.session, url, timeout=15)
                if not resp:
                    break
                try:
                    data = resp.json()
                except Exception:
                    break

                items = (
                    data.get("reviews")
                    or data.get("list")
                    or data.get("contents")
                    or []
                )
                if not items:
                    break

                for item in items:
                    content = (
                        item.get("body") or item.get("content") or ""
                    ).strip()
                    if not content:
                        continue
                    rating_raw = item.get("score") or item.get("rating")
                    try:
                        rating = float(rating_raw) if rating_raw is not None else None
                    except (ValueError, TypeError):
                        rating = None
                    date_str = str(
                        item.get("date") or item.get("createDate") or ""
                    )[:10]
                    reviews.append(CrawledReview(
                        platform=self.platform,
                        rating=rating,
                        content=content,
                        date=date_str,
                        helpful_count=int(item.get("recommCount") or 0),
                    ))

                total = int(data.get("totalCount") or data.get("total") or 0)
                if not total or len(reviews) >= min(max_reviews, total):
                    break
                page += 1
                polite_sleep()

            if reviews:
                break  # 첫 번째 성공한 엔드포인트로 충분

        return reviews[:max_reviews]
