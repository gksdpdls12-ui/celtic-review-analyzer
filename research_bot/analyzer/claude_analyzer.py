"""
Claude API — 리뷰 데이터 분석 및 인사이트 추출
"""
import anthropic
import json


SYSTEM_PROMPT = """당신은 대성쎌틱에너시스 마케팅 리서치 전문 분석가입니다.
수집된 소비자 리뷰, 블로그 포스트, 뉴스 데이터를 분석하여
마케팅 팀이 즉시 활용할 수 있는 인사이트를 제공합니다.

분석 원칙:
- 실제 데이터에 근거한 사실 기반 분석
- 긍정/부정/중립 감성 정확히 분류
- 경쟁사 언급 시 직접 비교 표현 사용 금지
- 소비자 언어 그대로 인용하여 설득력 강화
- 마케팅 액션으로 연결 가능한 구체적 제안"""


def analyze_reviews(
    client: anthropic.Anthropic,
    brand_name: str,
    reviews: list[dict],
    competitor_data: dict = None,
) -> str:
    """
    블로그/유튜브 리뷰를 Claude로 분석합니다.

    Returns: 마크다운 형식의 분석 리포트
    """
    # 리뷰 텍스트 준비 (최대 50개)
    review_texts = []
    for i, r in enumerate(reviews[:50], 1):
        source = r.get("source", "")
        if source == "naver_blog":
            review_texts.append(
                f"{i}. [{r.get('date', '')}] {r.get('title', '')} — {r.get('description', '')}"
            )
        elif source == "youtube":
            for c in r.get("comments", [])[:5]:
                review_texts.append(f"  댓글: {c.get('text', '')}")

    reviews_str = "\n".join(review_texts) if review_texts else "수집된 리뷰 없음"

    # 경쟁사 데이터 준비
    comp_str = ""
    if competitor_data:
        comp_lines = []
        for name, data in competitor_data.items():
            comp_lines.append(f"- {name}: 블로그 {data.get('blog_count', 0)}건, 최근 언급 트렌드 {data.get('trend', '불명')}")
        comp_str = "\n".join(comp_lines)

    prompt = f"""다음은 {brand_name}에 대해 수집된 소비자 리뷰 및 블로그 포스트입니다.

## 수집 데이터 ({len(reviews)}건)
{reviews_str}

{"## 경쟁사 언급 현황" + chr(10) + comp_str if comp_str else ""}

위 데이터를 기반으로 아래 형식으로 마케팅 리서치 리포트를 작성하세요:

## 1. 핵심 인사이트 (3~5가지 불릿)
## 2. 감성 분석
- 긍정 반응 주요 키워드 및 대표 인용구
- 부정/개선 요구 사항 및 대표 인용구
- 감성 비율 추정 (긍정/중립/부정 %)
## 3. 소비자 주요 관심사 TOP 5
## 4. 경쟁 환경 파악 (직접 비교 표현 없이)
## 5. 마케팅 액션 제안 (즉시 적용 가능한 3가지)
## 6. 콘텐츠 소재 아이디어 (블로그/SNS용 3가지)"""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        system=[
            {
                "type": "text",
                "text": SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},  # 시스템 프롬프트 캐싱
            }
        ],
        messages=[{"role": "user", "content": prompt}],
    )

    return response.content[0].text


def analyze_trends(
    client: anthropic.Anthropic,
    brand_name: str,
    trend_data: list[dict],
    season_context: str = "",
) -> str:
    """
    네이버 DataLab 트렌드 데이터를 분석합니다.
    """
    trend_lines = []
    for t in trend_data:
        period_str = " → ".join(
            f"{d['period']}:{d['ratio']:.1f}"
            for d in t.get("period_data", [])
        )
        trend_lines.append(
            f"- {t['keyword_group']}: 최근 {t['latest_ratio']:.1f} | 평균 {t['avg_ratio']:.1f} | "
            f"방향 {t['trend']} | {period_str}"
        )

    trend_str = "\n".join(trend_lines)

    prompt = f"""다음은 네이버 DataLab 키워드 검색 트렌드 데이터입니다. (검색량 상대지수 0-100)

## 브랜드: {brand_name}
## 시즌 컨텍스트: {season_context or "현재 시즌"}

## 트렌드 데이터
{trend_str}

위 데이터를 분석하여:
1. 현재 검색 트렌드 해석 (어떤 키워드가 주목받고 있는가)
2. 계절적 패턴 분석
3. 경쟁 키워드 대비 자사 브랜드 포지션
4. 검색 트렌드 기반 콘텐츠 타이밍 제안 (언제 어떤 콘텐츠를 발행하면 좋은가)
5. 급상승/급하락 키워드 주의 포인트

마케팅 담당자가 바로 활용할 수 있도록 간결하고 구체적으로 작성해주세요."""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        system=[
            {
                "type": "text",
                "text": SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": prompt}],
    )

    return response.content[0].text


def generate_content_ideas(
    client: anthropic.Anthropic,
    brand_name: str,
    insights: str,
    content_type: str = "블로그 매거진",
    season: str = "",
) -> str:
    """
    리서치 인사이트 기반 콘텐츠 아이디어를 생성합니다.
    """
    prompt = f"""아래 리서치 인사이트를 바탕으로 {brand_name} {content_type} 콘텐츠 아이디어를 제안하세요.

## 리서치 인사이트
{insights}

## 현재 시즌
{season or "현재"}

## 브랜드 슬로건
- "마음보일러 ON!" / "대성이 내일을 we합니다"

다음 형식으로 콘텐츠 아이디어 3개를 제안하세요:

### 아이디어 1
- **제목 안**: (후보 2~3개)
- **핵심 소재**:
- **타겟 독자**:
- **소비자 니즈 연결**:
- **제품 연계 포인트**:

### 아이디어 2
(동일 형식)

### 아이디어 3
(동일 형식)"""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        system=[
            {
                "type": "text",
                "text": SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": prompt}],
    )

    return response.content[0].text
