"""
대성쎌틱에너시스 마케팅 리서치 봇 — 설정 파일
API 키는 환경변수 또는 .env 파일로 관리합니다.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ── Anthropic (Claude) ─────────────────────────────────────────────
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# ── Naver Developers (https://developers.naver.com) ────────────────
NAVER_CLIENT_ID = os.getenv("NAVER_CLIENT_ID", "")
NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET", "")

# ── Google / YouTube Data API v3 ───────────────────────────────────
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "")

# ── 브랜드 설정 ────────────────────────────────────────────────────
BRAND = {
    "name": "대성쎌틱에너시스",
    "keywords": [
        "대성쎌틱", "대성보일러", "셀틱보일러",
        "대성 블랙 콘덴싱", "DEC보일러", "DNC보일러",
    ],
}

COMPETITORS = [
    {"name": "경동나비엔", "keywords": ["경동나비엔", "나비엔보일러"]},
    {"name": "린나이",    "keywords": ["린나이보일러", "린나이코리아"]},
    {"name": "귀뚜라미",  "keywords": ["귀뚜라미보일러"]},
]

# 분석할 제품 카테고리 키워드
PRODUCT_KEYWORDS = [
    "콘덴싱보일러", "가스보일러", "온수기", "각방온도", "보일러교체"
]

# ── 출력 설정 ──────────────────────────────────────────────────────
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "_research")
