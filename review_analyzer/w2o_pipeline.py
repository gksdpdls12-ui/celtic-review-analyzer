"""
W2O (Weakness to Opportunity) 핵심 분석 파이프라인
Claude Sonnet 4.6 + Pydantic structured output 사용
4단계 치환 로직:
  ① 경쟁사 약점 포착 → ② 숨겨진 니즈 추출 → ③ 우리 강점 매칭 → ④ 공략 카피 생성
"""

from __future__ import annotations

import os
from datetime import date

import anthropic
from anthropic import APIError

from .loader import ReviewDataset, reviews_to_text
from .models import W2OAnalysis

# ─────────────────────────────────────────────
# 브랜드 컨텍스트 (프롬프트 캐싱 대상)
# ─────────────────────────────────────────────

BRAND_CONTEXT = """
## 대성쎌틱에너시스 브랜드 컨텍스트

**브랜드 미션**: "마음보일러 ON!" — 따뜻하고 신뢰할 수 있는 에너지 솔루션
**슬로건**: "대성이 내일을 we합니다"
**포지셔닝**: 프리미엄 콘덴싱 보일러 + 에너지 효율 + 10년 무상보증

**핵심 강점 (카피에 활용 가능한 근거)**:
- 대성 블랙 콘덴싱: 원통형 이중 열교환기, 최대 약 44만원 가스비 절약
- 10년 무상보증 정책 (업계 최장)
- 고효율 인증, 친환경 설계
- 각방온도시스템(IOT/무선) — 방별 온도 개별 제어
- 스마트홈 연동 (IOT 온도조절기)
- 38년 이상 국내 보일러 제조 전문기업

**금지 사항**:
- 경쟁사 브랜드명 직접 언급 금지
- 임의 가격/할인율 생성 금지
- 미확인 수치/스펙 사용 금지

**톤&보이스**: 신뢰감 있되 따뜻하고 생활 밀착형 ("~이에요", "~해요", "~드릴게요")
"""

ANALYSIS_SYSTEM_PROMPT = f"""당신은 대성쎌틱에너시스의 마케팅 전략가입니다.
경쟁사 리뷰를 분석하여 W2O(Weakness to Opportunity) 마케팅 인사이트를 생성합니다.

{BRAND_CONTEXT}

## W2O 분석 4단계 프로세스:
1. **약점 포착**: 경쟁사 리뷰에서 반복되는 불만·불편 사항 추출
2. **니즈 발굴**: 불만 이면의 숨겨진 욕구·기대 파악
3. **강점 매칭**: 대성쎌틱의 구체적 강점·기능·정책으로 니즈를 충족하는 방법 연결
4. **카피 생성**: 경쟁사 약점을 우리 강점으로 공략하는 마케팅 카피 작성

## 출력 요구사항:
- 모든 분석은 실제 리뷰 내용 기반 (추측 금지)
- 카피는 브랜드 톤&보이스 준수
- 수치/스펙은 확인된 것만 사용
- JSON 형식으로 정확하게 출력
"""


def _build_analysis_prompt(dataset: ReviewDataset, max_reviews: int = 80) -> str:
    review_text = reviews_to_text(dataset.reviews, max_reviews=max_reviews)

    return f"""## 분석 대상
- 경쟁사: {dataset.competitor}
- 제품 카테고리: {dataset.product_category}
- 총 리뷰 수: {dataset.total_count}개 (최대 {min(dataset.total_count, max_reviews)}개 분석)
- 분석 일자: {date.today().isoformat()}

## 경쟁사 리뷰 데이터
{review_text}

---

위 리뷰를 W2O 프레임워크로 분석하여 다음 항목을 채워주세요:

1. **sentiment** (감성 분석): 긍정/부정/중립 비율 및 핵심 키워드
2. **pain_points** (페인포인트 Top5): 카테고리, 설명, 빈도, 심각도, 대표 인용구
3. **hidden_needs** (숨겨진 니즈): 각 페인포인트의 이면에 있는 진짜 욕구
4. **strength_matches** (강점 매칭): 대성쎌틱 강점으로 니즈를 해결하는 방법
5. **attack_copies** (공략 카피 4개): 헤드라인+본문+채널 조합
6. **personas** (구매자 세그먼트 2~3개): 리뷰에서 추론되는 주요 고객 유형
7. **marketing_insight** (마케팅 인사이트): 긍정 훅 카피 + 부정 신뢰 전략
8. **executive_summary** (핵심 요약): 3문장 이내
9. **priority_action** (우선 실행 액션): 즉시 적용 가능한 마케팅 활동 1가지

반드시 JSON 형식으로 출력하세요. W2OAnalysis 스키마를 따릅니다.
"""


