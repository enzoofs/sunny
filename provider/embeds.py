"""TMDB-ID based embed providers — no search needed, much faster than scraping."""

import re
import threading

from .http import get
from .decrypt import decrypt_stream

# Embed URL templates: (name, movie_url, tv_url)
# {id} = TMDB ID, {s} = season, {e} = episode
PROVIDERS = [
    (
        "autoembed",
        "https://player.autoembed.cc/embed/movie/{id}",
        "https://player.autoembed.cc/embed/tv/{id}/{s}/{e}",
    ),
    (
        "2embed",
        "https://www.2embed.cc/embed/{id}",
        "https://www.2embed.cc/embedtv/{id}&s={s}&e={e}",
    ),
]

# Patterns to find player URLs in embed pages
_PLAYER_PATTERNS = [
    # Direct megacloud/streameeeeee/vidcloud URLs
    re.compile(r'''["']?(https?://(?:megacloud\.tv|streameeeeee\.site|streamaaa\.top|videostr\.net|rapid-cloud\.co)/[^"'\s;]+)'''),
    # Generic iframe src pointing to known players
    re.compile(r'''<iframe[^>]+src=["']([^"']+(?:megacloud|vidcloud|rabbitstream|rapid-cloud)[^"']*)["']''', re.I),
]


def extract_by_tmdb_id(tmdb_id, media_type="movie", season=None, episode=None):
    """Try embed providers using TMDB ID. Returns {url, referer, subtitles} or {error}."""
    s = str(season or 1)
    e = str(episode or 1)

    for name, movie_tpl, tv_tpl in PROVIDERS:
        if media_type == "movie":
            url = movie_tpl.format(id=tmdb_id)
        else:
            url = tv_tpl.format(id=tmdb_id, s=s, e=e)

        try:
            result = _try_embed(url)
            if result and result.get("url"):
                return result
        except Exception:
            continue

    return {"error": "All embed providers failed"}


def _try_embed(embed_url):
    """Fetch embed page, find player URL, decrypt stream."""
    try:
        html = get(embed_url, referer=embed_url)
    except Exception:
        return None

    # Find player URLs in the page
    for pattern in _PLAYER_PATTERNS:
        m = pattern.search(html)
        if m:
            player_url = m.group(1)
            result = decrypt_stream(player_url)
            if result.get("url"):
                return result

    return None
