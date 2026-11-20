#!/usr/bin/env python3
"""Short-let comparables near a point, from the user's own dashboard data.

Reads morocco-str/listings.js — Airbnb listings the user collected for their Rabat
dashboard (position, bedrooms, rating, review count and a ONE-NIGHT spot price on a
stated date). It makes no network requests.

  str_comps.py --lat 34.002 --lng -6.850 --beds 2 [--radius-km 1.0] [--min-reviews 5]
               [--file PATH] [--fx MAD_PER_UNIT]

Prints JSON: how many comparable entire homes lie within the radius, the spread of
their nightly prices (in the file's currency and in MAD), and the nearest /
best-established ones.

What the price is and is not: it is the price Airbnb displayed for a single night
on `priceDate`, for a listing that was still AVAILABLE that night. It is not an
achieved average rate, says nothing about occupancy, and may include fees. Use it
to place a flat within its local market, then take the year-round rate from the
scenarios method in references/rental-analysis.md.
"""
import argparse
import json
import math
import re
import statistics
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
DEFAULT_FILE = Path.home() / "Desktop" / "Other random coding" / "morocco-str" / "listings.js"


def km(lat1, lng1, lat2, lng2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lng2 - lng1) / 2) ** 2
    return 6371.0 * 2 * math.asin(math.sqrt(a))


def spread(values):
    v = sorted(values)
    if not v:
        return None
    if len(v) < 4:
        return {"n": len(v), "min": round(v[0]), "median": round(statistics.median(v)), "max": round(v[-1])}
    q = statistics.quantiles(v, n=4, method="inclusive")
    return {"n": len(v), "min": round(v[0]), "p25": round(q[0]), "median": round(q[1]), "p75": round(q[2]), "max": round(v[-1])}


def comps(lat, lng, beds=None, radius_km=1.0, min_reviews=0, file=None, fx=None):
    """Comparable entire homes near a point, as a dict. Returns {"error": ...} when the data is missing."""
    path = Path(file).expanduser() if file else DEFAULT_FILE
    if not path.exists():
        return {"error": "No listing data at %s" % path,
                "hint": "This file only exists for markets the user has collected (Rabat). Use the browser-pane method in references/rental-analysis.md instead."}
    m = re.search(r"=\s*(\{.*\})\s*;?\s*$", path.read_text(encoding="utf-8"), flags=re.S)
    if not m:
        return {"error": "Could not read %s (expected 'window.STR_LISTINGS = {...}')" % path}
    data = json.loads(m.group(1))
    meta, items = data.get("meta", {}), data.get("items", [])
    cur = (meta.get("currency") or "GBP").upper()
    if fx is None:
        rows = json.loads((SKILL_DIR / "assets" / "defaults.json").read_text(encoding="utf-8"))["assumptions"]
        rates = {r["key"]: r.get("value") for r in rows}
        fx = 1.0 if cur == "MAD" else rates.get("fx_" + cur.lower())
    if not fx:
        return {"error": "No exchange rate for %s; pass fx" % cur}
    near = []
    for it in items:
        if it.get("room") != "entire_home" or it.get("lat") is None or not it.get("adr"):
            continue
        if beds is not None and it.get("bedrooms") != beds:
            continue
        if (it.get("reviews") or 0) < min_reviews:
            continue
        d = km(lat, lng, it["lat"], it["lng"])
        if d <= radius_km:
            near.append((d, it))
    near.sort(key=lambda x: x[0])
    prices = [it["adr"] for _d, it in near]
    best = sorted(near, key=lambda x: -(x[1].get("reviews") or 0))[:12]
    return {
        "source": str(path),
        "collected_on": meta.get("pulledAt"),
        "market": (meta.get("market") or {}).get("locality"),
        "listings_in_file": len(items),
        "filters": {"lat": lat, "lng": lng, "radius_km": radius_km, "beds": beds, "min_reviews": min_reviews, "room": "entire_home"},
        "matches": len(near),
        "currency": cur,
        "mad_per_unit": fx,
        "one_night_price": spread(prices),
        "one_night_price_mad": spread([p * fx for p in prices]),
        "caveat": "One-night spot prices on each listing's priceDate, for nights still unbooked. Not an achieved average, no occupancy. "
                  "Fewer than ~8 matches is thin: widen the radius.",
        "most_established": [
            {"name": it.get("name"), "bedrooms": it.get("bedrooms"), "rating": it.get("rating"), "reviews": it.get("reviews"),
             "price": it.get("adr"), "price_mad": round(it["adr"] * fx), "price_date": it.get("priceDate"),
             "km_away": round(d, 2), "superhost": it.get("superhost"), "url": "https://www.airbnb.co.uk/rooms/%s" % it.get("id")}
            for d, it in best
        ],
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--lat", type=float, required=True)
    ap.add_argument("--lng", type=float, required=True)
    ap.add_argument("--beds", type=int, help="bedrooms to match exactly")
    ap.add_argument("--radius-km", type=float, default=1.0)
    ap.add_argument("--min-reviews", type=int, default=0, help="ignore listings with fewer reviews (new listings price erratically)")
    ap.add_argument("--file", default=str(DEFAULT_FILE))
    ap.add_argument("--fx", type=float, help="MAD per 1 unit of the file's currency (default: from assets/defaults.json)")
    a = ap.parse_args()
    out = comps(a.lat, a.lng, a.beds, a.radius_km, a.min_reviews, a.file, a.fx)
    print(json.dumps(out, ensure_ascii=False, indent=1))
    if "error" in out:
        sys.exit(2)


if __name__ == "__main__":
    main()
