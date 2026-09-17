#!/usr/bin/env python3
"""Japanese -> French for the Japan Houses site. Nothing Japanese reaches the page
except the address, kept for copy-paste to agencies and Google Maps."""
import re, unicodedata
import pykakasi

_kks = pykakasi.kakasi()

def half(s):
    return unicodedata.normalize("NFKC", s or "").strip()

LONG = [(re.compile(r"ou(?![aeiou])"), "ō"), (re.compile(r"oo(?![aeiou])"), "ō"),
        (re.compile(r"uu(?![aeiou])"), "ū"), (re.compile(r"aa(?![aeiou])"), "ā"),
        (re.compile(r"ee(?![aeiou])"), "ē")]
# names French readers already know without macrons, plus katakana brands
NAME_FIX = {"Ōsaka":"Osaka","Kyōto":"Kyoto","Kōbe":"Kobe","Tōkyō":"Tokyo","Ōsakasen":"Osaka",
            "Hokurikushinkansen":"Hokuriku","Senchurii":"Century","Hausudou":"House Do",
            "Hausudō":"House Do","Hausu":"House","Hōmu":"Home","Hoomu":"Home","Ribaburu":"Livable",
            "Fudōsan":"Fudōsan","Pitattohausu":"Pitat House","Eeburu":"Able","Maaketto":"Market",
            "Māketto":"Market","Riaruto":"Realty","Esuteeto":"Estate","Esutēto":"Estate",
            "Guruupu":"Group","Gurūpu":"Group","Hausumaaketto":"House Market",
            "Hausumāketto":"House Market","Rezōto":"Resort","Rizōto":"Resort"}

def romaji(s, caps=True, joined=False):
    s = (s or "").strip()
    if not s:
        return ""
    out = []
    for w in _kks.convert(s):
        r = w["hepburn"].strip()
        if not r:
            continue
        for rx, rep in LONG:
            r = rx.sub(rep, r)
        if caps and not joined:
            r = r[:1].upper() + r[1:]
        out.append(NAME_FIX.get(r, r) if not joined else r)
    t = ("" if joined else " ").join(out)
    if joined and caps:
        t = t[:1].upper() + t[1:]
    t = NAME_FIX.get(t, t)
    return re.sub(r"\s{2,}", " ", t).strip()

PREF = {"nagano": "Nagano", "hyogo": "Hyōgo", "nara": "Nara", "kyoto": "Kyoto",
        "shiga": "Shiga", "wakayama": "Wakayama", "osaka": "Osaka", "mie": "Mie",
        "fukui": "Fukui"}

COMMUNE = {
 "軽井沢町":"Karuizawa","三田市":"Sanda","丹波篠山市":"Tamba-Sasayama","丹波市":"Tamba",
 "宍粟市":"Shisō","神河町":"Kamikawa","市川町":"Ichikawa","猪名川町":"Inagawa","淡路市":"Awaji",
 "洲本市":"Sumoto","加東市":"Katō","多可町":"Taka","西脇市":"Nishiwaki","神戸市北区":"Kobe (Kita-ku)",
 "宝塚市":"Takarazuka","亀岡市":"Kameoka","南丹市":"Nantan","京丹波町":"Kyōtamba",
 "宇治田原町":"Ujitawara","井手町":"Ide","和束町":"Wazuka","笠置町":"Kasagi",
 "南山城村":"Minamiyamashiro","京都市右京区":"Kyoto (Ukyō-ku)","木津川市":"Kizugawa",
 "宇陀市":"Uda","曽爾村":"Sōni","吉野町":"Yoshino","大淀町":"Ōyodo","下市町":"Shimoichi",
 "東吉野村":"Higashiyoshino","五條市":"Gojō","御所市":"Gose","明日香村":"Asuka",
 "高取町":"Takatori","桜井市":"Sakurai","平群町":"Heguri","奈良市":"Nara",
 "高島市":"Takashima","甲賀市":"Kōka","東近江市":"Higashiōmi","日野町":"Hino","多賀町":"Taga",
 "米原市":"Maibara","大津市":"Ōtsu","近江八幡市":"Ōmihachiman","橋本市":"Hashimoto",
 "かつらぎ町":"Katsuragi","九度山町":"Kudoyama","高野町":"Kōya","紀の川市":"Kinokawa",
 "海南市":"Kainan","紀美野町":"Kimino","有田川町":"Aridagawa","能勢町":"Nose","豊能町":"Toyono",
 "千早赤阪村":"Chihayaakasaka","河南町":"Kanan","太子町":"Taishi","岬町":"Misaki",
 "河内長野市":"Kawachinagano","名張市":"Nabari","伊賀市":"Iga","越前町":"Echizen",
}

