#!/usr/bin/env python3
"""ledger_full.json -> site/index.html (the page published as a Claude artifact).
Run after scan.py, then republish site/index.html to the same artifact URL."""
import json, os
HERE = os.path.dirname(os.path.abspath(__file__))
PINNED = os.path.join(HERE, "pinned.json")  # hand-picked finds outside the scan scope

def trim(s, n):
    return (s or "").strip()[:n]

def main():
    full = json.load(open(os.path.join(HERE, "ledger_full.json"), encoding="utf-8"))
    out = []
    for e in full["items"].values():
        if e.get("status") == "gone":
            continue
        out.append({
            "i": e["id"], "p": e["price_yen"], "c": e["commune"], "a": e["area"], "pf": e["pref"],
            "m": e.get("間取り", ""), "y": e.get("year_built"), "ys": e.get("築年月", ""),
            "l": e.get("land_m2"), "b": e.get("building_m2"),
            "ac": e.get("交通", ""), "sm": e.get("station_m"), "ad": e.get("所在地", ""),
            "ow": e.get("ownership", ""), "cp": e.get("city_planning", ""), "zn": e.get("zoning", ""),
            "rd": e.get("road", ""), "st": e.get("structure", ""), "fl": e.get("floors", ""),
            "ag": e.get("agency") or e.get("agency_card", ""), "tel": e.get("agency_tel", ""),
            "t": e["tier"], "f": e.get("flags", []), "k": e.get("kill", []), "kw": e.get("keywords", []),
            "u": e["url"], "rm": trim(e.get("remarks"), 500), "cm": trim(e.get("agency_comment"), 300),
            "ph": [h["price_yen"] for h in e.get("price_history", [])],
            "s": e.get("status"), "fs": e.get("first_seen"),
        })
    if os.path.exists(PINNED):
        out += json.load(open(PINNED, encoding="utf-8"))
    out.sort(key=lambda x: (x["t"], x["p"] or 0))
    payload = json.dumps({"date": full["meta"]["date"], "cap": full["meta"]["price_cap_yen"],
                          "communes": full["meta"]["communes"], "items": out},
                         ensure_ascii=False, separators=(",", ":"))
    payload = payload.replace("<", "\\u003c").replace(">", "\\u003e")
    tpl = open(os.path.join(HERE, "site", "tpl.html"), encoding="utf-8").read()
    open(os.path.join(HERE, "site", "index.html"), "w", encoding="utf-8").write(tpl.replace("__DATA__", payload))
    print(f"site/index.html: {len(out)} biens, {os.path.getsize(os.path.join(HERE,'site','index.html'))//1024} KB")

if __name__ == "__main__":
    main()
