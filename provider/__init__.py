"""Provider package — search, select, and extract streams."""

import logging
import time
import threading

from .flixhq import search, get_media_id, get_seasons, get_episodes, get_servers, get_link
from .embeds import extract_by_tmdb_id
from .decrypt import decrypt_stream

log = logging.getLogger("sunny")

# Cache resolved media info to speed up episode navigation and re-plays
# Key: title_lower -> {media_id, seasons, url, type, title, ts}
_media_cache = {}
_MEDIA_CACHE_TTL = 1800  # 30 minutes

# Cache search results
_search_cache = {}
_SEARCH_CACHE_TTL = 600  # 10 minutes


def _select_best(results, title_lower, anime=False):
    """Pick best match from search results."""
    if anime:
        def score(r):
            t = r["title"].lower()
            s = 0
            if t == title_lower:
                s += 100
            elif title_lower in t:
                s += 50
            if r["type"] == "series":
                s += 20
            if "dub" in t:
                s -= 30
            if "sub" in t:
                s += 10
            s -= abs(len(t) - len(title_lower))
            return s
        return max(results, key=score)
    else:
        for r in results:
            if r["title"].lower() == title_lower:
                return r
        return results[0]


def _extract_via_flixhq(title, season, episode, anime, original_title):
    """FlixHQ pipeline: search -> select -> get stream URL."""
    title_lower = title.lower()

    # --- Phase 1: Resolve media (cached or fresh) ---
    cached = _media_cache.get(title_lower)
    if cached and (time.time() - cached["ts"]) < _MEDIA_CACHE_TTL:
        selected = {"url": cached["url"], "type": cached["type"], "title": cached["title"]}
        media_id = cached["media_id"]
        cached_seasons = cached.get("seasons")
    else:
        # Search (with cache), try original_title as fallback
        search_cached = _search_cache.get(title_lower)
        if search_cached and (time.time() - search_cached["ts"]) < _SEARCH_CACHE_TTL:
            results = search_cached["data"]
        else:
            results = search(title)
            if not results and original_title and original_title.lower() != title_lower:
                results = search(original_title)
            if results:
                _search_cache[title_lower] = {"data": results, "ts": time.time()}
        if not results:
            return {"error": f"No results found for '{title}'"}

        selected = _select_best(results, title_lower, anime)

        # Fetch media_id for best match + prefetch for runner-up in parallel
        media_id = None
        media_id_err = None
        runner_up = results[1] if len(results) > 1 else None

        def fetch_main():
            nonlocal media_id, media_id_err
            try:
                media_id = get_media_id(selected["url"])
            except Exception as e:
                media_id_err = e

        def fetch_runner():
            if runner_up:
                try:
                    rid = get_media_id(runner_up["url"])
                    _media_cache[runner_up["title"].lower()] = {
                        "media_id": rid, "url": runner_up["url"],
                        "type": runner_up["type"], "title": runner_up["title"],
                        "ts": time.time(),
                    }
                except Exception:
                    pass

        t1 = threading.Thread(target=fetch_main)
        t2 = threading.Thread(target=fetch_runner)
        t1.start()
        t2.start()
        t1.join()
        t2.join(timeout=0.1)

        if media_id_err:
            return {"error": f"Failed to get media ID: {media_id_err}"}

        cached_seasons = None
        _media_cache[title_lower] = {
            "media_id": media_id, "url": selected["url"],
            "type": selected["type"], "title": selected["title"],
            "ts": time.time(),
        }

    # --- Phase 2: Get episode/server info ---
    if selected["type"] == "series" and season:
        if cached_seasons is not None:
            seasons_list = cached_seasons
        else:
            try:
                seasons_list = get_seasons(media_id)
            except Exception as e:
                return {"error": f"Failed to get seasons: {e}"}
            if title_lower in _media_cache:
                _media_cache[title_lower]["seasons"] = seasons_list

        if not seasons_list:
            return {"error": "No seasons found"}

        s_idx = max(0, min(int(season) - 1, len(seasons_list) - 1))
        season_id = seasons_list[s_idx]["id"]

        try:
            episodes = get_episodes(season_id, is_season=True)
        except Exception as e:
            return {"error": f"Failed to get episodes: {e}"}
        if not episodes:
            return {"error": "No episodes found"}

        e_idx = max(0, min(int(episode) - 1, len(episodes) - 1)) if episode else 0
        ep_id = episodes[e_idx]["id"]

        try:
            servers = get_servers(ep_id)
        except Exception as e:
            return {"error": f"Failed to get servers: {e}"}
    else:
        try:
            episodes = get_episodes(media_id, is_season=False)
        except Exception as e:
            return {"error": f"Failed to get movie servers: {e}"}
        if not episodes:
            return {"error": "No movie servers found"}
        servers = [{"id": ep["id"], "name": ep["name"]} for ep in episodes]

    if not servers:
        return {"error": "No servers found"}

    # --- Phase 3: Get embed links in parallel, prefer Vidcloud ---
    preferred_order = sorted(servers, key=lambda s: 0 if "vidcloud" in s["name"].lower() else 1)

    embed_links = {}
    def fetch_link(srv):
        try:
            embed_links[srv["id"]] = get_link(srv["id"])
        except Exception:
            embed_links[srv["id"]] = ""

    threads = [threading.Thread(target=fetch_link, args=(s,)) for s in preferred_order]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # --- Phase 4: Decrypt first working server ---
    result = {"error": "No servers available"}
    for s in preferred_order:
        link = embed_links.get(s["id"], "")
        if not link:
            continue
        result = decrypt_stream(link)
        if not result.get("error"):
            break

    result["title"] = selected["title"]
    result["media_type"] = selected["type"]

    if selected["type"] == "series" and season:
        result["season"] = int(season)
        result["episode"] = int(episode) if episode else 1
        result["total_episodes"] = len(episodes)

    return result