OWNERSHIP = {"所有権":"Pleine propriété","借地権":"Bail au sol","地上権":"Droit de superficie",
             "定期借地権":"Bail emphytéotique"}
PLANNING = {"非線引区域":"Hors plan d'urbanisme","市街化区域":"Zone urbanisée",
            "市街化調整区域":"Zone d'urbanisation restreinte","区域外":"Hors zone de planification",
            "都市計画区域外":"Hors zone de planification","準都市区域":"Quasi-zone urbaine",
            "準都市計画区域":"Quasi-zone urbaine","調整区域":"Zone d'urbanisation restreinte"}
ZONING = {"無指定":"Sans zonage","１種低層":"Résidentiel pavillonnaire (cat. 1)",
          "２種低層":"Résidentiel pavillonnaire (cat. 2)","１種中高":"Résidentiel R+2 et plus (cat. 1)",
          "２種中高":"Résidentiel R+2 et plus (cat. 2)","１種住居":"Résidentiel (cat. 1)",
          "２種住居":"Résidentiel (cat. 2)","準住居":"Résidentiel mixte","準工業":"Semi-industriel",
          "工業":"Industriel","工業専用":"Industriel strict","近隣商業":"Commerce de proximité",
          "商業":"Commercial","田園住居":"Résidentiel agricole"}
STRUCT = {"木造":"Ossature bois","鉄骨造":"Ossature acier","軽量鉄骨造":"Acier léger",
          "鉄筋コンクリート造":"Béton armé","鉄骨鉄筋コンクリート造":"Acier-béton armé",
          "ブロック造":"Parpaing","その他":"Autre","コンクリートブロック造":"Bloc béton"}
CONDITION = {"空家":"Vacant","空室":"Vacant","所有者居住中":"Occupé par le propriétaire",
             "居住中":"Occupé","賃貸中":"Loué","未完成":"Non terminé","建築中":"En construction"}
DEAL = {"専任媒介":"Mandat exclusif","専属専任媒介":"Mandat exclusif renforcé","一般媒介":"Mandat simple",
        "媒介":"Mandat simple","売主":"Vendeur en direct","代理":"Agent mandaté"}
DIRS = [("北東","nord-est"),("北西","nord-ouest"),("南東","sud-est"),("南西","sud-ouest"),
        ("北","nord"),("南","sud"),("東","est"),("西","ouest")]

def madori(s):
    """４ＬＤＫ -> ('4LDK', '4 chambres + séjour-cuisine')"""
    s = half(s).upper()
    if not s:
        return "", ""
    m = re.match(r"(\d+)\s*(S?)(LDK|LD|DK|K|R)", s)
    if not m:
        return s, ""
    n, serv, kind = int(m.group(1)), m.group(2), m.group(3)
    code = f"{n}{serv}{kind}"
    rooms = f"{n} pièce" + ("s" if n > 1 else "")
    tail = {"LDK":"séjour-cuisine","LD":"séjour","DK":"coin repas-cuisine","K":"cuisine","R":""}[kind]
    bits = [rooms]
    if serv:
        bits.append("cellier")
    if tail:
        bits.append(tail)
    return code, " + ".join(bits)

