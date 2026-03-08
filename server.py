#!/usr/bin/env python3
"""Sunny - Netflix-like visual interface for media streaming."""

import json
import logging
import os
import re
import sqlite3
import subprocess
import time
import urllib.request
import urllib.parse
import urllib.error
import threading
from http.server import HTTPServer, SimpleHTTPRequestHandler
from socketserver import ThreadingMixIn
from pathlib import Path

log = logging.getLogger("sunny")

CONFIG_PATH = Path(__file__).parent / "config.json"
LUFFY_HISTORY = Path.home() / ".config" / "luffy" / "history.sqlite"
STATIC_DIR = Path(__file__).parent / "static"

def load_config():
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH) as f:
            return json.load(f)
    return {}

def save_config(cfg):
    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg, f, indent=2)

def get_api_key():
    """Get TMDB API key: env var takes priority, then config.json."""
    return os.environ.get("TMDB_API_KEY", "") or load_config().get("tmdb_api_key", "")

def tmdb_request(path, params=None):
    api_key = get_api_key()
    if not api_key:
        return {"error": "No TMDB API key configured"}
    cfg = load_config()
    base = "https://api.themoviedb.org/3"
    params = params or {}
    params["api_key"] = api_key
    params["language"] = cfg.get("language", "pt-BR")
    qs = urllib.parse.urlencode(params)
    url = f"{base}{path}?{qs}"
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return {"error": f"TMDB API error: {e.code}"}
    except Exception as e:
        return {"error": str(e)}

JIKAN_BASE = "https://api.jikan.moe/v4"
_jikan_last_call = 0
_jikan_lock = threading.Lock()
_jikan_cache = {}
JIKAN_CACHE_TTL = 300  # 5 minutes

def jikan_request(path, params=None):
    """Request to Jikan API (MyAnimeList) with rate limiting, thread-safe + cache."""
    global _jikan_last_call
    params = params or {}
    qs = urllib.parse.urlencode(params)
    cache_key = f"{path}?{qs}"

    # Check cache first (no lock needed for read)
    cached = _jikan_cache.get(cache_key)
    if cached and (time.time() - cached["ts"]) < JIKAN_CACHE_TTL:
        return cached["data"]

    # Rate limit with lock so threads don't blast the API
    with _jikan_lock:
        # Double-check cache (another thread may have fetched while we waited)
        cached = _jikan_cache.get(cache_key)
        if cached and (time.time() - cached["ts"]) < JIKAN_CACHE_TTL:
            return cached["data"]

        now = time.time()
        elapsed = now - _jikan_last_call
        if elapsed < 0.35:
            time.sleep(0.35 - elapsed)
        _jikan_last_call = time.time()

    url = f"{JIKAN_BASE}{path}"
    if qs:
        url += f"?{qs}"
    try:
        req = urllib.request.Request(url, headers={
            "Accept": "application/json",
            "User-Agent": "Sunny/1.0",
        })
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
        # Cache successful responses
        if "error" not in data:
            _jikan_cache[cache_key] = {"data": data, "ts": time.time()}
        return data
    except urllib.error.HTTPError as e:
        return {"error": f"Jikan API error: {e.code}", "data": []}
    except Exception as e:
        return {"error": str(e), "data": []}

