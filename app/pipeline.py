"""Automatic first-pass analysis of a Mubawab listing, the video's way.

paste a link -> read the advert -> comparables (for sale, to rent, Airbnb) -> property record
-> build the tracker -> a result the page can show, saved under runs/ so history survives.

This is the rule-based version of what the morocco-property skill does with judgement.
Every rule is written down below and echoed in the result's "basis" texts, so nothing is hidden.
For a deeper look at one flat (choosing comparables by eye, reading the photos, drafting an
offer), ask Claude with the skill.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import shutil
import statistics
import subprocess
import threading
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent
# The engine (model, spreadsheet builder, Mubawab reader, defaults). On this Mac it is the installed
# skill; anywhere else (GitHub's servers) it is the copy kept in engine/, refreshed on every sync.
_LOCAL_SKILL = Path.home() / ".claude" / "skills" / "morocco-property"
SKILL = _LOCAL_SKILL if (_LOCAL_SKILL / "scripts").exists() else DATA / "engine"
# Airbnb listings collected for the Rabat dashboard: the live file on this Mac, else the synced copy.
_LIVE_LISTINGS = Path.home() / "Desktop" / "Other random coding" / "morocco-str" / "listings.js"
LISTINGS = _LIVE_LISTINGS if _LIVE_LISTINGS.exists() else DATA / "data" / "listings.js"
sys.path.insert(0, str(SKILL / "scripts"))

import deal_model  # noqa: E402
import mubawab  # noqa: E402
import str_comps  # noqa: E402

UA = "property-research-script/1.0 (personal, low-volume)"
SPOT_TO_ACHIEVED = 0.82   # one-night Airbnb spot price -> year-round achieved rate for a new listing
ASKING_RENT_HAIRCUT = 0.95
FURNISH_PER_M2 = 1200
OFF_PLAN = re.compile(r"en cours de construction|sur plan|hors[ -]plan|livraison|vefa|à partir de", re.I)
FURNISHED = re.compile(r"\bmeubl[ée]e?s?\b", re.I)


class Refusal(Exception):
    """A problem the user can act on; shown as-is on the page."""


def _norm(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def _get(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "fr,en;q=0.8"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="ignore")


def _json_file(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def context():
    spec = json.loads((SKILL / "assets" / "defaults.json").read_text(encoding="utf-8"))
    profile = _json_file(DATA / "profile.json", {})
    A, buyer_type, home = deal_model.resolve_assumptions(spec["assumptions"], profile)
    market = json.loads((SKILL / "assets" / "str_market.json").read_text(encoding="utf-8"))
    return {"A": A, "buyer_type": buyer_type, "home": home, "profile": profile, "market": market,
            "defaults_as_of": spec.get("as_of")}


def profile_summary():
    c = context()
    A, p = c["A"], c["profile"]
    return {"buyer_type": c["buyer_type"], "home_currency": c["home"], "financing": p.get("financing") or "undecided",
            "strategy": p.get("strategy") or [], "ltv": A["ltv"], "rate": A["rate"], "rate_eff": A["rate_eff"],
            "term_years": A["term_years"], "home_tax_rate": A["home_tax_rate"], "fx_home": A["fx_home"],
            "defaults_as_of": c["defaults_as_of"], "video_occ": A["video_occ"], "video_mgmt_pct": A["video_mgmt_pct"]}


# ---------------------------------------------------------------- evidence
def geocode(area, city):
    """Centre of a neighbourhood, from OpenStreetMap (cached). Only the place name is sent."""
    cache_path = DATA / "geocode_cache.json"
    cache = _json_file(cache_path, {})
    key = "%s|%s" % (_norm(area), _norm(city))
    if key in cache:
        return cache[key]
    q = urllib.parse.urlencode({"q": "%s, %s, Morocco" % (area, city), "format": "json", "limit": 1})
    try:
        hits = json.loads(_get("https://nominatim.openstreetmap.org/search?" + q, timeout=20))
        res = {"lat": float(hits[0]["lat"]), "lng": float(hits[0]["lon"]), "name": hits[0].get("display_name")} if hits else None
    except Exception:
        return None
    cache[key] = res
    cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")
    return res


def agenz_reference(city, area):
    """Agenz's published price per m² for apartments in a neighbourhood, if its city page lists it."""
    slug = _norm(city).replace(" ", "-")
    try:
        page = _get("https://agenz.ma/fr/prix-immobilier-maroc/" + urllib.parse.quote(slug))
    except Exception:
        return None
    text = re.sub(r"<script.*?</script>|<style.*?</style>", "", page, flags=re.S)
    text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text))
    start = text.find("par quartier")
    if start < 0:
        return None
    updated = re.search(r"mise à jour le (\d\d/\d\d/\d{4})", text)
    want = _norm(area)
    for m in re.finditer(r"([A-Za-zÀ-ÿ'’ \-]{3,40}?)\s+(\d{1,3}(?:[   ]\d{3})+)\s*DH", text[start:start + 6000]):
        toks = _norm(m.group(1)).split()
        while toks and toks[0] in {"dh", "moyen", "villa", "appartement", "prix", "m", "m2", "quartier"}:
            toks.pop(0)
        if " ".join(toks) == want:
            return {"mad_per_m2": int(re.sub(r"\D", "", m.group(2))), "area": area,
                    "updated": updated.group(1) if updated else None,
                    "url": "https://agenz.ma/fr/prix-immobilier-maroc/" + slug}
    return None


