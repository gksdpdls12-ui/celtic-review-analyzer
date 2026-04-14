"""
HTML 보고서 생성기
브라우저에서 바로 열리는 자기완결형 파일 (외부 의존성 없음)
"""

from __future__ import annotations
import math
from pathlib import Path
from .models import AdCopy, FullAnalysis, VOCIssue

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


def _e(s: str) -> str:
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _pct(v: float) -> str:
    return f"{v:.0%}"


def _bar(ratio: float, color: str = C_RED, w: int = 200) -> str:
    fw = int(ratio * w)
    return (f'<svg width="{w}" height="14" style="vertical-align:middle;border-radius:4px;overflow:hidden">'
            f'<rect width="{w}" height="14" fill="#E0E0E0"/>'
            f'<rect width="{fw}" height="14" fill="{color}"/></svg>')


def _donut(pos: float, neg: float, neu: float, size: int = 120) -> str:
    r = size // 2
    cx = cy = r
    sw = 28
    ri = r - sw // 2

    def arc(s: float, e: float, c: str) -> str:
        import math as m
        a1, a2 = m.radians(s - 90), m.radians(e - 90)
        x1, y1 = cx + ri * m.cos(a1), cy + ri * m.sin(a1)
        x2, y2 = cx + ri * m.cos(a2), cy + ri * m.sin(a2)
        lg = 1 if (e - s) > 180 else 0
        return (f'<path d="M {x1:.1f} {y1:.1f} A {ri} {ri} 0 {lg} 1 {x2:.1f} {y2:.1f}"'
                f' stroke="{c}" stroke-width="{sw}" fill="none"/>')

    total = pos + neg + neu or 1
    p_d = 360 * pos / total
    n_d = 360 * neg / total
    ne_d = 360 * neu / total

    arcs, cur = "", 0
    for val, color in [(p_d, "#4CAF50"), (n_d, C_RED), (ne_d, "#9E9E9E")]:
        if val > 0:
            arcs += arc(cur, cur + val, color)
            cur += val

    return (f'<svg width="{size}" height="{size}" viewBox="0 0 {size} {size}">'
            f'<circle cx="{cx}" cy="{cy}" r="{ri}" fill="none" stroke="#E0E0E0" stroke-width="{sw}"/>'
            f'{arcs}'
            f'<text x="{cx}" y="{cy-6}" text-anchor="middle" font-size="13" font-weight="bold" fill="{C_BLACK}">{_pct(pos)}</text>'
            f'<text x="{cx}" y="{cy+10}" text-anchor="middle" font-size="10" fill="#666">긍정</text>'
            f'</svg>')


def _tags(keywords: list[str], color: str) -> str:
    tags = " ".join(
        f'<span style="display:inline-block;background:{color}18;color:{color};'
        f'border:1px solid {color}40;border-radius:20px;padding:3px 12px;'
        f'margin:3px 2px;font-size:13px;font-weight:500">{_e(k)}</span>'
        for k in keywords
    )
    return f'<div style="line-height:2">{tags}</div>'


def _copy_card(c: AdCopy, idx: int) -> str:
    tc = COPY_TYPE_COLOR.get(c.copy_type, C_RED)
    return f'''
<div style="background:#fff;border-radius:12px;padding:20px 24px;margin-bottom:16px;
            box-shadow:0 2px 8px rgba(0,0,0,0.07);border-left:4px solid {tc}">
  <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:12px">
    <span style="font-size:12px;font-weight:700;color:{tc};letter-spacing:1px;
                 background:{tc}15;padding:3px 10px;border-radius:20px">{_e(c.copy_type)}</span>
    <span style="font-size:12px;color:#999">#{idx} · {_e(c.channel)}</span>
  </div>
  <div style="font-size:22px;font-weight:800;color:{C_BLACK};margin-bottom:8px;
              letter-spacing:-0.5px;line-height:1.3">{_e(c.headline)}</div>
  <div style="font-size:14px;color:{C_TEXT};margin-bottom:12px;line-height:1.6">{_e(c.sub_copy)}</div>
  <div style="font-size:12px;color:#888;padding-top:10px;border-top:1px solid #f0f0f0">
    근거: {_e(c.rationale)}
  </div>
</div>'''


