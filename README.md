# Slowd media

Everything in this repo is public. Never put passwords, tokens or unreleased secrets here.
Tokens live in GitHub Secrets only.

## Folder layout

```
products/
  honeybun/
    details.txt      price, size, materials, mood, buyer, care notes
    photos/          feed ready photos, 1080 x 1350 (4:5), JPEG
    inbox/           drop raw photos here, they are prepared automatically
    captions.json    approved captions for automatic posting
  _template/
    details.txt      copy this for a new product
posts.json           the posting queue for all products
schedule.json        automatic posting switch, days and times
scripts/post.py      publishes due, approved posts
.github/workflows/   runs the script every 30 minutes
```

## Add more photos (no cropping needed)

1. On GitHub, open `products/<product-name>/inbox/`.
2. Click **Add file, then Upload files**, drop in the photos and click **Commit changes**.
3. Within a minute the **Prepare new photos** workflow crops each one to 4:5 (1080 x 1350), saves it in
   `photos/` as `<product-name>-<number>.jpg`, and clears the inbox.

Portrait photos work best, because the crop keeps the centre. Wide photos lose their sides.
iPhone HEIC, PNG and WebP photos work too. Raw originals stay in the repo history, so keep truly private photos out.

## Automatic posting

`schedule.json` controls it. When `"auto"` is `true`, the workflow creates a post for every slot
(Sunday, Wednesday and Friday at 8:30 pm) with 3 or 4 random photos and a random caption from
`products/<name>/captions.json`. It avoids the photos of the last two posts and the captions of the last three.
A caption can list `"requires": ["honeybun-7"]` to make sure the matching photo is always included.
Leave `"auto"` as `false` until the captions are approved. An approved post in `posts.json` close to a slot replaces the automatic one.

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
