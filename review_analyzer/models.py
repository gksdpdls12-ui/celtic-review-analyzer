"""
W2O (Weakness to Opportunity) 분석을 위한 Pydantic 데이터 모델
경쟁사 리뷰 → 마케팅 인사이트 카드 변환 파이프라인
"""

from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, Field


# ─────────────────────────────────────────────
# 1단계: 원시 리뷰 데이터
# ─────────────────────────────────────────────

class RawReview(BaseModel):
    """로드된 개별 리뷰 항목"""
    competitor: str = Field(..., description="경쟁사 이름 (예: 경동나비엔, 귀뚜라미)")
    product: str = Field(default="", description="제품명 또는 모델명")
    rating: float | None = Field(default=None, description="별점 (1~5)")
    content: str = Field(..., description="리뷰 원문")
    source: str = Field(default="", description="출처 (naver_blog, coupang, etc.)")
    date: str = Field(default="", description="작성일 (YYYY-MM-DD 형식 권장)")


class ReviewDataset(BaseModel):
    """로드된 리뷰 데이터셋 전체"""
    competitor: str
    product_category: str = Field(default="보일러")
    total_count: int
    reviews: list[RawReview]


# ─────────────────────────────────────────────
# 2단계: W2O 분석 결과 구조체
# ─────────────────────────────────────────────

class PainPoint(BaseModel):
    """경쟁사 제품의 실제 불편/불만 사항"""
    category: str = Field(..., description="불만 카테고리 (예: 내구성, AS, 소음, 가격 등)")
    description: str = Field(..., description="구체적인 불만 내용 요약")
    frequency: int = Field(..., description="언급된 리뷰 수 (빈도)")
    severity: Literal["high", "medium", "low"] = Field(..., description="불만 심각도")
    representative_quotes: list[str] = Field(
        default_factory=list,
        description="대표적인 리뷰 원문 인용 (최대 3개)",
        max_length=3,
    )


class HiddenNeed(BaseModel):
    """페인포인트 이면의 숨겨진 니즈"""
    pain_point_category: str = Field(..., description="연결된 페인포인트 카테고리")
    hidden_need: str = Field(..., description="고객이 진짜 원하는 것 (욕구/기대)")
    insight: str = Field(..., description="마케터의 해석 — 왜 이 니즈가 충족되지 않는가")


class StrengthMatch(BaseModel):
    """대성쎌틱에너시스의 강점과 숨겨진 니즈의 매칭"""
    hidden_need: str = Field(..., description="매칭된 숨겨진 니즈")
    our_strength: str = Field(..., description="대성쎌틱의 구체적인 강점/기능/정책")
    match_score: int = Field(..., ge=1, le=10, description="매칭 강도 점수 (1~10)")
    evidence: str = Field(..., description="강점의 근거 (인증, 수치, 정책 등)")


class AttackCopy(BaseModel):
    """공략 마케팅 카피 (W2O 최종 산출물)"""
    target_pain: str = Field(..., description="공략하는 경쟁사 약점")
    our_strength: str = Field(..., description="내세우는 우리 강점")
    headline: str = Field(..., description="헤드라인 카피 (15자 이내 권장)")
    body_copy: str = Field(..., description="본문 카피 (50자 이내)")
    hook_angle: str = Field(..., description="소구 각도 (공감형/비교형/증명형/감성형 중 택1)")
    channel: str = Field(..., description="추천 채널 (블로그/인스타/이벤트배너/상세페이지 등)")


# ─────────────────────────────────────────────
# 3단계: 감성 분석
# ─────────────────────────────────────────────

class SentimentBreakdown(BaseModel):
    """리뷰 감성 분포"""
    positive_ratio: float = Field(..., ge=0, le=1, description="긍정 비율")
    negative_ratio: float = Field(..., ge=0, le=1, description="부정 비율")
    neutral_ratio: float = Field(..., ge=0, le=1, description="중립 비율")
    top_positive_keywords: list[str] = Field(
        default_factory=list,
        description="긍정 리뷰 핵심 키워드 Top5",
    )
    top_negative_keywords: list[str] = Field(
        default_factory=list,
        description="부정 리뷰 핵심 키워드 Top5",
    )


class PersonaSegment(BaseModel):
    """주요 구매자 페르소나 세그먼트"""
    segment_name: str = Field(..., description="세그먼트 이름 (예: 신혼부부, 교체수요 등)")
    characteristics: str = Field(..., description="세그먼트 특징")
    primary_concern: str = Field(..., description="주요 관심사/걱정거리")
    proportion: str = Field(..., description="전체 리뷰 중 비중 (예: 약 30%)")


# ─────────────────────────────────────────────
# 4단계: 마케팅 인사이트 통합
# ─────────────────────────────────────────────

class MarketingInsight(BaseModel):
    """긍정 리뷰 기반 훅 카피 + 부정 리뷰 기반 신뢰 전략"""
    positive_hook: str = Field(..., description="긍정 키워드 기반 훅 카피")
    trust_strategy: str = Field(..., description="부정 리뷰 역이용 신뢰 구축 전략")
    content_direction: str = Field(..., description="추천 콘텐츠 방향 (블로그/SNS/이벤트)")
    urgency_trigger: str = Field(default="", description="긴박감/구매 트리거 포인트")


# ─────────────────────────────────────────────
# 최종 W2O 분석 결과 (전체 통합)
# ─────────────────────────────────────────────

class W2OAnalysis(BaseModel):
    """경쟁사 1개에 대한 완전한 W2O 분석 결과"""
    competitor: str
    product_category: str = Field(default="보일러")
    analyzed_review_count: int
    analysis_date: str

    # 5단계 분석
    sentiment: SentimentBreakdown
    pain_points: list[PainPoint] = Field(..., description="Top 5 페인포인트")
    hidden_needs: list[HiddenNeed]
    strength_matches: list[StrengthMatch]
    attack_copies: list[AttackCopy] = Field(..., description="공략 카피 3~5개")
    personas: list[PersonaSegment]
    marketing_insight: MarketingInsight

    # 전략 요약
    executive_summary: str = Field(..., description="3문장 이내 핵심 전략 요약")
    priority_action: str = Field(..., description="가장 즉각적으로 실행할 마케팅 액션")


class W2OReport(BaseModel):
    """전체 분석 보고서 (복수 경쟁사)"""
    report_title: str
    generated_at: str
    our_brand: str = "대성쎌틱에너시스"
    analyses: list[W2OAnalysis]
    cross_competitor_insight: str = Field(
        default="",
        description="경쟁사 전반에 걸친 공통 기회 포인트",
    )