def _quart(values):
    v = sorted(values)
    if not v:
        return None
    if len(v) < 4:
        return {"n": len(v), "p25": v[0], "median": statistics.median(v), "p75": v[-1]}
    q = statistics.quantiles(v, n=4, method="inclusive")
    return {"n": len(v), "p25": q[0], "median": q[1], "p75": q[2]}


def _round10(x):
    return int(round(x / 10.0)) * 10


def market_for(city, beds, market):
    key = _norm(city)
    for name, row in market["cities"].items():
        if key in [_norm(name)] + [_norm(a) for a in row.get("aliases", [])]:
            b = (row.get("by_bedrooms") or {}).get(str(beds))
            src = dict(row, **b) if b else row
            return {"occ": src["occ"], "adr_mad": src["adr_mad"], "city": name, "bedroom_specific": bool(b)}
    return {"occ": market["national"]["occ"], "adr_mad": market["national"]["adr_mad"], "city": None, "bedroom_specific": False}


# ---------------------------------------------------------------- the run
def analyse_url(url, say=lambda msg: None):
    url = (url or "").strip()
    host = urllib.parse.urlsplit(url).netloc.lower()
    if not url.startswith("http"):
        raise Refusal("That is not a link. Paste the full address of a listing, starting with https://")
    if "mubawab.ma" not in host:
        raise Refusal("Only Mubawab links are read automatically. For %s, open the listing and ask Claude: “/morocco-property” "
                      "with the advert text or a screenshot." % (host or "this site"))
    if not re.search(r"/(a|pa)/\d+", url):
        raise Refusal("That Mubawab link is not a single listing. Open one property and paste its address "
                      "(it contains /a/ or /pa/ and a number).")
    c = context()
    A = c["A"]

    say("Reading the advert")
    try:
        li = mubawab.get_listing(url)
    except Exception as e:
        raise Refusal("Mubawab did not return that listing (%s). Check the link still opens." % e)
    if not li.get("price_mad"):
        if li.get("price") and li.get("currency") == "EUR":
            li["price_mad"] = li["price"] * A["fx_eur"]
            li["_price_note"] = "Advertised at €%s; converted at %.4f MAD/EUR." % (format(int(li["price"]), ","), A["fx_eur"])
        else:
            raise Refusal("The advert shows no price (“prix à consulter”). Ask the agent for the price, then ask Claude to analyse it.")
    lid = li["id"]
    area = (li.get("breadcrumb") or [None])[-1] if li.get("comparable_searches", {}).get("for_sale", "").count("/sd/") else None
    city = None
    m = re.search(r"/fr/s[dt]/([^/]+)/", li.get("comparable_searches", {}).get("for_sale", ""))
    if m:
        city = urllib.parse.unquote(m.group(1)).replace("-", " ").title()
    surface, beds = li.get("surface_m2"), li.get("bedrooms")
    text = " ".join([li.get("title") or "", li.get("description") or "", " ".join("%s %s" % kv for kv in (li.get("main_features") or {}).items())])
    off_plan = bool(li.get("new_development") or OFF_PLAN.search(text))
    furnished = bool(FURNISHED.search(text))
    searches = li.get("comparable_searches") or {}
    evidence, flags, unknowns = {}, [], []

    # -- for-sale comparables
    say("Finding similar flats for sale")
    comps_sale, sale_stats = [], None
    if searches.get("for_sale") and surface:
        time.sleep(1.0)
        res = mubawab.search([searches["for_sale"]], min_m2=surface * 0.7, max_m2=surface * 1.35, beds=beds, exclude_id=lid, fx_eur=A["fx_eur"])
        pool = [x for x in res["listings"] if x.get("in_stats") and x.get("mad_per_m2") and not x.get("suspect_outlier")]
        if len(pool) < 4:
            res = mubawab.search([searches["for_sale"]], min_m2=surface * 0.6, max_m2=surface * 1.5, exclude_id=lid, fx_eur=A["fx_eur"])
            pool = [x for x in res["listings"] if x.get("in_stats") and x.get("mad_per_m2") and not x.get("suspect_outlier")]
        pool.sort(key=lambda x: abs(x["surface_m2"] - surface))
        for x in pool[:10]:
            comps_sale.append({"desc": "%s-bed %d m², %s" % (x.get("bedrooms") if x.get("bedrooms") is not None else "?", x["surface_m2"], x.get("location") or ""),
                               "price_mad": x["price_mad"], "surface_m2": x["surface_m2"], "url": x["url"],
                               "note": "new build / off-plan advert" if x.get("mentions_new_build") else ""})
        sale_stats = _quart([c_["price_mad"] / c_["surface_m2"] for c_ in comps_sale])
    evidence["sale"] = {"count": len(comps_sale), "stats_mad_per_m2": sale_stats, "search": searches.get("for_sale")}

    say("Checking the area's reference price")
    ref = agenz_reference(city, area) if (city and area) else None
    evidence["agenz"] = ref
    area_override = None
    if ref and sale_stats:
        asked = sale_stats["median"] * (1 - A["asking_discount"])
        area_override = {"low": min(ref["mad_per_m2"], asked), "mid": (ref["mad_per_m2"] + asked) / 2, "high": max(ref["mad_per_m2"], asked),
                         "basis": "Automatic: midpoint of Agenz's reference for %s (%s MAD/m², updated %s) and the median of %d comparable adverts less %d%% (%s). "
                                  "A placeholder until agents tell you what flats actually sold for."
                                  % (ref["area"], format(ref["mad_per_m2"], ","), ref.get("updated") or "?", len(comps_sale), round(A["asking_discount"] * 100), format(round(asked), ","))}

    # -- long-let comparables
    say("Finding similar flats to rent")
    ltr, rent_stats, comps_ltr = None, None, []
    if searches.get("to_rent") and surface:
        time.sleep(1.0)
        res = mubawab.search([searches["to_rent"]], min_m2=surface * 0.7, max_m2=surface * 1.5, beds=beds, fx_eur=A["fx_eur"])
        pool = [x for x in res["listings"] if x.get("in_stats") and x.get("price_mad") and x["price_mad"] >= 2500 and x.get("surface_m2") and not x.get("price_per")]
        per_m2 = [x["price_mad"] / x["surface_m2"] for x in pool]
        if len(per_m2) >= 4:
            rent_stats = _quart(per_m2)
            ltr = {"rent_mad_month": {k: _round10(rent_stats[q] * surface * ASKING_RENT_HAIRCUT / 10) * 10
                                      for k, q in (("bear", "p25"), ("base", "median"), ("bull", "p75"))},
                   "rent_note": "Automatic: %d asking rents for similar flats in the area, as MAD per m² (lower quartile / median / upper quartile), × this flat's surface, less 5%% for negotiation."
                                % len(per_m2)}
            for x in sorted(pool, key=lambda x: abs(x["surface_m2"] - surface))[:8]:
                comps_ltr.append({"desc": "%s-bed %d m², %s" % (x.get("bedrooms"), x["surface_m2"], x.get("location") or ""),
                                  "rent_mad_month": x["price_mad"], "surface_m2": x["surface_m2"], "url": x["url"]})
            ltr["comps"] = comps_ltr
    evidence["rent"] = {"count": len(comps_ltr), "stats_mad_per_m2_month": rent_stats, "search": searches.get("to_rent")}

    # -- Airbnb nightly rate and occupancy
    say("Finding comparable Airbnb listings")
    mk = market_for(city or "", beds, c["market"])
    occ = {"bear": round(mk["occ"], 3), "base": round(min(mk["occ"] + 0.10, 0.75), 3), "bull": round(min(mk["occ"] + 0.22, 0.80), 3)}
    occ_note = ("Automatic: %s average occupancy %s (AirROI, 12 months to Oct 2026) as the bear case; +10 points for an always-available managed flat (base); +22 points, about the top quarter of listings (bull)."
                % ((mk["city"] or "national").title() + (" %s-bed" % beds if mk["bedroom_specific"] else ""), "%d%%" % round(mk["occ"] * 100)))
    adr, adr_note, comps_str, str_ev = None, "", [], {"method": None}
    geo = geocode(area, city) if (area and city) else None
    if geo:
        for radius in (1.0, 1.5, 2.5):
            r = str_comps.comps(geo["lat"], geo["lng"], beds=beds, radius_km=radius, min_reviews=5, file=LISTINGS)
            if "error" in r or r.get("matches", 0) >= 8:
                break
        if "error" not in r and r.get("matches", 0) >= 8 and (r.get("market") or "").lower() == _norm(city):
            sp = r["one_night_price_mad"]
            adr = {"bear": _round10(sp["p25"] * SPOT_TO_ACHIEVED), "base": _round10(sp["median"] * SPOT_TO_ACHIEVED), "bull": _round10(sp["p75"] * SPOT_TO_ACHIEVED)}
            adr_note = ("Automatic: %d established %s-bed Airbnb homes within %.1f km of central %s (your dashboard data, collected %s) show one-night prices of %s / %s / %s MAD "
                        "(lower quartile / median / upper quartile). Taken down 18%% for the cleaning fee, the one-night premium and a new listing's lack of reviews."
                        % (r["matches"], beds, r["filters"]["radius_km"], area, r.get("collected_on"), format(sp["p25"], ","), format(sp["median"], ","), format(sp["p75"], ",")))
            for x in r["most_established"][:8]:
                comps_str.append({"desc": ("%s (%s★, %.2f km)" % (x["name"][:60], x.get("rating"), x["km_away"])) if x.get("name") else "%s-bed Airbnb home, %.2f km away" % (x.get("bedrooms"), x["km_away"]),
                                  "nightly_mad": x["price_mad"],
                                  "bedrooms": x.get("bedrooms"), "reviews": x.get("reviews"), "url": x["url"], "note": "one-night price on %s" % x.get("price_date")})
            str_ev = {"method": "airbnb_file", "matches": r["matches"], "radius_km": r["filters"]["radius_km"], "spot_mad": sp, "collected_on": r.get("collected_on"), "centre": geo}
    if adr is None and searches.get("holiday_rental"):
        time.sleep(1.0)
        try:
            res = mubawab.search([searches["holiday_rental"]], beds=beds, fx_eur=A["fx_eur"])
            pool = [x for x in res["listings"] if x.get("in_stats") and x.get("price_mad") and 150 <= x["price_mad"] <= 6000]
        except Exception:
            pool = []
        if len(pool) >= 4:
            q = _quart([x["price_mad"] for x in pool])
            adr = {"bear": _round10(q["p25"]), "base": _round10(q["median"]), "bull": _round10(q["p75"])}
            adr_note = "Automatic: %d holiday-let adverts for %s-bed flats in the area on Mubawab (asking nightly prices: lower quartile / median / upper quartile). No Airbnb listing data is held for this city." % (len(pool), beds)
            for x in pool[:8]:
                comps_str.append({"desc": "%s, %s" % ((x.get("title") or "")[:60], x.get("location") or ""), "nightly_mad": x["price_mad"], "bedrooms": x.get("bedrooms"), "url": x["url"]})
            str_ev = {"method": "mubawab_holiday", "matches": len(pool)}
    if adr is None:
        base = mk["adr_mad"]
        adr = {"bear": _round10(base * 0.8), "base": _round10(base), "bull": _round10(base * 1.2)}
        adr_note = "Automatic and WEAK: no local comparables found, so this is the %s market's average nightly rate (AirROI) ± 20%%. Check real Airbnb listings before trusting it." % (mk["city"] or "national")
        str_ev = {"method": "market_average"}
        flags.append({"severity": "amber", "text": "Nightly rate is a city-wide average, not local evidence."})
    evidence["str"] = str_ev
    evidence["market"] = mk

    # -- the record
    today = dt.date.today().isoformat()
    existing = None
    for f in sorted((DATA / "properties").glob("*.json")):
        rec0 = _json_file(f, {})
        if re.search(r"/%s(/|$)" % re.escape(lid), rec0.get("source_url") or ""):
            existing = (f, rec0)
            break
    curated = bool(existing and existing[1].get("origin") != "auto")
    if curated:
        path, rec = existing
        say("Using the fuller analysis already on file for this flat")
    else:
        furnishing = 0 if furnished else int(round(FURNISH_PER_M2 * (surface or 0), -3))
        rec = {
            "id": "mubawab-%s" % lid, "origin": "auto",
            "short_name": ("%s %s" % (city or "", area or "")).strip()[:20] or "Mubawab %s" % lid,
            "added": (existing[1].get("added") if existing else today),
            "added_at": (existing[1].get("added_at") if existing else dt.datetime.now().isoformat(timespec="seconds")),
            "title": "%s%s — %s" % (("%s-bed, " % beds) if beds is not None else "", ("%d m²" % surface) if surface else "surface unknown",
                                    ", ".join(x for x in (area, city) if x) or (li.get("title") or "")[:60]),
            "advert_title": li.get("title"), "source_url": li["url"], "listing_date": li.get("date_posted"),
            "contact": " ".join(x for x in (li.get("agency"), ("ref " + li["agency_ref"]) if li.get("agency_ref") else None) if x) or None,
            "city": city, "neighbourhood": area, "address_note": "Advert gives the neighbourhood only; Airbnb comparables use its centre.",
            "property_type": (li.get("main_features") or {}).get("Type de bien", "apartment").lower(),
            "bedrooms": beds, "bathrooms": li.get("bathrooms"),
            "floor": (li.get("main_features") or {}).get("Étage du bien"), "lift": ("Ascenseur" in (li.get("amenities") or [])) or None,
            "year_built": None, "condition": (li.get("main_features") or {}).get("Etat") or (li.get("main_features") or {}).get("État"),
            "furnished": furnished, "title_status": "unknown", "off_plan": off_plan,
            "seller_type": "agent" if li.get("agency") else None,
            "asking_price_mad": round(li["price_mad"]), "asking_note": li.get("_price_note") or "From the advert (read %s)." % today,
            "surface_m2": surface, "surface_note": "From the advert. Confirm on the title certificate.",
            "furniture_value_mad": 0, "syndic_mad_month": None, "agent_fee_pct": None,
            "comps_sale": comps_sale, "furnishing_mad": furnishing,
            "furnishing_note": "" if furnished else "ASSUMPTION: %s MAD/m² to furnish and equip for letting; the advert does not mention furniture." % format(FURNISH_PER_M2, ","),
            "renovation_mad": 0,
            "str": {"comps": comps_str, "adr_mad": adr, "adr_note": adr_note, "occupancy": occ, "occupancy_note": occ_note},
            "notes": "%s: automatic first pass from the web app." % today,
        }
        if area_override:
            rec["area_price_per_m2"] = area_override
        if ltr:
            rec["ltr"] = ltr
        path = existing[0] if existing else DATA / "properties" / ("%s-mubawab-%s.json" % (today, lid))

        # flags and verdict need the numbers: compute them with the reference model first
        m0 = deal_model.compute(rec, A)
        fx = A["fx_home"]
        flags.insert(0, {"severity": "red", "text": "Title status is not in the advert. Ask for the title number (titre foncier) before anything else."})
        if off_plan:
            flags.insert(1, {"severity": "red", "text": "Reads as off-plan or still under construction: staged payments, developer risk, no rent until delivery and normally no mortgage until the title exists."})
        financing = (c["profile"].get("financing") or "undecided")
        if financing in ("mortgage", "undecided") and m0["c_profit"] < 0:
            flags.append({"severity": "red", "text": "On a %d%% mortgage the flat loses about %s%s a month in the checked base case (the video's way shows %s%s%s)."
                          % (round(A["ltv"] * 100), _sym(c["home"]), format(round(-m0["c_profit"] / fx), ","), "+" if m0["v_profit"] >= 0 else "−", _sym(c["home"]), format(round(abs(m0["v_profit"]) / fx), ","))})
        if ref and m0.get("ask_m2") and m0["ask_m2"] > ref["mad_per_m2"] * 1.2:
            flags.append({"severity": "amber", "text": "Asking %s MAD/m² is %d%% above Agenz's reference for %s (%s)."
                          % (format(round(m0["ask_m2"]), ","), round((m0["ask_m2"] / ref["mad_per_m2"] - 1) * 100), ref["area"], format(ref["mad_per_m2"], ","))})
        if len(comps_sale) < 5:
            flags.append({"severity": "amber", "text": "Only %d comparable flats for sale found: the price check is weak." % len(comps_sale)})
        flags.append({"severity": "amber", "text": "Short-let licensing for private flats is unsettled nationally and likely to tighten; this building's own rules are unknown."})
        flags.append({"severity": "amber", "text": "Service charge (syndic) and building age are not in the advert; the service charge is estimated."})
        if not furnished:
            flags.append({"severity": "amber", "text": "Furnishing budget is an assumption (%s MAD)." % format(furnishing, ",")})
        if not surface:
            flags.insert(1, {"severity": "red", "text": "No surface in the advert: the price cannot be checked per m²."})
        unknowns = ["Is it titled (titre foncier)? Title number?", "Exact address / map pin", "Year the building was built",
                    "Monthly syndic charge and what it covers", "Surface on the title", "Do the building rules allow short-term letting?",
                    "Agent's buyer-side commission", "Is any furniture or equipment included?"]
        rec["flags"], rec["unknowns"] = flags, unknowns
        if off_plan and financing != "cash":
            rec["verdict"], why = "pass", "Off-plan, and you are buying with a mortgage."
        elif financing in ("mortgage", "undecided") and m0["c_profit"] < 0:
            rec["verdict"] = "pass"
            why = ("The video's way shows %s a month; with realistic occupancy and the costs it leaves out, the flat loses %s a month on the mortgage."
                   % (_money(m0["v_profit"] / fx, c["home"], sign=True), _money(-m0["c_profit"] / fx, c["home"])))
        else:
            rec["verdict"] = "conditional"
            why = "The numbers hold in the base case; nothing is certain until the title is confirmed and sold prices are checked."
        rec["verdict_reason"] = "Automatic first pass. " + why
        (DATA / "properties").mkdir(exist_ok=True)
        path.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")

    # -- build the tracker (spreadsheet + independent recalculation), take the numbers from it
    say("Building the spreadsheet and checking the sums")
    proc = subprocess.run([sys.executable, str(SKILL / "scripts" / "build_tracker.py"), "--data-dir", str(DATA)], capture_output=True, text=True, timeout=300)
    try:
        built = json.loads(proc.stdout)
    except ValueError:
        raise Refusal("The spreadsheet builder failed: %s" % (proc.stderr or proc.stdout)[-400:])
    if "error" in built:
        raise Refusal("The spreadsheet builder refused the record: %s" % built["error"])
    mine = next((p for p in built["properties"] if p["id"] == rec["id"]), None)
    if mine is None:
        raise Refusal("The property was saved but is missing from the tracker output.")
    m = mine["metrics"]

    extras = _extras(rec, A)
    msg_fr, msg_en = _screening_message(rec, li)
    run = {
        "run_id": "%s-%s" % (dt.datetime.now().strftime("%Y%m%d-%H%M%S"), lid),
        "at": dt.datetime.now().isoformat(timespec="seconds"),
        "url": li["url"], "source": "curated" if curated else "auto", "sheet": mine["sheet"],
        "home_currency": c["home"], "fx_home": A["fx_home"],
        "terms": {"ltv": A["ltv"], "rate": A["rate"], "rate_eff": A["rate_eff"], "term_years": A["term_years"],
                  "video_occ": A["video_occ"], "video_mgmt_pct": A["video_mgmt_pct"], "mgmt_pct": A["mgmt_pct"], "platform_pct": A["platform_pct"],
                  "utilities_month": A["utilities_month"], "internet_month": A["internet_month"], "subs_month": A["subs_month"],
                  "home_tax_rate": A["home_tax_rate"], "defaults_as_of": c["defaults_as_of"]},
        "record": rec, "metrics": m, "extras": extras, "evidence": evidence,
        "check": built.get("check"), "message_fr": msg_fr, "message_en": msg_en,
    }
    (DATA / "runs").mkdir(exist_ok=True)
    (DATA / "runs" / (run["run_id"] + ".json")).write_text(json.dumps(run, ensure_ascii=False, indent=1), encoding="utf-8")
    import report_md
    run["result_file"] = report_md.save(run, DATA / "results")
    return run


