"""
대성쎌틱에너시스 리뷰 크롤러 — Streamlit 웹 앱
로컬: streamlit run app.py  →  http://localhost:8501
배포: Streamlit Cloud         →  https://[앱이름].streamlit.app
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import streamlit as st

# ─────────────────────────────────────────────
# 페이지 설정 (반드시 첫 번째 st 호출)
# ─────────────────────────────────────────────

st.set_page_config(
    page_title="리뷰 분석기 — 대성쎌틱에너시스",
    page_icon="🔥",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────
# API 키: .env → Streamlit secrets → 사용자 입력 순으로 확인
# ─────────────────────────────────────────────

def _get_api_key() -> str:
    # 1. 환경변수 (.env)
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env")
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if key:
        return key
    # 2. Streamlit secrets (Cloud 배포 시)
    try:
        key = st.secrets.get("ANTHROPIC_API_KEY", "")
        if key:
            return key
    except Exception:
        pass
    return ""

# ─────────────────────────────────────────────
# 사이드바
# ─────────────────────────────────────────────

with st.sidebar:
    st.image(
        "https://www.celtic.co.kr/favicon.ico",
        width=32,
    ) if False else None  # favicon placeholder

    st.markdown(
        """
        <div style="text-align:center;padding:16px 0 8px">
          <div style="font-size:20px;font-weight:800;color:#C8102E">대성쎌틱에너시스</div>
          <div style="font-size:12px;color:#888;margin-top:2px">마케팅 리서치 · 리뷰 분석기</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.divider()

    st.markdown("**⚙️ 설정**")
    max_reviews = st.slider(
        "최대 수집 리뷰 수",
        min_value=20,
        max_value=300,
        value=100,
        step=20,
        help="많을수록 분석 정확도↑ 시간↑",
    )

    st.divider()
    st.markdown("**🔑 API 키**")

    preset_key = _get_api_key()
    if preset_key:
        st.success("API 키 설정됨 ✓", icon="✅")
        api_key = preset_key
    else:
        api_key = st.text_input(
            "Anthropic API Key",
            type="password",
            placeholder="sk-ant-...",
            help=".env 파일에 ANTHROPIC_API_KEY를 설정하거나 여기에 입력하세요",
        )

    st.divider()
    st.markdown(
        """
        **지원 플랫폼**
        - 🟢 네이버 스마트스토어
        - 🟢 네이버 쇼핑 카탈로그
        - 🟢 쿠팡
        """,
    )

    st.divider()
    st.caption("celtic.co.kr · blog.naver.com/celticmaster")


# ─────────────────────────────────────────────
# 헤더
# ─────────────────────────────────────────────

st.markdown(
    """
    <h1 style="font-size:28px;font-weight:800;color:#1A1A1A;margin-bottom:4px">
      🔥 리뷰 분석기
    </h1>
    <p style="color:#888;font-size:14px;margin-bottom:0">
      상품 URL을 입력하면 최신 리뷰를 수집하고 5단계 마케팅 인사이트를 분석합니다
    </p>
    """,
    unsafe_allow_html=True,
)

st.divider()

# ─────────────────────────────────────────────
# URL 입력
# ─────────────────────────────────────────────

col_input, col_btn = st.columns([5, 1])
with col_input:
    url = st.text_input(
        "상품 URL",
        placeholder="https://smartstore.naver.com/.../products/... 또는 https://www.coupang.com/vp/products/...",
        label_visibility="collapsed",
    )
with col_btn:
    run_btn = st.button("분석 시작", type="primary", use_container_width=True)

