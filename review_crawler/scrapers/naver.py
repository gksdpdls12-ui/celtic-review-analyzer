"""
네이버 스마트스토어 & 네이버 쇼핑 스크레이퍼
최신순(RECENT) 리뷰 우선 수집
"""

from __future__ import annotations

import json
import re
import time

from bs4 import BeautifulSoup

from ..models import CrawledReview, ProductInfo
from ..router import ParsedURL
from .base import BaseScraper, JSON_HEADERS, polite_sleep, safe_get


class NaverSmartStoreScraper(BaseScraper):
    platform = "naver_smartstore"
    PAGE_SIZE = 20

    # ── 내부 API 엔드포인트 ─────────────────────
    STORE_INFO_API = "https://smartstore.naver.com/i/v1/channels/{store_id}"
    PRODUCT_API    = "https://smartstore.naver.com/i/v1/channels/{store_id}/products/{product_no}"
    REVIEW_API     = (
        "https://smartstore.naver.com/i/v1/stores/{channel_uid}"
        "/products/{origin_product_no}/reviews"
    )

    def _get_page_html(self, url: str) -> BeautifulSoup | None:
        resp = safe_get(self.session, url)
        if not resp:
            return None
        return BeautifulSoup(resp.text, "html.parser")

    def _extract_channel_uid(self, store_id: str) -> str:
        """스토어 별칭(store_id) → channel_uid 변환"""
        url = self.STORE_INFO_API.format(store_id=store_id)
        self.session.headers.update({"Referer": f"https://smartstore.naver.com/{store_id}"})
        resp = safe_get(self.session, url)
        if resp:
            try:
                data = resp.json()
                # 응답 구조: {"channelUid": "...", ...} 또는 nested
                uid = (
                    data.get("channelUid")
                    or data.get("channel", {}).get("channelUid")
                    or data.get("id")
                    or ""
                )
                return str(uid)
            except Exception:
                pass

        # HTML 페이지에서 직접 추출 시도
        soup = self._get_page_html(f"https://smartstore.naver.com/{store_id}")
        if soup:
            scripts = soup.find_all("script")
            for sc in scripts:
                if sc.string and "channelUid" in sc.string:
                    m = re.search(r'"channelUid"\s*:\s*"([^"]+)"', sc.string)
                    if m:
                        return m.group(1)
        return store_id  # fallback: store_id 자체를 uid로 사용

    def _extract_origin_product_no(self, store_id: str, product_no: str) -> str:
        """product_no → origin_product_no 변환 (API 응답에서 추출)"""
        url = self.PRODUCT_API.format(store_id=store_id, product_no=product_no)
        self.session.headers.update({
            "Referer": f"https://smartstore.naver.com/{store_id}/products/{product_no}"
        })
        resp = safe_get(self.session, url)
        if resp:
            try:
                data = resp.json()
                origin_no = (
                    data.get("originProductNo")
                    or data.get("product", {}).get("originProductNo")
                    or product_no
                )
                return str(origin_no)
            except Exception:
                pass
        return product_no

    def get_product_info(self, parsed: ParsedURL) -> ProductInfo:
        store_id = parsed.store_id
        product_no = parsed.product_id

        info = ProductInfo(
            url=parsed.original,
            platform=self.platform,
        )

        if not product_no:
            return info

        url = self.PRODUCT_API.format(store_id=store_id, product_no=product_no)
        self.session.headers.update({
            "Referer": f"https://smartstore.naver.com/{store_id}/products/{product_no}",
            **JSON_HEADERS,
        })

        resp = safe_get(self.session, url)
        if not resp:
            # HTML 페이지에서 직접 파싱
            return self._parse_product_from_html(parsed, info)

        try:
            data = resp.json()
            prod = data.get("product", data)

            info.brand = (
                prod.get("brand", {}).get("name", "")
                or prod.get("brandName", "")
                or store_id
            )
            info.product_name = prod.get("name", "")
            info.category = self._extract_category(prod)
            info.rating = prod.get("reviewSummary", {}).get("averageRating")
            info.total_reviews = prod.get("reviewSummary", {}).get("totalReviewCount", 0)

            # 가격
            price_info = prod.get("benefitBuyPrice") or prod.get("salePrice")
            if price_info:
                if isinstance(price_info, dict):
                    info.price_min = price_info.get("minPrice")
                    info.price_max = price_info.get("maxPrice")
                    info.price_display = f"{price_info.get('minPrice', 0):,}원~"
                else:
                    info.price_min = int(price_info)
                    info.price_display = f"{int(price_info):,}원"
        except Exception as e:
            print(f"[naver] 제품 정보 파싱 실패: {e}")

        return info

    def _extract_category(self, prod_data: dict) -> str:
        cats = prod_data.get("category", {})
        if isinstance(cats, dict):
            return cats.get("categoryName", cats.get("name", ""))
        if isinstance(cats, list) and cats:
            return " > ".join(c.get("name", "") for c in cats if c.get("name"))
        return ""

    def _parse_product_from_html(self, parsed: ParsedURL, info: ProductInfo) -> ProductInfo:
        """API 실패 시 HTML 직접 파싱 fallback"""
        url = f"https://smartstore.naver.com/{parsed.store_id}/products/{parsed.product_id}"
        soup = self._get_page_html(url)
        if not soup:
            return info

        # og:title
        og_title = soup.find("meta", property="og:title")
        if og_title:
            info.product_name = og_title.get("content", "")

        # JSON-LD structured data
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                ld = json.loads(script.string or "")
                if ld.get("@type") == "Product":
                    info.product_name = ld.get("name", info.product_name)
                    info.brand = ld.get("brand", {}).get("name", info.brand)
                    offers = ld.get("offers", {})
                    price = offers.get("price") or offers.get("lowPrice")
                    if price:
                        info.price_min = int(float(price))
                        info.price_display = f"{info.price_min:,}원"
                    agg = ld.get("aggregateRating", {})
                    if agg:
                        info.rating = float(agg.get("ratingValue", 0))
                        info.total_reviews = int(agg.get("reviewCount", 0))
                    break
            except Exception:
                continue

        info.brand = info.brand or parsed.store_id
        return info

    def get_reviews(self, parsed: ParsedURL, max_reviews: int = 100) -> list[CrawledReview]:
        store_id = parsed.store_id
        product_no = parsed.product_id

        if not store_id or not product_no:
            print("[naver] store_id 또는 product_no 없음 — 리뷰 수집 불가")
            return []

        # channel_uid & origin_product_no 획득
        channel_uid = self._extract_channel_uid(store_id)
        polite_sleep(0.5, 1.0)
        origin_no = self._extract_origin_product_no(store_id, product_no)
        polite_sleep(0.5, 1.0)

        reviews: list[CrawledReview] = []
        page = 1
        base_url = self.REVIEW_API.format(
            channel_uid=channel_uid,
            origin_product_no=origin_no,
        )
        self.session.headers.update({
            "Referer": f"https://smartstore.naver.com/{store_id}/products/{product_no}",
            **JSON_HEADERS,
        })

        while len(reviews) < max_reviews:
            params = {
                "reviewType": "PURCHASE",
                "sortType": "RECENT",         # 최신순
                "page": page,
                "pageSize": self.PAGE_SIZE,
            }
            resp = safe_get(self.session, base_url, params=params)
            if not resp:
                break

            try:
                data = resp.json()
            except Exception:
                break

            items = (
                data.get("reviews")
                or data.get("contents")
                or data.get("data", {}).get("reviews")
                or []
            )

            if not items:
                break

            for item in items:
                content = item.get("reviewContent", item.get("content", "")).strip()
                if not content:
                    continue

                rating_raw = item.get("reviewScore", item.get("starScore"))
                try:
                    rating = float(rating_raw) if rating_raw is not None else None
                except (ValueError, TypeError):
                    rating = None

                date_str = (
                    item.get("createDate", "")
                    or item.get("reviewDate", "")
                    or item.get("createdAt", "")
                )
                if date_str:
                    date_str = str(date_str)[:10]  # YYYY-MM-DD만 유지

                helpful = item.get("recommendCount", item.get("helpful", 0)) or 0

                reviews.append(CrawledReview(
                    platform=self.platform,
                    product_name=item.get("productName", ""),
                    rating=rating,
                    content=content,
                    date=date_str,
                    helpful_count=int(helpful),
                    is_photo_review=bool(item.get("hasPhotos") or item.get("imageUrls")),
                    purchase_option=item.get("productOptionContent", ""),
                ))

            total = (
                data.get("totalCount")
                or data.get("total")
                or data.get("data", {}).get("totalCount")
                or 0
            )

            if len(reviews) >= max_reviews or len(reviews) >= int(total or 0):
                break

            page += 1
            polite_sleep()

        return reviews[:max_reviews]


