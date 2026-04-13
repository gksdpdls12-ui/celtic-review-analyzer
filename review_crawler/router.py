"""
URL → 플랫폼 감지 & 스크레이퍼 라우팅
지원 플랫폼:
  - 네이버 스마트스토어  smartstore.naver.com
  - 네이버 쇼핑          shopping.naver.com/catalog
  - 쿠팡                 coupang.com/vp/products
  - 11번가               11st.co.kr/products
  - G마켓/옥션           gmarket.co.kr / auction.co.kr
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlparse


PLATFORM_PATTERNS: list[tuple[str, str]] = [
    # (regex pattern, platform_id)
    (r"smartstore\.naver\.com", "naver_smartstore"),
    (r"shopping\.naver\.com/catalog", "naver_shopping_catalog"),
    (r"shopping\.naver\.com/.*?nvMid=", "naver_shopping"),
    (r"shopping\.naver\.com", "naver_shopping"),
    (r"coupang\.com/vp/products", "coupang"),
    (r"coupang\.com", "coupang"),
    (r"11st\.co\.kr", "11st"),
    (r"gmarket\.co\.kr", "gmarket"),
    (r"auction\.co\.kr", "auction"),
    (r"youtube\.com/watch", "youtube"),
    (r"youtu\.be/", "youtube"),
]

SUPPORTED_PLATFORMS = {"naver_smartstore", "naver_shopping", "coupang"}
PARTIAL_SUPPORT = {"11st", "gmarket", "auction"}   # HTML만, 리뷰 수 제한


@dataclass
class ParsedURL:
    original: str
    platform: str
    product_id: str = ""
    store_id: str = ""
    extra: dict = None

    def __post_init__(self):
        if self.extra is None:
            self.extra = {}

    @property
    def is_supported(self) -> bool:
        return self.platform in SUPPORTED_PLATFORMS

    @property
    def support_level(self) -> str:
        if self.platform in SUPPORTED_PLATFORMS:
            return "full"
        if self.platform in PARTIAL_SUPPORT:
            return "partial"
        return "unsupported"


# ─────────────────────────────────────────────
# 플랫폼별 URL 파싱
# ─────────────────────────────────────────────

def _parse_naver_smartstore(url: str) -> ParsedURL:
    """
    https://smartstore.naver.com/{store_name}/products/{product_no}
    """
    m = re.search(r"smartstore\.naver\.com/([^/]+)/products/(\d+)", url)
    if m:
        return ParsedURL(
            original=url,
            platform="naver_smartstore",
            store_id=m.group(1),
            product_id=m.group(2),
        )
    # 스토어 홈 URL인 경우
    m2 = re.search(r"smartstore\.naver\.com/([^/?]+)", url)
    store = m2.group(1) if m2 else ""
    return ParsedURL(original=url, platform="naver_smartstore", store_id=store)


def _parse_naver_shopping(url: str) -> ParsedURL:
    """
    https://shopping.naver.com/catalog/{catalog_id}
    https://shopping.naver.com/...?nvMid={nvMid}
    """
    # catalog URL
    m = re.search(r"/catalog/(\d+)", url)
    if m:
        return ParsedURL(
            original=url,
            platform="naver_shopping",
            product_id=m.group(1),
            extra={"type": "catalog"},
        )
    # nvMid 파라미터
    m2 = re.search(r"[?&]nvMid=(\d+)", url)
    if m2:
        return ParsedURL(
            original=url,
            platform="naver_shopping",
            product_id=m2.group(1),
            extra={"type": "nvmid"},
        )
    return ParsedURL(original=url, platform="naver_shopping")


def _parse_coupang(url: str) -> ParsedURL:
    """
    https://www.coupang.com/vp/products/{product_id}?itemId={itemId}&vendorItemId={vendorItemId}
    """
    m = re.search(r"/vp/products/(\d+)", url)
    product_id = m.group(1) if m else ""

    item_id = ""
    m2 = re.search(r"[?&]itemId=(\d+)", url)
    if m2:
        item_id = m2.group(1)

    vendor_item_id = ""
    m3 = re.search(r"[?&]vendorItemId=(\d+)", url)
    if m3:
        vendor_item_id = m3.group(1)

    return ParsedURL(
        original=url,
        platform="coupang",
        product_id=product_id,
        extra={"item_id": item_id, "vendor_item_id": vendor_item_id},
    )


def _parse_generic(url: str, platform: str) -> ParsedURL:
    """기타 플랫폼 — 제품 ID 범용 추출 시도"""
    m = re.search(r"/(?:products?|goods?|item)[s/]+(\d+)", url)
    product_id = m.group(1) if m else ""
    return ParsedURL(original=url, platform=platform, product_id=product_id)


# ─────────────────────────────────────────────
# 공개 API
# ─────────────────────────────────────────────

def detect_platform(url: str) -> str:
    """URL에서 플랫폼 ID 감지"""
    for pattern, platform_id in PLATFORM_PATTERNS:
        if re.search(pattern, url, re.IGNORECASE):
            return platform_id
    return "unknown"


def parse_url(url: str) -> ParsedURL:
    """URL을 파싱하여 플랫폼 정보와 제품 ID를 추출"""
    # 프로토콜 없으면 추가
    if not url.startswith("http"):
        url = "https://" + url

    platform = detect_platform(url)

    if platform == "naver_smartstore":
        return _parse_naver_smartstore(url)
    if platform in ("naver_shopping", "naver_shopping_catalog"):
        return _parse_naver_shopping(url)
    if platform == "coupang":
        return _parse_coupang(url)
    if platform in PARTIAL_SUPPORT:
        return _parse_generic(url, platform)

    return ParsedURL(original=url, platform=platform)


def validate_url(url: str) -> tuple[bool, str]:
    """
    URL 유효성 검사.
    Returns: (is_valid, error_message)
    """
    parsed = parse_url(url)

    if parsed.platform == "unknown":
        supported = ", ".join(sorted(SUPPORTED_PLATFORMS | PARTIAL_SUPPORT))
        return False, f"지원하지 않는 플랫폼입니다. 지원: {supported}"

    if parsed.platform == "youtube":
        return False, "YouTube URL은 research_bot을 사용해주세요 (youtube.py)"

    if parsed.support_level == "unsupported":
        return False, f"{parsed.platform}은 현재 지원되지 않습니다."

    if parsed.support_level == "partial":
        return True, f"[주의] {parsed.platform}은 부분 지원 (리뷰 수 제한될 수 있음)"

    return True, ""
