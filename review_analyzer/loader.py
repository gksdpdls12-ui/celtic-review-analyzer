"""
reviews/ 폴더에서 .md 및 .csv 리뷰 파일을 로드하는 파서
지원 형식:
  - CSV: competitor, product, rating, content, source, date 컬럼
  - Markdown: YAML frontmatter + 리뷰 블록 형식
"""

from __future__ import annotations

import csv
import os
import re
from pathlib import Path

from .models import RawReview, ReviewDataset


# ─────────────────────────────────────────────
# CSV 파서
# ─────────────────────────────────────────────

def _parse_csv(filepath: Path, default_competitor: str) -> list[RawReview]:
    reviews = []
    with open(filepath, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            content = row.get("content", row.get("리뷰", row.get("review", ""))).strip()
            if not content:
                continue

            rating_raw = row.get("rating", row.get("별점", row.get("score", "")))
            try:
                rating = float(rating_raw) if rating_raw else None
            except ValueError:
                rating = None

            reviews.append(
                RawReview(
                    competitor=row.get("competitor", row.get("경쟁사", default_competitor)),
                    product=row.get("product", row.get("제품", "")),
                    rating=rating,
                    content=content,
                    source=row.get("source", row.get("출처", filepath.stem)),
                    date=row.get("date", row.get("날짜", "")),
                )
            )
    return reviews


# ─────────────────────────────────────────────
# Markdown 파서
# ─────────────────────────────────────────────

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_REVIEW_BLOCK_RE = re.compile(
    r"###?\s*(?:리뷰|review)\s*\d*\s*\n(.*?)(?=###?\s*(?:리뷰|review)|\Z)",
    re.DOTALL | re.IGNORECASE,
)
_RATING_RE = re.compile(r"별점[:\s]*([0-9.]+)", re.IGNORECASE)
_PRODUCT_RE = re.compile(r"제품[:\s]*(.+)", re.IGNORECASE)
_DATE_RE = re.compile(r"날짜[:\s]*(.+)", re.IGNORECASE)


def _parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    """YAML-like frontmatter 파싱 (의존성 없이 단순 key: value 처리)"""
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}, text

    meta: dict[str, str] = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            meta[key.strip()] = value.strip()

    body = text[m.end():]
    return meta, body


def _parse_markdown(filepath: Path, default_competitor: str) -> list[RawReview]:
    text = filepath.read_text(encoding="utf-8")
    meta, body = _parse_frontmatter(text)

    competitor = meta.get("competitor", meta.get("경쟁사", default_competitor))
    default_product = meta.get("product", meta.get("제품", ""))
    default_source = meta.get("source", meta.get("출처", filepath.stem))

    reviews: list[RawReview] = []

    # 구조화된 리뷰 블록 탐지
    blocks = _REVIEW_BLOCK_RE.findall(body)
    if blocks:
        for block in blocks:
            lines = block.strip().splitlines()
            content_lines = []
            rating = None
            product = default_product
            date = ""

            for line in lines:
                r = _RATING_RE.match(line)
                p = _PRODUCT_RE.match(line)
                d = _DATE_RE.match(line)
                if r:
                    try:
                        rating = float(r.group(1))
                    except ValueError:
                        pass
                elif p:
                    product = p.group(1).strip()
                elif d:
                    date = d.group(1).strip()
                else:
                    content_lines.append(line)

            content = "\n".join(content_lines).strip()
            if content:
                reviews.append(
                    RawReview(
                        competitor=competitor,
                        product=product,
                        rating=rating,
                        content=content,
                        source=default_source,
                        date=date,
                    )
                )
    else:
        # 구조 없이 단락으로 나뉜 텍스트 — 각 단락을 하나의 리뷰로 처리
        paragraphs = [p.strip() for p in re.split(r"\n{2,}", body) if p.strip()]
        for para in paragraphs:
            # 헤딩 줄(#으로 시작) 제외
            if para.startswith("#"):
                continue
            reviews.append(
                RawReview(
                    competitor=competitor,
                    product=default_product,
                    content=para,
                    source=default_source,
                )
            )

    return reviews


# ─────────────────────────────────────────────
# 공개 API
# ─────────────────────────────────────────────

def load_reviews_from_file(filepath: str | Path) -> list[RawReview]:
    """단일 파일을 로드하여 RawReview 목록 반환"""
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"리뷰 파일을 찾을 수 없습니다: {path}")

    # 파일명에서 경쟁사 이름 추출 (파일명_경쟁사.csv 형식 지원)
    stem = path.stem
    # 예: "경동나비엔_reviews" → "경동나비엔"
    competitor_guess = stem.split("_")[0] if "_" in stem else stem

    if path.suffix.lower() == ".csv":
        return _parse_csv(path, competitor_guess)
    elif path.suffix.lower() in (".md", ".markdown"):
        return _parse_markdown(path, competitor_guess)
    else:
        raise ValueError(f"지원하지 않는 파일 형식: {path.suffix} (지원: .csv, .md)")


def load_reviews_from_folder(
    folder: str | Path,
    competitor_filter: str | None = None,
) -> dict[str, ReviewDataset]:
    """
    reviews/ 폴더 전체를 스캔하여 경쟁사별 ReviewDataset 딕셔너리 반환.
    competitor_filter 지정 시 해당 경쟁사만 로드.
    """
    folder = Path(folder)
    if not folder.is_dir():
        raise FileNotFoundError(f"리뷰 폴더를 찾을 수 없습니다: {folder}")

    all_reviews: dict[str, list[RawReview]] = {}

    for filepath in sorted(folder.iterdir()):
        if filepath.suffix.lower() not in (".csv", ".md", ".markdown"):
            continue
        if filepath.name.startswith(".") or filepath.name.startswith("_"):
            continue

        try:
            file_reviews = load_reviews_from_file(filepath)
        except Exception as e:
            print(f"[loader] 경고: {filepath.name} 로드 실패 — {e}")
            continue

        for review in file_reviews:
            key = review.competitor
            if competitor_filter and competitor_filter not in key:
                continue
            all_reviews.setdefault(key, []).append(review)

    datasets: dict[str, ReviewDataset] = {}
    for competitor, reviews in all_reviews.items():
        datasets[competitor] = ReviewDataset(
            competitor=competitor,
            total_count=len(reviews),
            reviews=reviews,
        )
        print(f"[loader] {competitor}: {len(reviews)}개 리뷰 로드 완료")

    return datasets


def reviews_to_text(reviews: list[RawReview], max_reviews: int = 100) -> str:
    """Claude 프롬프트에 삽입할 텍스트 블록으로 변환"""
    sample = reviews[:max_reviews]
    lines = []
    for i, r in enumerate(sample, 1):
        rating_str = f"★{r.rating}" if r.rating is not None else ""
        product_str = f"[{r.product}]" if r.product else ""
        header = " ".join(filter(None, [f"리뷰{i}", product_str, rating_str]))
        lines.append(f"### {header}")
        lines.append(r.content)
        lines.append("")
    return "\n".join(lines)
