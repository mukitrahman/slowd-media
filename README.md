# Slowd media

Everything in this repo is public. Never put passwords, tokens or unreleased secrets here.
Tokens live in GitHub Secrets only.

## Folder layout

```
products/
  honeybun/
    details.txt      price, size, materials, mood, buyer, care notes
    photos/          feed ready photos, 1080 x 1350 (4:5), JPEG
  _template/
    details.txt      copy this for a new product
posts.json           the posting queue for all products
scripts/post.py      publishes due, approved posts
.github/workflows/   runs the script every 30 minutes
```

## Add a new product

1. Copy `products/_template` to `products/<product-name>` (lowercase, no spaces).
2. Fill in `details.txt`.
3. Add photos to `products/<product-name>/photos/` as JPEG, 1080 x 1350, named `<product-name>-1.jpg` and so on.
4. Add posts to `posts.json` with `"image": "products/<product-name>/photos/<file>.jpg"`.

## Photo rules

Instagram only accepts photos between 4:5 and 1.91:1. Use 1080 x 1350 for portrait photos.
Keep raw originals on your own computer. Only feed ready copies go here.

## Posts

A post goes out when `approved` is `true` and its `time` has passed. Times use Asia/Dhaka (+06:00).

Use `"images": [ ... ]` with 2 to 10 photos of the same product. That becomes an Instagram carousel
and a multi photo Facebook post. Use `"image": "..."` for a single photo.

## Schedule

Three posts a week: Sunday, Wednesday and Friday at 8:30 pm Dhaka time.
Review the Instagram and Facebook insights after three weeks and adjust the days or times.

## Testing

Actions, Post to Slowd, Run workflow with `check` ticked. It tests the secrets and posts nothing.
