"""Adult content provider — browse, search, and get video info."""

import re
import json
import urllib.request
import urllib.parse

_UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
_API_HEADERS = {
    "User-Agent": _UA,
    "Referer": "https://hanime.tv/",
    "X-Signature-Version": "web2",
    "X-Signature": "empty",
    "Accept": "application/json",
}
_SEARCH_URL = "https://search.htv-services.com/"


def _api_get(path):
    """GET from content API."""
    url = f"https://hanime.tv/api/v8/{path}"
    req = urllib.request.Request(url, headers=_API_HEADERS)
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode())


def _search_api(search_text="", tags=None, order_by="created_at_unix",
                ordering="desc", page=0):
    """POST to the search API and return parsed video list."""
    body = json.dumps({
        "search_text": search_text,
        "tags": tags or [],
        "tags_mode": "AND",
        "brands": [],
        "blacklist": [],
        "order_by": order_by,
        "ordering": ordering,
        "page": page,
    }).encode()
    headers = {**_API_HEADERS, "Content-Type": "application/json"}
    req = urllib.request.Request(_SEARCH_URL, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode())
    # Hits come as individual characters that form a JSON array when joined
    hits = json.loads("".join(data.get("hits", [])))
    return [{
        "id": h.get("id"),
        "name": h.get("name", ""),
        "slug": h.get("slug", ""),
        "released_at": h.get("released_at", ""),
        "views": h.get("views", 0),
        "poster_url": h.get("cover_url") or h.get("poster_url", ""),
        "cover_url": h.get("cover_url", ""),
        "tags": h.get("tags", []),
        "brand": h.get("brand", ""),
        "is_censored": h.get("is_censored", True),
    } for h in hits]


def browse_trending():
    """Get trending adult videos (most viewed this month)."""
    return _search_api(order_by="monthly_rank", ordering="asc")


def browse_new():
    """Get newest adult videos."""
    return _search_api(order_by="created_at_unix", ordering="desc")


def browse_popular():
    """Get most viewed adult videos of all time."""
    return _search_api(order_by="views", ordering="desc")


def browse_top_rated():
    """Get most liked adult videos."""
    return _search_api(order_by="likes", ordering="desc")


def browse_tag(tag):
    """Browse by tag (e.g. 'milf', 'uncensored', 'vanilla')."""
    return _search_api(tags=[tag], order_by="monthly_rank", ordering="desc")


def search(query):
    """Search adult videos by text."""
    return _search_api(search_text=query)


def get_video_info(slug):
    """Get detailed video info from API (tags, description, franchise, etc)."""
    data = _api_get(f"video?id={slug}")
    hv = data.get("hentai_video", {})
    tags = [t.get("text", "") for t in data.get("hentai_tags", [])]
    franchise = data.get("hentai_franchise", {})
    franchise_videos = data.get("hentai_franchise_hentai_videos", [])
    next_video = data.get("next_hentai_video")

    return {
        "id": hv.get("id"),
        "name": hv.get("name", ""),
        "slug": hv.get("slug", ""),
        "description": re.sub(r'<[^>]+>', '', hv.get("description", "")),
        "views": hv.get("views", 0),
        "likes": hv.get("likes", 0),
        "dislikes": hv.get("dislikes", 0),
        "poster_url": hv.get("poster_url", ""),
        "cover_url": hv.get("cover_url", ""),
        "released_at": hv.get("released_at", ""),
        "is_censored": hv.get("is_censored", True),
        "brand": hv.get("brand", ""),
        "duration_in_ms": hv.get("duration_in_ms", 0),
        "tags": tags,
        "franchise": franchise.get("title", ""),
        "franchise_videos": [{
            "id": fv.get("id"),
            "name": fv.get("name", ""),
            "slug": fv.get("slug", ""),
            "poster_url": fv.get("poster_url", ""),
        } for fv in franchise_videos],
        "next_video": {
            "name": next_video.get("name", ""),
            "slug": next_video.get("slug", ""),
            "poster_url": next_video.get("poster_url", ""),
        } if next_video else None,
        "player_url": f"https://hanime.tv/videos/hentai/{hv.get('slug', '')}",
    }


# Common tags for browsing UI
POPULAR_TAGS = [
    "uncensored", "vanilla", "milf", "big boobs", "creampie",
    "school girl", "netorare", "ahegao", "yuri", "bondage",
    "tentacle", "incest", "tsundere", "maid", "nurse",
    "dark skin", "cosplay", "femdom", "gangbang", "harem",
]