# URL 미리보기 (플랫폼 감지)
if url:
    try:
        from review_crawler.router import detect_platform, validate_url
        platform = detect_platform(url)
        valid, msg = validate_url(url)
        platform_labels = {
            "naver_smartstore": "네이버 스마트스토어",
            "naver_shopping": "네이버 쇼핑",
            "coupang": "쿠팡",
            "unknown": "알 수 없음",
        }
        label = platform_labels.get(platform, platform)
        if valid:
            st.caption(f"✅ 감지된 플랫폼: **{label}**  {('· ' + msg) if msg else ''}")
        else:
            st.warning(f"⚠️ {msg}", icon="⚠️")
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
        st.error("Anthropic API 키를 입력해주세요. (.env 파일 또는 사이드바)")
        st.stop()

    os.environ["ANTHROPIC_API_KEY"] = api_key

    from review_crawler.router import parse_url, validate_url
    valid, msg = validate_url(url)
    if not valid:
        st.error(f"지원하지 않는 URL입니다: {msg}")
        st.stop()

    parsed = parse_url(url)

    # ── 진행 표시 ─────────────────────────────
    progress_bar = st.progress(0, text="초기화 중...")

    try:
        # Step 1: 크롤링
        progress_bar.progress(10, text=f"리뷰 수집 중 ({parsed.platform})...")
        from review_crawler.scrapers import scrape_from_url
        product_info, reviews = scrape_from_url(parsed, max_reviews=max_reviews)
        progress_bar.progress(45, text=f"{len(reviews)}개 리뷰 수집 완료 · Claude 분석 중...")

        if not reviews:
            st.warning("수집된 리뷰가 없습니다. URL이 올바른지, 상품에 리뷰가 있는지 확인해주세요.")
            st.stop()

        # Step 2: Claude 분석
        from review_crawler.analyzer import analyze
        analysis = analyze(product_info, reviews)
        progress_bar.progress(85, text="보고서 생성 중...")

        # Step 3: HTML 생성
        from review_crawler.html_reporter import generate_html, save_html
        html_str = generate_html(analysis)

        # Step 4: 마크다운 + JSON
        from review_crawler.reporter import render_markdown
        import json
        md_str = render_markdown(analysis)
        json_str = analysis.model_dump_json(indent=2, ensure_ascii=False)

        progress_bar.progress(100, text="완료!")

    except Exception as e:
        progress_bar.empty()
        st.error(f"오류가 발생했습니다: {e}")
        with st.expander("상세 오류"):
            import traceback
            st.code(traceback.format_exc())
        st.stop()

    progress_bar.empty()
    st.success(f"✅ 분석 완료 — {len(reviews)}개 리뷰 · {analysis.product_info.product_name or '제품'}")

    # ─────────────────────────────────────────
    # 다운로드 버튼
    # ─────────────────────────────────────────
    st.divider()
    dl_col1, dl_col2, dl_col3 = st.columns(3)
    safe_name = (analysis.product_info.product_name or "report").replace(" ", "_")[:30]
    date_str = analysis.analyzed_at or "report"

    with dl_col1:
        st.download_button(
            label="⬇️ HTML 보고서 다운로드",
            data=html_str.encode("utf-8"),
            file_name=f"{date_str}_{safe_name}_리뷰분석.html",
            mime="text/html",
            use_container_width=True,
            type="primary",
            help="브라우저에서 바로 열 수 있는 완성된 보고서",
        )
    with dl_col2:
        st.download_button(
            label="⬇️ 마크다운 다운로드",
            data=md_str.encode("utf-8"),
            file_name=f"{date_str}_{safe_name}_리뷰분석.md",
            mime="text/markdown",
            use_container_width=True,
        )
    with dl_col3:
        st.download_button(
            label="⬇️ JSON 데이터 다운로드",
            data=json_str.encode("utf-8"),
            file_name=f"{date_str}_{safe_name}_분석데이터.json",
            mime="application/json",
            use_container_width=True,
        )

    st.divider()

    # ─────────────────────────────────────────
    # 결과 인라인 표시 (5개 탭)
    # ─────────────────────────────────────────
    p = analysis.product_info
    s = analysis.sentiment
    u = analysis.usage_context
    v = analysis.voc
    m_ins = analysis.marketing_insight

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "① 제품정보", "② 감성분석", "③ 사용맥락", "④ VOC", "⑤ 마케팅 카피"
    ])

    # ── Tab 1: 제품 정보 ──────────────────────
    with tab1:
        c1, c2, c3 = st.columns(3)
        c1.metric("브랜드", p.brand or "-")
        c2.metric("평균 별점", f"{p.rating:.1f}점" if p.rating else "-")
        c3.metric("총 리뷰", f"{p.total_reviews:,}개" if p.total_reviews else "-")
        c4, c5, c6 = st.columns(3)
        c4.metric("카테고리", p.category or "-")
        c5.metric("가격", p.price_display or "-")
        c6.metric("분석 리뷰", f"{len(reviews)}개")
        st.markdown(f"**URL**: [{p.url}]({p.url})")

    # ── Tab 2: 감성 분석 ─────────────────────
    with tab2:
        col_sent, col_kw = st.columns([1, 2])
        with col_sent:
            st.markdown(f"**종합 감성: {s.overall_sentiment}**")
            st.markdown(f"{s.sentiment_summary}")
            st.markdown("")
            st.progress(s.positive_ratio, text=f"긍정 {s.positive_ratio:.0%}")
            st.progress(s.negative_ratio, text=f"부정 {s.negative_ratio:.0%}")
            st.progress(s.neutral_ratio,  text=f"중립 {s.neutral_ratio:.0%}")

        with col_kw:
            st.markdown("**긍정 키워드**")
            st.markdown(
                " ".join(
                    f'<span style="background:#E8F5E9;color:#2E7D32;'
                    f'padding:3px 10px;border-radius:20px;font-size:13px;margin:2px;display:inline-block">'
                    f'{k}</span>'
                    for k in s.positive
                ),
                unsafe_allow_html=True,
            )
            st.markdown("**부정 키워드**")
            st.markdown(
                " ".join(
                    f'<span style="background:#FFEBEE;color:#C62828;'
                    f'padding:3px 10px;border-radius:20px;font-size:13px;margin:2px;display:inline-block">'
                    f'{k}</span>'
                    for k in s.negative
                ),
                unsafe_allow_html=True,
            )
            st.markdown("**중립 키워드**")
            st.markdown(
                " ".join(
                    f'<span style="background:#F5F5F5;color:#555;'
                    f'padding:3px 10px;border-radius:20px;font-size:13px;margin:2px;display:inline-block">'
                    f'{k}</span>'
                    for k in s.neutral
                ),
                unsafe_allow_html=True,
            )

    # ── Tab 3: 사용 맥락 ─────────────────────
    with tab3:
        st.info(f"**주 사용자 유형**: {u.primary_user_type}")
        st.success(f"**타겟 마케팅 방향**: {u.target_marketing_direction}")
        st.warning(f"**최적 광고 타이밍**: {u.best_timing}")
        st.markdown("")

        cols = st.columns(3)
        for col, (label, patterns) in zip(cols, [
            ("🕐 사용 시간대/계절", u.time_patterns),
            ("🏠 사용 장소/환경", u.place_patterns),
            ("💡 구매 계기/상황", u.trigger_patterns),
        ]):
            with col:
                st.markdown(f"**{label}**")
                for pat in patterns:
                    st.markdown(f"- **{pat.pattern}** ({pat.frequency})")
                    if pat.representative_quote:
                        st.caption(f'"{pat.representative_quote}"')

    # ── Tab 4: VOC ───────────────────────────
    with tab4:
        st.error(f"🔑 핵심 불만: **{v.recurring_complaint}**")
        if v.critical_dealbreaker:
            st.error(f"⚠️ 치명적 약점: **{v.critical_dealbreaker}**")
        st.markdown("")

        for i, issue in enumerate(v.top_issues, 1):
            severity_color = {"high": "🔴", "medium": "🟡", "low": "🟢"}
            icon = severity_color.get(issue.severity, "⚪")
            with st.expander(f"{icon} #{i} {issue.keyword}  |  {issue.category}  |  {issue.frequency}건"):
                st.markdown(issue.description)
                for q in issue.quotes:
                    st.markdown(f'> "{q}"')
                if issue.improvement_suggestion:
                    st.info(f"💡 개선 제안: {issue.improvement_suggestion}")

    # ── Tab 5: 마케팅 카피 ───────────────────
    with tab5:
        col_pos, col_neg = st.columns(2)

        with col_pos:
            st.markdown("### ✅ 긍정 기반 메인 후킹 카피")
            for i, copy in enumerate(m_ins.hook_copy_from_positive, 1):
                with st.container(border=True):
                    st.markdown(
                        f'<div style="font-size:20px;font-weight:800;color:#1A1A1A">'
                        f'{copy.headline}</div>',
                        unsafe_allow_html=True,
                    )
                    st.markdown(copy.sub_copy)
                    st.caption(
                        f"타입: {copy.copy_type}  |  채널: {copy.channel}  |  근거: {copy.rationale}"
                    )

        with col_neg:
            st.markdown("### 🛡 부정 반전 신뢰 보완 카피")
            for i, copy in enumerate(m_ins.trust_copy_from_negative, 1):
                with st.container(border=True):
                    st.markdown(
                        f'<div style="font-size:20px;font-weight:800;color:#C8102E">'
                        f'{copy.headline}</div>',
                        unsafe_allow_html=True,
                    )
                    st.markdown(copy.sub_copy)
                    st.caption(
                        f"타입: {copy.copy_type}  |  채널: {copy.channel}  |  근거: {copy.rationale}"
                    )

        st.divider()
        st.markdown(
            f"""
            **기회 포인트** — {m_ins.opportunity_gap}

            **추천 콘텐츠 주제** — {m_ins.recommended_content_theme}

            **대성쎌틱 어필 포인트** — {m_ins.competitive_advantage_hint}
            """
        )

    # ─────────────────────────────────────────
    # HTML 보고서 인라인 미리보기
    # ─────────────────────────────────────────
    st.divider()
    with st.expander("📄 HTML 보고서 미리보기 (전체 레이아웃)", expanded=False):
        st.components.v1.html(html_str, height=900, scrolling=True)