class NaverShoppingScraper(BaseScraper):
    """네이버 쇼핑 카탈로그 리뷰 스크레이퍼 (통합 리뷰)"""
    platform = "naver_shopping"
    CATALOG_REVIEW_API = (
        "https://shopping.naver.com/api/reviews/v2/list"
        "?nvMid={nvmid}&page={page}&pageSize={size}&sort=RECENT"
    )

    def get_product_info(self, parsed: ParsedURL) -> ProductInfo:
        info = ProductInfo(url=parsed.original, platform=self.platform)
        if not parsed.product_id:
            return info

        url = f"https://shopping.naver.com/catalog/{parsed.product_id}"
        soup_or_none = self._get_page_html(url)
        if not soup_or_none:
            return info

        # JSON-LD 파싱
        for script in soup_or_none.find_all("script", type="application/ld+json"):
            try:
                ld = json.loads(script.string or "")
                if ld.get("@type") == "Product":
                    info.product_name = ld.get("name", "")
                    info.brand = ld.get("brand", {}).get("name", "")
                    offers = ld.get("offers", {})
                    low = offers.get("lowPrice")
                    high = offers.get("highPrice")
                    if low:
                        info.price_min = int(float(low))
                        info.price_display = f"{info.price_min:,}원~"
                    if high:
                        info.price_max = int(float(high))
                    agg = ld.get("aggregateRating", {})
                    if agg:
                        info.rating = float(agg.get("ratingValue", 0))
                        info.total_reviews = int(agg.get("reviewCount", 0))
                    break
            except Exception:
                continue
        return info

    def _get_page_html(self, url: str) -> BeautifulSoup | None:
        resp = safe_get(self.session, url)
        if not resp:
            return None
        return BeautifulSoup(resp.text, "html.parser")

    def get_reviews(self, parsed: ParsedURL, max_reviews: int = 100) -> list[CrawledReview]:
        nvmid = parsed.product_id
        if not nvmid:
            return []

        reviews: list[CrawledReview] = []
        page = 1
        self.session.headers.update({
            "Referer": f"https://shopping.naver.com/catalog/{nvmid}",
            **JSON_HEADERS,
        })

        while len(reviews) < max_reviews:
            url = self.CATALOG_REVIEW_API.format(
                nvmid=nvmid, page=page, size=self.PAGE_SIZE
            )
            resp = safe_get(self.session, url)
            if not resp:
                break
            try:
                data = resp.json()
            except Exception:
                break

            items = data.get("reviews") or data.get("list") or []
            if not items:
                break

            for item in items:
                content = item.get("body", item.get("content", "")).strip()
                if not content:
                    continue
                rating_raw = item.get("score", item.get("rating"))
                try:
                    rating = float(rating_raw) if rating_raw is not None else None
                except (ValueError, TypeError):
                    rating = None
                date_str = str(item.get("date", item.get("createDate", "")))[:10]

                reviews.append(CrawledReview(
                    platform=self.platform,
                    rating=rating,
                    content=content,
                    date=date_str,
                    helpful_count=item.get("recommCount", 0),
                ))

            total = data.get("totalCount") or data.get("total") or 0
            if len(reviews) >= max_reviews or len(reviews) >= int(total):
                break
            page += 1
            polite_sleep()

        return reviews[:max_reviews]
