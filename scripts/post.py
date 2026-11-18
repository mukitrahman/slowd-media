#!/usr/bin/env python3
"""Publish due, approved posts from posts.json to Instagram and Facebook.

Secrets come from environment variables, never from files:
  IG_TOKEN, IG_USER_ID       Instagram posting
  FB_PAGE_TOKEN, FB_PAGE_ID  Facebook page posting
A platform without its secrets is skipped and retried on the next run.
"""
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone

API = "https://graph.facebook.com/v21.0"
RAW = "https://raw.githubusercontent.com/{repo}/main/{image}"  # image is a path inside the repo
REPO = os.environ.get("GITHUB_REPOSITORY", "mukitrahman/slowd-media")
POSTS_FILE = "posts.json"


def call(path, params):
    data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(f"{API}/{path}", data=data, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        raise RuntimeError(f"{path}: HTTP {e.code} {body}")


def get(path, params):
    url = f"{API}/{path}?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url, timeout=60) as r:
        return json.load(r)


def post_instagram(image_url, caption):
    token, user = os.environ.get("IG_TOKEN"), os.environ.get("IG_USER_ID")
    if not token or not user:
        return None
    container = call(f"{user}/media", {"image_url": image_url, "caption": caption, "access_token": token})
    cid = container["id"]
    for _ in range(12):
        status = get(cid, {"fields": "status_code", "access_token": token}).get("status_code")
        if status == "FINISHED":
            break
        if status == "ERROR":
            raise RuntimeError("Instagram could not process the image")
        time.sleep(5)
    return call(f"{user}/media_publish", {"creation_id": cid, "access_token": token})["id"]


def post_facebook(image_url, caption):
    token, page = os.environ.get("FB_PAGE_TOKEN"), os.environ.get("FB_PAGE_ID")
    if not token or not page:
        return None
    return call(f"{page}/photos", {"url": image_url, "caption": caption, "access_token": token}).get("post_id")


def check():
    """Verify secrets work without publishing anything."""
    ok = True
    for label, path, token, extra in (
        ("Instagram", os.environ.get("IG_USER_ID"), os.environ.get("IG_TOKEN"), "username"),
        ("Facebook", os.environ.get("FB_PAGE_ID"), os.environ.get("FB_PAGE_TOKEN"), "name"),
    ):
        if not path or not token:
            print(f"{label}: secrets missing")
            ok = False
            continue
        try:
            r = get(path, {"fields": extra, "access_token": token})
            print(f"{label}: OK ({r.get(extra)})")
        except Exception as e:
            print(f"{label}: FAILED {e}")
            ok = False
    sys.exit(0 if ok else 1)


def main():
    if "--check" in sys.argv:
        check()
    with open(POSTS_FILE, encoding="utf-8") as f:
        doc = json.load(f)
    now = datetime.now(timezone.utc)
    hashtags = doc.get("instagram_hashtags", "")
    changed = False
    failed = False

    for p in doc["posts"]:
        if not p.get("approved"):
            continue
        if datetime.fromisoformat(p["time"]) > now:
            continue
        done = p.setdefault("posted", {})
        image_url = RAW.format(repo=REPO, image=urllib.parse.quote(p["image"]))
        for platform in p["platforms"]:
            if platform in done:
                continue
            try:
                if platform == "instagram":
                    caption = p["caption"] + ("\n\n" + hashtags if hashtags else "")
                    result = post_instagram(image_url, caption)
                else:
                    result = post_facebook(image_url, p["caption"])
            except Exception as e:  # report, keep going with other platforms
                print(f"FAILED {p['id']} on {platform}: {e}", file=sys.stderr)
                failed = True
                continue
            if result is None:
                print(f"SKIPPED {p['id']} on {platform}: secrets not set")
                continue
            done[platform] = result
            changed = True
            print(f"POSTED {p['id']} on {platform}: {result}")

    if changed:
        with open(POSTS_FILE, "w", encoding="utf-8") as f:
            json.dump(doc, f, ensure_ascii=False, indent=2)
            f.write("\n")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
