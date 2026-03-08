"""Stream decryption for megacloud, embed.su, and generic embeds."""

import base64
import json
import re
import time
import threading
import urllib.parse
import urllib.request

from .http import UA, get, get_json

# Cache megacloud key (changes rarely, no need to fetch every request)
_megacloud_key_cache = {"key": "", "ts": 0}
_megacloud_key_lock = threading.Lock()
_MEGACLOUD_KEY_TTL = 600  # 10 minutes


def decrypt_stream(embed_url):
    """Route to the appropriate decryptor. Returns {url, referer, subtitles}."""
    if any(x in embed_url for x in ["megacloud.", "videostr.net", "streameeeeee.site", "streamaaa.top"]):
        return decrypt_megacloud(embed_url)
    if "embed.su" in embed_url:
        return decrypt_embedsu(embed_url)
    return decrypt_generic(embed_url)


def decrypt_generic(embed_url):
    """Try to extract m3u8 URL from page source."""
    parsed = urllib.parse.urlparse(embed_url)
    referer = f"{parsed.scheme}://{parsed.netloc}/"
    try:
        html = get(embed_url, referer=referer)
    except Exception as e:
        return {"error": str(e)}

    for pattern in [
        r"source:\s*['\"]([^'\"]+\.m3u8[^'\"]*)['\"]",
        r"file:\s*['\"]([^'\"]+\.m3u8[^'\"]*)['\"]",
        r"src:\s*['\"]([^'\"]+\.m3u8[^'\"]*)['\"]",
        r"['\"]([^'\"]*\.m3u8[^'\"]*)['\"]",
    ]:
        m = re.search(pattern, html)
        if m:
            return {"url": m.group(1), "referer": referer, "subtitles": []}

    return {"error": "Could not extract m3u8 from embed page"}


def decrypt_megacloud(embed_url):
    """Decrypt megacloud/rabbitstream sources."""
    parsed = urllib.parse.urlparse(embed_url)
    referer = f"{parsed.scheme}://{parsed.netloc}/"

    video_id = parsed.path.rsplit("/", 1)[-1]
    if "?" in video_id:
        video_id = video_id.split("?")[0]

    # Fetch embed page and megacloud key in parallel
    html_result = [None, None]  # [html, error]
    key_result = [None]

    def fetch_html():
        try:
            html_result[0] = get(embed_url, referer=referer)
        except Exception as e:
            html_result[1] = e

    def fetch_key():
        key_result[0] = _fetch_megacloud_key()

    t_html = threading.Thread(target=fetch_html)
    t_key = threading.Thread(target=fetch_key)
    t_html.start()
    t_key.start()
    t_html.join()
    t_key.join()

    if html_result[1]:
        return {"error": f"Failed to load megacloud page: {html_result[1]}"}
    html = html_result[0]

    client_key = _extract_client_key(html)
    if not client_key:
        return {"error": "Could not extract client key"}

    megacloud_key = key_result[0]
    if not megacloud_key:
        return {"error": "Could not fetch megacloud key"}

    api_url = f"{parsed.scheme}://{parsed.netloc}/embed-1/v3/e-1/getSources?id={video_id}&_k={client_key}"
    try:
        data = get_json(api_url, referer=embed_url, extra_headers={
            "X-Requested-With": "XMLHttpRequest",
        })
    except Exception as e:
        return {"error": f"getSources API failed: {e}"}

    sources = []
    if data.get("encrypted") and isinstance(data.get("sources"), str):
        decrypted = _decrypt_megacloud_src(data["sources"], client_key, megacloud_key)
        try:
            sources = json.loads(decrypted)
        except json.JSONDecodeError:
            return {"error": "Failed to decrypt sources"}
    elif isinstance(data.get("sources"), list):
        sources = data["sources"]

    subtitles = []
    for track in data.get("tracks", []):
        kind = track.get("kind", "")
        label = track.get("label", "").lower()
        if kind in ("captions", "subtitles"):
            if "english" in label or "eng" in label or "portuguese" in label or "portu" in label:
                subtitles.append(track["file"])

    for src in sources:
        if ".m3u8" in src.get("file", ""):
            return {"url": src["file"], "referer": referer, "subtitles": subtitles}

    if sources and sources[0].get("file"):
        return {"url": sources[0]["file"], "referer": referer, "subtitles": subtitles}

    return {"error": "No m3u8 source found in megacloud"}


