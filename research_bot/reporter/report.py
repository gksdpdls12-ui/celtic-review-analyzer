"""
마케팅 리서치 리포트 생성기
_research/ 폴더에 마크다운 파일로 저장합니다.
"""
import os
from datetime import datetime


def build_report(
    brand_name: str,
    topic: str,
    trend_analysis: str,
    review_analysis: str,
    content_ideas: str,
    raw_stats: dict,
) -> str:
    """전체 리서치 리포트를 마크다운으로 조립합니다."""
    today = datetime.today().strftime("%Y년 %m월 %d일")

    stats_lines = []
    for key, val in raw_stats.items():
        stats_lines.append(f"| {key} | {val} |")
    stats_str = "\n".join(stats_lines)

    report = f"""---
작성일: {today}
브랜드: {brand_name}
주제: {topic}
에이전트: research-agent
상태: COMPLETE
---

# {brand_name} 마케팅 리서치 리포트
> **주제**: {topic} | **작성일**: {today}

---

## 📊 수집 데이터 요약

| 항목 | 수치 |
|------|------|
{stats_str}

---

## 📈 트렌드 분석 (네이버 DataLab)

{trend_analysis}

---

## 💬 소비자 리뷰 분석 (네이버 블로그 + YouTube)

{review_analysis}

---

## 💡 콘텐츠 아이디어

{content_ideas}

---

*이 리포트는 대성쎌틱에너시스 마케팅 리서치 봇이 자동 생성했습니다.*
*수치 데이터 활용 시 원본 출처를 반드시 확인하세요.*
"""
    return report


def save_report(report: str, output_dir: str, filename: str = None) -> str:
    """리포트를 _research/ 폴더에 저장합니다."""
    os.makedirs(output_dir, exist_ok=True)

    if filename is None:
        date_str = datetime.today().strftime("%Y-%m-%d")
        filename = f"{date_str}_marketing_research_briefing.md"

    filepath = os.path.join(output_dir, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(report)

    return filepath
