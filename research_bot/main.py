"""
대성쎌틱에너시스 마케팅 리서치 자동화 봇
────────────────────────────────────────────────────────
사용법:
  python main.py                          # 전체 리서치 실행
  python main.py --topic "환절기 난방"     # 특정 주제로 실행
  python main.py --mode reviews           # 리뷰 분석만 실행
  python main.py --mode trends            # 트렌드 분석만 실행
  python main.py --mode ideas             # 콘텐츠 아이디어만 생성

필요 환경변수 (.env 파일):
  ANTHROPIC_API_KEY=sk-ant-...
  NAVER_CLIENT_ID=...
  NAVER_CLIENT_SECRET=...
  YOUTUBE_API_KEY=...   (선택사항)
"""
import argparse
import sys
import os
from datetime import datetime

import anthropic

# 경로 설정
sys.path.insert(0, os.path.dirname(__file__))

import config
from sources.naver_datalab import get_trend, parse_trend_summary
from sources.naver_search import collect_reviews, search_news
from sources.youtube import collect_video_reviews
from analyzer.claude_analyzer import analyze_reviews, analyze_trends, generate_content_ideas
from reporter.report import build_report, save_report


# ── 시즌 컨텍스트 자동 감지 ──────────────────────────────────────
def get_season_context() -> str:
    month = datetime.today().month
    if month in [1, 2]:
        return "겨울 난방 성수기 마무리 / AS 캠페인 시즌"
    elif month in [3, 4]:
        return "봄 이사 시즌 / 환절기 보일러 교체 수요"
    elif month in [5, 6, 7, 8]:
        return "비수기 / 냉방·생활가전 소구 시즌"
    elif month in [9, 10]:
        return "환절기 / 난방 시즌 예열 / 신제품 론칭"
    else:
        return "겨울 난방 성수기 / 연말 특가 이벤트"


# ── API 키 검증 ──────────────────────────────────────────────────
def validate_config():
    missing = []
    if not config.ANTHROPIC_API_KEY:
        missing.append("ANTHROPIC_API_KEY")
    if not config.NAVER_CLIENT_ID or not config.NAVER_CLIENT_SECRET:
        missing.append("NAVER_CLIENT_ID / NAVER_CLIENT_SECRET")
    if missing:
        print("❌ 필수 API 키가 없습니다:")
        for key in missing:
            print(f"   - {key}")
        print("\n.env 파일을 확인하거나 환경변수를 설정하세요.")
        print("참고: research_bot/.env.example")
        sys.exit(1)

    if not config.YOUTUBE_API_KEY:
        print("⚠️  YOUTUBE_API_KEY 없음 → YouTube 수집 건너뜀\n")


# ── Step 1: 트렌드 수집 ──────────────────────────────────────────
def run_trend_collection() -> tuple[list, str]:
    print("📊 [1/4] 네이버 DataLab 트렌드 수집 중...")

    # 자사 + 경쟁사 키워드 그룹 구성
    keyword_groups = [
        {
            "groupName": config.BRAND["name"],
            "keywords": config.BRAND["keywords"][:5],
        }
    ]
    for comp in config.COMPETITORS:
        keyword_groups.append({
            "groupName": comp["name"],
            "keywords": comp["keywords"][:3],
        })

    # 제품 카테고리 트렌드 (별도 요청)
    product_groups = [
        {"groupName": kw, "keywords": [kw]}
        for kw in config.PRODUCT_KEYWORDS[:5]
    ]

    trend_raw = get_trend(
        config.NAVER_CLIENT_ID,
        config.NAVER_CLIENT_SECRET,
        keyword_groups,
    )
    trend_summary = parse_trend_summary(trend_raw)

    product_raw = get_trend(
        config.NAVER_CLIENT_ID,
        config.NAVER_CLIENT_SECRET,
        product_groups,
    )
    product_summary = parse_trend_summary(product_raw)

    all_trends = trend_summary + product_summary
    print(f"   ✅ 트렌드 {len(all_trends)}개 그룹 수집 완료")
    return all_trends, get_season_context()


# ── Step 2: 리뷰 수집 ───────────────────────────────────────────
def run_review_collection() -> tuple[list, dict]:
    print("💬 [2/4] 소비자 리뷰 수집 중...")

    # 자사 리뷰 키워드
    brand_review_keywords = [
        f"{kw} 후기" for kw in config.BRAND["keywords"][:3]
    ] + [
        f"{kw} 리뷰" for kw in config.BRAND["keywords"][:2]
    ] + ["보일러 설치 후기", "콘덴싱보일러 후기"]

    brand_reviews = collect_reviews(
        config.NAVER_CLIENT_ID,
        config.NAVER_CLIENT_SECRET,
        keywords=brand_review_keywords,
        display_per_keyword=15,
    )
    print(f"   자사 블로그 리뷰: {len(brand_reviews)}건")

    # 경쟁사별 리뷰 수 파악
    competitor_data = {}
    for comp in config.COMPETITORS:
        comp_keywords = [f"{comp['keywords'][0]} 후기"]
        comp_reviews = collect_reviews(
            config.NAVER_CLIENT_ID,
            config.NAVER_CLIENT_SECRET,
            keywords=comp_keywords,
            display_per_keyword=5,
        )
        # DataLab 트렌드에서 방향 가져오기 (여기서는 단순 건수만)
        competitor_data[comp["name"]] = {
            "blog_count": len(comp_reviews),
            "trend": "수집됨",
        }

    # YouTube 리뷰 (API 키 있을 때만)
    yt_reviews = []
    if config.YOUTUBE_API_KEY:
        print("   YouTube 리뷰 수집 중...")
        yt_keywords = [
            f"{config.BRAND['keywords'][0]} 리뷰",
            "보일러 추천 2024",
            "콘덴싱보일러 비교",
        ]
        yt_reviews = collect_video_reviews(
            config.YOUTUBE_API_KEY,
            keywords=yt_keywords,
            videos_per_keyword=3,
            comments_per_video=15,
        )
        print(f"   YouTube 영상: {len(yt_reviews)}건")

    all_reviews = brand_reviews + yt_reviews
    print(f"   ✅ 총 리뷰 {len(all_reviews)}건 수집 완료")
    return all_reviews, competitor_data


