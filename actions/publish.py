#!/usr/bin/env python3
"""Publica Reel via Meta Graph API. Roda no GitHub Actions ou local.
Uso: python3 publish.py <slug>
Token lê de env META_LONG_TOKEN. Config lê de actions/configs/<slug>.json
"""
import json, os, sys, time, urllib.parse, urllib.request
from pathlib import Path

IG_USER_ID = "17841400260527486"  # @eusouaugusttoleao
GRAPH_VERSION = "v18.0"

BASE = Path(__file__).resolve().parent
CONFIGS = BASE / "configs"


def http_post(url, data):
    body = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(url, data=body, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def http_get(url):
    with urllib.request.urlopen(url, timeout=30) as r:
        return r.status, json.loads(r.read())


def log(msg):
    print(msg, flush=True)


def notify_whatsapp(text):
    """Manda confirmacao via UazAPI."""
    UAZ_URL = "https://aurasellect.uazapi.com/send/text"
    TOKEN = os.environ.get("UAZAPI_TOKEN", "a7a881a1-e914-4e67-af54-0214cfc1aba7")
    payload = json.dumps({"number": "5561985810821", "text": text}).encode()
    req = urllib.request.Request(
        UAZ_URL, data=payload, method="POST",
        headers={"Content-Type": "application/json", "token": TOKEN}
    )
    try:
        urllib.request.urlopen(req, timeout=15)
    except Exception as e:
        log(f"WhatsApp notify failed: {e}")


def publish(slug):
    token = os.environ.get("META_LONG_TOKEN")
    if not token:
        raise SystemExit("META_LONG_TOKEN env var nao definida")

    cfg_path = CONFIGS / f"{slug}.json"
    if not cfg_path.exists():
        raise SystemExit(f"Config nao encontrada: {cfg_path}")
    cfg = json.loads(cfg_path.read_text())
    video_url = cfg["video_url"]
    caption = cfg["caption"]

    log(f"=== publish {slug} ===")
    log(f"video_url: {video_url}")
    log(f"caption_chars: {len(caption)}")

    # 1 · container
    create_url = f"https://graph.facebook.com/{GRAPH_VERSION}/{IG_USER_ID}/media"
    code, resp = http_post(create_url, {
        "media_type": "REELS",
        "video_url": video_url,
        "caption": caption,
        "share_to_feed": "true",
        "access_token": token,
    })
    log(f"POST /media → HTTP {code} · {resp}")
    if code != 200 or "id" not in resp:
        notify_whatsapp(f"❌ Container falhou: {slug}\n{resp}")
        raise SystemExit("Container failed")
    container_id = resp["id"]

    # 2 · poll
    status_url = (
        f"https://graph.facebook.com/{GRAPH_VERSION}/{container_id}"
        f"?fields=status_code,status&access_token={token}"
    )
    for i in range(60):
        time.sleep(5)
        _, status = http_get(status_url)
        sc = status.get("status_code", "?")
        log(f"poll {i+1}/60 → {sc}")
        if sc == "FINISHED":
            break
        if sc in ("ERROR", "EXPIRED"):
            notify_whatsapp(f"❌ Container {sc}: {slug}\n{status}")
            raise SystemExit(sc)
    else:
        notify_whatsapp(f"⏱️ Container timeout: {slug}")
        raise SystemExit("Timeout")

    # 3 · publish
    pub_url = f"https://graph.facebook.com/{GRAPH_VERSION}/{IG_USER_ID}/media_publish"
    code, resp = http_post(pub_url, {
        "creation_id": container_id,
        "access_token": token,
    })
    log(f"POST /media_publish → HTTP {code} · {resp}")
    if code != 200 or "id" not in resp:
        notify_whatsapp(f"❌ Publish falhou: {slug}\n{resp}")
        raise SystemExit("Publish failed")

    media_id = resp["id"]
    log(f"✅ PUBLISHED · media_id={media_id}")
    notify_whatsapp(
        f"✅ Reel publicado · {slug}\n"
        f"media_id: {media_id}\n"
        f"instagram.com/eusouaugusttoleao"
    )
    return media_id


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("uso: publish.py <slug>")
    publish(sys.argv[1])