def _sym(home):
    return {"GBP": "£", "EUR": "€", "USD": "$"}.get(home, home + " ")


def _money(x, home, sign=False):
    s = "%s%s" % (_sym(home), format(round(abs(x)), ","))
    if sign:
        return ("+" if x >= 0 else "−") + s
    return s


def _solve(f, lo, hi, increasing=True):
    for _ in range(60):
        mid = (lo + hi) / 2
        if (f(mid) < 0) == increasing:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def _extras(rec, A):
    """What it would take to break even, and what the flat makes with real costs at the video's occupancy."""
    import copy

    def cf(**kw):
        p = copy.deepcopy(rec)
        if "occ" in kw:
            p["str"]["occupancy"] = {s: kw["occ"] for s in deal_model.SCEN}
        if "adr" in kw:
            p["str"]["adr_mad"] = {s: kw["adr"] for s in deal_model.SCEN}
        if "price" in kw:
            p["model_price_mad"] = kw["price"]
        return deal_model.compute(p, A)["cf_m"]["base"] / 12

    out = {"real_costs_at_video_occ": cf(occ=A["video_occ"])}
    base = deal_model.compute(rec, A)
    out["be_adr_at_base_occ"] = _solve(lambda x: cf(adr=x), 100, 20000) if base["occ"]["base"] > 0 else None
    out["be_price"] = _solve(lambda x: cf(price=x), 50000, max(base["asking"], 100000) * 1.2, increasing=False) if cf(price=50000) > 0 else None
    out["gap"] = [
        ["Fewer nights booked than the video assumes", (base["v_rev"] - base["c_rev"]) * (1 - A["video_mgmt_pct"])],
        ["Airbnb's fee", base["c_platform"]],
        ["Moroccan taxes", base["c_ma_tax"]],
        ["Management at %d%% instead of %d%%" % (round(A["mgmt_pct"] * 100), round(A["video_mgmt_pct"] * 100)), base["c_mgmt"] - base["c_rev"] * A["video_mgmt_pct"]],
        ["Building service charge", base["c_syndic"]],
        ["Upkeep, linen, insurance", base["c_upkeep"]],
        ["VAT and insurance on the mortgage", base["c_mort"] - base["v_mort"]],
        ["Home-country tax", base["c_home_tax"]],
    ]
    out["gap"].sort(key=lambda r: -r[1])
    return out