def _voc_card(issue: VOCIssue, idx: int) -> str:
    color = SEVERITY_COLOR.get(issue.severity, "#999")
    label = SEVERITY_LABEL.get(issue.severity, "")
    quotes_html = "".join(
        f'<blockquote style="margin:8px 0;padding:8px 14px;background:#fafafa;'
        f'border-left:3px solid #ddd;font-size:13px;color:#555;font-style:italic">"{_e(q)}"</blockquote>'
        for q in issue.quotes
    )
    suggest = (f'<div style="margin-top:10px;padding:8px 12px;background:#F0F4FF;border-radius:8px;'
               f'font-size:12px;color:#1565C0"><b>개선 제안:</b> {_e(issue.improvement_suggestion)}</div>'
               if issue.improvement_suggestion else "")
    return f'''
<div style="background:#fff;border-radius:12px;padding:20px 24px;margin-bottom:14px;
            box-shadow:0 2px 8px rgba(0,0,0,0.06)">
  <div style="display:flex;align-items:center;gap:10px;margin-bottom:10px">
    <span style="font-size:18px;font-weight:800;color:{color}">#{idx}</span>
    <span style="font-size:15px;font-weight:700;color:{C_BLACK}">{_e(issue.keyword)}</span>
    <span style="margin-left:auto;font-size:11px;font-weight:700;color:{color};
                 background:{color}15;padding:2px 8px;border-radius:20px">심각도 {label}</span>
    <span style="font-size:11px;color:#999;background:#f5f5f5;padding:2px 8px;border-radius:20px">{_e(issue.category)}</span>
  </div>
  <div style="font-size:13px;color:{C_TEXT};line-height:1.6;margin-bottom:8px">{_e(issue.description)}</div>
  <div style="font-size:12px;color:#888;margin-bottom:8px">언급 빈도: <strong>{issue.frequency}건</strong></div>
  {quotes_html}{suggest}
</div>'''


def _ctx_card(label: str, patterns: list, icon: str = "") -> str:
    if not patterns:
        return ""
    items = ""
    for p in patterns:
        q_html = (f'<div style="margin-top:6px;padding:6px 10px;background:#fafafa;'
                  f'border-left:3px solid {C_GOLD};font-size:12px;color:#666;font-style:italic">"{_e(p.representative_quote)}"</div>'
                  if p.representative_quote else "")
        items += (f'<div style="padding:12px 0;border-bottom:1px solid #f0f0f0">'
                  f'<div style="font-size:13px;font-weight:600;color:{C_BLACK}">{_e(p.pattern)}</div>'
                  f'<div style="font-size:12px;color:#888;margin-top:2px">{_e(p.frequency)}</div>'
                  f'{q_html}</div>')
    return (f'<div style="background:#fff;border-radius:12px;padding:20px 24px;box-shadow:0 2px 8px rgba(0,0,0,0.06)">'
            f'<div style="font-size:14px;font-weight:700;color:{C_BLACK};margin-bottom:4px">{icon} {_e(label)}</div>'
            f'{items}</div>')


# ─────────────────────────────────────────────
# 메인 HTML 생성
# ─────────────────────────────────────────────

