#!/usr/bin/env python3
"""
Japan Houses — daily athome scan.

Reads communes.json, scans athome 中古一戸建て listings (price ascending) for each
commune, keeps every listing at or under the price cap in ledger.json, fetches the
fiche once (and again on a price change) for ownership / zoning / road / hazard /
agency, computes flags and a tier, and writes diff.md for the day.

Needs Playwright (pages are loaded in a real browser, see Browser below).
"""
import json, re, sys, time, html, datetime, urllib.request, urllib.error, os

BASE = "https://www.athome.co.jp"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0 Safari/537.36")
DELAY = 3.0            # seconds between page loads (+ random 0-2s)
MAX_PAGES = 6          # per commune, 30 listings per page, price ascending
REFRESH_DAYS = 14      # re-fetch a fiche at least every N days
REFRESH_BUDGET = 40    # max routine re-fetches per run (new fiches are never capped)
FICHE_TAGS = {"nature"}  # fetch fiches only for these commune tags (suburbs stay list-level)
GONE_KEEP_DAYS = 60    # drop gone listings from ledger after N days

HERE = os.path.dirname(os.path.abspath(__file__))
TODAY = datetime.date.today().isoformat()

# ---------------------------------------------------------------- http
# athome sits behind a JS bot check (reese84). Plain HTTP clients get a
# 「認証中」 page after a few dozen requests, a real browser does not, so every
# page is loaded in one headless Chromium context, sequentially, with a pause.
import random
from playwright.sync_api import sync_playwright

class Browser:
    """One persistent browser profile (cookies survive between runs, so athome sees a
    returning visitor). Real Google Chrome when installed, Playwright Chromium otherwise.
    JH_HEADED=1 opens a visible window (most robust against the bot check)."""
    def __init__(self):
        self._pw = sync_playwright().start()
        profile = os.path.join(HERE, ".browser-profile")
        headed = os.environ.get("JH_HEADED") == "1"
        common = dict(
            headless=not headed, locale="ja-JP", timezone_id="Asia/Tokyo",
            viewport={"width": 1280, "height": 900},
            args=["--disable-blink-features=AutomationControlled", "--no-first-run", "--no-default-browser-check"],
            ignore_default_args=["--enable-automation"],
        )
        # JH_CHANNEL: "shell" (bundled headless shell, default: the only mode athome tolerates so far),
        # "chromium" (bundled, new headless) or "chrome" (installed Google Chrome: gets bot-checked).
        channel = os.environ.get("JH_CHANNEL", "shell")
        if channel == "shell":
            channel = None
        try:
            probe = self._pw.chromium.launch(channel=channel, headless=True) if channel else self._pw.chromium.launch(headless=True)
        except Exception:
            channel = None
            probe = self._pw.chromium.launch(headless=True)
        try:
            ua = probe.new_context().new_page().evaluate("navigator.userAgent")
        finally:
            probe.close()
        # headless builds announce themselves as "HeadlessChrome": present the normal UA
        common["user_agent"] = ua.replace("HeadlessChrome", "Chrome")
        if channel:
            self._ctx = self._pw.chromium.launch_persistent_context(profile, channel=channel, **common)
        else:
            self._ctx = self._pw.chromium.launch_persistent_context(profile, **common)
        self._page = self._ctx.pages[0] if self._ctx.pages else self._ctx.new_page()
        self._page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined});")
        self.requests = 0
        self.blocked = False

    def get(self, url, must=None, tries=3):
        """Load url, wait until `must` appears in the DOM. Returns (status, url, html)."""
        for i in range(tries):
            try:
                if i == tries - 1 and must:
                    self.blocked = True  # last attempt: if it fails, the run is cut short
                resp = self._page.goto(url, wait_until="domcontentloaded", timeout=60000)
                status = resp.status if resp else 0
                self.requests += 1
                html_ = self._page.content()
                if status in (404, 410):
                    return status, url, html_
                waited = 0
                while must and must not in html_ and waited < 25:
                    if "認証にご協力ください" in html_ and "Click to verify" in html_:
                        pass  # challenge page: give its JS a chance to reload
                    self._page.wait_for_timeout(2500)
                    waited += 2.5
                    html_ = self._page.content()
                time.sleep(DELAY + random.uniform(0, 2))
                if must is None or must in html_:
                    self.blocked = False
                    return status, self._page.url, html_
                if "認証にご協力ください" in html_:
                    # bot check: back off hard, the block usually lifts within minutes
                    self.blocked = True
                    print(f"  bot check on {url}, waiting {120 * (i + 1)}s", flush=True)
                    time.sleep(120 * (i + 1))
                    self.blocked = False
            except Exception as e:
                time.sleep(5 * (i + 1))
        return 0, url, ""

    def close(self):
        try:
            self._ctx.close(); self._pw.stop()
        except Exception:
            pass

