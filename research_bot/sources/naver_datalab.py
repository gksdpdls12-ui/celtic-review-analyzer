"""
네이버 DataLab API — 키워드 검색 트렌드 수집
공식 API: https://developers.naver.com/docs/serviceapi/datalab/search/v1/
"""
import requests
from datetime import datetime, timedelta


DATALAB_URL = "https://openapi.naver.com/v1/datalab/search"


def get_trend(
    client_id: str,
    client_secret: str,
    keyword_groups: list[dict],
    start_date: str = None,
    end_date: str = None,
    time_unit: str = "month",  # date | week | month
    device: str = "",          # "" = 전체, "pc", "mo"
    ages: list[str] = None,    # ["1","2",...] 연령대
    gender: str = "",          # "" = 전체, "m", "f"
) -> dict:
    """
    네이버 DataLab 검색어 트렌드를 가져옵니다.

    keyword_groups 예시:
    [
      {"groupName": "대성쎌틱", "keywords": ["대성쎌틱", "대성보일러"]},
      {"groupName": "경동나비엔", "keywords": ["경동나비엔", "나비엔보일러"]},
    ]
    """
    if end_date is None:
        end_date = datetime.today().strftime("%Y-%m-%d")
    if start_date is None:
        start_date = (datetime.today() - timedelta(days=365)).strftime("%Y-%m-%d")

    headers = {
        "X-Naver-Client-Id": client_id,
        "X-Naver-Client-Secret": client_secret,
        "Content-Type": "application/json",
    }
    body = {
        "startDate": start_date,
        "endDate": end_date,
        "timeUnit": time_unit,
        "keywordGroups": keyword_groups,
        "device": device,
        "ages": ages or [],
        "gender": gender,
    }
    resp = requests.post(DATALAB_URL, headers=headers, json=body, timeout=10)
    resp.raise_for_status()
    return resp.json()


def parse_trend_summary(trend_data: dict) -> list[dict]:
    """트렌드 데이터를 요약 형태로 파싱합니다."""
    results = []
    for group in trend_data.get("results", []):
        name = group["title"]
        data_points = group.get("data", [])

        if not data_points:
            continue

        ratios = [d["ratio"] for d in data_points]
        latest = ratios[-1] if ratios else 0
        avg = round(sum(ratios) / len(ratios), 1) if ratios else 0
        trend = "상승" if len(ratios) >= 2 and ratios[-1] > ratios[-3] else "하락/보합"

        results.append({
            "keyword_group": name,
            "latest_ratio": latest,
            "avg_ratio": avg,
            "trend": trend,
            "period_data": data_points[-6:],  # 최근 6개 기간
        })
    return results
