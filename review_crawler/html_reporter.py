"""
공유용 단일 HTML 보고서 생성기
- 브라우저에서 바로 열리는 자기완결형 파일 (외부 의존성 없음)
- 브랜드 컬러 기반 대시보드 레이아웃
- 5섹션: 제품정보 / 감성 / 사용맥락 / VOC / 마케팅카피
"""

from __future__ import annotations

from pathlib import Path

from .models import AdCopy, FullCrawlAnalysis, VOCIssue

# ─────────────────────────────────────────────
# 색상 & 스타일 상수
# ─────────────────────────────────────────────
C_RED   = "#C8102E"
C_BLACK = "#1A1A1A"
C_GOLD  = "#B8975A"
C_GRAY  = "#F5F5F3"
C_TEXT  = "#333333"

SEVERITY_COLOR = {"high": "#E53935", "medium": "#FB8C00", "low": "#43A047"}
SEVERITY_LABEL = {"high": "높음", "medium": "보통", "low": "낮음"}

COPY_TYPE_COLOR = {
    "후킹형": "#C8102E", "신뢰형": "#1565C0", "공감형": "#6A1B9A",
    "비교형": "#00695C", "혜택형": "#E65100",
}


# ─────────────────────────────────────────────
# 헬퍼
# ─────────────────────────────────────────────

def _esc(s: str) -> str:
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _pct(v: float) -> str:
    return f"{v:.0%}"


def _bar_svg(ratio: float, color: str = C_RED, width: int = 200, height: int = 14) -> str:
    fill_w = int(ratio * width)
    return (
        f'<svg width="{width}" height="{height}" style="vertical-align:middle;border-radius:4px;overflow:hidden">'
        f'<rect width="{width}" height="{height}" fill="#E0E0E0"/>'
        f'<rect width="{fill_w}" height="{height}" fill="{color}"/>'
        f'</svg>'
    )


def _donut_svg(positive: float, negative: float, neutral: float, size: int = 120) -> str:
    """도넛 차트 SVG (Chart.js 없이 순수 SVG)"""
    r = size // 2
    cx = cy = r
    stroke_w = 28
    r_inner = r - stroke_w // 2

    def _arc(start_deg: float, end_deg: float, color: str) -> str:
        import math
        start = math.radians(start_deg - 90)
        end   = math.radians(end_deg   - 90)
        x1 = cx + r_inner * math.cos(start)
        y1 = cy + r_inner * math.sin(start)
        x2 = cx + r_inner * math.cos(end)
        y2 = cy + r_inner * math.sin(end)
        large = 1 if (end_deg - start_deg) > 180 else 0
        return (
            f'<path d="M {x1:.1f} {y1:.1f} A {r_inner} {r_inner} 0 {large} 1 {x2:.1f} {y2:.1f}"'
            f' stroke="{color}" stroke-width="{stroke_w}" fill="none"/>'
        )

    total = positive + negative + neutral or 1
    p_deg = 360 * positive / total
    n_deg = 360 * negative / total
    ne_deg = 360 * neutral / total

    arcs = ""
    cursor = 0
    for val, color in [(p_deg, "#4CAF50"), (n_deg, C_RED), (ne_deg, "#9E9E9E")]:
        if val > 0:
            arcs += _arc(cursor, cursor + val, color)
            cursor += val

    return (
        f'<svg width="{size}" height="{size}" viewBox="0 0 {size} {size}">'
        f'<circle cx="{cx}" cy="{cy}" r="{r_inner}" fill="none" stroke="#E0E0E0" stroke-width="{stroke_w}"/>'
        f'{arcs}'
        f'<text x="{cx}" y="{cy-6}" text-anchor="middle" font-size="13" font-weight="bold" fill="{C_BLACK}">{_pct(positive)}</text>'
        f'<text x="{cx}" y="{cy+10}" text-anchor="middle" font-size="10" fill="#666">긍정</text>'
        f'</svg>'
    )


def _keyword_tags(keywords: list[str], color: str) -> str:
    tags = " ".join(
        f'<span style="display:inline-block;background:{color}18;color:{color};'
        f'border:1px solid {color}40;border-radius:20px;padding:3px 12px;'
        f'margin:3px 2px;font-size:13px;font-weight:500">{_esc(k)}</span>'
        for k in keywords
    )
    return f'<div style="line-height:2">{tags}</div>'


