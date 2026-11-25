#!/usr/bin/env python3
"""Douban recommend (TVBox T4) static generator.
Same logic/output as the T4 server it replaces: home + first MAXPG pages of each class,
written as one bundle (douban/bundle.json). Exit 1 (and write nothing) if validation fails."""
import json, math, os, sys, time, urllib.request, urllib.error

PAGE, MAXPG, MIN_GAP = 30, 10, 0.6
UA = ("Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36")
API = "https://m.douban.com/rexxar/api/v2/subject_collection/{}/items?start={}&count={}"
PIC_REF = "@Referer=https://movie.douban.com/"
CLASSES = [
    ("hot_movie", "热门电影", "movie_hot_gaia"),
    ("hot_tv", "热门剧集", "tv_hot"),
    ("showing", "正在热映", "movie_showing"),
    ("tv_cn", "国产剧", "tv_domestic"),
    ("tv_us", "美剧", "tv_american"),
    ("tv_kr", "韩剧", "tv_korean"),
    ("tv_jp", "日剧", "tv_japanese"),
    ("variety", "综艺", "tv_variety_show"),
    ("anime", "动画", "tv_animation"),
    ("top250", "豆瓣Top250", "movie_top250"),
]
HOME = [("movie_real_time_hotest", 10), ("tv_real_time_hotest", 10)]
_last = [0.0]
stat = {"req": 0, "fail": 0, "codes": {}}


def upstream(coll, start, count):
    req = urllib.request.Request(API.format(coll, start, count), headers={
        "User-Agent": UA, "Referer": "https://m.douban.com/",
        "Accept": "application/json", "Accept-Language": "zh-CN,zh;q=0.9"})
    last = None
    for _ in range(2):
        gap = MIN_GAP - (time.time() - _last[0])
        if gap > 0:
            time.sleep(gap)
        stat["req"] += 1
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                _last[0] = time.time()
                stat["codes"][r.status] = stat["codes"].get(r.status, 0) + 1
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            _last[0] = time.time()
            stat["codes"][e.code] = stat["codes"].get(e.code, 0) + 1
            last = e
            if e.code < 500:
                break
        except Exception as e:
            _last[0] = time.time()
            last = e
        time.sleep(1.5)
    stat["fail"] += 1
    print(f"fail {coll}@{start}: {last}", flush=True)
    return None


def slim(i):
    pic = ((i.get("pic") or {}).get("normal") or (i.get("cover") or {}).get("url") or "")
    r = (i.get("rating") or {}).get("value") or 0
    year = i.get("year") or ""
    remark = f"{r}分" if r else "暂无评分"
    if year:
        remark += f" {year}"
    return {"vod_id": "msearch:" + str(i.get("id") or i.get("title") or ""),
            "vod_name": i.get("title") or "",
            "vod_pic": (pic + PIC_REF) if pic else "",
            "vod_remarks": remark}


def fetch(coll, start, count):
    d = upstream(coll, start, count)
    if not d:
        return {"total": 0, "items": []}
    return {"total": int(d.get("total") or 0),
            "items": [slim(i) for i in (d.get("subject_collection_items") or [])]}


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "douban/bundle.json"
    lst = []
    for coll, n in HOME:
        lst += fetch(coll, 0, n)["items"]
    if not lst:
        lst = fetch("movie_hot_gaia", 0, 20)["items"]
    home = {"class": [{"type_id": t, "type_name": n} for t, n, _ in CLASSES], "filters": {}, "list": lst}
    cats, bad = {}, []
    for tid, _, coll in CLASSES:
        pages = []
        first = fetch(coll, 0, PAGE)
        if not first["items"]:
            bad.append(tid)
            continue
        total = first["total"] or len(first["items"])
        want = min(MAXPG, max(1, math.ceil(total / PAGE)))
        pages.append(first)
        for pg in range(2, want + 1):
            d = fetch(coll, (pg - 1) * PAGE, PAGE)
            if not d["items"]:
                break
            pages.append(d)
        pc = len(pages)
        for pg, d in enumerate(pages, 1):
            cats[f"{tid}_{pg}"] = {"page": pg, "pagecount": pc, "limit": PAGE, "total": total, "list": d["items"]}
    print(f"STAT req={stat['req']} fail={stat['fail']} codes={stat['codes']} home={len(lst)} pages={len(cats)} bad={bad}", flush=True)
    if not lst or bad:
        print("VALIDATION FAIL: not writing", flush=True)
        return 1
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    bundle = {"v": 1, "at": int(time.time()), "home": home, "c": cats}
    with open(out + ".tmp", "w") as f:
        json.dump(bundle, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(out + ".tmp", out)
    note = f"home={len(lst)} pages={len(cats)} req={stat['req']} fail={stat['fail']}"
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            f.write(f"note={note}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