def generate_html(analysis: FullAnalysis) -> str:
    p = analysis.product_info
    s = analysis.sentiment
    u = analysis.usage_context
    v = analysis.voc
    m = analysis.marketing_insight

    platform_label = {
        "naver_smartstore": "네이버 스마트스토어",
        "coupang": "쿠팡",
    }.get(p.platform, p.platform or "CSV")

    title       = _e(p.product_name or "제품 리뷰 분석")
    rating_str  = f"{p.rating:.1f}점" if p.rating else "-"
    total_str   = f"{p.total_reviews:,}개"
    analyzed_at = _e(analysis.analyzed_at or "")
    overall_color = {"매우긍정":"#2E7D32","긍정":"#4CAF50","보통":"#FF8F00",
                     "부정":"#E53935","매우부정":"#B71C1C"}.get(s.overall_sentiment, "#616161")

    voc_cards   = "".join(_voc_card(i, n+1) for n, i in enumerate(v.top_issues))
    hook_copies = "".join(_copy_card(c, n+1) for n, c in enumerate(m.hook_copy_from_positive))
    trust_copies= "".join(_copy_card(c, n+1) for n, c in enumerate(m.trust_copy_from_negative))
    time_ctx    = _ctx_card("사용 시간대 / 계절", u.time_patterns, "🕐")
    place_ctx   = _ctx_card("사용 장소 / 환경", u.place_patterns, "🏠")
    trigger_ctx = _ctx_card("구매 계기 / 사용 상황", u.trigger_patterns, "💡")

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{title} - 리뷰 분석 보고서</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:'Apple SD Gothic Neo','Pretendard',-apple-system,BlinkMacSystemFont,'Noto Sans KR',sans-serif;background:{C_GRAY};color:{C_TEXT};line-height:1.6}}
.hd{{background:{C_BLACK};color:#fff;padding:32px 48px;display:flex;align-items:flex-start;justify-content:space-between;gap:24px}}
.hd-l{{flex:1}}
.badge{{display:inline-block;background:{C_RED};color:#fff;font-size:11px;font-weight:700;letter-spacing:1px;padding:4px 10px;border-radius:4px;margin-bottom:10px}}
.hd h1{{font-size:26px;font-weight:800;line-height:1.3;letter-spacing:-0.5px;margin-bottom:6px}}
.hd-meta{{font-size:13px;color:#aaa;margin-top:8px}}
.hd-meta span{{margin-right:16px}}
.hd-stats{{display:flex;gap:24px;flex-shrink:0}}
.stat{{text-align:center;background:rgba(255,255,255,0.07);border-radius:10px;padding:14px 20px;min-width:90px}}
.stat .val{{font-size:22px;font-weight:800;color:#fff;display:block}}
.stat .lbl{{font-size:11px;color:#888;margin-top:2px}}
.nav{{background:#fff;border-bottom:1px solid #e0e0e0;padding:0 48px;display:flex;position:sticky;top:0;z-index:100;box-shadow:0 1px 4px rgba(0,0,0,0.07)}}
.nav a{{display:inline-block;padding:14px 18px;font-size:13px;font-weight:600;color:#888;text-decoration:none;border-bottom:3px solid transparent;transition:all 0.2s}}
.nav a:hover{{color:{C_RED};border-bottom-color:{C_RED}}}
.wrap{{max-width:1100px;margin:0 auto;padding:40px 32px}}
.sec{{background:#fff;border-radius:16px;padding:32px 36px;margin-bottom:28px;box-shadow:0 2px 12px rgba(0,0,0,0.05)}}
.sec-title{{font-size:18px;font-weight:800;color:{C_BLACK};margin-bottom:24px;padding-bottom:14px;border-bottom:2px solid {C_GRAY};display:flex;align-items:center;gap:10px}}
.num{{display:inline-flex;align-items:center;justify-content:center;width:28px;height:28px;background:{C_RED};color:#fff;font-size:13px;font-weight:800;border-radius:50%;flex-shrink:0}}
.igrid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:16px}}
.iitem{{background:{C_GRAY};border-radius:10px;padding:14px 18px}}
.iitem .ilbl{{font-size:11px;font-weight:700;color:#888;letter-spacing:.5px;margin-bottom:4px;text-transform:uppercase}}
.iitem .ival{{font-size:16px;font-weight:700;color:{C_BLACK}}}
.sent-row{{display:grid;grid-template-columns:140px 1fr;gap:32px;align-items:start}}
.sent-donut{{text-align:center}}
.bar-row{{display:flex;align-items:center;gap:12px;margin-bottom:10px}}
.bar-lbl{{width:36px;font-size:12px;font-weight:600}}
.bar-pct{{width:44px;text-align:right;font-size:13px;font-weight:700}}
.kw{{margin-top:20px}}
.kw-lbl{{font-size:12px;font-weight:700;color:#666;margin-bottom:8px;letter-spacing:.3px}}
.ctx-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:16px}}
.ctx-ins{{margin-top:24px;padding:20px 24px;background:{C_BLACK};color:#fff;border-radius:12px}}
.ctx-ins .ci-title{{font-size:13px;font-weight:700;color:{C_GOLD};margin-bottom:12px;letter-spacing:.5px}}
.ci-item{{margin-bottom:12px;padding-bottom:12px;border-bottom:1px solid rgba(255,255,255,.08)}}
.ci-item:last-child{{border-bottom:none;margin-bottom:0}}
.ci-lbl{{font-size:11px;color:#aaa;font-weight:600;letter-spacing:.5px;margin-bottom:4px}}
.ci-val{{font-size:14px;color:#fff;line-height:1.5}}
.voc-warn{{background:#FFF3E0;border-left:4px solid #FB8C00;padding:14px 18px;border-radius:0 8px 8px 0;margin-bottom:20px;font-size:13px;color:#E65100;font-weight:500}}
.copy-cols{{display:grid;grid-template-columns:1fr 1fr;gap:24px}}
.copy-hd{{font-size:13px;font-weight:800;color:#fff;padding:8px 16px;border-radius:8px;margin-bottom:14px;letter-spacing:.3px}}
.opp{{margin-top:24px;padding:20px 24px;background:linear-gradient(135deg,{C_BLACK} 0%,#2d2d2d 100%);border-radius:12px;color:#fff}}
.opp .ob-lbl{{font-size:11px;font-weight:700;color:{C_GOLD};letter-spacing:1px;margin-bottom:8px}}
.opp .ob-val{{font-size:15px;line-height:1.6;margin-bottom:14px}}
.opp .ob-val:last-child{{margin-bottom:0}}
footer{{text-align:center;padding:32px;color:#aaa;font-size:12px}}
@media(max-width:768px){{
  .hd{{padding:24px 20px;flex-direction:column}}
  .hd-stats{{flex-wrap:wrap}}
  .nav{{padding:0 16px;overflow-x:auto}}
  .wrap{{padding:20px 16px}}
  .sec{{padding:24px 20px}}
  .sent-row{{grid-template-columns:1fr}}
  .copy-cols{{grid-template-columns:1fr}}
  .ctx-grid{{grid-template-columns:1fr}}
}}
</style>
</head>
<body>

<div class="hd">
  <div class="hd-l">
    <div class="badge">REVIEW ANALYSIS</div>
    <h1>{title}</h1>
    <div class="hd-meta">
      <span>🛒 {_e(platform_label)}</span>
      <span>📅 {analyzed_at}</span>
      <span style="color:{overall_color};font-weight:700">● {_e(s.overall_sentiment)}</span>
    </div>
  </div>
  <div class="hd-stats">
    <div class="stat"><span class="val">{rating_str}</span><div class="lbl">평균 별점</div></div>
    <div class="stat"><span class="val">{total_str}</span><div class="lbl">전체 리뷰</div></div>
    <div class="stat"><span class="val">{p.analyzed_count}개</span><div class="lbl">분석 리뷰</div></div>
  </div>
</div>

<div class="nav">
  <a href="#s1">① 제품정보</a>
  <a href="#s2">② 감성분석</a>
  <a href="#s3">③ 사용맥락</a>
  <a href="#s4">④ VOC</a>
  <a href="#s5">⑤ 마케팅 카피</a>
</div>

<div class="wrap">

<div class="sec" id="s1">
  <div class="sec-title"><span class="num">1</span> 제품 기본 정보</div>
  <div class="igrid">
    <div class="iitem"><div class="ilbl">플랫폼</div><div class="ival">{_e(platform_label)}</div></div>
    <div class="iitem"><div class="ilbl">평균 별점</div><div class="ival" style="color:{C_RED}">{rating_str}</div></div>
    <div class="iitem"><div class="ilbl">전체 리뷰</div><div class="ival">{total_str}</div></div>
    <div class="iitem"><div class="ilbl">분석 리뷰</div><div class="ival">{p.analyzed_count}개</div></div>
    <div class="iitem"><div class="ilbl">분석일</div><div class="ival">{analyzed_at}</div></div>
    <div class="iitem"><div class="ilbl">종합 감성</div><div class="ival" style="color:{overall_color}">{_e(s.overall_sentiment)}</div></div>
  </div>
</div>

<div class="sec" id="s2">
  <div class="sec-title"><span class="num">2</span> 감성 분석</div>
  <div class="sent-row">
    <div class="sent-donut">
      {_donut(s.positive_ratio, s.negative_ratio, s.neutral_ratio)}
      <div style="margin-top:10px;font-size:12px;color:#666;line-height:1.8">
        <span style="color:#4CAF50;font-weight:700">● 긍정 {_pct(s.positive_ratio)}</span><br>
        <span style="color:{C_RED};font-weight:700">● 부정 {_pct(s.negative_ratio)}</span><br>
        <span style="color:#9E9E9E;font-weight:700">● 중립 {_pct(s.neutral_ratio)}</span>
      </div>
    </div>
    <div>
      <div class="bar-row"><div class="bar-lbl" style="color:#2E7D32">긍정</div>{_bar(s.positive_ratio,"#4CAF50",260)}<div class="bar-pct" style="color:#2E7D32">{_pct(s.positive_ratio)}</div></div>
      <div class="bar-row"><div class="bar-lbl" style="color:{C_RED}">부정</div>{_bar(s.negative_ratio,C_RED,260)}<div class="bar-pct" style="color:{C_RED}">{_pct(s.negative_ratio)}</div></div>
      <div class="bar-row"><div class="bar-lbl" style="color:#666">중립</div>{_bar(s.neutral_ratio,"#9E9E9E",260)}<div class="bar-pct" style="color:#666">{_pct(s.neutral_ratio)}</div></div>
      <div style="margin-top:14px;padding:12px 16px;background:{C_GRAY};border-radius:8px;font-size:13px;color:{C_TEXT}">
        <b>한 줄 요약:</b> {_e(s.sentiment_summary)}
      </div>
    </div>
  </div>
  <div class="kw"><div class="kw-lbl" style="color:#2E7D32">긍정 키워드 TOP 10</div>{_tags(s.positive,"#2E7D32")}</div>
  <div class="kw" style="margin-top:16px"><div class="kw-lbl" style="color:{C_RED}">부정 키워드 TOP 10</div>{_tags(s.negative,C_RED)}</div>
  <div class="kw" style="margin-top:16px"><div class="kw-lbl">중립 / 정보 키워드</div>{_tags(s.neutral,"#616161")}</div>
</div>

<div class="sec" id="s3">
  <div class="sec-title"><span class="num">3</span> 사용 맥락 분석</div>
  <div class="ctx-grid">{time_ctx}{place_ctx}{trigger_ctx}</div>
  <div class="ctx-ins">
    <div class="ci-title">마케팅 전략 인사이트</div>
    <div class="ci-item"><div class="ci-lbl">주 사용자 유형</div><div class="ci-val">{_e(u.primary_user_type)}</div></div>
    <div class="ci-item"><div class="ci-lbl">타겟 마케팅 방향</div><div class="ci-val">{_e(u.target_marketing_direction)}</div></div>
    <div class="ci-item"><div class="ci-lbl">최적 광고 타이밍</div><div class="ci-val">{_e(u.best_timing)}</div></div>
  </div>
</div>

<div class="sec" id="s4">
  <div class="sec-title"><span class="num">4</span> 불만 포인트 VOC</div>
  <div class="voc-warn">핵심 불만: <strong>{_e(v.recurring_complaint)}</strong>{f"&nbsp;&nbsp;|&nbsp;&nbsp;치명적 약점: <strong>{_e(v.critical_dealbreaker)}</strong>" if v.critical_dealbreaker else ""}</div>
  {voc_cards}
</div>

<div class="sec" id="s5">
  <div class="sec-title"><span class="num">5</span> 마케팅 인사이트 &amp; 광고 카피</div>
  <div class="copy-cols">
    <div><div class="copy-hd" style="background:#2E7D32">긍정 기반 - 메인 후킹 카피</div>{hook_copies}</div>
    <div><div class="copy-hd" style="background:{C_RED}">부정 반전 - 신뢰 보완 카피</div>{trust_copies}</div>
  </div>
  <div class="opp">
    <div class="ob-lbl">OPPORTUNITY GAP</div><div class="ob-val">{_e(m.opportunity_gap)}</div>
    <div class="ob-lbl" style="margin-top:14px">추천 콘텐츠 주제</div><div class="ob-val">{_e(m.recommended_content_theme)}</div>
    <div class="ob-lbl" style="margin-top:14px">대성쎌틱에너시스 어필 포인트</div><div class="ob-val">{_e(m.competitive_advantage_hint)}</div>
  </div>
</div>

</div>

<footer>대성쎌틱에너시스 마케팅 리서치 · 생성일 {analyzed_at} · <a href="https://www.celtic.co.kr" target="_blank" style="color:{C_RED}">celtic.co.kr</a></footer>
</body>
</html>"""


def save_html(analysis: FullAnalysis, output_dir: str | Path) -> Path:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    safe = (analysis.product_info.product_name or "report").replace("/","_").replace("\\","_").replace(" ","_")[:40]
    date_str = analysis.analyzed_at or "report"
    path = output_dir / f"{date_str}_{safe}_리뷰분석.html"
    path.write_text(generate_html(analysis), encoding="utf-8")
    print(f"[html] 보고서 저장: {path}")
    return path