BROWSER = None
def get(url, must=None, tries=3):
    global BROWSER
    if BROWSER is None:
        BROWSER = Browser()
    return BROWSER.get(url, must=must, tries=tries)

def clean(x):
    x = re.sub(r"<[^>]+>", " ", x)
    return re.sub(r"\s+", " ", html.unescape(x)).strip()

def yen(txt):
    """'480万円' / '1億2,000万円' / '480' -> int yen"""
    if not txt:
        return None
    t = txt.replace(",", "").replace(" ", "")
    m = re.search(r"(?:(\d+)億)?(\d+(?:\.\d+)?)?万", t)
    if m:
        oku = int(m.group(1)) if m.group(1) else 0
        man = float(m.group(2)) if m.group(2) else 0
        return int(oku * 100_000_000 + man * 10_000)
    m = re.search(r"(\d+(?:\.\d+)?)", t)
    return int(float(m.group(1)) * 10_000) if m else None

def m2(txt):
    m = re.search(r"(\d+(?:\.\d+)?)\s*m", txt or "")
    return float(m.group(1)) if m else None

def built(txt):
    """'1982年8月（築44年2ヶ月）' -> (1982, 8)"""
    m = re.search(r"(\d{4})年(?:(\d{1,2})月)?", txt or "")
    if not m:
        return None, None
    return int(m.group(1)), (int(m.group(2)) if m.group(2) else None)

# ---------------------------------------------------------------- list page
CARD_SPLIT = "<athome-csite-pc-part-bukken-card-ryutsu-sell-living"

def parse_list(body):
    out = []
    for card in body.split(CARD_SPLIT)[1:]:
        m = re.search(r"/kodate/(\d{7,})/", card)
        if not m:
            continue
        item = {"id": m.group(1)}
        pm = re.search(r'class="property-price">\s*(.*?)</div>', card, re.S)
        item["price_yen"] = yen(clean(pm.group(1))) if pm else None
        tm = re.search(r'class="title-wrap__title-text">\s*(.*?)<p', card, re.S)
        item["title"] = clean(tm.group(1)) if tm else ""
        for label, val in re.findall(r"<strong[^>]*>\s*([^<]+?)\s*</strong>\s*<span[^>]*>\s*(.*?)\s*</span>", card, re.S):
            item[label.strip()] = clean(val)
        am = re.search(r'estate-text-area__title-wrap">\s*<a[^>]*>(.*?)</a>', card, re.S)
        item["agency_card"] = clean(am.group(1)) if am else ""
        out.append(item)
    return out

def scan_commune(c, cap):
    """Return listings <= cap for one commune (price ascending pages)."""
    found, errors = [], []
    for page in range(1, MAX_PAGES + 1):
        suffix = "" if page == 1 else f"page{page}/"
        url = f"{BASE}/kodate/chuko/{c['pref']}/{c['slug']}/list/{suffix}?SORT=7"
        st, fu, body = get(url, must="該当物件数")
        if st != 200 or "該当物件数" not in body:
            errors.append(f"{c['slug']} list page {page} HTTP {st}")
            break
        cm = re.search(r"該当物件数\s*(?:<[^>]+>\s*)*([\d,]+)", body)
        total = int(cm.group(1).replace(",", "")) if cm else None
        if total == 0:
            break
        cards = parse_list(body)
        if not cards:
            break
        stop = False
        for it in cards:
            if it["price_yen"] is None:
                continue
            if it["price_yen"] > cap:
                stop = True
                break
            found.append(it)
        if stop or len(cards) < 30:
            break
    return found, errors

