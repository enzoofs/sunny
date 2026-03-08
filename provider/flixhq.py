"""FlixHQ scraping: search, seasons, episodes, servers."""

import re
import urllib.parse
from .http import get, get_json

FLIXHQ_BASE = "https://flixhq.to"
FLIXHQ_SEARCH = FLIXHQ_BASE + "/search"
FLIXHQ_AJAX = FLIXHQ_BASE + "/ajax"


def search(query):
    """Search FlixHQ, return list of {title, url, type}."""
    q = urllib.parse.quote(query.replace(" ", "-"), safe="-")
    html = get(f"{FLIXHQ_SEARCH}/{q}")
    results = []
    parts = re.split(r'class="flw-item"', html)
    for item in parts[1:11]:
        title_m = re.search(r'class="film-name"[^>]*>.*?title="([^"]*)"', item, re.DOTALL)
        href_m = re.search(r'<a[^>]*href="(/(?:movie|tv)/[^"]*)"', item)
        title = title_m.group(1) if title_m else "Unknown"
        href = href_m.group(1) if href_m else ""
        media_type = "series" if href.startswith("/tv/") else "movie"
        if href:
            results.append({
                "title": title,
                "url": FLIXHQ_BASE + href,
                "type": media_type,
            })
    return results


def get_media_id(url):
    """Get the internal media ID from a FlixHQ page."""
    html = get(url)
    for pattern in [
        r'id="watch-block"[^>]*data-id="([^"]+)"',
        r'detail_page-watch[^>]*data-id="([^"]+)"',
        r'id="movie_id"[^>]*value="([^"]+)"',
        r'data-id="(\d+)"[^>]*data-type=',
    ]:
        m = re.search(pattern, html)
        if m:
            return m.group(1)
    raise Exception("Could not find media ID")


def get_seasons(media_id):
    """Get seasons for a series. Returns list of {id, name}."""
    html = get(f"{FLIXHQ_AJAX}/season/list/{media_id}", referer=FLIXHQ_BASE + "/")
    seasons = []
    for m in re.finditer(r'data-id="([^"]*)"[^>]*>(.*?)<', html, re.DOTALL):
        seasons.append({"id": m.group(1), "name": m.group(2).strip()})
    return seasons


def get_episodes(season_or_media_id, is_season=True):
    """Get episodes for a season (or movie servers)."""
    endpoint = "season/episodes" if is_season else "movie/episodes"
    html = get(f"{FLIXHQ_AJAX}/{endpoint}/{season_or_media_id}", referer=FLIXHQ_BASE + "/")
    episodes = []
    for m in re.finditer(r'<a[^>]*data-id="([^"]*)"[^>]*title="([^"]*)"', html):
        episodes.append({"id": m.group(1), "name": m.group(2).strip()})
    if not episodes:
        for m in re.finditer(r'<a[^>]*data-id="([^"]*)"[^>]*>(.*?)<', html, re.DOTALL):
            episodes.append({"id": m.group(1), "name": m.group(2).strip()})
    if not episodes:
        for m in re.finditer(r'data-linkid="([^"]*)"[^>]*title="([^"]*)"', html):
            episodes.append({"id": m.group(1), "name": m.group(2).strip()})
    return episodes


def get_servers(episode_id):
    """Get servers for an episode."""
    html = get(f"{FLIXHQ_AJAX}/episode/servers/{episode_id}", referer=FLIXHQ_BASE + "/")
    servers = []
    for m in re.finditer(r'data-id="([^"]*)"[^>]*>.*?<span[^>]*>(.*?)</span>', html, re.DOTALL):
        servers.append({"id": m.group(1), "name": m.group(2).strip()})
    if not servers:
        for m in re.finditer(r'data-id="([^"]*)"[^>]*>(.*?)<', html, re.DOTALL):
            name = re.sub(r'<[^>]*>', '', m.group(2)).strip()
            if name:
                servers.append({"id": m.group(1), "name": name})
    return servers


def get_link(server_id):
    """Get the embed link for a server."""
    data = get_json(f"{FLIXHQ_AJAX}/episode/sources/{server_id}", referer=FLIXHQ_BASE + "/")
    return data.get("link", "")
