# Japan Houses

Daily buy-side scan of athome.co.jp for a house at or under ¥7,500,000 (所有権, 中古一戸建て)
in 軽井沢町 or in Kansai communes within roughly 90 minutes of Osaka with real nature.

The scan runs every morning at 06:30 JST on Robin's Mac mini (launchd job `com.fromanother.japan-houses`
→ `run_mac.sh`, log in `~/Library/Logs/japan-houses.log`) and commits two files:

- `diff.md` — today's changes: nouveaux / baisses / disparus (tier 1 as full cards, the rest as one-liners)
- `ledger.json` — every listing seen under the cap: essential fields, price history, flags, tier, status (~1 MB)
- `tier1.json` — the active tier-1 listings only, same fields (small, quick read)
- `ledger_full.json` — everything, including 備考, agency comment, agency address / licence, reform history

The desk (Grok task "Japan Houses", 07:00 JST) reads these raw URLs:

- https://raw.githubusercontent.com/roluron/japan-houses/main/diff.md
- https://raw.githubusercontent.com/roluron/japan-houses/main/ledger.json (or tier1.json when the full ledger is too heavy to fetch)

## Ledger fields

| field | meaning |
|---|---|
| `price_yen` | current price, from the list page |
| `price_history` | `[{date, price_yen}]`, one entry per change |
| `status` | `new` (first seen today) · `active` · `back` (reappeared) · `gone` (missing today) · `dead` (KILL flag) |
| `tier` | 1 = nature commune, no hard flag · 2 = hard flag (bus / pre-1981 / yellow zone / flood / 調整区域 / unregistered part / damage) · 3 = suburb commune · 0 = KILL |
| `flags` | `pre1981`, `bus`, `suburb`, `yellow_zone`, `flood_zone`, `kanri` (管理費 / 別荘地 / 自治会費), `urbanization_control`, `art43`, `stigmatized`, `unregistered_part` (未登記 extension or outbuilding), `damage` (雨漏り / シロアリ / 傾き) |
| `kill` | `land_right:…` (not 所有権), `leasehold`, `no_rebuild`, `red_zone`, `unregistered_building` (the house itself is 未登記) |
| `keywords` | everything matched in the listing's own text (備考, agency comment, 設備, 都市計画…), informational ones included: `septic`, `sewer`, `well`, `no_minpaku`, `minpaku_ok`, `designated_road`, `akiya_bank`, `disclosure` |
| `ownership` `city_planning` `zoning` `road` `utilities` `remarks` `agency_comment` | copied from the fiche (土地権利 / 都市計画 / 用途地域 / 接道状況 / 設備 / 備考 / 担当コメント) |
| `agency` `agency_tel` `agency_address` `agency_license` | 掲載会社 |
| `kanri_text` | the 管理費 sentence when the fiche mentions one |
| `station_m` | walking distance to the station in metres when stated |
| `fiche_fetched` | last time the fiche was parsed (re-parsed on price change and every 14 days) |

Missing fields mean the fiche did not state them.

## Why the Mac mini and not GitHub Actions

athome's bot check (reese84 / Imperva) fingerprints the browser. What passes: Playwright's bundled headless
shell with a normal Chrome user agent, no automation flags, a persistent profile and 3-5 s between pages
(`JH_CHANNEL=shell`, the default). Installed Google Chrome in new-headless mode gets challenged on the first
page. Plain HTTP clients get blocked after ~100 requests. A block lifts after 10-15 minutes.
`.github/workflows/scan.yml` is kept as a manual fallback (`workflow_dispatch`) only.

## Editing the scope

`communes.json` — add or remove communes (slug = athome URL segment), tag them `nature` or `suburb`,
change `price_cap_yen`. The next run picks it up.

## Running locally

```
python3 scan.py                       # full scan (first run ≈ 2 h for 1 300 fiches, then a few minutes a day)
python3 scan.py kitasaku_karuizawa-city   # one commune (debug)
python3 scan.py --recompute           # re-derive flags / tiers / diff from ledger_full.json, no scan
```

Needs Python 3 and Playwright with Chromium (`pip install playwright && python -m playwright install chromium`):
athome sits behind a JS bot check, so pages are loaded in a headless browser, one at a time, with a pause.
If the bot check still trips, the run stops early, nothing is marked gone, and `meta.errors` says so.

Fiches are fetched only for `nature` communes (suburbs stay at list level: no ownership / zoning / agency detail).