def decrypt_embedsu(embed_url):
    """Decrypt embed.su sources."""
    try:
        html = get(embed_url, referer="https://embed.su/")
    except Exception as e:
        return {"error": str(e)}

    m = re.search(r"window\.vConfig\s*=\s*JSON\.parse\(atob\(['\"]([A-Za-z0-9+/=]+)['\"]\)\)", html)
    if not m:
        return {"error": "Could not find vConfig in embed.su"}

    try:
        config = json.loads(base64.b64decode(m.group(1)))
    except Exception:
        return {"error": "Failed to decode vConfig"}

    hash_val = config.get("hash", "")
    if not hash_val:
        return {"error": "No hash in vConfig"}

    parts = hash_val.split(".")
    if len(parts) != 2:
        return {"error": "Invalid hash format"}

    try:
        d1 = base64.b64decode(parts[0]).decode()
        d2 = base64.b64decode(parts[1]).decode()
    except Exception:
        return {"error": "Failed to decode hash parts"}

    combined = d1[::-1] + d2[::-1]
    try:
        server_hash = base64.b64decode(combined).decode()
    except Exception:
        return {"error": "Failed to decode server hash"}

    api_hash = server_hash.split(".")[0]
    api_url = f"https://embed.su/api/e/{api_hash}"

    try:
        data = get_json(api_url, referer=embed_url)
    except Exception as e:
        return {"error": f"embed.su API failed: {e}"}

    subtitles = []
    for sub in data.get("subtitles", []):
        label = sub.get("label", "").lower()
        if "english" in label or "eng" in label or "portugu" in label:
            subtitles.append(sub["file"])

    source = data.get("source", "")
    if source:
        return {"url": source, "referer": "https://embed.su/", "subtitles": subtitles}

    return {"error": "No source in embed.su response"}


# --- Internal helpers ---

def _extract_client_key(html):
    patterns = [
        r'<meta\s+name="_gg_fb"\s+content="([^"]+)"',
        r'window\._xy_ws\s*=\s*"([^"]+)"',
        r"window\._xy_ws\s*=\s*'([^']+)'",
        r'<!--\s*_is_th:([0-9a-zA-Z]+)\s+-->',
        r'<div[^>]+data-dpi="([^"]+)"',
    ]
    for p in patterns:
        m = re.search(p, html)
        if m:
            return m.group(1)

    m = re.search(r'window\._lk_db\s*=\s*\{[^}]*x:\s*"([^"]+)"[^}]*y:\s*"([^"]+)"[^}]*z:\s*"([^"]+)"[^}]*\}', html)
    if m:
        return m.group(1) + m.group(2) + m.group(3)

    return ""


def _fetch_megacloud_key():
    # Return cached key if fresh
    with _megacloud_key_lock:
        if _megacloud_key_cache["key"] and (time.time() - _megacloud_key_cache["ts"]) < _MEGACLOUD_KEY_TTL:
            return _megacloud_key_cache["key"]

    key_urls = [
        ("https://raw.githubusercontent.com/yogesh-hacker/MegacloudKeys/refs/heads/main/keys.json", "json"),
        ("https://raw.githubusercontent.com/itzzzme/megacloud-keys/refs/heads/main/key.txt", "text"),
    ]
    for url, fmt in key_urls:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=10) as resp:
                body = resp.read().decode()
            if fmt == "json":
                data = json.loads(body)
                if data.get("mega"):
                    with _megacloud_key_lock:
                        _megacloud_key_cache["key"] = data["mega"]
                        _megacloud_key_cache["ts"] = time.time()
                    return data["mega"]
            else:
                key = body.strip()
                if key:
                    with _megacloud_key_lock:
                        _megacloud_key_cache["key"] = key
                        _megacloud_key_cache["ts"] = time.time()
                    return key
        except Exception:
            continue
    return ""


