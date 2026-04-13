"""
대성쎌틱에너시스 리뷰 크롤러 CLI
URL을 넣으면 최신 리뷰를 수집하고 5단계 분석 후 HTML 보고서를 생성합니다.

사용법:
  python -m review_crawler "https://smartstore.naver.com/..."
  python -m review_crawler "https://www.coupang.com/vp/products/..." --max 200
  python -m review_crawler "URL" --no-html      # 마크다운만 생성
  python -m review_crawler "URL" --dry-run      # 크롤링만, 분석 없음
  python -m review_crawler --check "URL"        # URL 지원 여부만 확인
"""

from __future__ import annotations

import argparse
import os
import sys
import webbrowser
from pathlib import Path

from dotenv import load_dotenv

_ROOT = Path(__file__).parent.parent
load_dotenv(_ROOT / ".env")


def _check_env() -> bool:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("\n[오류] ANTHROPIC_API_KEY가 설정되지 않았습니다.")
        print("  → .env 파일에 다음을 추가하세요:")
        print("    ANTHROPIC_API_KEY=sk-ant-...")
        return False
    return True


def _output_dir() -> Path:
    d = _ROOT / "_research"
    d.mkdir(exist_ok=True)
    return d


# ─────────────────────────────────────────────
# 메인 실행 흐름
# ─────────────────────────────────────────────

def run_crawl_and_analyze(
    url: str,
    max_reviews: int = 100,
    dry_run: bool = False,
    no_html: bool = False,
    open_browser: bool = True,
) -> int:
    from .router import parse_url, validate_url
    from .scrapers import scrape_from_url

    # ── URL 검증 ─────────────────────────────
    valid, msg = validate_url(url)
    if not valid:
        print(f"\n[오류] {msg}")
        print("  지원 URL 예시:")
        print("    네이버 스마트스토어: https://smartstore.naver.com/{스토어명}/products/{번호}")
        print("    네이버 쇼핑:        https://shopping.naver.com/catalog/{번호}")
        print("    쿠팡:               https://www.coupang.com/vp/products/{번호}")
        return 1

    if msg:
        print(f"[주의] {msg}")

    parsed = parse_url(url)
    print(f"\n{'='*60}")
    print(f"플랫폼: {parsed.platform}")
    print(f"제품 ID: {parsed.product_id or '(자동 감지)'}")
    print(f"{'='*60}")

    # ── 크롤링 ───────────────────────────────
    try:
        product_info, reviews = scrape_from_url(parsed, max_reviews=max_reviews)
    except Exception as e:
        print(f"\n[오류] 크롤링 실패: {e}")
        print("  가능한 원인:")
        print("  - 네트워크 연결 문제")
        print("  - 플랫폼 차단 (잠시 후 재시도)")
        print("  - URL이 올바르지 않음")
        return 1

    print(f"\n수집 완료: {len(reviews)}개 리뷰")
    print(f"제품명: {product_info.product_name or '(정보없음)'}")
    print(f"브랜드: {product_info.brand or '(정보없음)'}")

    if not reviews:
        print("\n[경고] 수집된 리뷰가 없습니다.")
        print("  가능한 원인: 리뷰 없음 / 비공개 상품 / 크롤링 차단")

    if dry_run:
        print("\n[dry-run] 크롤링만 수행. 분석 건너뜀.")
        print(f"  제품명 : {product_info.product_name or '(미확인)'}")
        print(f"  브랜드 : {product_info.brand or '(미확인)'}")
        print(f"  별점   : {product_info.rating or '(미확인)'}")
        print(f"  리뷰수 : {len(reviews)}개 수집")
        if reviews:
            print(f"\n  첫 번째 리뷰 미리보기:")
            print(f"  [{reviews[0].date}] ★{reviews[0].rating}  {reviews[0].content[:80]}...")
        return 0

    if not reviews:
        print("[오류] 리뷰 없이 분석을 진행할 수 없습니다.")
        return 1

    # ── Claude 분석 ──────────────────────────
    from .analyzer import analyze

    try:
        analysis = analyze(product_info, reviews)
    except Exception as e:
        print(f"\n[오류] Claude 분석 실패: {e}")
        return 1

    # ── 보고서 저장 ───────────────────────────
    output_dir = _output_dir()
    saved_files = []

    if not no_html:
        from .html_reporter import save_html
        html_path = save_html(analysis, output_dir)
        saved_files.append(("HTML 보고서", html_path))

    from .reporter import save_json, save_markdown
    md_path = save_markdown(analysis, output_dir)
    json_path = save_json(analysis, output_dir)
    saved_files.append(("마크다운", md_path))
    saved_files.append(("JSON 데이터", json_path))

    # ── 결과 요약 ─────────────────────────────
    print(f"\n{'='*60}")
    print("분석 완료")
    print(f"{'='*60}")
    print(f"제품: {product_info.product_name or '(정보없음)'}")
    print(f"감성: {analysis.sentiment.overall_sentiment} "
          f"(긍정 {analysis.sentiment.positive_ratio:.0%} / "
          f"부정 {analysis.sentiment.negative_ratio:.0%})")
    print(f"핵심 불만: {analysis.voc.recurring_complaint}")
    print(f"\n저장 완료:")
    for label, path in saved_files:
        print(f"  {label}: {path}")

    # ── 브라우저 자동 오픈 ────────────────────
    if not no_html and open_browser:
        html_path = next(p for l, p in saved_files if "HTML" in l)
        try:
            webbrowser.open(html_path.as_uri())
            print(f"\n브라우저에서 보고서를 열었습니다.")
        except Exception:
            print(f"\n보고서를 브라우저에서 열어주세요: {html_path}")

    return 0


