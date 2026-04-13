"""
쿠팡 리뷰 스크레이퍼
최신순(DATE) 리뷰 수집
"""

from __future__ import annotations

import json
import re

from bs4 import BeautifulSoup

from ..models import CrawledReview, ProductInfo
from ..router import ParsedURL
from .base import BaseScraper, JSON_HEADERS, polite_sleep, safe_get


class CoupangScraper(BaseScraper):
    platform = "coupang"
    PAGE_SIZE = 10

    REVIEW_API = (
        "https://www.coupang.com/vp/products/{product_id}/reviews"
        "?page={page}&per_page={size}&star=0&order_by=DATE"
        "&product_id={product_id}&target_product_id={product_id}"
        "{item_params}"
    )

    def _get_page(self, url: str) -> BeautifulSoup | None:
        self.session.headers.update({"Referer": "https://www.coupang.com/"})
        resp = safe_get(self.session, url)
        if not resp:
            return None
        return BeautifulSoup(resp.text, "html.parser")

    def get_product_info(self, parsed: ParsedURL) -> ProductInfo:
        info = ProductInfo(url=parsed.original, platform=self.platform)
        product_id = parsed.product_id
        if not product_id:
            return info

        url = f"https://www.coupang.com/vp/products/{product_id}"
        soup = self._get_page(url)
        if not soup:
            return info

        try:
            # 상품명
            title_el = (
                soup.find("h1", class_=re.compile(r"prod-buy-header"))
                or soup.find("h2", class_=re.compile(r"prod-buy-header"))
                or soup.find("meta", attrs={"name": "og:title"})
                or soup.find("meta", property="og:title")
            )
            if title_el:
                info.product_name = (
                    title_el.get_text(strip=True)
                    if hasattr(title_el, "get_text")
                    else title_el.get("content", "")
                )

            # 가격
            price_el = soup.find(class_=re.compile(r"prod-price|total-price"))
            if price_el:
                price_text = re.sub(r"[^\d]", "", price_el.get_text())
                if price_text:
                    info.price_min = int(price_text)
                    info.price_display = f"{info.price_min:,}원"

            # JSON-LD
            for script in soup.find_all("script", type="application/ld+json"):
                try:
                    ld = json.loads(script.string or "")
                    if ld.get("@type") == "Product":
                        info.product_name = ld.get("name", info.product_name)
                        info.brand = ld.get("brand", {}).get("name", "")
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

            # 카테고리 breadcrumb
            breadcrumb = soup.find(class_=re.compile(r"breadcrumb|category"))
            if breadcrumb:
                items = breadcrumb.find_all("li")
                if items:
                    info.category = " > ".join(
                        li.get_text(strip=True) for li in items if li.get_text(strip=True)
                    )

            # 별점 / 리뷰 수 (HTML fallback)
            rating_el = soup.find(class_=re.compile(r"star-gray|avg-rating|ratingValue"))
            if rating_el and not info.rating:
                try:
                    info.rating = float(re.search(r"[\d.]+", rating_el.get_text()).group())
                except Exception:
                    pass

            review_count_el = soup.find(class_=re.compile(r"count-review|reviewCount"))
            if review_count_el and not info.total_reviews:
                try:
                    info.total_reviews = int(
                        re.sub(r"[^\d]", "", review_count_el.get_text())
                    )
                except Exception:
                    pass

        except Exception as e:
            print(f"[coupang] 제품 정보 파싱 오류: {e}")

        return info

    def get_reviews(self, parsed: ParsedURL, max_reviews: int = 100) -> list[CrawledReview]:
        product_id = parsed.product_id
        if not product_id:
            print("[coupang] product_id 없음 — 리뷰 수집 불가")
            return []

        item_id = parsed.extra.get("item_id", "")
        vendor_item_id = parsed.extra.get("vendor_item_id", "")
        item_params = ""
        if item_id:
            item_params += f"&item_id={item_id}"
        if vendor_item_id:
            item_params += f"&vendor_item_id={vendor_item_id}"

        # 제품 페이지 방문으로 쿠키 획득
        self.session.get(
            f"https://www.coupang.com/vp/products/{product_id}",
            timeout=15,
        )
        polite_sleep(1.0, 2.0)

        self.session.headers.update({
            "Referer": f"https://www.coupang.com/vp/products/{product_id}",
            "X-Requested-With": "XMLHttpRequest",
            **JSON_HEADERS,
        })

        reviews: list[CrawledReview] = []
        page = 1

        while len(reviews) < max_reviews:
            url = self.REVIEW_API.format(
                product_id=product_id,
                page=page,
                size=self.PAGE_SIZE,
                item_params=item_params,
            )
            resp = safe_get(self.session, url)
            if not resp:
                break

            # 쿠팡 응답: JSON 또는 HTML
            content_type = resp.headers.get("Content-Type", "")
            if "json" in content_type:
                try:
                    data = resp.json()
                    items = (
                        data.get("reviews")
                        or data.get("data", {}).get("reviews")
                        or []
                    )
                except Exception:
                    break
            else:
                # HTML 파싱 fallback
                items = self._parse_review_html(resp.text)

            if not items:
                break

            for item in items:
                content = self._extract_review_content(item)
                if not content:
                    continue

                rating_raw = item.get("rating", item.get("starScore", item.get("score")))
                try:
                    rating = float(rating_raw) if rating_raw is not None else None
                except (ValueError, TypeError):
                    rating = None

                date_str = str(
                    item.get("orderDate", item.get("writeDate", item.get("date", "")))
                )[:10]

                helpful = item.get("helpfulCount", item.get("useful", 0)) or 0

                reviews.append(CrawledReview(
                    platform=self.platform,
                    product_name=item.get("productName", ""),
                    rating=rating,
                    content=content,
                    date=date_str,
                    helpful_count=int(helpful),
                    is_photo_review=bool(
                        item.get("hasImages") or item.get("imageList")
                    ),
                    purchase_option=item.get("purchaseOptionName", ""),
                    user_profile=item.get("userProfileType", ""),
                ))

            if len(reviews) >= max_reviews:
                break

            page += 1
            polite_sleep(1.0, 2.5)  # 쿠팡은 좀 더 여유있게

        return reviews[:max_reviews]

    def _extract_review_content(self, item: dict | str) -> str:
        if isinstance(item, str):
            return item.strip()
        return (
            item.get("reviewBody", "")
            or item.get("content", "")
            or item.get("body", "")
            or item.get("review", "")
            or ""
        ).strip()

    def _parse_review_html(self, html: str) -> list[dict]:
        """HTML 응답에서 리뷰 파싱 (JSON API 실패 시 fallback)"""
        soup = BeautifulSoup(html, "html.parser")
        items = []

        review_els = soup.find_all(
            class_=re.compile(r"review-item|js_reviewArticle|sdp-review-article")
        )
        for el in review_els:
            body_el = el.find(class_=re.compile(r"review-body|reviewBody|sdp-review-article__body"))
            if not body_el:
                body_el = el.find("p")
            content = body_el.get_text(strip=True) if body_el else ""
            if not content:
                continue

            rating_el = el.find(class_=re.compile(r"star-gray|rating|stars"))
            rating = None
            if rating_el:
                m = re.search(r"(\d+(?:\.\d+)?)", rating_el.get("style", "") + rating_el.get_text())
                if m:
                    try:
                        rating = min(float(m.group(1)), 5.0)
                    except ValueError:
                        pass

            date_el = el.find(class_=re.compile(r"date|review-date"))
            date_str = date_el.get_text(strip=True) if date_el else ""

            items.append({"content": content, "rating": rating, "date": date_str})

        return items