# ---------------------------------------------------------------- fiche
LABELS = {
    "土地権利": "ownership", "都市計画": "city_planning", "用途地域": "zoning",
    "接道状況": "road", "設備・サービス": "utilities", "備考": "remarks",
    "取引態様": "transaction", "建物構造": "structure", "現況": "condition",
    "地勢": "terrain", "情報公開日": "published", "次回更新予定日": "next_update",
    "駐車場": "parking", "階建 / 階": "floors", "建物名": "building_name",
    "私道負担面積": "private_road_share", "建ぺい率": "bcr", "容積率": "far",
    "国土法届出": "kokudo", "セットバック": "setback", "引渡可能時期": "handover",
    "リフォーム履歴 【水回り】": "reform_water", "リフォーム履歴 【内装】": "reform_interior",
    "リフォーム履歴 【外装】": "reform_exterior", "瑕疵保険": "defect_insurance",
    "維持費等": "maintenance", "借地期間・地代 （月額）": "leasehold_terms", "権利金": "key_money",
}

KEYWORDS = [
    (r"土砂災害特別警戒区域|レッドゾーン", "red_zone"), (r"土砂災害警戒区域|イエローゾーン", "yellow_zone"),
    (r"浸水想定|浸水区域", "flood_zone"), (r"再建築不可|再建築が?できません|再建築は?不可|再建築は?出来ません", "no_rebuild"),
    (r"借地権|地上権|定期借地", "leasehold"),
    (r"建物未登記|母屋未登記|未登記の建物|建物は未登記|建物（未登記）|主屋未登記", "unregistered_building"),
    (r"未登記", "unregistered_part"),
    (r"管理費|管理規約|別荘地|管理組合|自治会費|環境整備費", "kanri"), (r"民泊不可", "no_minpaku"),
    (r"民泊可|旅館業", "minpaku_ok"), (r"市街化調整区域|調整区域", "urbanization_control"),
    (r"浄化槽", "septic"), (r"下水", "sewer"), (r"井戸", "well"),
    (r"告知事項", "disclosure"), (r"事故物件|心理的瑕疵", "stigmatized"),
    (r"位置指定道路|位置指定有", "designated_road"), (r"但し書き|43条", "art43"),
    (r"雨漏り|シロアリ|白蟻|傾き|腐食", "damage"), (r"空き家バンク", "akiya_bank"),
]
TEXT_FIELDS = ("remarks", "agency_comment", "utilities", "city_planning", "zoning", "road",
               "building_name", "title", "maintenance", "leasehold_terms", "kanri_text", "condition")

def keywords_from(e):
    """Keywords from the listing's own fields only (the whole fiche page carries athome
    boilerplate such as a 借地期間 label row, which produced false positives)."""
    text = " ".join(str(e.get(k) or "") for k in TEXT_FIELDS)
    if e.get("leasehold_terms") and e["leasehold_terms"].strip("－- "):
        text += " 借地権"
    if e.get("ownership") and "所有権" not in e["ownership"]:
        text += " 借地権"
    kw = [tag for pat, tag in KEYWORDS if re.search(pat, text)]
    if "unregistered_building" in kw and "unregistered_part" in kw:
        kw.remove("unregistered_part")
    return sorted(set(kw))

