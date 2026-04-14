"""
Claude Sonnet 4.6 기반 5단계 리뷰 분석
- 시스템 프롬프트 캐싱 (ephemeral)
- 별점 분포 유지 샘플링 + 텍스트 절삭으로 토큰 절약
- thinking budget 제한
"""

from __future__ import annotations

import json
import math
import os
import re
from collections import defaultdict
from datetime import date

import anthropic

from .models import (
    FullAnalysis,
    MarketingInsightAnalysis,
    ProductInfo,
    Review,
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
- IOT 각방온도시스템 - 방별 개별 온도 제어
- 38년 이상 국내 제조 전문

## 출력 형식
반드시 지정된 JSON 스키마를 완벽하게 채워서 출력합니다.
"""

_MAX_REVIEW_CHARS = 120     # 리뷰 1건당 최대 글자수
_SAMPLE_SIZE = 70           # Claude에 넘길 최대 리뷰 수
_THINKING_BUDGET = int(os.environ.get("THINKING_BUDGET", "1500"))


# ─────────────────────────────────────────────
# 샘플링 & 프롬프트 빌드
# ─────────────────────────────────────────────

def _sample(reviews: list[Review], n: int = _SAMPLE_SIZE) -> list[Review]:
    """별점 분포 유지 + 도움됨 순 샘플링"""
    if len(reviews) <= n:
        return reviews

    buckets: dict[int, list[Review]] = defaultdict(list)
    for r in reviews:
        key = round(r.rating) if r.rating is not None else 0
        buckets[key].append(r)

    result: list[Review] = []
    for key in sorted(buckets, reverse=True):
        bucket = sorted(buckets[key], key=lambda r: r.helpful_count or 0, reverse=True)
        quota = max(1, math.ceil(len(bucket) / len(reviews) * n))
        result.extend(bucket[:quota])

    return result[:n]


def _to_prompt_block(reviews: list[Review]) -> str:
    sample = _sample(reviews)
    lines = []
    for i, r in enumerate(sample, 1):
        parts = []
        if r.rating is not None:
            parts.append(f"★{r.rating:.1f}")
        if r.date:
            parts.append(r.date[:10])
        if r.helpful_count:
            parts.append(f"도움됨:{r.helpful_count}")
        meta = " | ".join(parts)
        content = r.content[:_MAX_REVIEW_CHARS] + "…" if len(r.content) > _MAX_REVIEW_CHARS else r.content
        lines.append(f"[{i}] {meta}")
        lines.append(content)
        lines.append("")
    return "\n".join(lines)


def _build_prompt(info: ProductInfo, reviews: list[Review]) -> str:
    sample_count = len(_sample(reviews))
    platform_label = {
        "naver_smartstore": "네이버 스마트스토어",
        "coupang": "쿠팡",
    }.get(info.platform, info.platform or "CSV")

    stars = f"{info.rating:.1f}점" if info.rating else "정보없음"

    return f"""## 분석 대상 제품
- 플랫폼: {platform_label}
- 제품명: {info.product_name or '정보없음'}
- 평균 별점: {stars} (전체 {info.total_reviews}개 중 {sample_count}개 분석)
- 분석일: {date.today().isoformat()}

## 리뷰 데이터 ({sample_count}개)
{_to_prompt_block(reviews)}

---
위 리뷰를 5단계로 분석하여 다음 JSON 스키마를 완벽하게 채워주세요.

```json
{{
  "sentiment": {{
    "positive": ["키워드1", "키워드2"],
    "negative": ["키워드1", "키워드2"],
    "neutral": ["키워드1"],
    "positive_ratio": 0.0,
    "negative_ratio": 0.0,
    "neutral_ratio": 0.0,
    "overall_sentiment": "매우긍정|긍정|보통|부정|매우부정",
    "sentiment_summary": "한 줄 요약"
  }},
  "usage_context": {{
    "time_patterns": [{{"pattern":"", "frequency":"", "representative_quote":""}}],
    "place_patterns": [{{"pattern":"", "frequency":"", "representative_quote":""}}],
    "trigger_patterns": [{{"pattern":"", "frequency":"", "representative_quote":""}}],
    "primary_user_type": "",
    "target_marketing_direction": "",
    "best_timing": ""
  }},
  "voc": {{
    "top_issues": [{{
      "keyword": "",
      "category": "내구성|AS|소음|설치|가격|기능|앱/IoT|디자인|기타",
      "description": "",
      "frequency": 0,
      "severity": "high|medium|low",
      "quotes": ["인용1"],
      "improvement_suggestion": ""
    }}],
    "recurring_complaint": "",
    "critical_dealbreaker": ""
  }},
  "marketing_insight": {{
    "hook_copy_from_positive": [{{
      "headline": "15자 이내",
      "sub_copy": "30자 이내",
      "rationale": "",
      "channel": "",
      "copy_type": "후킹형|신뢰형|공감형|비교형|혜택형"
    }}],
    "trust_copy_from_negative": [{{
      "headline": "",
      "sub_copy": "",
      "rationale": "",
      "channel": "",
      "copy_type": "신뢰형|공감형|혜택형"
    }}],
    "opportunity_gap": "",
    "recommended_content_theme": "",
    "competitive_advantage_hint": ""
  }}
}}
```

JSON만 출력하세요. 마크다운 코드블록 없이 순수 JSON."""


# ─────────────────────────────────────────────
# Claude API 호출
# ─────────────────────────────────────────────

def analyze(
    product_info: ProductInfo,
    reviews: list[Review],
    api_key: str | None = None,
) -> FullAnalysis:
    """5단계 분석 실행 -> FullAnalysis 반환"""
    client = anthropic.Anthropic(api_key=api_key or os.environ["ANTHROPIC_API_KEY"])

    sample_count = len(_sample(reviews))
    prompt = _build_prompt(product_info, reviews)
    print(f"[analyzer] Claude 분석 중 (전체 {len(reviews)}개 -> 샘플 {sample_count}개, thinking<={_THINKING_BUDGET})...")

    try:
        result = _call_parse(client, prompt, product_info)
    except Exception as e:
        print(f"[analyzer] parse() 실패, JSON fallback: {e}")
        result = _call_json(client, prompt, product_info)

    result.analyzed_at = date.today().isoformat()
    result.product_info.analyzed_count = sample_count
    print("[analyzer] 분석 완료")
    return result


def _call_parse(client: anthropic.Anthropic, prompt: str, info: ProductInfo) -> FullAnalysis:
    response = client.messages.parse(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        thinking={"type": "enabled", "budget_tokens": _THINKING_BUDGET},
        system=[{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": prompt}],
        output_type=FullAnalysis,
    )
    result: FullAnalysis = response.parsed
    result.product_info = info
    _log_usage(response.usage)
    return result


def _call_json(client: anthropic.Anthropic, prompt: str, info: ProductInfo) -> FullAnalysis:
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        thinking={"type": "enabled", "budget_tokens": _THINKING_BUDGET},
        system=[{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": prompt}],
    )
    _log_usage(response.usage)

    text = ""
    for block in response.content:
        if hasattr(block, "text"):
            text = block.text
            break

    text = re.sub(r"^```(?:json)?\s*", "", text.strip())
    text = re.sub(r"\s*```$", "", text)
    data = json.loads(text)

    return FullAnalysis(
        product_info=info,
        sentiment=SentimentKeywords(**data["sentiment"]),
        usage_context=UsageContextAnalysis(**data["usage_context"]),
        voc=VOCAnalysis(**data["voc"]),
        marketing_insight=MarketingInsightAnalysis(**data["marketing_insight"]),
    )


def _log_usage(usage) -> None:
    hit   = getattr(usage, "cache_read_input_tokens", 0) or 0
    write = getattr(usage, "cache_creation_input_tokens", 0) or 0
    out   = getattr(usage, "output_tokens", 0) or 0
    print(f"[analyzer] 캐시히트:{hit} | 캐시쓰기:{write} | 출력:{out} tokens")