# ─────────────────────────────────────────────
# 초기 화면 (분석 전)
# ─────────────────────────────────────────────

else:
    st.markdown(
        """
        <div style="text-align:center;padding:60px 20px 40px">
          <div style="font-size:56px;margin-bottom:16px">🔍</div>
          <div style="font-size:18px;font-weight:600;color:#1A1A1A;margin-bottom:8px">
            상품 URL을 입력하고 분석 시작을 클릭하세요
          </div>
          <div style="font-size:14px;color:#888;line-height:1.8">
            네이버 스마트스토어 · 네이버 쇼핑 · 쿠팡 지원<br>
            최신 리뷰 자동 수집 → 감성 분석 → 사용 맥락 → VOC → 마케팅 카피 도출
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("---")
    ex1, ex2, ex3 = st.columns(3)
    with ex1:
        st.markdown(
            """
            **① 감성 분석**
            - 긍정·부정·중립 비율
            - 핵심 키워드 Top 10
            - 종합 감성 판단
            """
        )
    with ex2:
        st.markdown(
            """
            **② 사용 맥락 분석**
            - 사용 시간대·계절
            - 구매 계기·상황
            - 타겟 마케팅 방향
            """
        )
    with ex3:
        st.markdown(
            """
            **③ 마케팅 카피 생성**
            - 긍정 기반 후킹 카피
            - 부정 반전 신뢰 카피
            - 채널별 광고 문구
            """
        )