def parse_fiche(body):
    d = {}
    pairs = re.findall(r"<(?:th|dt)[^>]*>(.*?)</(?:th|dt)>\s*<(?:td|dd)[^>]*>(.*?)</(?:td|dd)>", body, re.S)
    seen_agency_addr = False
    for k, v in pairs:
        k, v = clean(k), clean(v)
        if k in LABELS and LABELS[k] not in d:
            d[LABELS[k]] = v
        elif k == "お問合せ先":
            d["agency"] = v
        elif k == "TEL/FAX":
            d["agency_tel"] = v.split("／")[0].replace("TEL", "").strip()
        elif k == "免許番号":
            d["agency_license"] = v
        elif k == "所在地" and v.startswith("〒") and not seen_agency_addr:
            d["agency_address"] = v.replace(" 地図で見る", "")
            seen_agency_addr = True
        elif k == "交通" and "agency_access" not in d and ("バス" in v or "徒歩" in v) and d.get("agency_address"):
            d["agency_access"] = v
    cm = re.search(r'"comment":"((?:[^"\\]|\\.)*)"', body)
    if cm:
        try:
            d["agency_comment"] = json.loads('"' + cm.group(1) + '"')
        except Exception:
            d["agency_comment"] = cm.group(1)
    km = re.search(r"[^。、,，]{0,20}管理費[^。、,，]{0,40}", " ".join(str(d.get(k) or "") for k in ("remarks", "agency_comment", "maintenance")))
    if km:
        d["kanri_text"] = km.group(0)
    d["keywords"] = keywords_from(d)
    return d

# ---------------------------------------------------------------- flags
def compute(entry, commune):
    flags, kill = [], []
    if entry.get("fiche_fetched"):
        entry["keywords"] = keywords_from(entry)
    kws = entry.get("keywords", [])
    own = entry.get("ownership", "") or ""
    if own and "所有権" not in own:
        kill.append(f"land_right:{own}")
    elif "leasehold" in kws:
        kill.append("leasehold")
    if "no_rebuild" in kws:
        kill.append("no_rebuild")
    if "red_zone" in kws:
        kill.append("red_zone")
    if "unregistered_building" in kws:
        kill.append("unregistered_building")
    y, mth = built(entry.get("築年月", ""))
    if y and (y < 1981 or (y == 1981 and (mth or 12) <= 5)):
        flags.append("pre1981")
    acc = entry.get("交通", "") or ""
    if "バス" in acc:
        flags.append("bus")
    if commune["tag"] == "suburb":
        flags.append("suburb")
    for k in ("yellow_zone", "flood_zone", "kanri", "urbanization_control", "art43", "stigmatized", "unregistered_part", "damage"):
        if k in kws:
            flags.append(k)
    m = re.search(r"徒歩\s*(\d[\d,]*)\s*ｍ", acc) or re.search(r"徒歩\s*(\d[\d,]*)\s*m", acc)
    if m:
        entry["station_m"] = int(m.group(1).replace(",", ""))
    else:
        m = re.search(r"徒歩\s*(\d+)\s*分", acc)
        entry["station_m"] = int(m.group(1)) * 80 if m else None
    entry["year_built"] = y
    entry["flags"] = flags
    entry["kill"] = kill
    hard = [f for f in flags if f in ("pre1981", "bus", "yellow_zone", "flood_zone", "urbanization_control", "art43", "stigmatized", "unregistered_part", "damage")]
    if kill:
        entry["tier"] = 0
    elif commune["tag"] == "suburb":
        entry["tier"] = 3
    elif not hard:
        entry["tier"] = 1
    else:
        entry["tier"] = 2
    return entry