def access(s):
    """'ＪＲ和歌山線 「高野口」駅 徒歩5分' -> 'Ligne JR Wakayama, gare de Kōyaguchi, 5 min à pied'"""
    s = half(s)
    if not s:
        return ""
    tail = []
    w = re.search(r"徒歩\s*([\d,]+)\s*m", s, re.I)
    if w:
        m_ = int(w.group(1).replace(",", ""))
        tail.append((f"{m_/1000:.1f} km").replace(".", ",") if m_ >= 1000 else f"{m_} m")
    else:
        w = re.search(r"徒歩\s*(\d+)\s*分", s)
        if w:
            tail.append(f"{w.group(1)} min à pied")
    bus = re.search(r"バス\s*(\d+)\s*分", s)
    if bus:
        tail.append(f"{bus.group(1)} min de bus")
    stop = re.search(r"停歩\s*(\d+)\s*分", s)
    if stop:
        tail.append(f"arrêt à {stop.group(1)} min à pied")

    if re.search(r"IC", s, re.I):
        name = re.search(r"[「『]([^」』]+)[」』]\s*IC", s, re.I)
        if not name:
            name = re.search(r"([\u4e00-\u9fff\u30a0-\u30ff]{2,8})\s*IC", s, re.I)
        ic_fr = romaji(name.group(1), joined=True) if name else ""
        head = s[: name.start()] if name else ""
        rd_ = re.search(r"([\u4e00-\u9fff]{2,10}?(?:自動車道|道))", head)
        road_fr = romaji(re.sub(r"(自動車道|道)$", "", rd_.group(1)), joined=True) if rd_ else ""
        d = re.search(r"約?\s*([\d.]+)\s*km", s, re.I)
        parts = ["Échangeur " + ic_fr if ic_fr else "Échangeur"]
        if road_fr:
            parts[0] += f" (autoroute {road_fr})"
        if d:
            parts.append(d.group(1).replace(".", ",") + " km")
        parts += tail
        return ", ".join(parts)

    st = re.search(r"「([^」]+)」", s)
    if st:
        station = st.group(1)
        line = s.split("「")[0]
    else:
        st = re.search(r"(?:[/／]\s*)?([^\s/／]+?)駅", s)
        station = st.group(1) if st else ""
        line = s.split("/")[0].split("／")[0] if ("/" in s or "／" in s) else ""
        if station and not line:
            line = s.split(station)[0]
    station = re.sub(r"駅$", "", station or "")
    station_fr = romaji(station, joined=True) if station else ""

    line = re.sub(r"[/／]", " ", line or "").strip()
    line = re.sub(r"[（(].*?[)）]", "", line)
    lr = ""
    if line:
        shink = "新幹線" in line
        line = line.replace("新幹線", "").replace("本線", "").replace("線", "").replace("電鉄", "").replace("鉄道", "")
        head = ""
        m = re.match(r"^(ＪＲ|JR)", line)
        if m:
            head = "JR "
            line = line[len(m.group(1)):]
        body = romaji(line, joined=True)
        lr = (head + body).strip()
        if lr:
            lr = ("Shinkansen " + lr) if shink else ("Ligne " + lr)
    parts = []
    if lr:
        parts.append(lr)
    if station_fr:
        parts.append(f"gare de {station_fr}")
    parts += tail
    return ", ".join([p for p in parts if p]) or romaji(s)

def road(s):
    s = half(s)
    if not s or s in ("-", "－"):
        return ""
    out = []
    for seg in re.split(r"[・,]", s):
        seg = seg.strip()
        if not seg:
            continue
        if "四方道路" in seg: out.append("rues sur les 4 côtés"); continue
        if "三方道路" in seg: out.append("rues sur 3 côtés"); continue
        if "二方道路" in seg: out.append("rues sur 2 côtés"); continue
        bits = []
        for jp, fr in DIRS:
            if seg.startswith(jp):
                bits.append(fr); seg = seg[len(jp):]; break
        w = re.search(r"([\d.]+)\s*m(?!²)", seg)
        if w:
            bits.append(f"{w.group(1).replace('.', ',')} m de large")
        if "公道" in seg: bits.append("voie publique")
        if "私道" in seg: bits.append("voie privée")
        if "位置指定" in seg: bits.append("voie agréée")
        f = re.search(r"接面\s*([\d.]+)\s*m", seg)
        if f:
            bits.append(f"{f.group(1).replace('.', ',')} m de façade")
        if bits:
            out.append(" ".join(bits[:1]) + (" : " + ", ".join(bits[1:]) if len(bits) > 1 else ""))
    return " · ".join(out)

def simple(s, table, fallback_romaji=True):
    s = (s or "").strip()
    if not s or s in ("-", "－"):
        return ""
    for jp, fr in sorted(table.items(), key=lambda kv: -len(kv[0])):
        if jp in s:
            return fr
    return romaji(s) if fallback_romaji else ""

