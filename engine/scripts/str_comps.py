#!/usr/bin/env python3
"""Short-let comparables near a point, from the user's own Airbnb atlas.

Reads morocco-str/listings.js — the listings behind the user's atlas
(https://iwaheedo.github.io/morocco-str-atlas/): position, bedrooms, rating, review
count, a ONE-NIGHT spot price on a stated date, and the atlas's own estimate of each
listing's occupancy and yearly revenue. It makes no network requests itself; a caller
may pass the file's text (for example fetched from the published atlas) as `text`.

  str_comps.py --lat 34.002 --lng -6.850 --beds 2 [--radius-km 1.0] [--min-reviews 5]
               [--file PATH] [--fx MAD_PER_UNIT]

Prints JSON: how many comparable entire homes lie within the radius, the spread of
their nightly prices (in the file's currency and in MAD), and the nearest /
best-established ones.

What the numbers are and are not:
- price: what Airbnb displayed for a single night on `priceDate`, for a listing still
  AVAILABLE that night. Not an achieved average rate; may include fees.
- occupancy (`occ`): the atlas's ESTIMATE for each listing with 3+ reviews — listings are
  ranked by reviews per year of age and given the occupancy AirROI measures at that rank
  in the city. An estimate for comparing listings, not a measurement.
- atlas revenue (`rev`): price x occupancy x the nights a typical host in that city keeps
  the calendar open (243 in Rabat). A flat let all year is open 365.
- calendar: share of the next six weeks already taken (bookings AND host blocks).
"""
import argparse
import datetime
import json
import math
import re
import statistics
import sys
import unicodedata
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


def quart(values):
    """Quartiles as plain numbers (no rounding), or None."""
    v = sorted(values)
    if not v:
        return None
    if len(v) < 4:
        return {"n": len(v), "p25": v[0], "median": statistics.median(v), "p75": v[-1]}
    q = statistics.quantiles(v, n=4, method="inclusive")
    return {"n": len(v), "p25": q[0], "median": q[1], "p75": q[2]}


def _plain(s):
    return re.sub(r"[^a-z0-9]+", " ", unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()).strip()


def comps(lat, lng, beds=None, radius_km=1.0, min_reviews=0, file=None, fx=None, text=None, city=None):
    """Comparable entire homes near a point, as a dict. Returns {"error": ...} when the data is missing."""
    path = Path(file).expanduser() if file else DEFAULT_FILE
    if text is None:
        if not path.exists():
            return {"error": "No listing data at %s" % path,
                    "hint": "This file only exists for markets the user has collected (Rabat). Use the browser-pane method in references/rental-analysis.md instead."}
        text = path.read_text(encoding="utf-8")
    m = re.search(r"=\s*(\{.*\})\s*;?\s*$", text, flags=re.S)
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
        if city and _plain(it.get("city") or (meta.get("market") or {}).get("locality")) != _plain(city):   # older files: one city, named in the header
            continue
        d = km(lat, lng, it["lat"], it["lng"])
        if d <= radius_km:
            near.append((d, it))
    near.sort(key=lambda x: x[0])
    prices = [it["adr"] for _d, it in near]
    best = sorted(near, key=lambda x: -(x[1].get("reviews") or 0))[:12]
    # Occupancy the atlas estimated for each listing (review rate ranked against the city's measured spread),
    # what each one earns per night of the year (price x occupancy), and how full their calendars are right now.
    with_occ = [it for _d, it in near if it.get("occ") is not None and not it.get("priceOdd")]
    occs = [it["occ"] / 100.0 for it in with_occ]
    per_night_of_year = [it["adr"] * it["occ"] / 100.0 * fx for it in with_occ]
    cal = [it["calOcc"] / 100.0 for _d, it in near if it.get("calOcc") is not None]
    # Older atlas files cover one city and say so only in the header; newer ones tag every listing with its city.
    home_city = (meta.get("market") or {}).get("locality")
    city_of = lambda it: it.get("city") or home_city
    cities = sorted({city_of(it) for it in with_occ if city_of(it)}, key=lambda c: -sum(1 for it in with_occ if city_of(it) == c))
    city_meta = ((meta.get("cities") or {}).get(cities[0]) or {}) if cities else {}
    open_nights = city_meta.get("openNights") or meta.get("openNights")
    top_occ = city_meta.get("topQuarterOcc") or meta.get("topQuarterOcc")
    # reviews a year for each listing: an independent handle on how many stays it really gets
    try:
        d0 = datetime.date.fromisoformat(meta.get("pulledAt"))
        now = d0.year + (d0.timetuple().tm_yday - 1) / 365.25
    except (TypeError, ValueError):
        now = None
    pace = [it["reviews"] / max(now - it["since"], 0.25) for it in with_occ if now and it.get("since") and it.get("reviews")]
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
        "with_occupancy": len(with_occ),
        "occupancy": quart(occs),
        "earned_per_night_of_year_mad": quart(per_night_of_year),
        "price_mad_with_occupancy": quart([it["adr"] * fx for it in with_occ]),
        "atlas_revenue_month_mad": quart([it["rev"] * fx / 12 for it in with_occ if it.get("rev")]),
        "atlas_potential_month_mad": quart([it["adr"] * fx * 365 / 12 * top_occ / 100.0 for it in with_occ]) if top_occ else None,
        "atlas_open_nights": open_nights,
        "atlas_top_quarter_occupancy": (top_occ / 100.0) if top_occ else None,
        "reviews_per_year": quart(pace),
        "cities": cities,
        "cities_in_file": sorted((meta.get("cities") or {}).keys()) or ([home_city] if home_city else []),
        "each_listing": [{"price_mad": round(it["adr"] * fx), "occ": it["occ"] / 100.0,
                          "atlas_rev_month_mad": round(it["rev"] * fx / 12) if it.get("rev") else None} for it in with_occ],
        "calendar": ({"n": len(cal), "median_taken": statistics.median(cal), "from": meta.get("calFrom"), "to": meta.get("calTo")} if cal else None),
        "caveat": "Prices are one-night spot prices on each listing's priceDate, for nights still unbooked. Occupancy and revenue are the atlas's "
                  "estimates from review pace, not measurements. Fewer than ~8 matches is thin: widen the radius.",
        "most_established": [
            {"name": it.get("name"), "bedrooms": it.get("bedrooms"), "rating": it.get("rating"), "reviews": it.get("reviews"),
             "price": it.get("adr"), "price_mad": round(it["adr"] * fx), "price_date": it.get("priceDate"),
             "occ": it.get("occ"), "cal_taken": it.get("calOcc"),
             "km_away": round(d, 2), "superhost": it.get("superhost"), "url": ("https://www.airbnb.co.uk/rooms/%s" % it["id"]) if it.get("id") else None}
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
    ap.add_argument("--city", help="only listings the atlas places in this city")
    a = ap.parse_args()
    out = comps(a.lat, a.lng, a.beds, a.radius_km, a.min_reviews, a.file, a.fx, city=a.city)
    print(json.dumps(out, ensure_ascii=False, indent=1))
    if "error" in out:
        sys.exit(2)


if __name__ == "__main__":
    main()