def _screening_message(rec, li):
    price = format(int(rec["asking_price_mad"]), ",").replace(",", " ")
    ref = (" réf. %s," % li["agency_ref"]) if li.get("agency_ref") else ""
    title = rec.get("advert_title") or rec.get("title") or ""
    fr = ("Bonjour, je suis intéressé par votre annonce « %s »,%s à %s DH.\n"
          "Avant d'organiser une visite, pourriez-vous me confirmer :\n"
          "1. Le bien est-il titré (titre foncier) ? Si oui, quel est le numéro du titre ?\n"
          "2. S'agit-il d'un bien achevé avec permis d'habiter, ou d'une vente sur plan ?\n"
          "3. L'adresse ou la localisation exacte (point Google Maps) ?\n"
          "4. La superficie exacte inscrite sur le titre (hors terrasse) et l'année de construction ?\n"
          "5. Le montant mensuel des charges de syndic ?\n"
          "6. La location de courte durée (type Airbnb) est-elle autorisée par le règlement de copropriété ?\n"
          "7. Le prix comprend-il des meubles ou de l'équipement ?\n"
          "8. Votre commission d'agence côté acheteur, TVA comprise ?\n"
          "Merci d'avance." % (title, ref, price))
    en = ("Hello, I'm interested in your listing “%s”,%s at %s DH. Before arranging a viewing, could you confirm: "
          "1. Is it titled, and what is the title number? 2. Is it finished with a certificate of occupancy, or an off-plan sale? "
          "3. The exact address or a map pin? 4. The exact surface on the title (excluding terrace) and the year built? "
          "5. The monthly service charge? 6. Do the building rules allow short-term letting? "
          "7. Does the price include any furniture or equipment? 8. Your buyer-side commission including VAT? Thank you."
          % (title, ref.replace("réf.", "ref."), price))
    return fr, en