def floors(s):
    s = half(s)
    if not s or s in ("-", "－"):
        return ""
    if "平屋" in s:
        return "Plain-pied"
    m = re.search(r"(\d+)\s*階建", s)
    if m:
        return f"{m.group(1)} niveaux"
    return romaji(s)

def agency(s):
    s = (s or "").strip()
    if not s:
        return ""
    s = re.sub(r"[（(]株[)）]|株式会社", " ", s)
    s = re.sub(r"[（(]有[)）]|有限会社", " ", s)
    s = re.sub(r"[（(]同[)）]|合同会社", " ", s)
    s = re.sub(r"\s*[（(][^）)]*[)）]\s*", " ", s)
    br = ""
    m = re.search(r"([\u4e00-\u9fff]{2,4})店$", s)
    if m:
        br = romaji(m.group(1).replace("店", ""), joined=True)
        s = s[: m.start()]
    out = re.sub(r"\s{2,}", " ", romaji(half(s))).strip()
    if len(out) > 40:
        out = out[:40].rsplit(" ", 1)[0] + "…"
    return f"{out} ({br})" if br else out

def address(s, commune_fr):
    s = (s or "").strip()
    if not s:
        return ""
    for jp, fr in COMMUNE.items():
        if jp in s:
            rest = s.split(jp, 1)[1]
            rest = re.sub(r"^大字|^字", "", rest)
            r = romaji(rest, joined=True)
            return f"{fr}, {r}" if r else fr
    return romaji(s, joined=True)

