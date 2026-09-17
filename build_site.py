#!/usr/bin/env python3
"""ledger_full.json + photos.json + pinned.json -> site/index.html.

Everything on the page is French: fr.py translates the athome fields, romanises the
place names and turns the Japanese free text into flagged bullets. The Japanese
address is kept (hidden) so the page can hand it to Google Maps or to an agency.
Thumbnails are embedded as data URIs because published artifacts cannot load
external images.
"""
import json, os, io, sys, time
from concurrent.futures import ThreadPoolExecutor
import urllib.request
import fr

HERE = os.path.dirname(os.path.abspath(__file__))
WEB_BASE = "https://raw.githubusercontent.com/roluron/japan-houses/main/web/"
RATE = 155.65            # JPY per USD, fallback if the daily lookup fails
RATE_DATE = "2026-09-17"


def live_rate():
    """Today's USD/JPY, so prices in dollars do not drift. Falls back on the constant."""
    global RATE, RATE_DATE
    try:
        req = urllib.request.Request("https://api.frankfurter.app/latest?from=USD&to=JPY",
                                     headers={"User-Agent": UA})
        d = json.loads(urllib.request.urlopen(req, timeout=15).read())
        r = float(d["rates"]["JPY"])
        if 80 < r < 400:
            RATE, RATE_DATE = round(r, 2), d.get("date", RATE_DATE)
            print("taux du jour : %.2f ¥/$ (%s)" % (RATE, RATE_DATE))
            return
    except Exception as e:
        pass
    print("taux indisponible, on garde %.2f ¥/$" % RATE)
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36")
# tier -> (thumbnail width, webp quality). Tiers with None get no photo.
THUMB = {9: (420, 60), 1: (380, 58), 2: (190, 50), 3: None, 0: None}
CACHE = os.path.join(HERE, ".thumbcache")

FLAG_FR = {
    "pre1981": ("Construite avant 1981 (ancienne norme sismique)", 1),
    "bus": ("Bus nécessaire pour rejoindre la gare", 1),
    "suburb": ("Commune de banlieue", 0),
    "yellow_zone": ("Zone jaune glissement de terrain", 1),
    "flood_zone": ("Zone inondable", 1),
    "kanri": ("Charges ou redevances annuelles", 1),
    "urbanization_control": ("Zone d'urbanisation restreinte", 1),
    "art43": ("Accès par dérogation art. 43", 2),
    "stigmatized": ("Bien stigmatisé", 2),
    "unregistered_part": ("Annexe non enregistrée au cadastre", 1),
    "damage": ("Dégâts signalés", 1),
    "sabo": ("Zone protection torrentielle / terrassement", 1),
}
KILL_FR = {
    "no_rebuild": "Reconstruction interdite",
    "red_zone": "Zone rouge glissement de terrain",
    "unregistered_building": "Maison non enregistrée au cadastre",
    "leasehold": "Terrain en bail, pas en pleine propriété",
}


def fetch_thumb(args):
    url, width, q = args
    key = os.path.join(CACHE, "%s_%d_%d.webp" % (abs(hash(url)), width, q))
    if os.path.exists(key):
        return open(key, "rb").read()
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        raw = urllib.request.urlopen(req, timeout=25).read()
        from PIL import Image
        im = Image.open(io.BytesIO(raw)).convert("RGB")
        im.thumbnail((width, int(width * 0.95)), Image.LANCZOS)
        buf = io.BytesIO()
        im.save(buf, "WEBP", quality=q, method=5)
        data = buf.getvalue()
        os.makedirs(CACHE, exist_ok=True)
        open(key, "wb").write(data)
        return data
    except Exception:
        return None


