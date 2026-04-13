"""
리뷰 크롤러 데이터 모델
URL → CrawledReview[] → FullCrawlAnalysis (5단계)
"""

from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, Field


# ─────────────────────────────────────────────
# 크롤링 원시 데이터
# ─────────────────────────────────────────────

class ProductInfo(BaseModel):
    """제품 기본 정보 (크롤링 + Claude 보완)"""
    url: str
    platform: str = Field(..., description="naver_smartstore | coupang | naver_shopping | etc.")
    brand: str = Field(default="", description="브랜드명")
    product_name: str = Field(default="", description="제품명")
    category: str = Field(default="", description="카테고리")
    price_min: int | None = Field(default=None, description="최저가 (원)")
    price_max: int | None = Field(default=None, description="최고가 (원)")
    price_display: str = Field(default="", description="표시 가격 문자열")
    release_date: str = Field(default="", description="출시일 (YYYY-MM)")
    rating: float | None = Field(default=None, description="평균 별점")
    total_reviews: int = Field(default=0, description="총 리뷰 수")
    crawled_reviews: int = Field(default=0, description="실제 수집한 리뷰 수")


class CrawledReview(BaseModel):
    """크롤링된 개별 리뷰"""
    platform: str
    product_name: str = ""
    rating: float | None = None
    content: str
    date: str = ""
    helpful_count: int = 0                        # 도움됨 수
    is_photo_review: bool = False
    purchase_option: str = ""                     # 구매 옵션 (색상/용량 등)
    user_profile: str = ""                        # 리뷰어 등급/구분


# ─────────────────────────────────────────────
# 5단계 분석 결과 모델
# ─────────────────────────────────────────────

# 1. 제품 기본 정보 → ProductInfo (위)

# 2. 감성 분석
class SentimentKeywords(BaseModel):
    positive: list[str] = Field(default_factory=list, description="긍정 키워드 Top10")
    negative: list[str] = Field(default_factory=list, description="부정 키워드 Top10")
    neutral: list[str] = Field(default_factory=list, description="중립/정보 키워드 Top5")
    positive_ratio: float = Field(..., ge=0, le=1)
    negative_ratio: float = Field(..., ge=0, le=1)
    neutral_ratio: float = Field(..., ge=0, le=1)
    overall_sentiment: Literal["매우긍정", "긍정", "보통", "부정", "매우부정"] = "보통"
    sentiment_summary: str = Field(..., description="한 줄 감성 요약")


# 3. 사용 맥락 분석
class UsagePattern(BaseModel):
    """빈도 상위 사용 패턴"""
    pattern: str = Field(..., description="구체적인 사용 패턴 설명")
    frequency: str = Field(..., description="빈도 (예: '전체 리뷰의 약 35%')")
    representative_quote: str = Field(default="", description="대표 리뷰 인용")


class UsageContextAnalysis(BaseModel):
    time_patterns: list[UsagePattern] = Field(
        default_factory=list, description="주요 사용 시간대/계절 패턴"
    )
    place_patterns: list[UsagePattern] = Field(
        default_factory=list, description="주요 사용 장소/환경"
    )
    trigger_patterns: list[UsagePattern] = Field(
        default_factory=list, description="구매 계기/사용 상황 (이사, 교체, 신혼 등)"
    )
    primary_user_type: str = Field(..., description="주 사용자 유형 요약")
    target_marketing_direction: str = Field(
        ..., description="맥락 기반 타겟 마케팅 방향 제안"
    )
    best_timing: str = Field(
        ..., description="최적 광고 노출 타이밍 (계절/상황/라이프이벤트)"
    )


# 4. VOC — 문제 키워드 & 불만 포인트
class VOCIssue(BaseModel):
    keyword: str = Field(..., description="핵심 불만 키워드")
    category: Literal["내구성", "AS", "소음", "설치", "가격", "기능", "앱/IoT", "디자인", "기타"]
    description: str = Field(..., description="불만 내용 상세")
    frequency: int = Field(..., description="언급 건수")
    severity: Literal["high", "medium", "low"]
    quotes: list[str] = Field(default_factory=list, max_length=2, description="대표 인용 최대 2개")
    improvement_suggestion: str = Field(default="", description="개선 제안")


class VOCAnalysis(BaseModel):
    top_issues: list[VOCIssue] = Field(..., description="Top 5 불만 이슈")
    recurring_complaint: str = Field(..., description="가장 반복되는 핵심 불만 한 줄 요약")
    critical_dealbreaker: str = Field(
        default="", description="구매 결정을 포기시킬 수 있는 치명적 약점"
    )


# 5. 마케팅 인사이트
class AdCopy(BaseModel):
    """광고 카피 제안"""
    headline: str = Field(..., description="헤드라인 (15자 이내)")
    sub_copy: str = Field(..., description="서브 카피 (30자 이내)")
    rationale: str = Field(..., description="카피 근거 — 어떤 리뷰 키워드 기반인지")
    channel: str = Field(..., description="추천 채널 (인스타/블로그/검색광고/배너 등)")
    copy_type: Literal["후킹형", "신뢰형", "공감형", "비교형", "혜택형"]


class MarketingInsightAnalysis(BaseModel):
    hook_copy_from_positive: list[AdCopy] = Field(
        ..., description="긍정 키워드 기반 메인 후킹 카피 2개"
    )
    trust_copy_from_negative: list[AdCopy] = Field(
        ..., description="부정 키워드 보완 전략 카피 2개"
    )
    opportunity_gap: str = Field(
        ..., description="리뷰에서 발견한 미충족 니즈 / 시장 기회"
    )
    recommended_content_theme: str = Field(
        ..., description="SNS/블로그 콘텐츠 추천 주제"
    )
    competitive_advantage_hint: str = Field(
        ..., description="대성쎌틱이 이 제품 대비 어필할 수 있는 포인트 힌트"
    )


# ─────────────────────────────────────────────
# 통합 분석 결과
# ─────────────────────────────────────────────

class FullCrawlAnalysis(BaseModel):
    """URL 크롤링 → 5단계 분석 통합 결과"""
    product_info: ProductInfo
    sentiment: SentimentKeywords
    usage_context: UsageContextAnalysis
    voc: VOCAnalysis
    marketing_insight: MarketingInsightAnalysis

    # 메타
    analyzed_at: str = ""
    analysis_model: str = "claude-sonnet-4-6"
    crawl_success: bool = True
    crawl_error: str = ""
