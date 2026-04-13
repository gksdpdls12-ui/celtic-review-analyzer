"""
Claude Sonnet 4.6 기반 5단계 리뷰 분석
1. 제품 정보 보완
2. 감성 분석 (긍정/부정/중립 키워드)
3. 사용 맥락 분석 (시간대/장소/계기 + 타겟 마케팅)
4. VOC (문제 키워드, 불만 포인트)
5. 마케팅 인사이트 (광고 카피 제안)
"""

from __future__ import annotations

import os
from datetime import date

import anthropic

from .models import (
    CrawledReview,
    FullCrawlAnalysis,
    MarketingInsightAnalysis,
    ProductInfo,
    SentimentKeywords,
    UsageContextAnalysis,
    VOCAnalysis,
)

# ─────────────────────────────────────────────
# 시스템 프롬프트 (캐싱 대상)
# ─────────────────────────────────────────────

SYSTEM_PROMPT = """당신은 대성쎌틱에너시스 마케팅팀의 시니어 리서치 애널리스트입니다.
제품 리뷰 데이터를 분석하여 실행 가능한 마케팅 인사이트를 도출합니다.

## 분석 원칙
- 실제 리뷰 텍스트에서만 근거를 찾습니다 (추측 금지)
- 빈도와 강도(severity)를 구분하여 우선순위를 매깁니다
- 마케팅 카피는 즉시 사용 가능한 수준으로 완성합니다
- 대성쎌틱에너시스 관점에서 시사점을 도출합니다

## 대성쎌틱에너시스 핵심 강점 (비교 인사이트 생성 시 참고)
- 대성 블랙 콘덴싱: 원통형 이중 열교환기, 최대 약 44만원 가스비 절약
- 10년 무상보증 (업계 최장 수준)
- IOT 각방온도시스템 — 방별 개별 온도 제어
- 38년 이상 국내 제조 전문

## 출력 형식
반드시 지정된 JSON 스키마를 완벽하게 채워서 출력합니다.
"""


def _reviews_to_prompt_block(reviews: list[CrawledReview], max_count: int = 100) -> str:
    """리뷰 목록을 Claude 프롬프트 텍스트로 변환"""
    sample = reviews[:max_count]
    lines = []
    for i, r in enumerate(sample, 1):
        rating_str = f"★{r.rating:.1f}" if r.rating is not None else ""
        date_str = r.date[:10] if r.date else ""
        helpful_str = f"도움됨:{r.helpful_count}" if r.helpful_count else ""
        meta = " | ".join(filter(None, [rating_str, date_str, helpful_str]))
        lines.append(f"[{i}] {meta}")
        lines.append(r.content)
        lines.append("")
    return "\n".join(lines)


def _build_prompt(
    product_info: ProductInfo,
    reviews: list[CrawledReview],
) -> str:
    review_block = _reviews_to_prompt_block(reviews)
    stars = f"{product_info.rating:.1f}점" if product_info.rating else "정보없음"
    price = product_info.price_display or "정보없음"

    return f"""## 분석 대상 제품
- 플랫폼: {product_info.platform}
- 브랜드: {product_info.brand or '정보없음'}
- 제품명: {product_info.product_name or '정보없음'}
- 카테고리: {product_info.category or '정보없음'}
- 가격: {price}
- 평균 별점: {stars} (총 리뷰 {product_info.total_reviews}개 중 {len(reviews)}개 분석)
- 분석일: {date.today().isoformat()}

## 리뷰 데이터 ({len(reviews)}개)
{review_block}

---
위 리뷰를 5단계로 분석하여 다음 JSON 스키마를 완벽하게 채워주세요.

```json
{{
  "sentiment": {{
    "positive": ["키워드1", "키워드2", ...],       // 긍정 Top10
    "negative": ["키워드1", "키워드2", ...],       // 부정 Top10
    "neutral": ["키워드1", ...],                   // 중립/정보 Top5
    "positive_ratio": 0.0~1.0,
    "negative_ratio": 0.0~1.0,
    "neutral_ratio": 0.0~1.0,
    "overall_sentiment": "매우긍정|긍정|보통|부정|매우부정",
    "sentiment_summary": "한 줄 요약"
  }},
  "usage_context": {{
    "time_patterns": [{{"pattern":"", "frequency":"", "representative_quote":""}}],
    "place_patterns": [{{"pattern":"", "frequency":"", "representative_quote":""}}],
    "trigger_patterns": [{{"pattern":"이사/교체/신혼 등", "frequency":"", "representative_quote":""}}],
    "primary_user_type": "주 사용자 유형 한 줄",
    "target_marketing_direction": "맥락 기반 타겟 마케팅 방향",
    "best_timing": "최적 광고 노출 타이밍"
  }},
  "voc": {{
    "top_issues": [
      {{
        "keyword": "핵심 불만 키워드",
        "category": "내구성|AS|소음|설치|가격|기능|앱/IoT|디자인|기타",
        "description": "불만 내용 상세",
        "frequency": 숫자,
        "severity": "high|medium|low",
        "quotes": ["인용1", "인용2"],
        "improvement_suggestion": "개선 제안"
      }}
    ],
    "recurring_complaint": "가장 반복되는 핵심 불만 한 줄",
    "critical_dealbreaker": "치명적 약점 (없으면 빈 문자열)"
  }},
  "marketing_insight": {{
    "hook_copy_from_positive": [
      {{
        "headline": "헤드라인 15자 이내",
        "sub_copy": "서브카피 30자 이내",
        "rationale": "근거 키워드",
        "channel": "추천채널",
        "copy_type": "후킹형|신뢰형|공감형|비교형|혜택형"
      }}
    ],
    "trust_copy_from_negative": [
      {{
        "headline": "헤드라인",
        "sub_copy": "서브카피",
        "rationale": "이 불만을 어떻게 반전시켰는지",
        "channel": "추천채널",
        "copy_type": "신뢰형|공감형|혜택형"
      }}
    ],
    "opportunity_gap": "리뷰에서 발견한 미충족 니즈",
    "recommended_content_theme": "SNS/블로그 추천 콘텐츠 주제",
    "competitive_advantage_hint": "대성쎌틱이 어필할 수 있는 포인트"
  }}
}}
```

JSON만 출력하세요. 마크다운 코드블록 없이 순수 JSON."""