# ─────────────────────────────────────────────
# 메인 분석 함수
# ─────────────────────────────────────────────

def analyze_competitor_reviews(
    dataset: ReviewDataset,
    api_key: str | None = None,
) -> W2OAnalysis:
    """
    경쟁사 리뷰 데이터셋을 Claude로 W2O 분석하여 W2OAnalysis 반환.
    prompt caching: 시스템 프롬프트에 cache_control 적용.
    structured output: client.messages.parse() + W2OAnalysis 스키마.
    """
    client = anthropic.Anthropic(api_key=api_key or os.environ["ANTHROPIC_API_KEY"])

    prompt = _build_analysis_prompt(dataset)

    print(f"[w2o] {dataset.competitor} 리뷰 {dataset.total_count}개 분석 중...")

    try:
        response = client.messages.parse(
            model="claude-sonnet-4-6",
            max_tokens=8192,
            thinking={"type": "adaptive"},
            system=[
                {
                    "type": "text",
                    "text": ANALYSIS_SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[{"role": "user", "content": prompt}],
            output_type=W2OAnalysis,
        )
    except AttributeError:
        # anthropic SDK가 .parse()를 지원하지 않는 구버전 fallback
        response = _analyze_with_json_mode(client, prompt)
        return response

    result: W2OAnalysis = response.parsed

    # 메타 데이터 보정
    result.competitor = dataset.competitor
    result.product_category = dataset.product_category
    result.analyzed_review_count = min(dataset.total_count, 80)
    result.analysis_date = date.today().isoformat()

    cache_stats = getattr(response.usage, "cache_read_input_tokens", 0)
    print(f"[w2o] {dataset.competitor} 분석 완료 (캐시 히트: {cache_stats} tokens)")
    return result


def _analyze_with_json_mode(client: anthropic.Anthropic, prompt: str) -> W2OAnalysis:
    """SDK .parse() 미지원 시 JSON 텍스트 추출 fallback"""
    import json

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=8192,
        thinking={"type": "adaptive"},
        system=[
            {
                "type": "text",
                "text": ANALYSIS_SYSTEM_PROMPT + "\n\n반드시 유효한 JSON만 출력하세요. 마크다운 코드블록 없이 순수 JSON.",
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": prompt}],
    )

    text = ""
    for block in response.content:
        if hasattr(block, "text"):
            text = block.text
            break

    # JSON 블록 추출 (```json ... ``` 제거)
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)

    data = json.loads(text)
    return W2OAnalysis(**data)


# ─────────────────────────────────────────────
# 배치 분석 (복수 경쟁사)
# ─────────────────────────────────────────────

def analyze_all_competitors(
    datasets: dict[str, ReviewDataset],
    api_key: str | None = None,
) -> list[W2OAnalysis]:
    """여러 경쟁사 데이터셋을 순차적으로 분석"""
    results = []
    for competitor, dataset in datasets.items():
        try:
            analysis = analyze_competitor_reviews(dataset, api_key=api_key)
            results.append(analysis)
        except APIError as e:
            print(f"[w2o] {competitor} 분석 실패: {e}")
        except Exception as e:
            print(f"[w2o] {competitor} 예상치 못한 오류: {e}")
    return results


import re  # noqa: E402 (analyze_with_json_mode에서 사용)