def run_check(url: str) -> int:
    from .router import detect_platform, parse_url, validate_url

    platform = detect_platform(url)
    valid, msg = validate_url(url)
    parsed = parse_url(url)

    status = "✅ 지원" if valid else "❌ 미지원"
    print(f"\nURL 분석 결과:")
    print(f"  플랫폼:   {platform}")
    print(f"  지원여부: {status}")
    print(f"  제품 ID:  {parsed.product_id or '(감지 불가)'}")
    print(f"  스토어:   {parsed.store_id or '-'}")
    if msg:
        print(f"  메시지:   {msg}")
    return 0 if valid else 1


# ─────────────────────────────────────────────
# CLI 파서
# ─────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m review_crawler",
        description="대성쎌틱에너시스 리뷰 크롤러 — URL → 5단계 분석 → HTML 보고서",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  python -m review_crawler "https://smartstore.naver.com/celticmaster/products/1234567"
  python -m review_crawler "https://www.coupang.com/vp/products/1234567" --max 200
  python -m review_crawler "URL" --no-html --no-open
  python -m review_crawler --check "URL"
        """,
    )
    parser.add_argument("url", nargs="?", help="분석할 제품 URL")
    parser.add_argument(
        "--max", "-m",
        type=int, default=100,
        help="최대 수집 리뷰 수 (기본: 100)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="크롤링만 수행 (Claude 분석 없음)",
    )
    parser.add_argument(
        "--no-html",
        action="store_true",
        help="HTML 보고서 생성 안 함 (마크다운만)",
    )
    parser.add_argument(
        "--no-open",
        action="store_true",
        help="완료 후 브라우저 자동 열기 안 함",
    )
    parser.add_argument(
        "--check",
        metavar="URL",
        help="URL 지원 여부만 확인 (크롤링 없음)",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.check:
        return run_check(args.check)

    if not args.url:
        parser.print_help()
        print("\n\n사용 예시:")
        print("  python -m review_crawler \"https://smartstore.naver.com/celticmaster/products/1234\"")
        return 1

    if not args.dry_run and not _check_env():
        return 1

    return run_crawl_and_analyze(
        url=args.url,
        max_reviews=args.max,
        dry_run=args.dry_run,
        no_html=args.no_html,
        open_browser=not args.no_open,
    )


if __name__ == "__main__":
    sys.exit(main())