# ---- free-text -> French bullets. (pattern, bullet, severity) sev: 0 info, 1 attention, 2 rouge
PHRASES = [
 (r"再建築不可|再建築が?でき(?:ない|ません)|再建築は?不可", "Reconstruction interdite", 2),
 (r"土砂災害特別警戒区域|レッドゾーン", "Zone rouge glissement de terrain", 2),
 (r"土砂災害警戒区域|イエローゾーン", "Zone jaune glissement de terrain", 1),
 (r"浸水想定|浸水区域|洪水", "Zone inondable", 1),
 (r"急傾斜地崩壊危険", "Zone d'éboulement (forte pente)", 1),
 (r"砂防指定|砂防法", "Terrain classé protection torrentielle (砂防)", 1),
 (r"宅地造成工事規制区域", "Zone réglementée pour les terrassements", 1),
 (r"二項道路|42条2項|４２条２項", "Voie étroite art. 42-2 : recul obligatoire", 1),
 (r"セットバック(?:要|が必要|必要)", "Recul de façade obligatoire (élargissement de rue)", 1),
 (r"位置指定道路|位置指定有", "Voie privée agréée par la préfecture", 0),
 (r"但し書き|43条|４３条", "Accès par dérogation art. 43", 1),
 (r"建物未登記|母屋未登記|主屋未登記|建物は未登記|建物（未登記）", "La maison n'est pas enregistrée au cadastre", 2),
 (r"未登記", "Une annexe ou extension n'est pas enregistrée", 1),
 (r"借地権|地上権|定期借地", "Terrain en bail, pas en pleine propriété", 2),
 (r"事故物件|心理的瑕疵", "Bien stigmatisé (décès ou incident)", 2),
 (r"告知事項", "Fait à déclarer par le vendeur", 1),
 (r"市街化調整区域", "Zone d'urbanisation restreinte : construire est encadré", 1),
 (r"農地法|農地転用", "Terrain agricole : loi sur les terres agricoles", 1),
 (r"競売|任意売却", "Vente forcée ou à l'amiable après défaut", 1),
 (r"雨漏り", "Fuite de toiture signalée", 1),
 (r"シロアリ|白蟻", "Termites signalés", 1),
 (r"傾[きい]て?", "Affaissement / plancher penché", 1),
 (r"カビ", "Moisissure signalée", 1),
 (r"水漏れ", "Fuite d'eau signalée", 1),
 (r"破損", "Dégâts signalés", 1),
 (r"現状有姿|現況有姿|現況渡し|現状渡し", "Vendu en l'état, sans remise en état", 1),
 (r"契約不適合責任(?:免責|不担保)", "Vendeur dégagé de la garantie des vices", 1),
 (r"境界非明示|境界未確定", "Limites de terrain non bornées", 1),
 (r"越境", "Empiétement d'un voisin (toit, clôture, mur)", 1),
 (r"private_road|私道負担", "Quote-part de voie privée incluse", 0),
 (r"管理費|管理組合|管理規約", "Charges annuelles de lotissement", 1),
 (r"自治会", "Adhésion à l'association de quartier demandée", 0),
 (r"環境整備費", "Redevance d'entretien du site", 1),
 (r"別荘地|リゾート", "Lotissement de résidences secondaires", 1),
 (r"民泊不可", "Location touristique interdite", 1),
 (r"民泊可|旅館業", "Location touristique possible", 0),
 (r"商用利用は?不可|商業利用不可", "Usage commercial interdit", 1),
 (r"空き家バンク", "Issu d'une banque de maisons vides (akiya bank)", 0),
 (r"リノベーション済|リフォーム済|改装済", "Déjà rénové", 0),
 (r"全面改築|全面リフォーム", "Rénovation complète effectuée", 0),
 (r"即入居可?能?", "Habitable immédiatement", 0),
 (r"要リフォーム|リフォーム必須|要修繕", "Travaux indispensables avant d'habiter", 1),
 (r"増築", "Extension construite après l'origine", 0),
 (r"土蔵|蔵", "Kura : grange traditionnelle en torchis", 0),
 (r"物置|納屋", "Remise / cabanon sur le terrain", 0),
 (r"倉庫", "Entrepôt ou dépendance", 0),
 (r"車庫|ガレージ", "Garage", 0),
 (r"離れ|別棟", "Bâtiment séparé sur le terrain", 0),
 (r"山林", "Parcelle de forêt incluse", 0),
 (r"[畑田]地?付", "Terrain cultivable inclus", 0),
 (r"家庭菜園", "Potager", 0),
 (r"井戸", "Puits", 0),
 (r"集中浄化槽", "Fosse septique collective (redevance)", 1),
 (r"浄化槽", "Fosse septique individuelle", 0),
 (r"下水道", "Raccordé au tout-à-l'égout", 0),
 (r"公営|上水道", "Eau de ville", 0),
 (r"集中プロパン", "Propane collectif (redevance)", 1),
 (r"プロパンガス|ＬＰガス|LPガス", "Gaz propane en bouteille", 0),
 (r"都市ガス", "Gaz de ville", 0),
 (r"オール電化", "Tout électrique", 0),
 (r"太陽光", "Panneaux solaires", 0),
 (r"南向き", "Exposition sud", 0),
 (r"東向き", "Exposition est", 0),
 (r"西向き", "Exposition ouest", 0),
 (r"北向き", "Exposition nord", 1),
 (r"高台", "Sur hauteur", 0),
 (r"角地", "Terrain d'angle", 0),
 (r"平坦", "Terrain plat", 0),
 (r"傾斜地|法面", "Terrain en pente", 1),
 (r"駐車\s*[２2]台|駐車場\s*[２2]台", "2 places de stationnement", 0),
 (r"駐車|カースペース", "Stationnement sur place", 0),
 (r"車進入不可|車両進入不可", "Voiture ne peut pas accéder au bien", 2),
 (r"除雪", "Déneigement à vérifier l'hiver", 1),
 (r"更地渡し", "Livré terrain nu (maison démolie)", 1),
 (r"建物対価[０0]|建物価格[０0]", "Bâtiment valorisé à zéro", 1),
 (r"歴史的風土|伝統的建造物|景観地区", "Secteur patrimonial protégé (travaux encadrés)", 1),
 (r"エアコン", "Climatisation installée", 0),
 (r"IT重説|ＩＴ重説", "Explication légale possible en visio", 0),
 (r"古民家|kominka", "Kominka : maison traditionnelle ancienne", 0),
]
_COMPILED = [(re.compile(p), b, s) for p, b, s in PHRASES]

def notes(*texts):
    blob = " ".join([t for t in texts if t])
    if not blob:
        return []
    seen, out = set(), []
    for rx, bullet, sev in _COMPILED:
        if bullet in seen:
            continue
        if rx.search(blob):
            seen.add(bullet)
            out.append([bullet, sev])
    out.sort(key=lambda b: -b[1])
    return out[:14]