def _copy_card(copy: AdCopy, idx: int) -> str:
    type_color = COPY_TYPE_COLOR.get(copy.copy_type, C_RED)
    return f'''
<div style="background:#fff;border-radius:12px;padding:20px 24px;margin-bottom:16px;
            box-shadow:0 2px 8px rgba(0,0,0,0.07);border-left:4px solid {type_color}">
  <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:12px">
    <span style="font-size:12px;font-weight:700;color:{type_color};letter-spacing:1px;
                 background:{type_color}15;padding:3px 10px;border-radius:20px">
      {_esc(copy.copy_type)}
    </span>
    <span style="font-size:12px;color:#999">#{idx} · {_esc(copy.channel)}</span>
  </div>
  <div style="font-size:22px;font-weight:800;color:{C_BLACK};margin-bottom:8px;
              letter-spacing:-0.5px;line-height:1.3">
    {_esc(copy.headline)}
  </div>
  <div style="font-size:14px;color:{C_TEXT};margin-bottom:12px;line-height:1.6">
    {_esc(copy.sub_copy)}
  </div>
  <div style="font-size:12px;color:#888;padding-top:10px;border-top:1px solid #f0f0f0">
    근거: {_esc(copy.rationale)}
  </div>
</div>'''


def _voc_card(issue: VOCIssue, idx: int) -> str:
    color = SEVERITY_COLOR.get(issue.severity, "#999")
    label = SEVERITY_LABEL.get(issue.severity, "")
    quotes_html = "".join(
        f'<blockquote style="margin:8px 0;padding:8px 14px;background:#fafafa;'
        f'border-left:3px solid #ddd;font-size:13px;color:#555;font-style:italic">'
        f'"{_esc(q)}"</blockquote>'
        for q in issue.quotes
    )
    return f'''
<div style="background:#fff;border-radius:12px;padding:20px 24px;margin-bottom:14px;
            box-shadow:0 2px 8px rgba(0,0,0,0.06)">
  <div style="display:flex;align-items:center;gap:10px;margin-bottom:10px">
    <span style="font-size:18px;font-weight:800;color:{color}">#{idx}</span>
    <span style="font-size:15px;font-weight:700;color:{C_BLACK}">{_esc(issue.keyword)}</span>
    <span style="margin-left:auto;font-size:11px;font-weight:700;color:{color};
                 background:{color}15;padding:2px 8px;border-radius:20px">
      심각도 {label}
    </span>
    <span style="font-size:11px;color:#999;background:#f5f5f5;
                 padding:2px 8px;border-radius:20px">{_esc(issue.category)}</span>
  </div>
  <div style="font-size:13px;color:{C_TEXT};line-height:1.6;margin-bottom:8px">
    {_esc(issue.description)}
  </div>
  <div style="font-size:12px;color:#888;margin-bottom:8px">
    언급 빈도: <strong>{issue.frequency}건</strong>
  </div>
  {quotes_html}
  {f'<div style="margin-top:10px;padding:8px 12px;background:#F0F4FF;border-radius:8px;font-size:12px;color:#1565C0"><b>개선 제안:</b> {_esc(issue.improvement_suggestion)}</div>' if issue.improvement_suggestion else ""}
</div>'''


def _context_card(label: str, patterns: list, icon: str = "📍") -> str:
    if not patterns:
        return ""
    items = ""
    for p in patterns:
        quote_html = (
            f'<div style="margin-top:6px;padding:6px 10px;background:#fafafa;'
            f'border-left:3px solid {C_GOLD};font-size:12px;color:#666;font-style:italic">'
            f'"{_esc(p.representative_quote)}"</div>'
            if p.representative_quote else ""
        )
        items += f'''
        <div style="padding:12px 0;border-bottom:1px solid #f0f0f0">
          <div style="font-size:13px;font-weight:600;color:{C_BLACK}">{_esc(p.pattern)}</div>
          <div style="font-size:12px;color:#888;margin-top:2px">{_esc(p.frequency)}</div>
          {quote_html}
        </div>'''
    return f'''
<div style="background:#fff;border-radius:12px;padding:20px 24px;box-shadow:0 2px 8px rgba(0,0,0,0.06)">
  <div style="font-size:14px;font-weight:700;color:{C_BLACK};margin-bottom:4px">{icon} {_esc(label)}</div>
  {items}
</div>'''


# ─────────────────────────────────────────────
# 메인 HTML 생성 함수
# ─────────────────────────────────────────────

