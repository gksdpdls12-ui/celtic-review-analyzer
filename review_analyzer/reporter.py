"""
마크다운 / JSON 보고서 저장
"""

from __future__ import annotations
from pathlib import Path
from .models import FullAnalysis


def save_markdown(analysis: FullAnalysis, output_dir: str | Path) -> Path:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    p = analysis.product_info
    s = analysis.sentiment
    u = analysis.usage_context
    v = analysis.voc
    m = analysis.marketing_insight

    platform_label = {"naver_smartstore": "네이버 스마트스토어", "coupang": "쿠팡"}.get(p.platform, p.platform or "CSV")

    lines = [
        f"# 리뷰 분석 보고서 — {p.product_name or '제품'}",
        f"",
        f"- **플랫폼**: {platform_label}",
        f"- **평균 별점**: {p.rating:.1f}점" if p.rating else "- **평균 별점**: -",
        f"- **전체 리뷰**: {p.total_reviews:,}개 (분석: {p.analyzed_count}개)",
        f"- **분석일**: {analysis.analyzed_at}",
        f"",
        f"---",
        f"",
        f"## 1. 감성 분석",
        f"",
        f"**종합 감성**: {s.overall_sentiment}",
        f"**요약**: {s.sentiment_summary}",
        f"",
        f"| 감성 | 비율 |",
        f"|------|------|",
        f"| 긍정 | {s.positive_ratio:.0%} |",
        f"| 부정 | {s.negative_ratio:.0%} |",
        f"| 중립 | {s.neutral_ratio:.0%} |",
        f"",
        f"**긍정 키워드**: {', '.join(s.positive)}",
        f"**부정 키워드**: {', '.join(s.negative)}",
        f"",
        f"---",
        f"",
        f"## 2. 사용 맥락 분석",
        f"",
        f"- **주 사용자 유형**: {u.primary_user_type}",
        f"- **타겟 마케팅 방향**: {u.target_marketing_direction}",
        f"- **최적 광고 타이밍**: {u.best_timing}",
        f"",
        f"---",
        f"",
        f"## 3. VOC — 핵심 불만",
        f"",
        f"> **핵심 불만**: {v.recurring_complaint}",
        f"",
    ]

    for i, issue in enumerate(v.top_issues, 1):
        lines += [
            f"### #{i} {issue.keyword} [{issue.category}] — 심각도 {issue.severity}",
            f"{issue.description}",
            f"- 빈도: {issue.frequency}건",
        ]
        for q in issue.quotes:
            lines.append(f'- > "{q}"')
        if issue.improvement_suggestion:
            lines.append(f"- 개선 제안: {issue.improvement_suggestion}")
        lines.append("")

    lines += [
        "---",
        "",
        "## 4. 마케팅 카피",
        "",
        "### 긍정 기반 후킹 카피",
        "",
    ]
    for i, c in enumerate(m.hook_copy_from_positive, 1):
        lines += [f"**{i}. {c.headline}**", f"{c.sub_copy}", f"- 채널: {c.channel} | 타입: {c.copy_type}", ""]

    lines += ["### 부정 반전 신뢰 카피", ""]
    for i, c in enumerate(m.trust_copy_from_negative, 1):
        lines += [f"**{i}. {c.headline}**", f"{c.sub_copy}", f"- 채널: {c.channel} | 타입: {c.copy_type}", ""]

    lines += [
        "---",
        "",
        "## 5. 기회 포인트",
        "",
        f"- **기회 포인트**: {m.opportunity_gap}",
        f"- **추천 콘텐츠**: {m.recommended_content_theme}",
        f"- **대성쎌틱 어필**: {m.competitive_advantage_hint}",
    ]

    safe = (p.product_name or "report").replace(" ", "_")[:40]
    date_str = analysis.analyzed_at or "report"
    path = output_dir / f"{date_str}_{safe}_리뷰분석.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    print(f"[reporter] 마크다운 저장: {path}")
    return path


def save_json(analysis: FullAnalysis, output_dir: str | Path) -> Path:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    safe = (analysis.product_info.product_name or "report").replace(" ", "_")[:40]
    date_str = analysis.analyzed_at or "report"
    path = output_dir / f"{date_str}_{safe}_분석데이터.json"
    path.write_text(analysis.model_dump_json(indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[reporter] JSON 저장: {path}")
    return path
