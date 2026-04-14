"""
대성쎌틱에너시스 리뷰 분석기 — Streamlit 웹 앱
경쟁사 스마트스토어 / 쿠팡 URL 입력 → 리뷰 수집 → Claude 분석 → 보고서

로컬 실행: streamlit run app.py
"""

from __future__ import annotations

import os
from pathlib import Path

import streamlit as st

st.set_page_config(
    page_title="경쟁사 리뷰 분석기 — 대성쎌틱에너시스",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ─────────────────────────────────────────────
# API 키 로드
# ─────────────────────────────────────────────

def _load_env():
    from dotenv import load_dotenv
    env = Path(__file__).parent / ".env"
    if env.is_dir():
        env = env / ".env"
    load_dotenv(env)

_load_env()

# Streamlit Cloud secrets → 환경변수로 주입 (로컬 .env 없을 때 대체)
try:
    for _k in ["ANTHROPIC_API_KEY", "NAVER_COOKIES"]:
        if _k in st.secrets and not os.environ.get(_k):
            os.environ[_k] = st.secrets[_k]
except Exception:
    pass


def _get_api_key() -> str:
    return os.environ.get("ANTHROPIC_API_KEY", "")


# ─────────────────────────────────────────────
# 사이드바
# ─────────────────────────────────────────────

with st.sidebar:
    st.markdown(
        """<div style="text-align:center;padding:16px 0 8px">
          <div style="font-size:20px;font-weight:800;color:#C8102E">대성쎌틱에너시스</div>
          <div style="font-size:12px;color:#888;margin-top:2px">경쟁사 리뷰 분석기</div>
        </div>""",
        unsafe_allow_html=True,
    )
    st.divider()

    st.markdown("**지원 플랫폼**")
    st.markdown("""
- 🟢 **네이버 스마트스토어**
- 🟢 **쿠팡**
""")

    st.divider()
    st.markdown("**⚙️ 설정**")
    max_reviews = st.slider(
        "최대 수집 리뷰 수", 20, 300, 100, 20,
        help="많을수록 정확도↑  시간·비용↑"
    )

    st.divider()
    st.markdown("**🔑 API 키**")
    preset_key = _get_api_key()
    if preset_key:
        st.success("API 키 설정됨 ✓")
        api_key = preset_key
    else:
        api_key = st.text_input(
            "Anthropic API Key", type="password", placeholder="sk-ant-...",
            help=".env 파일에 ANTHROPIC_API_KEY를 설정하거나 여기에 입력하세요"
        )

    # 쿠키 상태 표시
    st.divider()
    st.markdown("**🍪 네이버 쿠키**")
    naver_cookie = os.environ.get("NAVER_COOKIES", "")
    if naver_cookie:
        st.success("쿠키 설정됨 ✓")
    else:
        st.warning("쿠키 미설정 — 스마트스토어 수집 불가")
        with st.expander("설정 방법"):
            st.markdown("""
1. 네이버 로그인 후 아무 페이지 방문
2. `F12` → Application → Cookies → `smartstore.naver.com`
3. 모든 쿠키를 복사
4. `.env` 파일에 `NAVER_COOKIES=...` 저장
""")

    st.divider()
    st.caption("celtic.co.kr · blog.naver.com/celticmaster")


# ─────────────────────────────────────────────
# 헤더
# ─────────────────────────────────────────────

st.markdown(
    """<h1 style="font-size:28px;font-weight:800;color:#1A1A1A;margin-bottom:4px">
      🔍 경쟁사 리뷰 분석기
    </h1>
    <p style="color:#888;font-size:14px;margin-bottom:0">
      경쟁사 스마트스토어 · 쿠팡 URL을 입력하면 리뷰를 수집하고 마케팅 인사이트를 분석합니다
    </p>""",
    unsafe_allow_html=True,
)
st.divider()

# ─────────────────────────────────────────────
# URL 입력
# ─────────────────────────────────────────────

col_input, col_btn = st.columns([5, 1])
with col_input:
    url = st.text_input(
        "경쟁사 상품 URL",
        placeholder="https://smartstore.naver.com/스토어명/products/상품번호  또는  https://www.coupang.com/vp/products/번호",
        label_visibility="collapsed",
    )
with col_btn:
    run_btn = st.button("분석 시작", type="primary", use_container_width=True)

# URL 입력 시 플랫폼 미리보기
if url:
    try:
        from review_analyzer.scraper import detect_platform
        platform = detect_platform(url)
        labels = {"naver_smartstore": "네이버 스마트스토어", "coupang": "쿠팡"}
        if platform in labels:
            st.caption(f"감지된 플랫폼: **{labels[platform]}**")
        else:
            st.warning("지원하지 않는 URL입니다. 스마트스토어 또는 쿠팡 URL을 입력해주세요.")
    except Exception:
        pass

# ─────────────────────────────────────────────
# 분석 실행
# ─────────────────────────────────────────────

if run_btn:
    if not url:
        st.error("URL을 입력해주세요.")
        st.stop()
    if not api_key:
        st.error("Anthropic API 키를 입력해주세요.")
        st.stop()

    os.environ["ANTHROPIC_API_KEY"] = api_key

    progress = st.progress(0, text="리뷰 수집 중...")

    try:
        # Step 1: 수집
        from review_analyzer.scraper import scrape
        product_info, reviews = scrape(url, max_reviews=max_reviews)

        if not reviews:
            st.warning("수집된 리뷰가 없습니다. URL을 확인하거나 쿠키를 갱신해주세요.")
            st.stop()

        progress.progress(40, text=f"{len(reviews)}개 리뷰 수집 완료 · Claude 분석 중...")

        # Step 2: 분석
        from review_analyzer.analyzer import analyze
        analysis = analyze(product_info, reviews)
        progress.progress(85, text="보고서 생성 중...")

        # Step 3: 보고서 생성
        from review_analyzer.html_reporter import generate_html, save_html
        html_str = generate_html(analysis)

        from review_analyzer.reporter import save_json, save_markdown
        output_dir = Path(__file__).parent / "_research"
        output_dir.mkdir(exist_ok=True)
        md_path = save_markdown(analysis, output_dir)
        json_str = analysis.model_dump_json(indent=2, ensure_ascii=False)

        progress.progress(100, text="완료!")

    except Exception as e:
        progress.empty()
        st.error(f"오류: {e}")
        with st.expander("상세 오류"):
            import traceback
            st.code(traceback.format_exc())
        st.stop()

    progress.empty()
    st.success(f"분석 완료 — {len(reviews)}개 리뷰 · {product_info.product_name or '제품'}")

    # ── 다운로드 버튼 ──────────────────────────
    st.divider()
    safe_name = (analysis.product_info.product_name or "report").replace(" ", "_")[:30]
    date_str  = analysis.analyzed_at or "report"

    c1, c2, c3 = st.columns(3)
    with c1:
        st.download_button(
            "⬇ HTML 보고서 다운로드", data=html_str.encode("utf-8"),
            file_name=f"{date_str}_{safe_name}_리뷰분석.html",
            mime="text/html", use_container_width=True, type="primary",
        )
    with c2:
        st.download_button(
            "⬇ 마크다운 다운로드", data=md_path.read_bytes(),
            file_name=f"{date_str}_{safe_name}_리뷰분석.md",
            mime="text/markdown", use_container_width=True,
        )
    with c3:
        st.download_button(
            "⬇ JSON 데이터 다운로드", data=json_str.encode("utf-8"),
            file_name=f"{date_str}_{safe_name}_분석데이터.json",
            mime="application/json", use_container_width=True,
        )

    st.divider()

    # ── 결과 탭 ───────────────────────────────
    p    = analysis.product_info
    s    = analysis.sentiment
    u    = analysis.usage_context
    v    = analysis.voc
    m_ins = analysis.marketing_insight

    platform_label = {"naver_smartstore": "네이버 스마트스토어", "coupang": "쿠팡"}.get(
        p.platform, p.platform or "-"
    )

    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        ["① 제품정보", "② 감성분석", "③ 사용맥락", "④ VOC", "⑤ 마케팅 카피"]
    )

    with tab1:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("플랫폼", platform_label)
        c2.metric("평균 별점", f"{p.rating:.1f}점" if p.rating else "-")
        c3.metric("전체 리뷰", f"{p.total_reviews:,}개" if p.total_reviews else "-")
        c4.metric("분석 리뷰", f"{p.analyzed_count}개")

    with tab2:
        col1, col2 = st.columns([1, 2])
        with col1:
            st.markdown(f"**종합 감성: {s.overall_sentiment}**")
            st.markdown(s.sentiment_summary)
            st.markdown("")
            st.progress(s.positive_ratio, text=f"긍정 {s.positive_ratio:.0%}")
            st.progress(s.negative_ratio, text=f"부정 {s.negative_ratio:.0%}")
            st.progress(s.neutral_ratio,  text=f"중립 {s.neutral_ratio:.0%}")
        with col2:
            def _tags(kws, color):
                return " ".join(
                    f'<span style="background:{color}18;color:{color};border:1px solid {color}40;'
                    f'border-radius:20px;padding:3px 10px;font-size:13px;display:inline-block;margin:2px">{k}</span>'
                    for k in kws
                )
            st.markdown("**긍정 키워드**")
            st.markdown(_tags(s.positive, "#2E7D32"), unsafe_allow_html=True)
            st.markdown("**부정 키워드**")
            st.markdown(_tags(s.negative, "#C8102E"), unsafe_allow_html=True)

    with tab3:
        st.info(f"**주 사용자 유형**: {u.primary_user_type}")
        st.success(f"**타겟 마케팅 방향**: {u.target_marketing_direction}")
        st.warning(f"**최적 광고 타이밍**: {u.best_timing}")

    with tab4:
        st.error(f"핵심 불만: **{v.recurring_complaint}**")
        if v.critical_dealbreaker:
            st.error(f"치명적 약점: **{v.critical_dealbreaker}**")
        for i, issue in enumerate(v.top_issues, 1):
            icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(issue.severity, "⚪")
            with st.expander(f"{icon} #{i} {issue.keyword}  |  {issue.category}  |  {issue.frequency}건"):
                st.markdown(issue.description)
                for q in issue.quotes:
                    st.markdown(f'> "{q}"')
                if issue.improvement_suggestion:
                    st.info(f"개선 제안: {issue.improvement_suggestion}")

    with tab5:
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("### 긍정 기반 후킹 카피")
            for c in m_ins.hook_copy_from_positive:
                with st.container(border=True):
                    st.markdown(f"**{c.headline}**")
                    st.markdown(c.sub_copy)
                    st.caption(f"{c.copy_type} · {c.channel} · {c.rationale}")
        with col2:
            st.markdown("### 부정 반전 신뢰 카피")
            for c in m_ins.trust_copy_from_negative:
                with st.container(border=True):
                    st.markdown(f"**{c.headline}**")
                    st.markdown(c.sub_copy)
                    st.caption(f"{c.copy_type} · {c.channel} · {c.rationale}")
        st.divider()
        st.markdown(f"**기회 포인트**: {m_ins.opportunity_gap}")
        st.markdown(f"**추천 콘텐츠 주제**: {m_ins.recommended_content_theme}")
        st.markdown(f"**대성쎌틱에너시스 어필 포인트**: {m_ins.competitive_advantage_hint}")

    st.divider()
    with st.expander("HTML 보고서 미리보기", expanded=False):
        st.components.v1.html(html_str, height=900, scrolling=True)


# ─────────────────────────────────────────────
# 초기 화면
# ─────────────────────────────────────────────

else:
    st.markdown(
        """<div style="text-align:center;padding:60px 20px 40px">
          <div style="font-size:56px;margin-bottom:16px">🔍</div>
          <div style="font-size:18px;font-weight:600;color:#1A1A1A;margin-bottom:8px">
            경쟁사 상품 URL을 입력하고 분석 시작을 클릭하세요
          </div>
          <div style="font-size:14px;color:#888;line-height:1.8">
            네이버 스마트스토어 · 쿠팡 지원<br>
            리뷰 자동 수집 → 감성 분석 → VOC → 마케팅 카피 도출
          </div>
        </div>""",
        unsafe_allow_html=True,
    )
    st.markdown("---")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("**① 감성 분석**\n- 긍정·부정·중립 비율\n- 핵심 키워드 Top 10\n- 종합 감성 판단")
    with c2:
        st.markdown("**② VOC 분석**\n- 핵심 불만 Top 5\n- 심각도·빈도 분류\n- 개선 제안")
    with c3:
        st.markdown("**③ 마케팅 카피**\n- 경쟁사 약점 공략 카피\n- 채널별 광고 문구\n- 대성쎌틱 어필 포인트")