def extract_stream(title, season=None, episode=None, anime=False, original_title=None,
                   tmdb_id=None, media_type=None):
    """Extract stream URL. Tries fast embed providers first, falls back to FlixHQ scraping."""

    # If we have a TMDB ID, race embed providers against FlixHQ
    if tmdb_id:
        embed_result = [None]
        flixhq_result = [None]

        # Map media_type: frontend sends "movie"/"tv", embeds expect "movie"/"tv"
        embed_type = media_type or ("movie" if not season else "tv")

        def try_embeds():
            try:
                embed_result[0] = extract_by_tmdb_id(
                    tmdb_id, media_type=embed_type, season=season, episode=episode
                )
            except Exception as e:
                log.debug("Embed providers failed: %s", e)
                embed_result[0] = {"error": str(e)}

        def try_flixhq():
            try:
                flixhq_result[0] = _extract_via_flixhq(
                    title, season, episode, anime, original_title
                )
            except Exception as e:
                log.debug("FlixHQ failed: %s", e)
                flixhq_result[0] = {"error": str(e)}

        # Start both in parallel
        t_embed = threading.Thread(target=try_embeds)
        t_flixhq = threading.Thread(target=try_flixhq)
        t_embed.start()
        t_flixhq.start()

        # Wait for embed first (typically ~2-3s)
        t_embed.join(timeout=10)

        if embed_result[0] and embed_result[0].get("url"):
            log.debug("Embed provider succeeded")
            result = embed_result[0]
            result["title"] = title
            result["media_type"] = embed_type
            if season:
                result["season"] = int(season)
                result["episode"] = int(episode) if episode else 1
            return result

        # Embed failed — wait for FlixHQ
        log.debug("Embed providers failed, waiting for FlixHQ fallback")
        t_flixhq.join(timeout=25)

        if flixhq_result[0] and flixhq_result[0].get("url"):
            return flixhq_result[0]

        # Both failed — return best error
        if flixhq_result[0]:
            return flixhq_result[0]
        if embed_result[0]:
            return embed_result[0]
        return {"error": "All providers failed"}

    # No TMDB ID — FlixHQ only (anime, history, etc.)
    return _extract_via_flixhq(title, season, episode, anime, original_title)