# ---------------------------------------------------------------- history
def history():
    rows = []
    for f in sorted((DATA / "runs").glob("*.json"), reverse=True):
        r = _json_file(f, None)
        if not r:
            continue
        m, rec, fx = r.get("metrics") or {}, r.get("record") or {}, r.get("fx_home") or 1
        rows.append({"run_id": r["run_id"], "at": r["at"], "title": rec.get("title"), "city": rec.get("city"), "area": rec.get("neighbourhood"),
                     "asking_mad": rec.get("asking_price_mad"), "ask_m2": m.get("ask_m2"), "verdict": rec.get("verdict"), "source": r.get("source"),
                     "video_profit_home": (m.get("v_profit") or 0) / fx, "checked_profit_home": (m.get("c_profit") or 0) / fx,
                     "home_currency": r.get("home_currency"), "url": r.get("url")})
    return rows


def load_run(run_id):
    if not re.fullmatch(r"[0-9]{8}-[0-9]{6}-[0-9A-Za-z]+", run_id or ""):
        return None
    return _json_file(DATA / "runs" / (run_id + ".json"), None)


# ---------------------------------------------------------------- GitHub sync
_SYNC = threading.Lock()
_last_pull = [0.0]


def _git(*args, timeout=90):
    return subprocess.run(["git", "-C", str(DATA)] + list(args), capture_output=True, text=True, timeout=timeout)


