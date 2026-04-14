"""
대성쎌틱에너시스 경쟁사 리뷰 분석기 CLI

사용법:
  python -m review_analyzer "https://smartstore.naver.com/경쟁사/products/번호"
  python -m review_analyzer "https://www.coupang.com/vp/products/번호" --max 200
  python -m review_analyzer "URL" --dry-run
  python -m review_analyzer "URL" --no-html
"""

from __future__ import annotations

import argparse
import os
import sys
import webbrowser
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr.encoding and sys.stderr.encoding.lower() != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from dotenv import load_dotenv

_ROOT = Path(__file__).parent.parent
_ENV = _ROOT / ".env"
if _ENV.is_dir():
    _ENV = _ENV / ".env"
load_dotenv(_ENV)


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="python -m review_analyzer",
        description="경쟁사 URL -> 리뷰 수집 -> Claude 분석 -> HTML 보고서",
    )
    parser.add_argument("url", help="경쟁사 상품 URL (스마트스토어 또는 쿠팡)")
    parser.add_argument("--max", "-m", type=int, default=100, help="최대 수집 리뷰 수 (기본: 100)")
    parser.add_argument("--dry-run", action="store_true", help="수집만 수행, Claude 분석 없음")
    parser.add_argument("--no-html", action="store_true", help="HTML 보고서 생성 안 함")
    parser.add_argument("--no-open", action="store_true", help="완료 후 브라우저 자동 열기 안 함")
    args = parser.parse_args()

    # ── 수집 ──────────────────────────────────
    from .scraper import detect_platform, scrape

    platform = detect_platform(args.url)
    if platform == "unknown":
        print(f"[오류] 지원하지 않는 URL입니다: {args.url}")
        print("  지원: 네이버 스마트스토어, 쿠팡")
        return 1

    print(f"\n{'='*60}")
    print(f"플랫폼: {'네이버 스마트스토어' if platform == 'naver_smartstore' else '쿠팡'}")
    print(f"URL: {args.url}")
    print(f"{'='*60}\n")

    try:
        product_info, reviews = scrape(args.url, max_reviews=args.max)
    except Exception as e:
        print(f"\n[오류] 수집 실패: {e}")
        return 1

    print(f"\n제품명: {product_info.product_name or '(미확인)'}")
    print(f"평균 별점: {product_info.rating or '-'}")
    print(f"수집된 리뷰: {len(reviews)}개")

    if not reviews:
        print("[오류] 수집된 리뷰가 없습니다.")
        return 1

    if args.dry_run:
        print("\n[dry-run] 수집 완료. 분석은 건너뜁니다.")
        r = reviews[0]
        print(f"\n첫 번째 리뷰: [{r.date}] ★{r.rating}  {r.content[:80]}...")
        return 0

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("\n[오류] ANTHROPIC_API_KEY가 설정되지 않았습니다.")
        print("  .env 파일에 ANTHROPIC_API_KEY=sk-ant-... 를 추가하세요.")
        return 1

    # ── 분석 ──────────────────────────────────
    from .analyzer import analyze
    try:
        analysis = analyze(product_info, reviews)
    except Exception as e:
        print(f"\n[오류] 분석 실패: {e}")
        return 1

    # ── 보고서 ────────────────────────────────
    output_dir = _ROOT / "_research"
    output_dir.mkdir(exist_ok=True)
    saved = []

    if not args.no_html:
        from .html_reporter import save_html
        saved.append(("HTML 보고서", save_html(analysis, output_dir)))

    from .reporter import save_json, save_markdown
    saved.append(("마크다운", save_markdown(analysis, output_dir)))
    saved.append(("JSON", save_json(analysis, output_dir)))

    print(f"\n{'='*60}")
    print(f"분석 완료")
    print(f"제품: {product_info.product_name or '-'}")
    print(f"감성: {analysis.sentiment.overall_sentiment} "
          f"(긍정 {analysis.sentiment.positive_ratio:.0%} / 부정 {analysis.sentiment.negative_ratio:.0%})")
    print(f"핵심 불만: {analysis.voc.recurring_complaint}")
    print(f"\n저장 완료:")
    for label, path in saved:
        print(f"  {label}: {path}")

    if not args.no_html and not args.no_open:
        html_path = next(p for l, p in saved if "HTML" in l)
        try:
            webbrowser.open(html_path.as_uri())
        except Exception:
            pass

    return 0


if __name__ == "__main__":
    sys.exit(main())
