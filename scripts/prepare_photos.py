#!/usr/bin/env python3
"""Turn raw photos dropped in products/<name>/inbox/ into feed ready photos.

Each photo is turned upright, cropped from the centre to 4:5, resized to 1080 x 1350,
saved as JPEG in products/<name>/photos/<name>-<n>.jpg, and removed from the inbox.
Works with JPEG, PNG, WebP and iPhone HEIC photos.
"""
import re
import sys
from pathlib import Path

from PIL import Image, ImageOps

try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
except ImportError:
    pass

EXTS = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"}
W, H = 1080, 1350


def next_index(photos_dir, name):
    nums = [int(m.group(1)) for p in photos_dir.glob(f"{name}-*.jpg") if (m := re.fullmatch(rf"{re.escape(name)}-(\d+)\.jpg", p.name))]
    return max(nums, default=0) + 1


def main():
    done = 0
    for inbox in sorted(Path("products").glob("*/inbox")):
        name = inbox.parent.name
        photos = inbox.parent / "photos"
        photos.mkdir(exist_ok=True)
        for src in sorted(inbox.iterdir()):
            if src.suffix.lower() not in EXTS:
                continue
            try:
                im = ImageOps.exif_transpose(Image.open(src)).convert("RGB")
            except Exception as e:
                print(f"SKIPPED {src}: {e}", file=sys.stderr)
                continue
            target = ImageOps.fit(im, (W, H), Image.LANCZOS, centering=(0.5, 0.5))
            out = photos / f"{name}-{next_index(photos, name)}.jpg"
            target.save(out, "JPEG", quality=88, optimize=True)
            src.unlink()
            print(f"{src} -> {out}")
            done += 1
    print(f"{done} photo(s) prepared")


if __name__ == "__main__":
    main()