def sync(push=True, message="Update from the deal desk"):
    """Keep this folder and the private GitHub repo in step. Never raises; returns a short status."""
    if not (DATA / ".git").exists():
        return "not linked to GitHub"
    if not _SYNC.acquire(blocking=False):
        return "sync already running"
    try:
        if push and _LOCAL_SKILL.exists():   # refresh the copies GitHub's servers run from
            eng = DATA / "engine"
            for name in ("scripts", "assets", "references"):
                shutil.copytree(_LOCAL_SKILL / name, eng / name, dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            shutil.copy2(_LOCAL_SKILL / "SKILL.md", eng / "SKILL.md")
            if _LIVE_LISTINGS.exists():
                (DATA / "data").mkdir(exist_ok=True)
                export_listings(_LIVE_LISTINGS, DATA / "data" / "listings.js")
        if push:
            _git("add", "-A")
            if _git("diff", "--cached", "--quiet").returncode != 0:
                _git("commit", "-m", message)
        pull = _git("pull", "--rebase", "--autostash", "-X", "theirs")
        _last_pull[0] = time.time()
        if pull.returncode != 0:
            _git("rebase", "--abort")
            return "could not fetch from GitHub: %s" % (pull.stderr or pull.stdout).strip()[-160:]
        if push:
            out = _git("push")
            if out.returncode != 0:
                return "saved here, not yet on GitHub: %s" % (out.stderr or out.stdout).strip()[-160:]
        return "in step with GitHub"
    except Exception as e:
        return "sync skipped: %s" % e
    finally:
        _SYNC.release()


def export_listings(src, dst):
    """The repository is public, so it carries only what the nightly-rate sum needs from the Airbnb file:
    rounded position, bedrooms, review count and spot price. No listing ids, names, hosts or ratings."""
    m = re.search(r"=\s*(\{.*\})\s*;?\s*$", Path(src).read_text(encoding="utf-8"), flags=re.S)
    data = json.loads(m.group(1))
    items = [{"room": i.get("room"), "lat": round(i["lat"], 3), "lng": round(i["lng"], 3), "bedrooms": i.get("bedrooms"),
              "reviews": i.get("reviews"), "adr": i.get("adr"), "priceDate": i.get("priceDate")}
             for i in data.get("items", []) if i.get("lat") is not None and i.get("adr")]
    meta = {k: data.get("meta", {}).get(k) for k in ("pulledAt", "currency", "market")}
    meta["note"] = "Reduced copy: positions rounded to about 100 m; no listing ids or names."
    Path(dst).write_text("// Reduced copy for the public deal desk.\nwindow.STR_LISTINGS = " + json.dumps({"meta": meta, "items": items}, separators=(",", ":")) + ";\n", encoding="utf-8")


def pull_if_stale(seconds=120):
    if time.time() - _last_pull[0] > seconds:
        return sync(push=False)
    return None