# ---------------------------------------------------------------- main
def main():
    cfg = json.load(open(os.path.join(HERE, "communes.json"), encoding="utf-8"))
    cap = int(cfg["price_cap_yen"])
    lpath = os.path.join(HERE, "ledger_full.json")
    ledger = json.load(open(lpath, encoding="utf-8")) if os.path.exists(lpath) else {"meta": {}, "items": {}}
    items = ledger["items"]
    errors, seen_today = [], set()
    new_ids, price_drops, price_ups = [], [], []
    failed_slugs = set()
    refresh_used = 0
    only = [a for a in sys.argv[1:] if not a.startswith("--")]  # optional: slugs to scan (debug)
    t0 = time.time()

    for c in cfg["communes"]:
        if only and c["slug"] not in only:
            continue
        found, errs = scan_commune(c, cap)
        errors += errs
        if errs:
            failed_slugs.add(c["slug"])
        print(f"[{time.time()-t0:5.0f}s] {c['name']:<8} {len(found):>3} sous le cap" + (f"  ERR {errs}" if errs else ""), flush=True)
        if BROWSER and BROWSER.blocked:
            errors.append("athome bot check triggered, scan stopped early")
            break
        for it in found:
            pid = it["id"]
            seen_today.add(pid)
            url = f"{BASE}/kodate/{pid}/"
            prev = items.get(pid)
            base = {
                "id": pid, "url": url, "price_yen": it["price_yen"],
                "pref": c["pref"], "commune": c["name"], "commune_slug": c["slug"],
                "area": c["area"], "commune_tag": c["tag"], "title": it.get("title", ""),
                "間取り": it.get("間取り", ""), "築年月": it.get("築年月", ""),
                "土地面積": it.get("土地面積", ""), "建物面積": it.get("建物面積", ""),
                "所在地": it.get("所在地", ""), "交通": it.get("交通", ""),
                "land_m2": m2(it.get("土地面積", "")), "building_m2": m2(it.get("建物面積", "")),
                "agency_card": it.get("agency_card", ""),
            }
            if prev is None:
                entry = dict(base)
                entry["first_seen"] = TODAY
                entry["price_history"] = [{"date": TODAY, "price_yen": it["price_yen"]}]
                entry["status"] = "new"
                need_fiche = c["tag"] in FICHE_TAGS
                new_ids.append(pid)
            else:
                entry = prev
                entry.update(base)
                old = entry["price_history"][-1]["price_yen"]
                need_fiche = False
                if it["price_yen"] != old:
                    entry["price_history"].append({"date": TODAY, "price_yen": it["price_yen"]})
                    (price_drops if it["price_yen"] < old else price_ups).append((pid, old, it["price_yen"]))
                    need_fiche = True
                if entry.get("status") == "gone":
                    entry["status"] = "back"
                    entry.pop("gone_date", None)
                elif entry.get("status") != "dead":
                    entry["status"] = "active"
                last = entry.get("fiche_fetched")
                if c["tag"] in FICHE_TAGS and (not last or (datetime.date.fromisoformat(TODAY) - datetime.date.fromisoformat(last)).days >= REFRESH_DAYS):
                    if refresh_used < REFRESH_BUDGET:
                        need_fiche = True
                        refresh_used += 1
                need_fiche = need_fiche and c["tag"] in FICHE_TAGS
            entry["last_seen"] = TODAY
            if need_fiche:
                st, fu, body = get(url, must="物件番号")
                if st == 200 and "物件番号" in body:
                    entry.update(parse_fiche(body))
                    entry["fiche_fetched"] = TODAY
                else:
                    errors.append(f"fiche {pid} HTTP {st}")
            compute(entry, c)
            if entry["kill"]:
                entry["status"] = "dead"
            items[pid] = entry

    # gone (skipped when the scan was cut short, so nothing is wrongly marked gone)
    newly_gone = []
    scanned_slugs = {c["slug"] for c in cfg["communes"] if not only or c["slug"] in only}
    n_communes = len(scanned_slugs)
    scanned_slugs -= failed_slugs  # a commune whose list failed today keeps its listings as they were
    if BROWSER and BROWSER.blocked:
        scanned_slugs = set()
    for pid, e in list(items.items()):
        if e.get("commune_slug") not in scanned_slugs:
            continue
        if pid in seen_today:
            continue
        if e.get("status") in ("new", "active", "back", "dead") and e.get("last_seen") != TODAY:
            if e.get("status") != "dead":
                newly_gone.append(pid)
            e["status"] = "gone"
            e["gone_date"] = TODAY
        elif e.get("status") == "gone" and e.get("gone_date"):
            if (datetime.date.fromisoformat(TODAY) - datetime.date.fromisoformat(e["gone_date"])).days > GONE_KEEP_DAYS:
                del items[pid]

    ledger["meta"] = {
        "scanned_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "date": TODAY, "price_cap_yen": cap, "communes": n_communes,
        "seen_today": len(seen_today), "new": len(new_ids), "price_drops": len(price_drops),
        "gone": len(newly_gone), "errors": errors,
        "source": "athome.co.jp 中古一戸建て, SORT=価格が安い順",
    }
    if BROWSER:
        ledger["meta"]["page_loads"] = BROWSER.requests
        BROWSER.close()
    save_ledger(ledger)
    write_diff(ledger, new_ids, price_drops, price_ups, newly_gone, errors)
    print(f"done in {time.time()-t0:.0f}s: {len(seen_today)} sous le cap, {len(new_ids)} nouveaux, {len(price_drops)} baisses, {len(newly_gone)} disparus, erreurs {len(errors)}")


