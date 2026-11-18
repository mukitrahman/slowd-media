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
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

SCHEDULE_FILE = "schedule.json"
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


DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def latest_slot(slots, now, tz):
    """Most recent scheduled slot at or before now, in the given time zone."""
    local = now.astimezone(tz)
    best = None
    for s in slots:
        hh, mm = map(int, s["time"].split(":"))
        for back in range(8):
            day = (local - timedelta(days=back)).date()
            if DAYS[day.weekday()] != s["day"]:
                continue
            t = datetime(day.year, day.month, day.day, hh, mm, tzinfo=tz)
            if t <= local and (best is None or t > best):
                best = t
            break
    return best


def auto_generate(doc, now):
    """Create the post for the current slot with random photos and a random caption.

    Only runs when schedule.json has "auto": true. Photos from the last two posts
    and captions from the last three are avoided while enough others remain.
    """
    try:
        with open(SCHEDULE_FILE, encoding="utf-8") as f:
            sched = json.load(f)
    except FileNotFoundError:
        return False
    if not sched.get("auto"):
        return False
    tz = ZoneInfo(sched.get("timezone", "Asia/Dhaka"))
    slot = latest_slot(sched["slots"], now, tz)
    if slot is None or now - slot.astimezone(timezone.utc) > timedelta(hours=sched.get("grace_hours", 3)):
        return False
    post_id = "auto-" + slot.strftime("%Y%m%d-%H%M")
    if any(p["id"] == post_id for p in doc["posts"]):
        return False
    # an explicit post close to this slot replaces the automatic one
    for p in doc["posts"]:
        if abs(datetime.fromisoformat(p["time"]) - slot) < timedelta(hours=2):
            return False

    rng = random.SystemRandom()
    product = rng.choice(sched["products"])
    photos = sorted(str(p) for p in Path(f"products/{product}/photos").glob("*.jpg"))
    bank_file = Path(f"products/{product}/captions.json")
    if not photos or not bank_file.exists():
        print(f"AUTO skipped: {product} needs photos and captions.json")
        return False
    bank = json.load(open(bank_file, encoding="utf-8"))

    history = sorted((p for p in doc["posts"] if p.get("product") == product), key=lambda p: p["time"])
    recent_photos = {i for p in history[-2:] for i in images_of(p)}
    recent_caps = {p.get("caption_id") for p in history[-3:]}
    k = min(rng.randint(*sched.get("images_per_post", [3, 4])), len(photos), IG_MAX_IMAGES)
    pool = [p for p in photos if p not in recent_photos]
    if len(pool) < k:
        last = set(images_of(history[-1])) if history else set()
        pool = [p for p in photos if p not in last] or photos
    caps = [c for c in bank if c["id"] not in recent_caps] or bank
    cap = rng.choice(caps)
    # a caption can name photos it needs, for example a desk caption needs the desk photo
    required = [f"products/{product}/photos/{n}.jpg" for n in cap.get("requires", [])]
    required = [p for p in required if p in photos][:k]
    rest = [p for p in pool if p not in required]
    chosen = required + rng.sample(rest, min(k - len(required), len(rest)))

    doc["posts"].append({
        "id": post_id,
        "auto": True,
        "product": product,
        "images": chosen,
        "caption_id": cap["id"],
        "caption": cap["text"],
        "time": slot.isoformat(),
        "platforms": sched.get("platforms", ["instagram", "facebook"]),
        "approved": True,
    })
    print(f"AUTO created {post_id}: {len(chosen)} photos of {product}, caption {cap['id']}")
    return True


def main():
    if "--check" in sys.argv:
        check()
    with open(POSTS_FILE, encoding="utf-8") as f:
        doc = json.load(f)
    now = datetime.now(timezone.utc)
    hashtags = doc.get("instagram_hashtags", "")
    changed = auto_generate(doc, now)
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
