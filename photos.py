#!/usr/bin/env python3
"""Collect listing photo URLs from athome list pages -> photos.json {id: [urls]}.
Cards lazy-load their images, so each page is scrolled before the DOM is read."""
import json, re, os, time
import scan

HERE = os.path.dirname(os.path.abspath(__file__))
IMG_RX = re.compile(r"image_files/path/([A-Za-z0-9_=+\-]+)")


def main():
    cfg = json.load(open(os.path.join(HERE, "communes.json"), encoding="utf-8"))
    cap = int(cfg["price_cap_yen"])
    path = os.path.join(HERE, "photos.json")
    out = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else {}
    t0 = time.time()
    for c in cfg["communes"]:
        for page in range(1, 7):
            suffix = "" if page == 1 else "page%d/" % page
            url = "%s/kodate/chuko/%s/%s/list/%s?SORT=7" % (scan.BASE, c["pref"], c["slug"], suffix)
            st, fu, body = scan.get(url, must="該当物件数")
            if st != 200 or "該当物件数" not in body:
                print("  ERR", c["slug"], page, st, flush=True)
                break
            pg = scan.BROWSER._page
            try:
                for _ in range(12):
                    pg.mouse.wheel(0, 1500)
                    pg.wait_for_timeout(250)
                pg.wait_for_timeout(900)
                body = pg.content()
            except Exception as e:
                print("  scroll fail", e, flush=True)
            cards = body.split(scan.CARD_SPLIT)[1:]
            if not cards:
                break
            stop = False
            for card in cards:
                m = re.search(r"/kodate/(\d{7,})/", card)
                if not m:
                    continue
                pm = re.search(r'class="property-price">\s*(.*?)</div>', card, re.S)
                price = scan.yen(scan.clean(pm.group(1))) if pm else None
                if price is None:
                    continue
                if price > cap:
                    stop = True
                    break
                imgs = []
                for u in IMG_RX.findall(card):
                    full = "https://www.athome.co.jp/image_files/path/" + u
                    if full not in imgs:
                        imgs.append(full)
                if imgs:
                    out[m.group(1)] = imgs[:4]
            if stop or len(cards) < 30:
                break
        print("[%5.0fs] %-10s total %d" % (time.time() - t0, c["name"], len(out)), flush=True)
        json.dump(out, open(path, "w"), separators=(",", ":"))
    if scan.BROWSER:
        scan.BROWSER.close()
    print("done", len(out), "listings with photos")


if __name__ == "__main__":
    main()