# ── Step 3: Claude 분석 ─────────────────────────────────────────
def run_analysis(
    client: anthropic.Anthropic,
    trends: list,
    season: str,
    reviews: list,
    competitor_data: dict,
    topic: str,
) -> tuple[str, str, str]:
    print("🤖 [3/4] Claude 분석 중...")

    print("   트렌드 분석...")
    trend_analysis = analyze_trends(
        client,
        config.BRAND["name"],
        trends,
        season_context=f"{season} | 주제: {topic}",
    )

    print("   리뷰 감성 분석...")
    review_analysis = analyze_reviews(
        client,
        config.BRAND["name"],
        reviews,
        competitor_data=competitor_data,
    )

    print("   콘텐츠 아이디어 생성...")
    content_ideas = generate_content_ideas(
        client,
        config.BRAND["name"],
        insights=review_analysis[:1500],  # 인사이트 요약 전달
        content_type="블로그 매거진 「내일해」",
        season=season,
    )

    print("   ✅ 분석 완료")
    return trend_analysis, review_analysis, content_ideas


# ── Step 4: 리포트 저장 ─────────────────────────────────────────
def run_report(
    topic: str,
    trends: list,
    reviews: list,
    yt_count: int,
    trend_analysis: str,
    review_analysis: str,
    content_ideas: str,
) -> str:
    print("📝 [4/4] 리포트 생성 중...")

    stats = {
        "수집 키워드 그룹": len(trends),
        "네이버 블로그 리뷰": len([r for r in reviews if r.get("source") == "naver_blog"]),
        "YouTube 영상": yt_count,
        "분석 에이전트": "Claude Sonnet 4.6",
        "수집 일시": datetime.today().strftime("%Y-%m-%d %H:%M"),
    }

    report = build_report(
        brand_name=config.BRAND["name"],
        topic=topic,
        trend_analysis=trend_analysis,
        review_analysis=review_analysis,
        content_ideas=content_ideas,
        raw_stats=stats,
    )

    date_str = datetime.today().strftime("%Y-%m-%d")
    safe_topic = topic.replace(" ", "_").replace("/", "-")
    filename = f"{date_str}_{safe_topic}_briefing.md"

    filepath = save_report(report, config.OUTPUT_DIR, filename)
    print(f"   ✅ 리포트 저장: {filepath}")
    return filepath


# ── 메인 실행 ────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="대성쎌틱에너시스 마케팅 리서치 봇")
    parser.add_argument("--topic", default="종합 마케팅 리서치", help="리서치 주제")
    parser.add_argument(
        "--mode",
        choices=["full", "trends", "reviews", "ideas"],
        default="full",
        help="실행 모드",
    )
    args = parser.parse_args()

    print("=" * 55)
    print("  대성쎌틱에너시스 마케팅 리서치 봇")
    print(f"  주제: {args.topic} | 모드: {args.mode}")
    print("=" * 55)

    validate_config()

    anthropic_client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

    trends, season = [], get_season_context()
    reviews, competitor_data = [], {}
    yt_count = 0

    try:
        if args.mode in ["full", "trends"]:
            trends, season = run_trend_collection()

        if args.mode in ["full", "reviews"]:
            reviews, competitor_data = run_review_collection()
            yt_count = len([r for r in reviews if r.get("source") == "youtube"])

        # 분석 (수집된 데이터 기반)
        trend_analysis = ""
        review_analysis = ""
        content_ideas = ""

        if trends or reviews:
            trend_analysis, review_analysis, content_ideas = run_analysis(
                anthropic_client, trends, season, reviews, competitor_data, args.topic
            )
        elif args.mode == "ideas":
            # 데이터 없이 아이디어만 생성
            print("🤖 콘텐츠 아이디어 생성 중...")
            from analyzer.claude_analyzer import generate_content_ideas
            content_ideas = generate_content_ideas(
                anthropic_client,
                config.BRAND["name"],
                insights="최근 환절기 난방 관리, 에너지 절약 관심 증가",
                content_type="블로그 매거진 「내일해」",
                season=season,
            )

        filepath = run_report(
            args.topic, trends, reviews, yt_count,
            trend_analysis, review_analysis, content_ideas
        )

        print("\n" + "=" * 55)
        print(f"  ✅ 완료! 리포트: {os.path.basename(filepath)}")
        print("=" * 55)

    except KeyboardInterrupt:
        print("\n\n중단됨.")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
