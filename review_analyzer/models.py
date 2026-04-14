"""
리뷰 분석기 데이터 모델
Excel/CSV -> Review[] -> FullAnalysis (5단계)
"""

from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, Field


# ─────────────────────────────────────────────
# 입력 데이터
# ─────────────────────────────────────────────

class ProductInfo(BaseModel):
    """제품 기본 정보 (Excel에서 추출)"""
    product_name: str = ""
    brand: str = ""
    platform: str = ""          # "naver_smartstore" | "coupang" | "csv"
    category: str = ""
    price_display: str = ""
    rating: float | None = None
    total_reviews: int = 0
    analyzed_count: int = 0


class Review(BaseModel):
    """개별 리뷰"""
    product_name: str = ""
    rating: float | None = None
    content: str
    date: str = ""
    helpful_count: int = 0
    is_photo_review: bool = False
    purchase_option: str = ""


# ─────────────────────────────────────────────
# 5단계 분석 결과
# ─────────────────────────────────────────────

class SentimentKeywords(BaseModel):
    positive: list[str] = Field(default_factory=list, description="긍정 키워드 Top10")
    negative: list[str] = Field(default_factory=list, description="부정 키워드 Top10")
    neutral: list[str] = Field(default_factory=list, description="중립 키워드 Top5")
    positive_ratio: float = Field(..., ge=0, le=1)
    negative_ratio: float = Field(..., ge=0, le=1)
    neutral_ratio: float = Field(..., ge=0, le=1)
    overall_sentiment: Literal["매우긍정", "긍정", "보통", "부정", "매우부정"] = "보통"
    sentiment_summary: str = ""


class UsagePattern(BaseModel):
    pattern: str
    frequency: str
    representative_quote: str = ""


class UsageContextAnalysis(BaseModel):
    time_patterns: list[UsagePattern] = Field(default_factory=list)
    place_patterns: list[UsagePattern] = Field(default_factory=list)
    trigger_patterns: list[UsagePattern] = Field(default_factory=list)
    primary_user_type: str = ""
    target_marketing_direction: str = ""
    best_timing: str = ""


class VOCIssue(BaseModel):
    keyword: str
    category: Literal["내구성", "AS", "소음", "설치", "가격", "기능", "앱/IoT", "디자인", "기타"]
    description: str
    frequency: int
    severity: Literal["high", "medium", "low"]
    quotes: list[str] = Field(default_factory=list)
    improvement_suggestion: str = ""


class VOCAnalysis(BaseModel):
    top_issues: list[VOCIssue]
    recurring_complaint: str
    critical_dealbreaker: str = ""


class AdCopy(BaseModel):
    headline: str
    sub_copy: str
    rationale: str
    channel: str
    copy_type: Literal["후킹형", "신뢰형", "공감형", "비교형", "혜택형"]


class MarketingInsightAnalysis(BaseModel):
    hook_copy_from_positive: list[AdCopy]
    trust_copy_from_negative: list[AdCopy]
    opportunity_gap: str
    recommended_content_theme: str
    competitive_advantage_hint: str


class FullAnalysis(BaseModel):
    """5단계 분석 통합 결과"""
    product_info: ProductInfo
    sentiment: SentimentKeywords
    usage_context: UsageContextAnalysis
    voc: VOCAnalysis
    marketing_insight: MarketingInsightAnalysis
    analyzed_at: str = ""
    analysis_model: str = "claude-sonnet-4-6"
