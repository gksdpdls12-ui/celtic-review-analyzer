"""
YouTube Data API v3 — 제품 리뷰 영상 및 댓글 수집
API 키 발급: https://console.cloud.google.com → YouTube Data API v3 활성화
"""
import requests


SEARCH_URL   = "https://www.googleapis.com/youtube/v3/search"
VIDEOS_URL   = "https://www.googleapis.com/youtube/v3/videos"
COMMENTS_URL = "https://www.googleapis.com/youtube/v3/commentThreads"


def search_videos(
    api_key: str,
    query: str,
    max_results: int = 10,
    order: str = "relevance",  # relevance | date | viewCount
    region_code: str = "KR",
    relevance_language: str = "ko",
) -> list[dict]:
    """
    YouTube 영상 검색

    Returns: [{video_id, title, description, channel, published_at, view_count}, ...]
    """
    params = {
        "key": api_key,
        "q": query,
        "part": "snippet",
        "type": "video",
        "maxResults": max_results,
        "order": order,
        "regionCode": region_code,
        "relevanceLanguage": relevance_language,
    }
    resp = requests.get(SEARCH_URL, params=params, timeout=10)
    resp.raise_for_status()
    items = resp.json().get("items", [])

    video_ids = [item["id"]["videoId"] for item in items]
    stats = _get_video_stats(api_key, video_ids) if video_ids else {}

    results = []
    for item in items:
        vid = item["id"]["videoId"]
        snippet = item["snippet"]
        s = stats.get(vid, {})
        results.append({
            "video_id": vid,
            "url": f"https://www.youtube.com/watch?v={vid}",
            "title": snippet.get("title", ""),
            "description": snippet.get("description", "")[:300],
            "channel": snippet.get("channelTitle", ""),
            "published_at": snippet.get("publishedAt", "")[:10],
            "view_count": int(s.get("viewCount", 0)),
            "like_count": int(s.get("likeCount", 0)),
            "comment_count": int(s.get("commentCount", 0)),
            "source": "youtube",
        })
    return sorted(results, key=lambda x: x["view_count"], reverse=True)


def _get_video_stats(api_key: str, video_ids: list[str]) -> dict:
    """영상 통계(조회수, 좋아요, 댓글 수) 조회"""
    params = {
        "key": api_key,
        "id": ",".join(video_ids),
        "part": "statistics",
    }
    resp = requests.get(VIDEOS_URL, params=params, timeout=10)
    resp.raise_for_status()
    return {
        item["id"]: item.get("statistics", {})
        for item in resp.json().get("items", [])
    }


def get_comments(
    api_key: str,
    video_id: str,
    max_results: int = 30,
    order: str = "relevance",  # relevance | time
) -> list[dict]:
    """
    YouTube 영상 댓글 수집 (실제 소비자 반응)

    Returns: [{text, author, like_count, published_at}, ...]
    """
    params = {
        "key": api_key,
        "videoId": video_id,
        "part": "snippet",
        "maxResults": max_results,
        "order": order,
        "textFormat": "plainText",
    }
    try:
        resp = requests.get(COMMENTS_URL, params=params, timeout=10)
        resp.raise_for_status()
    except requests.HTTPError as e:
        if e.response.status_code == 403:
            return []  # 댓글 비활성화된 영상
        raise

    items = resp.json().get("items", [])
    results = []
    for item in items:
        top = item["snippet"]["topLevelComment"]["snippet"]
        results.append({
            "text": top.get("textDisplay", ""),
            "author": top.get("authorDisplayName", ""),
            "like_count": top.get("likeCount", 0),
            "published_at": top.get("publishedAt", "")[:10],
        })
    return results


def collect_video_reviews(
    api_key: str,
    keywords: list[str],
    videos_per_keyword: int = 5,
    comments_per_video: int = 20,
) -> list[dict]:
    """
    키워드별 YouTube 리뷰 영상 + 댓글을 수집합니다.
    """
    collected = []
    seen_ids = set()

    for keyword in keywords:
        try:
            videos = search_videos(api_key, keyword, max_results=videos_per_keyword)
            for video in videos:
                vid = video["video_id"]
                if vid in seen_ids:
                    continue
                seen_ids.add(vid)

                comments = get_comments(api_key, vid, max_results=comments_per_video)
                video["comments"] = comments
                video["search_keyword"] = keyword
                collected.append(video)
        except Exception as e:
            print(f"  [경고] '{keyword}' YouTube 수집 실패: {e}")

    return collected