def _decrypt_megacloud_src(src, client_key, megacloud_key):
    dec_src = base64.b64decode(src)

    char_array = [chr(32 + i) for i in range(95)]
    gen_key = _megacloud_keygen(megacloud_key, client_key)

    for layer in range(3, 0, -1):
        layer_key = gen_key + str(layer)
        text = dec_src.decode("latin-1") if isinstance(dec_src, bytes) else dec_src
        text = _seed_shift(text, layer_key, char_array)
        text = _columnar_decrypt(text, layer_key)
        text = _substitution_decrypt(text, layer_key, char_array)
        dec_src = text

    result = dec_src if isinstance(dec_src, str) else dec_src.decode("latin-1")
    if len(result) < 4:
        return result
    data_len = int(result[:4])
    return result[4:4 + data_len]


def _megacloud_keygen(megacloud_key, client_key):
    temp_key = megacloud_key + client_key

    hash_val = 0
    for ch in temp_key:
        hash_val = ord(ch) + hash_val * 31 + (hash_val << 7) - hash_val
        hash_val &= 0xFFFFFFFFFFFFFFFF

    xored = bytes([ord(c) ^ 247 for c in temp_key])

    pivot = (hash_val % len(temp_key)) + 5
    if pivot > len(xored):
        pivot = pivot % len(xored)
    shifted = xored[pivot:] + xored[:pivot]

    leaf_str = client_key[::-1]
    shifted_str = shifted.decode("latin-1")

    return_key = ""
    for i in range(max(len(shifted_str), len(leaf_str))):
        if i < len(shifted_str):
            return_key += shifted_str[i]
        if i < len(leaf_str):
            return_key += leaf_str[i]

    key_len = 96 + (hash_val % 33)
    if key_len > len(return_key):
        key_len = len(return_key)
    return_key = return_key[:key_len]

    normalized = "".join(chr((ord(c) % 95) + 32) for c in return_key)
    return normalized


def _hash_key(key):
    h = 0
    for ch in key:
        h = (h * 31 + ord(ch)) & 0xFFFFFFFF
    return h


def _seed_shift(src, key, char_array):
    seed = _hash_key(key)
    char_to_idx = {c: i for i, c in enumerate(char_array)}
    result = []
    for ch in src:
        idx = char_to_idx.get(ch, -1)
        if idx == -1:
            result.append(ch)
            continue
        seed = (seed * 1103515245 + 12345) & 0x7FFFFFFF
        rand_num = seed % 95
        new_idx = (idx - rand_num + 95) % 95
        result.append(char_array[new_idx])
    return "".join(result)


def _columnar_decrypt(src, key):
    col_count = len(key)
    row_count = (len(src) + col_count - 1) // col_count

    key_map = sorted(enumerate(key), key=lambda x: x[1])

    grid = [['' for _ in range(col_count)] for _ in range(row_count)]

    src_idx = 0
    for orig_idx, _ in key_map:
        for r in range(row_count):
            if src_idx < len(src):
                grid[r][orig_idx] = src[src_idx]
                src_idx += 1

    result = []
    for r in range(row_count):
        for c in range(col_count):
            if grid[r][c]:
                result.append(grid[r][c])
    return "".join(result)


def _seed_shuffle(arr, key):
    result = list(arr)
    seed = _hash_key(key)
    for i in range(len(result) - 1, 0, -1):
        seed = (seed * 1103515245 + 12345) & 0x7FFFFFFF
        j = seed % (i + 1)
        result[i], result[j] = result[j], result[i]
    return result


def _substitution_decrypt(src, key, char_array):
    shuffled = _seed_shuffle(char_array, key)
    char_map = {shuffled[i]: char_array[i] for i in range(len(char_array))}
    return "".join(char_map.get(ch, ch) for ch in src)