LEAN_FIELDS = ("id", "url", "price_yen", "price_history", "status", "tier", "flags", "kill", "keywords",
               "pref", "commune", "commune_tag", "area", "所在地", "間取り", "築年月", "year_built",
               "土地面積", "建物面積", "land_m2", "building_m2", "交通", "station_m",
               "ownership", "city_planning", "zoning", "road", "structure", "floors", "condition",
               "agency", "agency_tel", "agency_card", "kanri_text", "maintenance", "published",
               "first_seen", "last_seen", "gone_date", "fiche_fetched")

def save_ledger(ledger):
    """ledger_full.json = everything. ledger.json = same items, essential fields only (what the
    desk reads). tier1.json = active tier-1 items only, for a quick read."""
    full = os.path.join(HERE, "ledger_full.json")
    json.dump(ledger, open(full, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    lean = {"meta": ledger["meta"], "items": {i: {k: e[k] for k in LEAN_FIELDS if k in e} for i, e in ledger["items"].items()}}
    json.dump(lean, open(os.path.join(HERE, "ledger.json"), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    t1 = {"meta": ledger["meta"], "items": {i: e for i, e in lean["items"].items() if e.get("tier") == 1 and e.get("status") in ("new", "active", "back")}}
    json.dump(t1, open(os.path.join(HERE, "tier1.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)

def fmt(e):
    p = e.get("price_yen")
    price = f"¥{p:,}" if p else "non indiqué"
    return (f"- **{price}** · {e['commune']} · {e.get('間取り') or 'non indiqué'} · {e.get('築年月') or 'non indiqué'} · "
            f"terrain {e.get('土地面積') or 'non indiqué'} · bât. {e.get('建物面積') or 'non indiqué'}\n"
            f"  - accès : {e.get('交通') or 'non indiqué'}\n"
            f"  - {e.get('所在地') or ''} · 権利 {e.get('ownership') or 'non indiqué'} · {e.get('city_planning') or ''} {e.get('zoning') or ''} · 接道 {e.get('road') or 'non indiqué'}\n"
            f"  - agence : {e.get('agency') or e.get('agency_card') or 'non indiqué'} {('· ' + e['agency_tel']) if e.get('agency_tel') else ''}\n"
            f"  - tier {e.get('tier')} · flags {', '.join(e.get('flags') or []) or 'aucun'}"
            f"{(' · KILL ' + ', '.join(e['kill'])) if e.get('kill') else ''} · mots-clés {', '.join(e.get('keywords') or []) or 'aucun'}\n"
            f"  - {e['url']}")

def line(e):
    p = e.get("price_yen")
    price = f"¥{p:,}" if p else "non indiqué"
    fl = ", ".join(e.get("flags") or []) or "aucun"
    return (f"- {price} · {e['commune']} · {e.get('間取り') or '?'} · {e.get('年') or e.get('year_built') or '?'} · "
            f"terrain {e.get('土地面積') or '?'} · {fl}{(' · KILL ' + ', '.join(e['kill'])) if e.get('kill') else ''} · {e['url']}")

CARDS_MAX = {1: 40, 2: 30, 3: 15, 0: 10}

def write_diff(ledger, new_ids, drops, ups, gone, errors):
    items = ledger["items"]
    meta = ledger["meta"]
    L = [f"# Japan Houses — diff {TODAY}", "",
         f"**{len(new_ids)} nouveaux / {len(drops)} baisses / {len(gone)} disparus** "
         f"(cap ¥{meta['price_cap_yen']:,}, {meta['communes']} communes, {meta['seen_today']} fiches sous le cap aujourd'hui)", ""]
    if new_ids:
        L.append("## Nouveaux")
        for tier in (1, 2, 3, 0):
            grp = sorted([items[i] for i in new_ids if items[i].get("tier") == tier], key=lambda x: x["price_yen"] or 0)
            if not grp:
                continue
            L.append(f"### Tier {tier}{' (KILL)' if tier == 0 else ''} — {len(grp)}")
            shown = grp[:CARDS_MAX[tier]]
            for e in shown:
                L.append(fmt(e) if tier == 1 else line(e))
            if len(grp) > len(shown):
                L.append(f"- … et {len(grp) - len(shown)} autres tier {tier} dans ledger.json (status=new)")
            L.append("")
    else:
        L += ["## Nouveaux", "Rien de neuf aujourd'hui.", ""]
    L.append("## Baisses de prix")
    if drops:
        for pid, old, new in sorted(drops, key=lambda x: (x[2] - x[1]) / x[1]):
            e = items[pid]
            L.append(f"- {e['commune']} {pid} : ¥{old:,} → ¥{new:,} ({(new-old)/old*100:+.1f}%) · tier {e.get('tier')} · {e['url']}")
    else:
        L.append("Aucune.")
    L.append("")
    if ups:
        L.append("## Hausses de prix")
        for pid, old, new in ups:
            e = items[pid]
            L.append(f"- {e['commune']} {pid} : ¥{old:,} → ¥{new:,} · {e['url']}")
        L.append("")
    L.append("## Disparus")
    if gone:
        for pid in gone:
            e = items[pid]
            L.append(f"- {e['commune']} {pid} · ¥{e['price_yen']:,} · {e.get('間取り','')} · tier {e.get('tier')} · {e['url']}")
    else:
        L.append("Aucun.")
    L.append("")
    active = [e for e in items.values() if e.get("status") in ("new", "active", "back")]
    L.append(f"## Stock actif : {len(active)} fiches (tier 1 : {sum(1 for e in active if e.get('tier')==1)}, "
             f"tier 2 : {sum(1 for e in active if e.get('tier')==2)}, tier 3 : {sum(1 for e in active if e.get('tier')==3)}), "
             f"KILL : {sum(1 for e in items.values() if e.get('status')=='dead')}")
    if errors:
        L += ["", "## Erreurs de scan", *[f"- {x}" for x in errors]]
    L.append("")
    open(os.path.join(HERE, "diff.md"), "w", encoding="utf-8").write("\n".join(L))
    hist = os.path.join(HERE, "history")
    os.makedirs(hist, exist_ok=True)
    open(os.path.join(hist, f"{TODAY}.md"), "w", encoding="utf-8").write("\n".join(L))

def recompute():
    """Re-derive keywords / flags / tiers for every entry from stored fields (no scan),
    then rewrite diff.md for today from the ledger's own dates."""
    cfg = json.load(open(os.path.join(HERE, "communes.json"), encoding="utf-8"))
    communes = {c["slug"]: c for c in cfg["communes"]}
    lpath = os.path.join(HERE, "ledger_full.json")
    ledger = json.load(open(lpath, encoding="utf-8"))
    items = ledger["items"]
    for e in items.values():
        c = communes.get(e["commune_slug"], {"tag": e.get("commune_tag", "nature")})
        compute(e, c)
        if e["kill"] and e.get("status") in ("new", "active", "back"):
            e["status"] = "dead"
        elif not e["kill"] and e.get("status") == "dead":
            e["status"] = "active" if e.get("first_seen") != TODAY else "new"
    new_ids = [i for i, e in items.items() if e.get("first_seen") == TODAY]
    drops, ups = [], []
    for i, e in items.items():
        h = e.get("price_history") or []
        if len(h) >= 2 and h[-1]["date"] == TODAY:
            (drops if h[-1]["price_yen"] < h[-2]["price_yen"] else ups).append((i, h[-2]["price_yen"], h[-1]["price_yen"]))
    gone = [i for i, e in items.items() if e.get("gone_date") == TODAY and e.get("status") == "gone"]
    ledger["meta"]["recomputed_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    save_ledger(ledger)
    write_diff(ledger, new_ids, drops, ups, gone, ledger["meta"].get("errors", []))
    print(f"recomputed {len(items)} entries: tiers", {t: sum(1 for e in items.values() if e.get('tier') == t) for t in (1, 2, 3, 0)})

if __name__ == "__main__":
    if "--recompute" in sys.argv:
        recompute()
    else:
        main()