# ─────────────────────────────────────────────
# 메인 분석 함수
# ─────────────────────────────────────────────

def analyze(
    product_info: ProductInfo,
    reviews: list[CrawledReview],
    api_key: str | None = None,
) -> FullCrawlAnalysis:
    """5단계 분석 실행 → FullCrawlAnalysis 반환"""
    client = anthropic.Anthropic(api_key=api_key or os.environ["ANTHROPIC_API_KEY"])

    prompt = _build_prompt(product_info, reviews)
    print(f"[analyzer] Claude 분석 중 (리뷰 {len(reviews)}개)...")

    # structured output 시도
    try:
        result = _analyze_with_parse(client, prompt, product_info)
    except Exception as e:
        print(f"[analyzer] parse() 실패, JSON fallback: {e}")
        result = _analyze_with_json(client, prompt, product_info)

    result.analyzed_at = date.today().isoformat()
    print("[analyzer] 분석 완료")
    return result


def _analyze_with_parse(
    client: anthropic.Anthropic,
    prompt: str,
    product_info: ProductInfo,
) -> FullCrawlAnalysis:
    """client.messages.parse() + Pydantic 검증"""
    response = client.messages.parse(
        model="claude-sonnet-4-6",
        max_tokens=8192,
        thinking={"type": "adaptive"},
        system=[{
            "type": "text",
            "text": SYSTEM_PROMPT,
            "cache_control": {"type": "ephemeral"},
        }],
        messages=[{"role": "user", "content": prompt}],
        output_type=FullCrawlAnalysis,
    )
    result: FullCrawlAnalysis = response.parsed
    result.product_info = product_info
    cache_hit = getattr(response.usage, "cache_read_input_tokens", 0)
    print(f"[analyzer] 캐시 히트: {cache_hit} tokens")
    return result


def _analyze_with_json(
    client: anthropic.Anthropic,
    prompt: str,
    product_info: ProductInfo,
) -> FullCrawlAnalysis:
    """JSON 텍스트 추출 fallback"""
    import json
    import re

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=8192,
        thinking={"type": "adaptive"},
        system=[{
            "type": "text",
            "text": SYSTEM_PROMPT,
            "cache_control": {"type": "ephemeral"},
        }],
        messages=[{"role": "user", "content": prompt}],
    )

    text = ""
    for block in response.content:
        if hasattr(block, "text"):
            text = block.text
            break

    text = text.strip()
    # 마크다운 코드블록 제거
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)

    data = json.loads(text)

    return FullCrawlAnalysis(
        product_info=product_info,
        sentiment=SentimentKeywords(**data["sentiment"]),
        usage_context=UsageContextAnalysis(**data["usage_context"]),
        voc=VOCAnalysis(**data["voc"]),
        marketing_insight=MarketingInsightAnalysis(**data["marketing_insight"]),
    )