# Curated anime genre/demographic IDs from MAL via Jikan
ANIME_GENRES = {
    "shounen":      {"id": 27,  "type": "demographics", "name": "Shounen"},
    "seinen":       {"id": 42,  "type": "demographics", "name": "Seinen"},
    "shoujo":       {"id": 25,  "type": "demographics", "name": "Shoujo"},
    "isekai":       {"id": 62,  "type": "genres",       "name": "Isekai"},
    "ecchi":        {"id": 9,   "type": "genres",       "name": "Ecchi"},
    "acao":         {"id": 1,   "type": "genres",       "name": "Acao"},
    "aventura":     {"id": 2,   "type": "genres",       "name": "Aventura"},
    "comedia":      {"id": 4,   "type": "genres",       "name": "Comedia"},
    "drama":        {"id": 8,   "type": "genres",       "name": "Drama"},
    "fantasia":     {"id": 10,  "type": "genres",       "name": "Fantasia"},
    "horror":       {"id": 14,  "type": "genres",       "name": "Horror"},
    "mecha":        {"id": 18,  "type": "genres",       "name": "Mecha"},
    "romance":      {"id": 22,  "type": "genres",       "name": "Romance"},
    "sci_fi":       {"id": 24,  "type": "genres",       "name": "Sci-Fi"},
    "slice_of_life": {"id": 36, "type": "genres",       "name": "Slice of Life"},
    "esporte":      {"id": 30,  "type": "genres",       "name": "Esporte"},
    "supernatural": {"id": 37,  "type": "genres",       "name": "Sobrenatural"},
    "suspense":     {"id": 41,  "type": "genres",       "name": "Suspense"},
    "misterio":     {"id": 7,   "type": "genres",       "name": "Misterio"},
    "musica":       {"id": 19,  "type": "genres",       "name": "Musica"},
    "psicologico":  {"id": 40,  "type": "genres",       "name": "Psicologico"},
    "gore":         {"id": 49,  "type": "explicit_genres", "name": "Gore"},
    "harem":        {"id": 35,  "type": "genres",       "name": "Harem"},
}


def get_history():
    if not LUFFY_HISTORY.exists():
        return []
    conn = sqlite3.connect(str(LUFFY_HISTORY))
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT title, season, episode, ep_name, provider, position_secs, watched_at,
               MAX(id) as last_id
        FROM history
        GROUP BY title
        ORDER BY last_id DESC
    """).fetchall()
    result = []
    for r in rows:
        result.append({
            "title": r["title"],
            "season": r["season"],
            "episode": r["episode"],
            "ep_name": r["ep_name"],
            "provider": r["provider"],
            "position_secs": r["position_secs"],
            "watched_at": r["watched_at"],
        })
    conn.close()
    return result

def delete_history(title):
    if not LUFFY_HISTORY.exists():
        return False
    conn = sqlite3.connect(str(LUFFY_HISTORY))
    conn.execute("DELETE FROM history WHERE title = ?", (title,))
    conn.commit()
    conn.close()
    return True


def get_full_history(title):
    if not LUFFY_HISTORY.exists():
        return []
    conn = sqlite3.connect(str(LUFFY_HISTORY))
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT title, season, episode, ep_name, provider, position_secs, watched_at
        FROM history
        WHERE title = ?
        ORDER BY season, episode
    """, (title,)).fetchall()
    result = [dict(r) for r in rows]
    conn.close()
    return result


from provider import extract_stream

# Track unavailable titles (TMDB IDs that failed extraction)
# {tmdb_id -> timestamp_of_failure}
_unavailable_cache = {}
_UNAVAILABLE_TTL = 86400  # re-check after 24h

def mark_unavailable(tmdb_id):
    if tmdb_id:
        _unavailable_cache[str(tmdb_id)] = time.time()

def is_unavailable(tmdb_id):
    ts = _unavailable_cache.get(str(tmdb_id))
    if ts is None:
        return False
    if time.time() - ts > _UNAVAILABLE_TTL:
        del _unavailable_cache[str(tmdb_id)]
        return False
    return True

def filter_unavailable(data):
    """Remove unavailable titles from TMDB API results."""
    if not isinstance(data, dict) or "results" not in data:
        return data
    data["results"] = [r for r in data["results"] if not is_unavailable(r.get("id"))]
    return data

# Stream proxy: stores active stream info for proxying HLS requests
_active_streams = {}  # stream_id -> {url, referer, user_agent}
_stream_counter = 0
_stream_lock = threading.Lock()


class CatalogHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        params = dict(urllib.parse.parse_qsl(parsed.query))

        if path == "/api/search":
            query = params.get("q", "")
            media_type = params.get("type", "multi")
            page = params.get("page", "1")
            if media_type == "multi":
                data = tmdb_request("/search/multi", {"query": query, "page": page})
            elif media_type == "tv":
                data = tmdb_request("/search/tv", {"query": query, "page": page})
            elif media_type == "movie":
                data = tmdb_request("/search/movie", {"query": query, "page": page})
            else:
                data = tmdb_request("/search/multi", {"query": query, "page": page})
            self._json_response(data)

        elif path == "/api/trending":
            media = params.get("type", "all")
            window = params.get("window", "week")
            page = params.get("page", "1")
            data = tmdb_request(f"/trending/{media}/{window}", {"page": page})
            self._json_response(filter_unavailable(data))

        elif path == "/api/discover":
            media = params.get("type", "tv")
            sort = params.get("sort", "popularity.desc")
            p = {"page": params.get("page", "1"), "sort_by": sort}
            genre = params.get("genre")
            if genre == "awards":
                # Award-caliber content: high ratings + many votes
                p["vote_count.gte"] = "1000"
                p["vote_average.gte"] = "7.5"
                p["sort_by"] = "vote_average.desc"
            elif genre:
                p["with_genres"] = genre
            keyword = params.get("keyword")
            if keyword:
                p["with_keywords"] = keyword
            origin = params.get("origin_country")
            if origin:
                p["with_origin_country"] = origin
            vote_count = params.get("vote_count")
            if vote_count:
                p["vote_count.gte"] = vote_count
            data = tmdb_request(f"/discover/{media}", p)
            self._json_response(filter_unavailable(data))

        elif path == "/api/details":
            media_type = params.get("type", "tv")
            tmdb_id = params.get("id", "")
            data = tmdb_request(f"/{media_type}/{tmdb_id}", {"append_to_response": "seasons,recommendations,similar"})
            self._json_response(data)

        elif path == "/api/season":
            tmdb_id = params.get("id", "")
            season = params.get("season", "1")
            data = tmdb_request(f"/tv/{tmdb_id}/season/{season}")
            self._json_response(data)

        elif path == "/api/genres":
            media = params.get("type", "tv")
            data = tmdb_request(f"/genre/{media}/list")
            self._json_response(data)

        elif path == "/api/history":
            title = params.get("title")
            if title:
                data = get_full_history(title)
            else:
                data = get_history()
            self._json_response(data)

        elif path == "/api/config":
            self._json_response({"has_api_key": bool(get_api_key())})

        elif path.startswith("/api/proxy/"):
            self._handle_proxy(path)

        elif path.startswith("/api/anime"):
            self._handle_anime(path, params)

        elif path.startswith("/api/adult"):
            self._handle_adult(path, params)

        else:
            super().do_GET()

    def do_DELETE(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        params = dict(urllib.parse.parse_qs(parsed.query))
        params = {k: v[0] for k, v in params.items()}

        if path == "/api/history":
            title = params.get("title", "")
            if not title:
                self._json_response({"ok": False, "error": "Title required"}, status=400)
                return
            delete_history(title)
            self._json_response({"ok": True})
        else:
            self.send_error(404)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        length = int(self.headers.get("Content-Length", 0))
        try:
            body = json.loads(self.rfile.read(length)) if length else {}
        except (json.JSONDecodeError, Exception) as e:
            self._json_response({"ok": False, "error": f"Invalid request body: {e}"}, status=400)
            return

        if path == "/api/config":
            cfg = load_config()
            cfg.update(body)
            save_config(cfg)
            self._json_response({"ok": True})

        elif path == "/api/play":
            title = body.get("title", "").strip()
            original_title = body.get("original_title", "").strip()
            season = body.get("season")
            episode = body.get("episode")
            anime = body.get("anime", False)
            tmdb_id = body.get("tmdb_id")
            media_type = body.get("media_type")
            if not title:
                self._json_response({"ok": False, "error": "Title is required"}, status=400)
                return
            if season is not None:
                try:
                    season = int(season)
                    if season < 1:
                        raise ValueError
                except (ValueError, TypeError):
                    self._json_response({"ok": False, "error": "Invalid season number"}, status=400)
                    return
            if episode is not None:
                try:
                    episode = int(episode)
                    if episode < 1:
                        raise ValueError
                except (ValueError, TypeError):
                    self._json_response({"ok": False, "error": "Invalid episode number"}, status=400)
                    return
            try:
                result = extract_stream(title, season, episode, anime=anime,
                                        original_title=original_title or None,
                                        tmdb_id=tmdb_id, media_type=media_type)
            except Exception as e:
                log.exception("extract_stream failed for /api/play")
                self._json_response({"ok": False, "error": f"Stream extraction crashed: {e}"})
                return
            if result.get("url"):
                stream_url = result["url"]
                referer = result.get("referer", "")
                ua = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                cmd = [
                    "mpv", stream_url,
                    f"--referrer={referer}",
                    f"--user-agent={ua}",
                    f"--force-media-title={title}",
                ]
                for sub in result.get("subtitles", []):
                    cmd.append(f"--sub-file={sub}")
                subprocess.Popen(cmd, start_new_session=True,
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                self._json_response({"ok": True, "cmd": f"mpv {title}"})
            else:
                mark_unavailable(tmdb_id)
                self._json_response({"ok": False, "error": result.get("error", "Failed to extract stream")})

        elif path == "/api/stream":
            title = body.get("title", "").strip()
            original_title = body.get("original_title", "").strip()
            season = body.get("season")
            episode = body.get("episode")
            anime = body.get("anime", False)
            tmdb_id = body.get("tmdb_id")
            media_type = body.get("media_type")
            if not title:
                self._json_response({"ok": False, "error": "Title is required"}, status=400)
                return
            if season is not None:
                try:
                    season = int(season)
                    if season < 1:
                        raise ValueError
                except (ValueError, TypeError):
                    self._json_response({"ok": False, "error": "Invalid season number"}, status=400)
                    return
            if episode is not None:
                try:
                    episode = int(episode)
                    if episode < 1:
                        raise ValueError
                except (ValueError, TypeError):
                    self._json_response({"ok": False, "error": "Invalid episode number"}, status=400)
                    return
            try:
                result = extract_stream(title, season, episode, anime=anime,
                                        original_title=original_title or None,
                                        tmdb_id=tmdb_id, media_type=media_type)
            except Exception as e:
                log.exception("extract_stream failed for /api/stream")
                self._json_response({"ok": False, "error": f"Stream extraction crashed: {e}"})
                return
            if result.get("url"):
                global _stream_counter
                with _stream_lock:
                    _stream_counter += 1
                    stream_id = str(_stream_counter)
                    _active_streams[stream_id] = {
                        "url": result["url"],
                        "referer": result.get("referer", ""),
                        "user_agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    }
                result["ok"] = True
                result["proxy_url"] = f"/api/proxy/{stream_id}/master.m3u8"
                result["stream_id"] = stream_id
            else:
                mark_unavailable(tmdb_id)
            self._json_response(result)

        else:
            self.send_error(404)

    def _handle_proxy(self, path):
        """Proxy HLS requests with correct Referer/User-Agent headers."""
        # Path format: /api/proxy/{stream_id}/master.m3u8
        #          or: /api/proxy/{stream_id}/segment/...
        parts = path.split("/")  # ['', 'api', 'proxy', stream_id, ...]
        if len(parts) < 5:
            self.send_error(404)
            return

        stream_id = parts[3]
        stream_info = _active_streams.get(stream_id)
        if not stream_info:
            self.send_error(404, "Stream not found")
            return

        sub_path = "/".join(parts[4:])

        if sub_path == "master.m3u8":
            target_url = stream_info["url"]
        elif sub_path.startswith("url/"):
            # Fully encoded URL
            target_url = urllib.parse.unquote(sub_path[4:])
        else:
            # Resolve relative URL against the master m3u8 URL
            base = stream_info["url"].rsplit("/", 1)[0] + "/"
            target_url = urllib.parse.urljoin(base, sub_path)

        try:
            headers = {
                "User-Agent": stream_info["user_agent"],
                "Referer": stream_info["referer"],
            }
            req = urllib.request.Request(target_url, headers=headers)
            with urllib.request.urlopen(req, timeout=30) as resp:
                content = resp.read()
                content_type = resp.headers.get("Content-Type", "application/octet-stream")

            # Rewrite m3u8 playlists to route through proxy
            if b"#EXTM3U" in content[:20]:
                content = self._rewrite_m3u8(content, stream_id, target_url)
                content_type = "application/vnd.apple.mpegurl"

            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", len(content))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(content)
        except Exception as e:
            self.send_error(502, f"Proxy error: {e}")

    def _rewrite_m3u8(self, content, stream_id, source_url):
        """Rewrite URLs in m3u8 to route through our proxy."""
        base_url = source_url.rsplit("/", 1)[0] + "/"
        lines = content.decode("utf-8", errors="replace").split("\n")
        rewritten = []
        for line in lines:
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                # This is a URL line - make it go through proxy
                if stripped.startswith("http"):
                    # Absolute URL - extract path relative to base
                    rel = stripped
                else:
                    rel = urllib.parse.urljoin(base_url, stripped)
                # Encode the full URL as a path segment
                encoded = urllib.parse.quote(rel, safe="")
                rewritten.append(f"/api/proxy/{stream_id}/url/{encoded}")
            else:
                rewritten.append(line)
        return "\n".join(rewritten).encode("utf-8")

    def _handle_anime(self, path, params):
        if path == "/api/anime/categories":
            cats = []
            for k, v in ANIME_GENRES.items():
                entry = {"id": k, "name": v["name"]}
                cats.append(entry)
            self._json_response(cats)

        elif path == "/api/anime/top":
            page = params.get("page", "1")
            filter_type = params.get("filter", "bypopularity")
            data = jikan_request("/top/anime", {
                "page": page, "filter": filter_type,
                "type": "tv", "sfw": "true",
            })
            self._json_response(data)

        elif path == "/api/anime/season":
            year = params.get("year", "")
            season = params.get("season", "")
            page = params.get("page", "1")
            if year and season:
                data = jikan_request(f"/seasons/{year}/{season}", {
                    "page": page, "sfw": "true",
                })
            else:
                data = jikan_request("/seasons/now", {
                    "page": page, "sfw": "true",
                })
            self._json_response(data)

        elif path == "/api/anime/genre":
            genre_key = params.get("genre", "")
            page = params.get("page", "1")
            order = params.get("order_by", "score")
            min_score = params.get("min_score", "6")
            start_date = params.get("start_date", "")
            genre_info = ANIME_GENRES.get(genre_key)
            if not genre_info:
                self._json_response({"error": "Unknown genre", "data": []})
                return
            req_params = {
                "genres": str(genre_info["id"]),
                "page": page,
                "order_by": order,
                "sort": "desc",
                "sfw": "true",
                "limit": 25,
                "min_score": min_score,
                "type": "tv",
            }
            if start_date:
                req_params["start_date"] = start_date
            data = jikan_request("/anime", req_params)
            self._json_response(data)

        elif path == "/api/anime/search":
            q = params.get("q", "")
            page = params.get("page", "1")
            data = jikan_request("/anime", {
                "q": q, "page": page, "sfw": "true", "limit": 25,
            })
            self._json_response(data)

        elif path == "/api/anime/details":
            mal_id = params.get("id", "")
            data = jikan_request(f"/anime/{mal_id}/full")
            self._json_response(data)

        elif path == "/api/anime/recommendations":
            mal_id = params.get("id", "")
            data = jikan_request(f"/anime/{mal_id}/recommendations")
            self._json_response(data)

        elif path == "/api/anime/schedules":
            day = params.get("day", "")
            p = {"sfw": "true", "kids": "false"}
            if day:
                p["filter"] = day
            data = jikan_request("/schedules", p)
            self._json_response(data)

        else:
            # Default: popular anime
            page = params.get("page", "1")
            data = jikan_request("/top/anime", {
                "page": page, "filter": "bypopularity",
                "type": "tv", "sfw": "true",
            })
            self._json_response(data)

    def _handle_adult(self, path, params):
        from provider.adult import (
            browse_trending, browse_new, browse_popular, browse_top_rated,
            browse_tag, search as adult_search, get_video_info, POPULAR_TAGS
        )
        try:
            if path == "/api/adult/trending":
                self._json_response(browse_trending())

            elif path == "/api/adult/new":
                self._json_response(browse_new())

            elif path == "/api/adult/popular":
                self._json_response(browse_popular())

            elif path == "/api/adult/top":
                self._json_response(browse_top_rated())

            elif path == "/api/adult/tags":
                self._json_response(POPULAR_TAGS)

            elif path == "/api/adult/tag":
                tag = params.get("tag", "")
                if not tag:
                    self._json_response({"error": "Tag required"})
                    return
                self._json_response(browse_tag(tag))

            elif path == "/api/adult/search":
                q = params.get("q", "")
                if not q:
                    self._json_response({"error": "Query required"})
                    return
                self._json_response(adult_search(q))

            elif path == "/api/adult/video":
                slug = params.get("slug", "")
                if not slug:
                    self._json_response({"error": "Slug required"})
                    return
                self._json_response(get_video_info(slug))

            else:
                self._json_response(browse_trending())
        except Exception as e:
            log.exception("Adult API error")
            self._json_response({"error": str(e)})

    def _json_response(self, data, status=200):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        if log.isEnabledFor(logging.DEBUG):
            log.debug(format % args)


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True
    allow_reuse_address = True

def start_server(port):
    server = ThreadedHTTPServer(("0.0.0.0", port), CatalogHandler)
    server.serve_forever()


def start_tunnel(port):
    """Start cloudflared quick tunnel and print the URL."""
    import sys
    try:
        proc = subprocess.Popen(
            ["cloudflared", "tunnel", "--url", f"http://localhost:{port}"],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            bufsize=1
        )
        for line in proc.stdout:
            sys.stderr.write(line)
            sys.stderr.flush()
            match = re.search(r"(https://[a-z0-9-]+\.trycloudflare\.com)", line)
            if match:
                url = match.group(1)
                msg = f"\n{'='*50}\n  LINK PARA CELULAR: {url}\n{'='*50}\n\n"
                sys.stderr.write(msg)
                sys.stderr.flush()
    except FileNotFoundError:
        sys.stderr.write("cloudflared nao encontrado. Instale: sudo pacman -S cloudflared\n")
    except Exception as e:
        sys.stderr.write(f"Erro ao iniciar tunnel: {e}\n")


def main():
    import sys

    debug = "--debug" in sys.argv
    logging.basicConfig(
        level=logging.DEBUG if debug else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    port = int(os.environ.get("PORT", 8888))

    if "--server" in sys.argv:
        local_ip = get_local_ip()
        url = f"http://{local_ip}:{port}"
        print()
        print("  ╔═══════════════════════════════════╗")
        print("  ║          Sunny rodando!           ║")
        print("  ╚═══════════════════════════════════╝")
        print()
        print(f"  Local:    http://localhost:{port}")
        print(f"  Rede:     {url}")
        print()
        _print_qr(url)
        print("  Escaneie o QR code acima com o celular")
        print("  (ambos devem estar na mesma rede WiFi)")
        print()
        if "--tunnel" in sys.argv:
            t_tunnel = threading.Thread(target=start_tunnel, args=(port,), daemon=True)
            t_tunnel.start()
        start_server(port)
    else:
        import webview
        t = threading.Thread(target=start_server, args=(port,), daemon=True)
        t.start()
        webview.create_window(
            "Sunny",
            f"http://127.0.0.1:{port}",
            width=1280,
            height=800,
            min_size=(800, 500),
        )
        webview.start()


def _print_qr(text):
    """Gera QR code ASCII no terminal (sem dependencias externas)."""
    try:
        # Tenta usar qrcode se instalado
        import qrcode  # type: ignore
        qr = qrcode.QRCode(box_size=1, border=1)
        qr.add_data(text)
        qr.make(fit=True)
        # Usa blocos unicode — cada linha combina 2 rows do QR em 1 char
        matrix = qr.get_matrix()
        rows = len(matrix)
        for r in range(0, rows, 2):
            line = "  "
            for c in range(len(matrix[0])):
                top = matrix[r][c]
                bot = matrix[r + 1][c] if r + 1 < rows else False
                if top and bot:
                    line += "\u2588"      # full block
                elif top and not bot:
                    line += "\u2580"      # upper half
                elif not top and bot:
                    line += "\u2584"      # lower half
                else:
                    line += " "
            print(line)
        print()
    except ImportError:
        # Sem qrcode instalado — mostra URL grande e legivel
        print(f"  (instale 'pip install qrcode' para ver QR code no terminal)")
        print()


def get_local_ip():
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "0.0.0.0"


if __name__ == "__main__":
    main()
