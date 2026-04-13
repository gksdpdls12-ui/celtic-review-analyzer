"""
대성쎌틱에너시스 W2O 경쟁사 리뷰 분석 CLI
사용법:
  python -m review_analyzer                           # reviews/ 폴더 전체 분석
  python -m review_analyzer --competitor 경동나비엔   # 특정 경쟁사만
  python -m review_analyzer --file reviews/경동.csv  # 단일 파일
  python -m review_analyzer --dry-run                # 로드만, 분석 없음
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

# 프로젝트 루트 기준 .env 로드
_ROOT = Path(__file__).parent.parent
load_dotenv(_ROOT / ".env")


def _check_env() -> bool:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("[오류] ANTHROPIC_API_KEY 환경변수가 설정되지 않았습니다.")
        print("  → .env 파일에 ANTHROPIC_API_KEY=sk-ant-... 를 추가하세요.")
        return False
    return True


def _get_output_dir() -> Path:
    out = _ROOT / "_research"
    out.mkdir(exist_ok=True)
    return out


def cmd_analyze(args: argparse.Namespace) -> int:
    from .insight_builder import build_full_report, generate_pencil_layout_hints
    from .loader import load_reviews_from_file, load_reviews_from_folder
    from .models import W2OReport
    from .reporter import save_full_report, save_pencil_hints
    from .w2o_pipeline import analyze_all_competitors, analyze_competitor_reviews

    output_dir = _get_output_dir()

    # ── 리뷰 데이터 로드 ──────────────────────────
    if args.file:
        filepath = Path(args.file)
        print(f"[main] 파일 로드: {filepath}")
        reviews = load_reviews_from_file(filepath)
        from .loader import ReviewDataset
        competitor = reviews[0].competitor if reviews else filepath.stem
        datasets = {
            competitor: ReviewDataset(
                competitor=competitor,
                total_count=len(reviews),
                reviews=reviews,
            )
        }
    else:
        reviews_dir = _ROOT / "reviews"
        if not reviews_dir.exists():
            print(f"[오류] reviews/ 폴더가 없습니다: {reviews_dir}")
            print("  → reviews/ 폴더를 만들고 .csv 또는 .md 리뷰 파일을 넣어주세요.")
            return 1

        print(f"[main] 리뷰 폴더 스캔: {reviews_dir}")
        datasets = load_reviews_from_folder(
            reviews_dir,
            competitor_filter=args.competitor,
        )

    if not datasets:
        print("[오류] 분석할 리뷰 데이터가 없습니다.")
        return 1

    if args.dry_run:
        print("\n[dry-run] 로드 결과:")
        for comp, ds in datasets.items():
            print(f"  - {comp}: {ds.total_count}개 리뷰")
        return 0

    # ── W2O 분석 ──────────────────────────────────
    print(f"\n[main] W2O 분석 시작 ({len(datasets)}개 경쟁사)")
    analyses = analyze_all_competitors(datasets)

    if not analyses:
        print("[오류] 분석 결과가 없습니다.")
        return 1

    # ── 보고서 생성 ───────────────────────────────
    report = W2OReport(
        report_title=f"경쟁사 W2O 리뷰 분석 — {date.today().isoformat()}",
        generated_at=date.today().isoformat(),
        analyses=analyses,
    )

    md_path, json_path = save_full_report(report, output_dir)

    # ── Pencil 레이아웃 힌트 저장 ─────────────────
    full_report = build_full_report(report)
    for deck in full_report.decks:
        hints = generate_pencil_layout_hints(deck)
        save_pencil_hints(hints, output_dir, deck.competitor)

    # ── 결과 요약 출력 ────────────────────────────
    print("\n" + "=" * 60)
    print("W2O 분석 완료")
    print("=" * 60)
    for analysis in analyses:
        print(f"\n[ {analysis.competitor} ]")
        print(f"  페인포인트: {len(analysis.pain_points)}개")
        print(f"  공략 카피: {len(analysis.attack_copies)}개")
        print(f"  우선 액션: {analysis.priority_action}")

    print(f"\n보고서 저장 위치:")
    print(f"  {md_path}")
    print(f"  {json_path}")

    if not args.no_pencil_hint:
        print("\n다음 단계 — Pencil 디자인 레이아웃:")
        print("  Claude Code에서 아래 명령을 실행하세요:")
        print(f"  '_{output_dir.name}/ 폴더의 pencil_hints.json을 참고해서")
        print("   W2O 인사이트 카드 레이아웃을 Pencil로 만들어줘'")

    return 0


def cmd_list(args: argparse.Namespace) -> int:
    """reviews/ 폴더의 리뷰 파일 목록 출력"""
    reviews_dir = _ROOT / "reviews"
    if not reviews_dir.exists():
        print("reviews/ 폴더가 없습니다.")
        return 1

    files = list(reviews_dir.glob("*.csv")) + list(reviews_dir.glob("*.md"))
    if not files:
        print("reviews/ 폴더에 리뷰 파일이 없습니다.")
        return 0

    print(f"reviews/ 폴더 내 파일 ({len(files)}개):")
    for f in sorted(files):
        size_kb = f.stat().st_size / 1024
        print(f"  {f.name}  ({size_kb:.1f} KB)")
    return 0


# ─────────────────────────────────────────────
# CLI 파서
# ─────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m review_analyzer",
        description="대성쎌틱에너시스 W2O 경쟁사 리뷰 분석기",
    )
    subparsers = parser.add_subparsers(dest="command")

    # analyze (기본 명령)
    analyze_parser = subparsers.add_parser("analyze", help="W2O 분석 실행 (기본)")
    analyze_parser.add_argument(
        "--competitor", "-c",
        help="특정 경쟁사 이름 필터 (예: 경동나비엔)",
    )
    analyze_parser.add_argument(
        "--file", "-f",
        help="단일 리뷰 파일 경로 (지정 시 폴더 스캔 생략)",
    )
    analyze_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="파일 로드만 수행, Claude API 호출 없음",
    )
    analyze_parser.add_argument(
        "--no-pencil-hint",
        action="store_true",
        help="Pencil 힌트 파일 저장 생략",
    )

    # list
    subparsers.add_parser("list", help="reviews/ 폴더 파일 목록")

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    # 기본 커맨드: analyze
    if args.command is None or args.command == "analyze":
        if not args.dry_run and not _check_env():
            return 1
        # argparse.Namespace에 누락된 속성 기본값 보정
        if not hasattr(args, "competitor"):
            args.competitor = None
        if not hasattr(args, "file"):
            args.file = None
        if not hasattr(args, "dry_run"):
            args.dry_run = False
        if not hasattr(args, "no_pencil_hint"):
            args.no_pencil_hint = False
        return cmd_analyze(args)

    if args.command == "list":
        return cmd_list(args)

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