def generate_html(analysis: FullCrawlAnalysis) -> str:
    p = analysis.product_info
    s = analysis.sentiment
    u = analysis.usage_context
    v = analysis.voc
    m = analysis.marketing_insight

    title = _esc(p.product_name or "제품 리뷰 분석")
    brand = _esc(p.brand or "")
    platform_label = {
        "naver_smartstore": "네이버 스마트스토어",
        "naver_shopping": "네이버 쇼핑",
        "coupang": "쿠팡",
    }.get(p.platform, p.platform)

    price_str = _esc(p.price_display or "정보없음")
    rating_str = f"{p.rating:.1f}점" if p.rating else "-"
    total_r_str = f"{p.total_reviews:,}개" if p.total_reviews else "-"
    analyzed_str = _esc(analysis.analyzed_at or "")

    donut = _donut_svg(s.positive_ratio, s.negative_ratio, s.neutral_ratio)
    pos_tags = _keyword_tags(s.positive, "#2E7D32")
    neg_tags = _keyword_tags(s.negative, C_RED)
    neu_tags = _keyword_tags(s.neutral, "#616161")

    time_ctx = _context_card("사용 시간대 / 계절", u.time_patterns, "🕐")
    place_ctx = _context_card("사용 장소 / 환경", u.place_patterns, "🏠")
    trigger_ctx = _context_card("구매 계기 / 사용 상황", u.trigger_patterns, "💡")

    voc_cards_html = "".join(
        _voc_card(issue, i + 1) for i, issue in enumerate(v.top_issues)
    )

    hook_copies = "".join(
        _copy_card(c, i + 1) for i, c in enumerate(m.hook_copy_from_positive)
    )
    trust_copies = "".join(
        _copy_card(c, i + 1) for i, c in enumerate(m.trust_copy_from_negative)
    )

    overall_color = {
        "매우긍정": "#2E7D32", "긍정": "#4CAF50",
        "보통": "#FF8F00", "부정": "#E53935", "매우부정": "#B71C1C",
    }.get(s.overall_sentiment, "#616161")

    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title} — 리뷰 분석 보고서</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: 'Apple SD Gothic Neo', 'Pretendard', -apple-system, BlinkMacSystemFont,
                 'Segoe UI', 'Noto Sans KR', sans-serif;
    background: {C_GRAY};
    color: {C_TEXT};
    line-height: 1.6;
  }}
  .header {{
    background: {C_BLACK};
    color: #fff;
    padding: 32px 48px;
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 24px;
  }}
  .header-left {{ flex: 1; }}
  .badge {{
    display: inline-block;
    background: {C_RED};
    color: #fff;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 1px;
    padding: 4px 10px;
    border-radius: 4px;
    margin-bottom: 10px;
  }}
  .header h1 {{
    font-size: 26px;
    font-weight: 800;
    line-height: 1.3;
    letter-spacing: -0.5px;
    margin-bottom: 6px;
  }}
  .header-meta {{
    font-size: 13px;
    color: #aaa;
    margin-top: 8px;
  }}
  .header-meta span {{ margin-right: 16px; }}
  .header-stats {{
    display: flex;
    gap: 24px;
    flex-shrink: 0;
  }}
  .stat-box {{
    text-align: center;
    background: rgba(255,255,255,0.07);
    border-radius: 10px;
    padding: 14px 20px;
    min-width: 90px;
  }}
  .stat-box .val {{
    font-size: 22px;
    font-weight: 800;
    color: #fff;
    display: block;
  }}
  .stat-box .lbl {{
    font-size: 11px;
    color: #888;
    margin-top: 2px;
  }}
  .nav-bar {{
    background: #fff;
    border-bottom: 1px solid #e0e0e0;
    padding: 0 48px;
    display: flex;
    gap: 0;
    position: sticky;
    top: 0;
    z-index: 100;
    box-shadow: 0 1px 4px rgba(0,0,0,0.07);
  }}
  .nav-bar a {{
    display: inline-block;
    padding: 14px 18px;
    font-size: 13px;
    font-weight: 600;
    color: #888;
    text-decoration: none;
    border-bottom: 3px solid transparent;
    transition: all 0.2s;
  }}
  .nav-bar a:hover {{ color: {C_RED}; border-bottom-color: {C_RED}; }}
  .container {{ max-width: 1100px; margin: 0 auto; padding: 40px 32px; }}
  .section {{
    background: #fff;
    border-radius: 16px;
    padding: 32px 36px;
    margin-bottom: 28px;
    box-shadow: 0 2px 12px rgba(0,0,0,0.05);
  }}
  .section-title {{
    font-size: 18px;
    font-weight: 800;
    color: {C_BLACK};
    margin-bottom: 24px;
    padding-bottom: 14px;
    border-bottom: 2px solid {C_GRAY};
    display: flex;
    align-items: center;
    gap: 10px;
  }}
  .section-title .num {{
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 28px;
    height: 28px;
    background: {C_RED};
    color: #fff;
    font-size: 13px;
    font-weight: 800;
    border-radius: 50%;
    flex-shrink: 0;
  }}
  .info-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
    gap: 16px;
  }}
  .info-item {{
    background: {C_GRAY};
    border-radius: 10px;
    padding: 14px 18px;
  }}
  .info-item .info-lbl {{
    font-size: 11px;
    font-weight: 700;
    color: #888;
    letter-spacing: 0.5px;
    margin-bottom: 4px;
    text-transform: uppercase;
  }}
  .info-item .info-val {{
    font-size: 16px;
    font-weight: 700;
    color: {C_BLACK};
  }}
  .sentiment-row {{
    display: grid;
    grid-template-columns: 140px 1fr;
    gap: 32px;
    align-items: start;
  }}
  .sentiment-donut {{ text-align: center; }}
  .sentiment-bars .row {{
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 10px;
  }}
  .sentiment-bars .row .lbl {{
    width: 36px;
    font-size: 12px;
    font-weight: 600;
  }}
  .sentiment-bars .row .pct {{
    width: 44px;
    text-align: right;
    font-size: 13px;
    font-weight: 700;
  }}
  .kw-section {{ margin-top: 20px; }}
  .kw-label {{
    font-size: 12px;
    font-weight: 700;
    color: #666;
    margin-bottom: 8px;
    letter-spacing: 0.3px;
  }}
  .context-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
    gap: 16px;
  }}
  .context-insights {{
    margin-top: 24px;
    padding: 20px 24px;
    background: {C_BLACK};
    color: #fff;
    border-radius: 12px;
  }}
  .context-insights .ci-title {{
    font-size: 13px;
    font-weight: 700;
    color: {C_GOLD};
    margin-bottom: 12px;
    letter-spacing: 0.5px;
  }}
  .context-insights .ci-item {{
    margin-bottom: 12px;
    padding-bottom: 12px;
    border-bottom: 1px solid rgba(255,255,255,0.08);
  }}
  .context-insights .ci-item:last-child {{ border-bottom: none; margin-bottom: 0; }}
  .context-insights .ci-lbl {{
    font-size: 11px;
    color: #aaa;
    font-weight: 600;
    letter-spacing: 0.5px;
    margin-bottom: 4px;
  }}
  .context-insights .ci-val {{
    font-size: 14px;
    color: #fff;
    line-height: 1.5;
  }}
  .voc-warning {{
    background: #FFF3E0;
    border-left: 4px solid #FB8C00;
    padding: 14px 18px;
    border-radius: 0 8px 8px 0;
    margin-bottom: 20px;
    font-size: 13px;
    color: #E65100;
    font-weight: 500;
  }}
  .copy-columns {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 24px;
  }}
  .copy-col-title {{
    font-size: 13px;
    font-weight: 800;
    color: #fff;
    padding: 8px 16px;
    border-radius: 8px;
    margin-bottom: 14px;
    letter-spacing: 0.3px;
  }}
  .opportunity-box {{
    margin-top: 24px;
    padding: 20px 24px;
    background: linear-gradient(135deg, {C_BLACK} 0%, #2d2d2d 100%);
    border-radius: 12px;
    color: #fff;
  }}
  .opportunity-box .ob-label {{
    font-size: 11px;
    font-weight: 700;
    color: {C_GOLD};
    letter-spacing: 1px;
    margin-bottom: 8px;
  }}
  .opportunity-box .ob-val {{
    font-size: 15px;
    line-height: 1.6;
    margin-bottom: 14px;
  }}
  .opportunity-box .ob-val:last-child {{ margin-bottom: 0; }}
  .footer {{
    text-align: center;
    padding: 32px;
    color: #aaa;
    font-size: 12px;
  }}
  @media (max-width: 768px) {{
    .header {{ padding: 24px 20px; flex-direction: column; }}
    .header-stats {{ flex-wrap: wrap; }}
    .nav-bar {{ padding: 0 16px; overflow-x: auto; }}
    .container {{ padding: 20px 16px; }}
    .section {{ padding: 24px 20px; }}
    .sentiment-row {{ grid-template-columns: 1fr; }}
    .copy-columns {{ grid-template-columns: 1fr; }}
    .context-grid {{ grid-template-columns: 1fr; }}
  }}
</style>
</head>
<body>

<!-- HEADER -->
<div class="header">
  <div class="header-left">
    <div class="badge">REVIEW ANALYSIS</div>
    <h1>{title}</h1>
    <div style="font-size:14px;color:#888;margin-top:4px">{brand}</div>
    <div class="header-meta">
      <span>🛒 {_esc(platform_label)}</span>
      <span>📅 {analyzed_str}</span>
      <span style="color:{overall_color};font-weight:700">● {_esc(s.overall_sentiment)}</span>
    </div>
  </div>
  <div class="header-stats">
    <div class="stat-box">
      <span class="val">{rating_str}</span>
      <div class="lbl">평균 별점</div>
    </div>
    <div class="stat-box">
      <span class="val">{total_r_str}</span>
      <div class="lbl">전체 리뷰</div>
    </div>
    <div class="stat-box">
      <span class="val">{price_str}</span>
      <div class="lbl">가격</div>
    </div>
  </div>
</div>

<!-- NAV -->
<div class="nav-bar">
  <a href="#s1">① 제품정보</a>
  <a href="#s2">② 감성분석</a>
  <a href="#s3">③ 사용맥락</a>
  <a href="#s4">④ VOC</a>
  <a href="#s5">⑤ 마케팅 카피</a>
</div>

<div class="container">

<!-- ① 제품 기본 정보 -->
<div class="section" id="s1">
  <div class="section-title"><span class="num">1</span> 제품 기본 정보</div>
  <div class="info-grid">
    <div class="info-item">
      <div class="info-lbl">브랜드</div>
      <div class="info-val">{_esc(p.brand or '-')}</div>
    </div>
    <div class="info-item">
      <div class="info-lbl">카테고리</div>
      <div class="info-val">{_esc(p.category or '-')}</div>
    </div>
    <div class="info-item">
      <div class="info-lbl">가격</div>
      <div class="info-val">{price_str}</div>
    </div>
    <div class="info-item">
      <div class="info-lbl">평균 별점</div>
      <div class="info-val" style="color:{C_RED}">{rating_str}</div>
    </div>
    <div class="info-item">
      <div class="info-lbl">전체 리뷰</div>
      <div class="info-val">{total_r_str}</div>
    </div>
    <div class="info-item">
      <div class="info-lbl">분석 리뷰</div>
      <div class="info-val">{p.crawled_reviews}개</div>
    </div>
    <div class="info-item" style="grid-column: 1 / -1">
      <div class="info-lbl">URL</div>
      <div style="font-size:12px;color:#888;word-break:break-all">
        <a href="{_esc(p.url)}" target="_blank" style="color:{C_RED}">{_esc(p.url)}</a>
      </div>
    </div>
  </div>
</div>

<!-- ② 감성 분석 -->
<div class="section" id="s2">
  <div class="section-title"><span class="num">2</span> 감성 분석</div>
  <div class="sentiment-row">
    <div class="sentiment-donut">
      {donut}
      <div style="margin-top:10px;font-size:12px;color:#666;line-height:1.8">
        <span style="color:#4CAF50;font-weight:700">● 긍정 {_pct(s.positive_ratio)}</span><br>
        <span style="color:{C_RED};font-weight:700">● 부정 {_pct(s.negative_ratio)}</span><br>
        <span style="color:#9E9E9E;font-weight:700">● 중립 {_pct(s.neutral_ratio)}</span>
      </div>
    </div>
    <div>
      <div class="sentiment-bars">
        <div class="row">
          <div class="lbl" style="color:#2E7D32">긍정</div>
          {_bar_svg(s.positive_ratio, "#4CAF50", 260)}
          <div class="pct" style="color:#2E7D32">{_pct(s.positive_ratio)}</div>
        </div>
        <div class="row">
          <div class="lbl" style="color:{C_RED}">부정</div>
          {_bar_svg(s.negative_ratio, C_RED, 260)}
          <div class="pct" style="color:{C_RED}">{_pct(s.negative_ratio)}</div>
        </div>
        <div class="row">
          <div class="lbl" style="color:#666">중립</div>
          {_bar_svg(s.neutral_ratio, "#9E9E9E", 260)}
          <div class="pct" style="color:#666">{_pct(s.neutral_ratio)}</div>
        </div>
      </div>
      <div style="margin-top:14px;padding:12px 16px;background:{C_GRAY};border-radius:8px;
                  font-size:13px;color:{C_TEXT}">
        <b>한 줄 요약:</b> {_esc(s.sentiment_summary)}
      </div>
    </div>
  </div>
  <div class="kw-section">
    <div class="kw-label" style="color:#2E7D32">긍정 키워드 TOP 10</div>
    {pos_tags}
  </div>
  <div class="kw-section" style="margin-top:16px">
    <div class="kw-label" style="color:{C_RED}">부정 키워드 TOP 10</div>
    {neg_tags}
  </div>
  <div class="kw-section" style="margin-top:16px">
    <div class="kw-label">중립 / 정보 키워드</div>
    {neu_tags}
  </div>
</div>

<!-- ③ 사용 맥락 분석 -->
<div class="section" id="s3">
  <div class="section-title"><span class="num">3</span> 사용 맥락 분석</div>
  <div class="context-grid">
    {time_ctx}
    {place_ctx}
    {trigger_ctx}
  </div>
  <div class="context-insights" style="margin-top:20px">
    <div class="ci-title">마케팅 전략 인사이트</div>
    <div class="ci-item">
      <div class="ci-lbl">주 사용자 유형</div>
      <div class="ci-val">{_esc(u.primary_user_type)}</div>
    </div>
    <div class="ci-item">
      <div class="ci-lbl">타겟 마케팅 방향</div>
      <div class="ci-val">{_esc(u.target_marketing_direction)}</div>
    </div>
    <div class="ci-item">
      <div class="ci-lbl">최적 광고 타이밍</div>
      <div class="ci-val">{_esc(u.best_timing)}</div>
    </div>
  </div>
</div>

<!-- ④ VOC -->
<div class="section" id="s4">
  <div class="section-title"><span class="num">4</span> 불만 포인트 VOC (Voice of Customer)</div>
  <div class="voc-warning">
    ⚠ 핵심 불만: <strong>{_esc(v.recurring_complaint)}</strong>
    {f'&nbsp;&nbsp;|&nbsp;&nbsp;치명적 약점: <strong>{_esc(v.critical_dealbreaker)}</strong>' if v.critical_dealbreaker else ''}
  </div>
  {voc_cards_html}
</div>

<!-- ⑤ 마케팅 인사이트 & 카피 -->
<div class="section" id="s5">
  <div class="section-title"><span class="num">5</span> 마케팅 인사이트 & 광고 카피</div>
  <div class="copy-columns">
    <div>
      <div class="copy-col-title" style="background:#2E7D32">
        ✅ 긍정 기반 — 메인 후킹 카피
      </div>
      {hook_copies}
    </div>
    <div>
      <div class="copy-col-title" style="background:{C_RED}">
        🛡 부정 반전 — 신뢰 보완 카피
      </div>
      {trust_copies}
    </div>
  </div>
  <div class="opportunity-box">
    <div class="ob-label">OPPORTUNITY GAP</div>
    <div class="ob-val">{_esc(m.opportunity_gap)}</div>
    <div class="ob-label" style="margin-top:14px">추천 콘텐츠 주제</div>
    <div class="ob-val">{_esc(m.recommended_content_theme)}</div>
    <div class="ob-label" style="margin-top:14px">대성쎌틱에너시스 어필 포인트</div>
    <div class="ob-val">{_esc(m.competitive_advantage_hint)}</div>
  </div>
</div>

</div><!-- /container -->

<div class="footer">
  대성쎌틱에너시스 마케팅 리서치 · 생성일 {analyzed_str} ·
  <a href="https://www.celtic.co.kr" target="_blank" style="color:{C_RED}">celtic.co.kr</a>
</div>

</body>
</html>"""

    return html


# ─────────────────────────────────────────────
# 파일 저장
# ─────────────────────────────────────────────

def save_html(analysis: FullCrawlAnalysis, output_dir: str | Path) -> Path:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    safe_name = (
        (analysis.product_info.product_name or "report")
        .replace("/", "_").replace("\\", "_")
        .replace(" ", "_")[:40]
    )
    date_str = analysis.analyzed_at or "report"
    filename = f"{date_str}_{safe_name}_리뷰분석.html"
    filepath = output_dir / filename

    filepath.write_text(generate_html(analysis), encoding="utf-8")
    print(f"[html] 보고서 저장: {filepath}")
    return filepath
