"""
W2O 분석 결과를 마케팅 인사이트 카드 데이터로 가공
Pencil MCP 디자인 레이아웃 및 PPT 슬라이드 입력용 구조체 생성
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from .models import AttackCopy, PainPoint, StrengthMatch, W2OAnalysis, W2OReport


# ─────────────────────────────────────────────
# 인사이트 카드 데이터 구조체
# ─────────────────────────────────────────────

@dataclass
class InsightCard:
    """W2O 핵심 카드 1장 — 강점 / 부정 / 공략카피 3단 구조"""
    card_number: int
    competitor: str

    # 경쟁사 약점
    pain_category: str
    pain_description: str
    pain_severity: str
    representative_quote: str

    # 숨겨진 니즈
    hidden_need: str

    # 우리 강점
    our_strength: str
    strength_evidence: str
    match_score: int

    # 공략 카피
    headline: str
    body_copy: str
    hook_angle: str
    recommended_channel: str

    # 메타
    priority: Literal["high", "medium", "low"] = "medium"
    tag: str = ""


@dataclass
class CompetitorInsightDeck:
    """경쟁사 1개에 대한 인사이트 카드 덱"""
    competitor: str
    executive_summary: str
    priority_action: str
    positive_hook: str
    trust_strategy: str
    cards: list[InsightCard] = field(default_factory=list)
    persona_labels: list[str] = field(default_factory=list)

    # 감성 요약
    positive_ratio: float = 0.0
    negative_ratio: float = 0.0
    top_positive_kw: list[str] = field(default_factory=list)
    top_negative_kw: list[str] = field(default_factory=list)


@dataclass
class FullInsightReport:
    """전체 보고서 — 복수 경쟁사 덱 모음"""
    report_title: str
    generated_at: str
    decks: list[CompetitorInsightDeck] = field(default_factory=list)
    cross_insight: str = ""


# ─────────────────────────────────────────────
# 빌더 함수
# ─────────────────────────────────────────────

def _severity_to_priority(severity: str) -> Literal["high", "medium", "low"]:
    mapping = {"high": "high", "medium": "medium", "low": "low"}
    return mapping.get(severity.lower(), "medium")  # type: ignore[return-value]


def build_insight_cards(analysis: W2OAnalysis) -> list[InsightCard]:
    """W2OAnalysis → InsightCard 목록 변환"""
    cards: list[InsightCard] = []

    # pain_points × attack_copies 매칭 (순서 기반)
    pain_points: list[PainPoint] = analysis.pain_points
    strength_matches: list[StrengthMatch] = analysis.strength_matches
    attack_copies: list[AttackCopy] = analysis.attack_copies

    for i, copy in enumerate(attack_copies):
        # 관련 페인포인트 찾기
        pain = next(
            (p for p in pain_points if p.category in copy.target_pain or copy.target_pain in p.category),
            pain_points[min(i, len(pain_points) - 1)] if pain_points else None,
        )
        # 관련 강점 찾기
        strength = next(
            (s for s in strength_matches if copy.our_strength in s.our_strength or s.our_strength in copy.our_strength),
            strength_matches[min(i, len(strength_matches) - 1)] if strength_matches else None,
        )

        # 숨겨진 니즈
        hidden_need_obj = next(
            (n for n in analysis.hidden_needs if pain and n.pain_point_category == pain.category),
            None,
        )

        card = InsightCard(
            card_number=i + 1,
            competitor=analysis.competitor,
            # 약점
            pain_category=pain.category if pain else copy.target_pain,
            pain_description=pain.description if pain else copy.target_pain,
            pain_severity=pain.severity if pain else "medium",
            representative_quote=pain.representative_quotes[0] if (pain and pain.representative_quotes) else "",
            # 니즈
            hidden_need=hidden_need_obj.hidden_need if hidden_need_obj else copy.target_pain,
            # 강점
            our_strength=strength.our_strength if strength else copy.our_strength,
            strength_evidence=strength.evidence if strength else "",
            match_score=strength.match_score if strength else 5,
            # 카피
            headline=copy.headline,
            body_copy=copy.body_copy,
            hook_angle=copy.hook_angle,
            recommended_channel=copy.channel,
            # 메타
            priority=_severity_to_priority(pain.severity if pain else "medium"),
            tag=copy.hook_angle,
        )
        cards.append(card)

    return cards


def build_competitor_deck(analysis: W2OAnalysis) -> CompetitorInsightDeck:
    """W2OAnalysis → CompetitorInsightDeck"""
    cards = build_insight_cards(analysis)

    persona_labels = [p.segment_name for p in analysis.personas]

    return CompetitorInsightDeck(
        competitor=analysis.competitor,
        executive_summary=analysis.executive_summary,
        priority_action=analysis.priority_action,
        positive_hook=analysis.marketing_insight.positive_hook,
        trust_strategy=analysis.marketing_insight.trust_strategy,
        cards=cards,
        persona_labels=persona_labels,
        positive_ratio=analysis.sentiment.positive_ratio,
        negative_ratio=analysis.sentiment.negative_ratio,
        top_positive_kw=analysis.sentiment.top_positive_keywords,
        top_negative_kw=analysis.sentiment.top_negative_keywords,
    )


def build_full_report(w2o_report: W2OReport) -> FullInsightReport:
    """W2OReport → FullInsightReport"""
    decks = [build_competitor_deck(a) for a in w2o_report.analyses]
    return FullInsightReport(
        report_title=w2o_report.report_title,
        generated_at=w2o_report.generated_at,
        decks=decks,
        cross_insight=w2o_report.cross_competitor_insight,
    )


# ─────────────────────────────────────────────
# Pencil MCP 레이아웃 힌트 생성
# ─────────────────────────────────────────────

def generate_pencil_layout_hints(deck: CompetitorInsightDeck) -> list[dict]:
    """
    Pencil MCP batch_design 작업에 전달할 카드 레이아웃 힌트 목록 생성.
    각 카드는 3-column 구조: 약점(적) | 숨겨진 니즈(중간) | 공략카피(초록)
    실제 batch_design 호출은 Claude Code 인터랙티브 세션에서 수행.
    """
    hints = []
    for card in deck.cards:
        hints.append({
            "card_number": card.card_number,
            "competitor": card.competitor,
            "priority": card.priority,
            "columns": {
                "weakness": {
                    "label": "경쟁사 약점",
                    "category": card.pain_category,
                    "description": card.pain_description,
                    "quote": card.representative_quote,
                    "severity": card.pain_severity,
                    "bg_color": "#FFE5E5",
                    "accent_color": "#C8102E",
                },
                "need": {
                    "label": "숨겨진 니즈",
                    "content": card.hidden_need,
                    "bg_color": "#FFF8E1",
                    "accent_color": "#B8975A",
                },
                "attack_copy": {
                    "label": "공략 카피",
                    "headline": card.headline,
                    "body": card.body_copy,
                    "channel": card.recommended_channel,
                    "angle": card.hook_angle,
                    "bg_color": "#E8F5E9",
                    "accent_color": "#1A1A1A",
                },
            },
        })
    return hints


def cards_to_ppt_slides(deck: CompetitorInsightDeck) -> list[dict]:
    """
    /pptx 스킬에 전달할 슬라이드 데이터 목록 생성.
    슬라이드 구조: 표지 → 감성 요약 → 카드별 슬라이드 → 우선 액션
    """
    slides = []

    # 표지 슬라이드
    slides.append({
        "type": "cover",
        "title": f"{deck.competitor} 리뷰 W2O 분석",
        "subtitle": "경쟁사 약점 → 마케팅 기회",
        "generated_at": "",
    })

    # 감성 분석 요약
    slides.append({
        "type": "sentiment_summary",
        "title": "고객 감성 분포",
        "positive": f"{deck.positive_ratio:.0%}",
        "negative": f"{deck.negative_ratio:.0%}",
        "positive_keywords": deck.top_positive_kw,
        "negative_keywords": deck.top_negative_kw,
        "personas": deck.persona_labels,
    })

    # W2O 인사이트 카드 슬라이드
    for card in deck.cards:
        slides.append({
            "type": "w2o_card",
            "title": f"공략 카드 #{card.card_number}: {card.pain_category}",
            "weakness": card.pain_description,
            "quote": card.representative_quote,
            "hidden_need": card.hidden_need,
            "our_strength": card.our_strength,
            "evidence": card.strength_evidence,
            "headline": card.headline,
            "body_copy": card.body_copy,
            "channel": card.recommended_channel,
            "angle": card.hook_angle,
        })

    # 마케팅 인사이트 슬라이드
    slides.append({
        "type": "marketing_insight",
        "title": "마케팅 인사이트",
        "positive_hook": deck.positive_hook,
        "trust_strategy": deck.trust_strategy,
    })

    # 우선 액션 슬라이드
    slides.append({
        "type": "action",
        "title": "핵심 전략 요약 & 우선 실행 액션",
        "summary": deck.executive_summary,
        "priority_action": deck.priority_action,
    })

    return slides
