#!/usr/bin/env python3
"""Publish due, approved posts from posts.json to Instagram and Facebook.

A post has one or more images. One image makes a normal photo post.
Two or more make an Instagram carousel and a multi photo Facebook post.

Secrets come from environment variables, never from files:
  IG_TOKEN, IG_USER_ID       Instagram posting
  FB_PAGE_TOKEN, FB_PAGE_ID  Facebook page posting
A platform without its secrets is skipped and retried on the next run.

Run with --check to test the secrets without publishing anything.
"""
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone

API = "https://graph.facebook.com/v21.0"
RAW = "https://raw.githubusercontent.com/{repo}/main/{image}"
REPO = os.environ.get("GITHUB_REPOSITORY", "mukitrahman/slowd-media")
POSTS_FILE = "posts.json"
IG_MAX_IMAGES = 10


def call(path, params):
    data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(f"{API}/{path}", data=data, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"{path}: HTTP {e.code} {e.read().decode()}")


def get(path, params):
    url = f"{API}/{path}?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url, timeout=60) as r:
        return json.load(r)


def wait_ready(container_id, token):
    for _ in range(24):
        status = get(container_id, {"fields": "status_code", "access_token": token}).get("status_code")
        if status == "FINISHED":
            return
        if status in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"Instagram could not process the media ({status})")
        time.sleep(5)
    raise RuntimeError("Instagram took too long to process the media")


def post_instagram(image_urls, caption):
    token, user = os.environ.get("IG_TOKEN"), os.environ.get("IG_USER_ID")
    if not token or not user:
        return None
    if len(image_urls) == 1:
        cid = call(f"{user}/media", {"image_url": image_urls[0], "caption": caption, "access_token": token})["id"]
    else:
        if len(image_urls) > IG_MAX_IMAGES:
            raise RuntimeError(f"Instagram allows at most {IG_MAX_IMAGES} images in one post")
        children = []
        for url in image_urls:
            child = call(f"{user}/media", {"image_url": url, "is_carousel_item": "true", "access_token": token})["id"]
            wait_ready(child, token)
            children.append(child)
        cid = call(f"{user}/media", {
            "media_type": "CAROUSEL",
            "children": ",".join(children),
            "caption": caption,
            "access_token": token,
        })["id"]
    wait_ready(cid, token)
    return call(f"{user}/media_publish", {"creation_id": cid, "access_token": token})["id"]


def post_facebook(image_urls, caption):
    token, page = os.environ.get("FB_PAGE_TOKEN"), os.environ.get("FB_PAGE_ID")
    if not token or not page:
        return None
    if len(image_urls) == 1:
        return call(f"{page}/photos", {"url": image_urls[0], "caption": caption, "access_token": token}).get("post_id")
    params = {"message": caption, "access_token": token}
    for i, url in enumerate(image_urls):
        photo = call(f"{page}/photos", {"url": url, "published": "false", "access_token": token})["id"]
        params[f"attached_media[{i}]"] = json.dumps({"media_fbid": photo})
    return call(f"{page}/feed", params)["id"]


def check():
    """Verify secrets work without publishing anything."""
    ok = True
    for label, path, token, field in (
        ("Instagram", os.environ.get("IG_USER_ID"), os.environ.get("IG_TOKEN"), "username"),
        ("Facebook", os.environ.get("FB_PAGE_ID"), os.environ.get("FB_PAGE_TOKEN"), "name"),
    ):
        if not path or not token:
            print(f"{label}: secrets missing")
            ok = False
            continue
        try:
            r = get(path, {"fields": field, "access_token": token})
            print(f"{label}: OK ({r.get(field)})")
        except Exception as e:
            print(f"{label}: FAILED {e}")
            ok = False
    sys.exit(0 if ok else 1)


def images_of(post):
    return post.get("images") or [post["image"]]


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
        urls = [RAW.format(repo=REPO, image=urllib.parse.quote(i)) for i in images_of(p)]
        for platform in p["platforms"]:
            if platform in done:
                continue
            try:
                if platform == "instagram":
                    caption = p["caption"] + ("\n\n" + hashtags if hashtags else "")
                    result = post_instagram(urls, caption)
                else:
                    result = post_facebook(urls, p["caption"])
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