def main():
    web = "--web" in sys.argv
    live_rate()
    full = json.load(open(os.path.join(HERE, "ledger_full.json"), encoding="utf-8"))
    photos = {}
    pp = os.path.join(HERE, "photos.json")
    if os.path.exists(pp):
        photos = json.load(open(pp, encoding="utf-8"))

    rows = list(full["items"].values())
    pinned_raw = []
    pj = os.path.join(HERE, "pinned.json")
    if os.path.exists(pj):
        pinned_raw = json.load(open(pj, encoding="utf-8"))

    out = []
    for e in rows:
        if e.get("status") == "gone":
            continue
        out.append(translate(e))
    for e in pinned_raw:
        out.append(translate_pinned(e))

    # --- thumbnails
    imgdir = os.path.join(HERE, "web", "img")
    if web:
        os.makedirs(imgdir, exist_ok=True)
    jobs, idx = [], []
    for i, x in enumerate(out):
        spec = THUMB.get(x["t"])
        if not spec:
            continue
        urls = photos.get(x["i"]) or x.get("_img") or []
        if not urls:
            continue
        jobs.append((urls[0], spec[0], spec[1]))
        idx.append(i)
    print("téléchargement de %d vignettes…" % len(jobs), flush=True)
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=6) as ex:
        for n, (i, data) in enumerate(zip(idx, ex.map(fetch_thumb, jobs))):
            if data:
                if web:
                    name = "img/%s.webp" % out[i]["i"]
                    dest = os.path.join(HERE, "web", name)
                    if not os.path.exists(dest) or open(dest, "rb").read() != data:
                        open(dest, "wb").write(data)
                    out[i]["im"] = name
                else:
                    out[i]["im"] = "data:image/webp;base64," + __import__("base64").b64encode(data).decode()
            if n and n % 200 == 0:
                print("  %d/%d (%.0fs)" % (n, len(jobs), time.time() - t0), flush=True)
    got = sum(1 for x in out if x.get("im"))
    for x in out:
        x.pop("_img", None)

    out.sort(key=lambda x: (x["t"], x["p"] or 0))
    data = {"date": full["meta"]["date"], "cap": full["meta"]["price_cap_yen"],
            "communes": full["meta"]["communes"], "rate": RATE,
            "rate_date": RATE_DATE, "items": out}
    tpl = open(os.path.join(HERE, "site", "tpl.html"), encoding="utf-8").read()

    if web:
        data["imgbase"] = WEB_BASE
        json.dump(data, open(os.path.join(HERE, "web", "data.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, separators=(",", ":"))
        loader = json.dumps({"src": WEB_BASE + "data.json"})
        page = ("<!doctype html>\n<html lang=\"fr\">\n<head>\n"
                "<meta charset=\"utf-8\">\n"
                "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1,viewport-fit=cover\">\n"
                "<meta name=\"robots\" content=\"noindex, nofollow\">\n"
                "<style>:root{padding:env(safe-area-inset-top,0) 0 env(safe-area-inset-bottom,0);"
                "color-scheme:light dark}body{margin:0}img{max-width:100%}[hidden]{display:none!important}</style>\n"
                + tpl.replace("__DATA__", loader) + "\n</body>\n</html>\n")
        # the shared template opens its content right after <head>; close the head first
        page = page.replace("<title>Japan Houses</title>", "<title>Japan Houses — fromanother</title>", 1)
        head_end = page.index("</style>\n\n<header")
        page = page[:head_end + len("</style>")] + "\n</head>\n<body>" + page[head_end + len("</style>"):]
        dest = os.path.join(HERE, "web", "index.html")
        open(dest, "w", encoding="utf-8").write(page)
        dj = os.path.getsize(os.path.join(HERE, "web", "data.json")) / 1024 / 1024
        print("web/ : %d biens, %d photos, page %d KB + data %.2f MB + img/" % (
            len(out), got, os.path.getsize(dest) // 1024, dj))
        return

    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    payload = payload.replace("<", "\\u003c").replace(">", "\\u003e")
    dest = os.path.join(HERE, "site", "index.html")
    open(dest, "w", encoding="utf-8").write(tpl.replace("__DATA__", payload))
    mb = os.path.getsize(dest) / 1024 / 1024
    print("site/index.html : %d biens, %d photos, %.2f MB" % (len(out), got, mb))
    if mb > 15.5:
        print("!! trop lourd pour un artifact (16 MB), baisser THUMB")


def translate(e):
    commune = fr.COMMUNE.get(e["commune"], fr.romaji(e["commune"], joined=True))
    code, gloss = fr.madori(e.get("間取り", ""))
    notes = fr.notes(e.get("remarks"), e.get("agency_comment"), e.get("utilities"),
                     e.get("kanri_text"), e.get("maintenance"))
    flags = []
    for f in e.get("flags", []):
        lb = FLAG_FR.get(f)
        flags.append(list(lb) if lb else [f, 0])
    kill = []
    for k in e.get("kill", []):
        if k.startswith("land_right:"):
            kill.append("Droit du sol : " + fr.simple(k.split(":", 1)[1], fr.OWNERSHIP))
        else:
            kill.append(KILL_FR.get(k, k))
    return {
        "i": e["id"], "p": e["price_yen"], "t": e["tier"], "s": e.get("status"),
        "c": commune, "pfx": fr.PREF.get(e["pref"], e["pref"].title()),
        "ad": fr.address(e.get("所在地", ""), commune), "adj": e.get("所在地", ""),
        "m": code, "mg": gloss, "y": e.get("year_built"),
        "l": e.get("land_m2"), "b": e.get("building_m2"),
        "ac": fr.access(e.get("交通", "")), "sm": e.get("station_m"),
        "ow": fr.simple(e.get("ownership", ""), fr.OWNERSHIP),
        "cp": fr.simple(e.get("city_planning", ""), fr.PLANNING),
        "zn": fr.simple(e.get("zoning", ""), fr.ZONING),
        "rd": fr.road(e.get("road", "")),
        "st": fr.simple(e.get("structure", ""), fr.STRUCT), "fl": fr.floors(e.get("floors", "")),
        "cd": fr.simple(e.get("condition", ""), fr.CONDITION),
        "dl": fr.simple(e.get("transaction", ""), fr.DEAL),
        "ag": fr.agency(e.get("agency") or e.get("agency_card", "")), "tel": e.get("agency_tel", ""),
        "fg": flags, "k": kill, "n": notes, "u": e["url"],
        "ph": [h["price_yen"] for h in e.get("price_history", [])], "fs": e.get("first_seen"),
    }


def translate_pinned(e):
    """pinned.json entries are already in the compact shape used by the old build."""
    code, gloss = fr.madori(e.get("m", ""))
    commune = fr.COMMUNE.get(e.get("c", ""), e.get("c", ""))
    notes = fr.notes(e.get("rm"), e.get("cm"))
    return {
        "i": e["i"], "p": e["p"], "t": 9, "s": "manuel",
        "c": commune, "pfx": fr.PREF.get(e.get("pf", ""), ""),
        "ad": fr.address(e.get("ad", ""), commune), "adj": e.get("ad", ""),
        "m": code, "mg": gloss, "y": e.get("y"), "l": e.get("l"), "b": e.get("b"),
        "ac": fr.access(e.get("ac", "")), "sm": e.get("sm"),
        "ow": fr.simple(e.get("ow", ""), fr.OWNERSHIP),
        "cp": fr.simple(e.get("cp", ""), fr.PLANNING),
        "zn": fr.simple(e.get("zn", ""), fr.ZONING),
        "rd": fr.road(e.get("rd", "")),
        "st": fr.simple(e.get("st", ""), fr.STRUCT), "fl": fr.floors(e.get("fl", "")),
        "cd": "Occupé par le propriétaire", "dl": "Mandat simple",
        "ag": fr.agency(e.get("ag", "")), "tel": e.get("tel", ""),
        "fg": [["Au-dessus du budget de 50 000 $", 1], ["Recul de façade obligatoire : 46,14 m²", 1]],
        "k": [], "n": notes, "u": e["u"],
        "ph": e.get("ph", [e["p"]]), "fs": e.get("fs"),
        "_img": e.get("imgs", []),
    }


if __name__ == "__main__":
    main()
