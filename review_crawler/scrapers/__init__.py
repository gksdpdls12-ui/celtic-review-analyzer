"""플랫폼별 스크레이퍼 팩토리"""

from ..router import ParsedURL
from .base import BaseScraper
from .coupang import CoupangScraper
from .naver import NaverShoppingScraper, NaverSmartStoreScraper

_SCRAPERS: dict[str, type[BaseScraper]] = {
    "naver_smartstore": NaverSmartStoreScraper,
    "naver_shopping": NaverShoppingScraper,
    "naver_shopping_catalog": NaverShoppingScraper,
    "coupang": CoupangScraper,
}


def get_scraper(platform: str) -> BaseScraper:
    cls = _SCRAPERS.get(platform)
    if not cls:
        raise ValueError(
            f"지원하지 않는 플랫폼: '{platform}'\n"
            f"지원 플랫폼: {', '.join(_SCRAPERS)}"
        )
    return cls()


def scrape_from_url(
    parsed: ParsedURL, max_reviews: int = 100
) -> tuple:
    scraper = get_scraper(parsed.platform)
    return scraper.scrape(parsed, max_reviews=max_reviews)
