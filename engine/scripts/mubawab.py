#!/usr/bin/env python3
"""Read Mubawab (mubawab.ma) without a browser — it serves plain HTML.

  mubawab.py listing <listing-url>
      One listing as JSON: price, surface, rooms, state, amenities, description,
      dates, agency, plus ready-made search URLs for the same neighbourhood
      (for sale / to rent / holiday rental).

  mubawab.py search <search-url> [<search-url> ...] [--min-m2 N] [--max-m2 N]
                    [--beds N] [--exclude-id ID] [--exclude-new-build] [--fx-eur 10.96]
      Every listing card on the FIRST page of each search URL (about 33 cards) as JSON, with MAD per m² and
      summary statistics (median, quartiles) over the listings that pass the
      filters. New-development adverts ("à partir de" prices) are listed but
      left out of the statistics.

Search URL shapes (accents in the area slug must be kept; they are URL-encoded for you):
  https://www.mubawab.ma/fr/st/<city>/appartements-a-vendre             whole city, for sale
  https://www.mubawab.ma/fr/sd/<city>/<area>/appartements-a-vendre      one neighbourhood
  ...appartements-a-louer        long-term rentals (price = MAD per month)
  ...appartements-vacational     holiday rentals (price = MAD per night, "par jour")
  swap "appartements" for villas-et-maisons-de-luxe, maisons, riads, studios ...
  Only first pages are read: the site's robots.txt disallows paginated/filtered URLs (those
  containing ":"), so widen with more search URLs (next-door neighbourhood, whole city) instead.

These are ASKING prices from adverts, not sold prices. Standard library only.
"""
import argparse
import html
import json
import re
import statistics
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

UA = "property-research-script/1.0 (personal, low-volume; one page per request)"


MAX_BYTES = 4_000_000


def _allowed(url):
    parts = urllib.parse.urlsplit(url)
    host = (parts.hostname or "").lower()
    return parts.scheme == "https" and (host == "mubawab.ma" or host.endswith(".mubawab.ma"))


class _SameSiteRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not _allowed(newurl):
            raise urllib.error.URLError("redirect to another site refused: %s" % urllib.parse.urlsplit(newurl).hostname)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_opener = urllib.request.build_opener(_SameSiteRedirects)


def fetch(url):
    """Fetch one Mubawab page. Refuses any other site, plain http, and redirects that leave Mubawab."""
    parts = urllib.parse.urlsplit(url)
    path = urllib.parse.quote(urllib.parse.unquote(parts.path), safe="/:")
    url = urllib.parse.urlunsplit((parts.scheme, parts.netloc, path, parts.query, ""))
    if not _allowed(url):
        raise urllib.error.URLError("only https://www.mubawab.ma pages are read")
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8"})
    with _opener.open(req, timeout=30) as r:
        return r.read(MAX_BYTES).decode("utf-8", errors="ignore"), r.geturl()


def clean(fragment):
    text = re.sub(r"<[^>]+>", " ", fragment)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def parse_price(text):
    """'841 800 DH' -> (841800.0, 'MAD', ''), '450 DH par jour' -> (450.0, 'MAD', 'par jour')."""
    text = clean(text)
    m = re.search(r"(\d[\d\s\u00a0\u202f.,]*)\s*(DH|MAD|EUR|€|USD|\$|GBP|£)\s*(par\s+\w+|/\s*\w+)?", text)
    if not m:
        return None, None, text[:60]
    digits = re.sub(r"[^\d]", "", m.group(1))
    if not digits:
        return None, None, text[:60]
    cur = {"DH": "MAD", "MAD": "MAD", "EUR": "EUR", "€": "EUR", "USD": "USD", "$": "USD", "GBP": "GBP", "£": "GBP"}[m.group(2)]
    return float(digits), cur, (m.group(3) or "").strip()


NEW_BUILD = re.compile(r"\bneufs?\b|hors[ -]plan|sur plan|programme|livraison|promoteur|vefa|en cours de construction|nouveau d[ée]veloppement", re.I)


def _int(pattern, text):
    m = re.search(pattern, text, flags=re.I)
    return int(m.group(1)) if m else None


def parse_details(fragments):
    out = {"surface_m2": None, "rooms": None, "bedrooms": None, "bathrooms": None}
    for f in fragments:
        t = clean(f)
        if out["surface_m2"] is None:
            m = re.fullmatch(r"(\d[\d\s]*)\s*m²", t)
            if m:
                out["surface_m2"] = float(re.sub(r"\s", "", m.group(1)))
                continue
        if out["rooms"] is None and re.search(r"Pi[èe]ce", t):
            out["rooms"] = _int(r"(\d+)", t)
        elif out["bedrooms"] is None and re.search(r"\bCh\b|Chambre", t):
            out["bedrooms"] = _int(r"(\d+)", t)
        elif out["bathrooms"] is None and re.search(r"Salle", t):
            out["bathrooms"] = _int(r"(\d+)", t)
    return out


def to_mad(price, cur, fx):
    if price is None:
        return None
    if cur == "MAD":
        return price
    rate = fx.get(cur)
    return price * rate if rate else None


def parse_search_page(page, fx):
    listings = []
    for block in re.split(r'(?=<div class="listingBox)', page)[1:]:
        head = re.match(r'<div class="(listingBox[^"]*)"\s+linkRef="([^"]+)"', block)
        if not head:
            continue
        url = html.unescape(head.group(2))
        id_m = re.search(r"/fr/(pa|a|p)/(\d+)/", url)
        price_m = re.search(r'class="priceTag[^"]*">(.*?)</span>\s*(?:<div|<i|<img|</div)', block, flags=re.S)
        price, cur, per = parse_price(price_m.group(1)) if price_m else (None, None, "")
        title_m = re.search(r'class="listingTit[^"]*">\s*<a[^>]*>(.*?)</a>', block, flags=re.S)
        loc_m = re.search(r'class="listingH3">(.*?)</span>', block, flags=re.S)
        det = parse_details(re.findall(r'class="adDetailFeature">(.*?)</div>', block, flags=re.S))
        feats = [clean(x) for x in re.findall(r'class="adFeature">(.*?)</div>', block, flags=re.S)]
        price_mad = to_mad(price, cur, fx)
        item = {
            "id": id_m.group(2) if id_m else None,
            "url": url,
            "title": clean(title_m.group(1)) if title_m else None,
            "location": clean(loc_m.group(1)) if loc_m else None,
            "price": price, "currency": cur, "price_per": per or None, "price_mad": price_mad,
            **det,
            "features": [f for f in feats if f],
            "new_development": bool(id_m and id_m.group(1) == "p") or "IMMOBILIER NEUF" in block or "partir de" in (price_m.group(1) if price_m else ""),
            "mentions_new_build": bool(NEW_BUILD.search(clean(title_m.group(1)) if title_m else "")),
            "promoted": "remium" in head.group(1) or "Boost" in head.group(1) or "spotlight" in head.group(1),
        }
        item["mad_per_m2"] = round(price_mad / det["surface_m2"]) if price_mad and det["surface_m2"] else None
        listings.append(item)
    total = re.search(r"\(\s*([\d\s\u00a0]+)\s*résultats?\s*\)", clean(page))
    return listings, (int(re.sub(r"\D", "", total.group(1))) if total else None)


def quantiles(values):
    v = sorted(values)
    if not v:
        return None
    if len(v) < 4:
        return {"n": len(v), "min": v[0], "median": round(statistics.median(v)), "max": v[-1]}
    q = statistics.quantiles(v, n=4, method="inclusive")
    return {"n": len(v), "min": v[0], "p25": round(q[0]), "median": round(q[1]), "p75": round(q[2]), "max": v[-1]}


def cmd_search(a):
    fx = {"EUR": a.fx_eur, "USD": a.fx_usd, "GBP": a.fx_gbp}
    # One page per search URL. Mubawab's robots.txt disallows URLs containing ":" (pagination and
    # filters), so this helper never requests them. For more comparables, pass several search URLs
    # (neighbourhood, adjoining neighbourhood, whole city) rather than paging.
    seen, listings, total, pages_read, sources = set(), [], None, 0, []
    for raw in a.url:
        cut = raw.find(":", raw.find("://") + 3)   # drop any ":p:2"-style suffix
        base = raw if cut == -1 else raw[:cut]
        page, _ = fetch(base)
        found, tot = parse_search_page(page, fx)
        total = (total or 0) + (tot or 0) if tot else total
        for x in found:
            if x["id"] not in seen:
                seen.add(x["id"])
                x["from_search"] = base
                listings.append(x)
        pages_read += 1
        sources.append(base)
        time.sleep(1.5)
    base = sources[0] if len(sources) == 1 else sources

    def passes(x):
        if x["new_development"] or x["id"] == a.exclude_id:
            return False
        if a.exclude_new_build and x["mentions_new_build"]:
            return False
        if a.min_m2 and (x["surface_m2"] is None or x["surface_m2"] < a.min_m2):
            return False
        if a.max_m2 and (x["surface_m2"] is None or x["surface_m2"] > a.max_m2):
            return False
        if a.beds is not None and x["bedrooms"] != a.beds:
            return False
        return True

    kept = [x for x in listings if passes(x)]
    for x in listings:
        x["in_stats"] = x in kept
    per_m2 = [x["mad_per_m2"] for x in kept if x["mad_per_m2"]]
    prices = [x["price_mad"] for x in kept if x["price_mad"]]
    # Typos are common (an extra zero, rent typed as a sale price): flag anything far from the median.
    suspects = []
    if len(per_m2) >= 5:
        med = statistics.median(per_m2)
        for x in kept:
            v = x["mad_per_m2"]
            x["suspect_outlier"] = bool(v and (v > med * 2.5 or v < med / 2.5))
            if x["suspect_outlier"]:
                suspects.append(x["id"])
    trimmed = [x["mad_per_m2"] for x in kept if x["mad_per_m2"] and not x.get("suspect_outlier")]
    out = {
        "source": base, "pages_read": pages_read, "results_on_site": total,
        "listings_read": len(listings), "listings_in_stats": len(kept),
        "filters": {"min_m2": a.min_m2, "max_m2": a.max_m2, "beds": a.beds, "exclude_id": a.exclude_id,
                    "new_developments": "developer project pages ('à partir de' prices) excluded from stats",
                    "exclude_new_build": a.exclude_new_build},
        "stats_mad_per_m2": quantiles(trimmed),
        "stats_mad_per_m2_including_suspect_outliers": quantiles(per_m2) if suspects else None,
        "suspect_outlier_ids": suspects,
        "stats_price_mad": quantiles(prices),
        "caveat": "Asking prices from adverts (sale), monthly rents (a-louer) or nightly rates (vacational). "
                  "Not transaction prices. Check outliers by hand: wrong surface, price per night vs per month, duplicates.",
        "listings": listings,
    }
    return out


def cmd_listing(a):
    page, final_url = fetch(a.url)
    ld = {}
    for raw in re.findall(r'<script type="application/ld\+json">(.*?)</script>', page, flags=re.S):
        try:
            d = json.loads(raw, strict=False)
        except ValueError:
            continue
        if isinstance(d, dict) and d.get("@type") == "RealEstateListing":
            ld = d
            break
    price_m = re.search(r'class="orangeTit">(.*?)</h3>', page, flags=re.S)
    price, cur, per = parse_price(price_m.group(1)) if price_m else (None, None, "")
    det = parse_details(re.findall(r'class="adDetailFeature">(.*?)</div>', page, flags=re.S))
    main = {}
    for frag in re.findall(r'class="adMainFeatureContent">(.*?)</div>\s*</div>', page, flags=re.S):
        parts = [clean(p) for p in re.findall(r"<p[^>]*>(.*?)</p>", frag, flags=re.S)]
        parts = [p for p in parts if p]
        if len(parts) >= 2:
            main[parts[0].rstrip(":")] = parts[1]
        else:
            t = clean(frag)
            if ":" in t:
                k, v = t.split(":", 1)
                main[k.strip()] = v.strip()
            elif t:
                main[t] = True
    crumbs = re.findall(r'<a class="darkblue" href="([^"]+)" title="([^"]*)"', page)
    area_url = next((u for u, _t in crumbs if "/fr/sd/" in u), None)
    city_url = next((u for u, _t in crumbs if "/fr/st/" in u), None)
    base = html.unescape(area_url or city_url or "")
    searches = {}
    if base:
        kind = re.sub(r"-a-(vendre|louer)$|-vacational$", "", base.rsplit("/", 1)[-1])
        root = base.rsplit("/", 1)[0]
        searches = {"for_sale": "%s/%s-a-vendre" % (root, kind), "to_rent": "%s/%s-a-louer" % (root, kind),
                    "holiday_rental": "%s/%s-vacational" % (root, kind)}
        searches = {k: urllib.parse.unquote(v) for k, v in searches.items()}
    agency = re.search(r'class="link businessName">\s*<a href="([^"]+)">(.*?)</a>', page, flags=re.S)
    ref = re.search(r"Réf:\s*([^<]+)<", page)
    loc = re.search(r'class="greyTit">(.*?)<', page, flags=re.S)
    id_m = re.search(r"/fr/(pa|a|p)/(\d+)/", final_url)
    desc = html.unescape(ld.get("description") or "").replace("\r\n", "\n")
    out = {
        "id": id_m.group(2) if id_m else None,
        "url": urllib.parse.unquote(final_url),
        "title": html.unescape(ld.get("name") or "") or None,
        "location": clean(loc.group(1)) if loc else None,
        "breadcrumb": [html.unescape(t) for _u, t in crumbs],
        "price": price, "currency": cur, "price_per": per or None,
        "price_mad": price if cur == "MAD" else None,
        **det,
        "mad_per_m2": round(price / det["surface_m2"]) if (price and cur == "MAD" and det["surface_m2"]) else None,
        "main_features": main,
        "amenities": sorted({clean(x) for x in re.findall(r'class="adFeature">(.*?)</div>', page, flags=re.S)} - {""}),
        "date_posted": ld.get("datePosted"), "date_modified": ld.get("dateModified"),
        "agency": clean(agency.group(2)) if agency else None,
        "agency_url": agency.group(1) if agency else None,
        "agency_ref": ref.group(1).strip() if ref else None,
        "new_development": bool(id_m and id_m.group(1) == "p"),
        "mentions_new_build": bool(NEW_BUILD.search(" ".join([html.unescape(ld.get("name") or ""), desc, " ".join("%s %s" % kv for kv in main.items())]))),
        "photos": len(ld.get("image") or []),
        "photo_urls": (ld.get("image") or [])[:12],
        "description": desc,
        "comparable_searches": searches,
        "not_on_the_page": "Title status (titre foncier / melkia), exact address, syndic charges and agent commission are "
                           "almost never in the advert — ask the seller.",
    }
    return out


def get_listing(url):
    """One listing as a dict (same content the `listing` command prints)."""
    return cmd_listing(argparse.Namespace(url=url))


def search(urls, min_m2=None, max_m2=None, beds=None, exclude_id=None, exclude_new_build=False, fx_eur=None, fx_usd=None, fx_gbp=None):
    """First page of each search URL as a dict (same content the `search` command prints)."""
    return cmd_search(argparse.Namespace(url=list(urls), min_m2=min_m2, max_m2=max_m2, beds=beds, exclude_id=exclude_id,
                                         exclude_new_build=exclude_new_build, fx_eur=fx_eur, fx_usd=fx_usd, fx_gbp=fx_gbp))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("search")
    s.add_argument("url", nargs="+", help="one or more search-page URLs (first page of each is read)")
    s.add_argument("--min-m2", type=float)
    s.add_argument("--max-m2", type=float)
    s.add_argument("--beds", type=int)
    s.add_argument("--exclude-id", help="the listing you are analysing, so it is not its own comparable")
    s.add_argument("--exclude-new-build", action="store_true", help="drop adverts whose title mentions new-build / off-plan")
    s.add_argument("--fx-eur", type=float, help="MAD per EUR, to convert adverts priced in euros")
    s.add_argument("--fx-usd", type=float)
    s.add_argument("--fx-gbp", type=float)
    s.set_defaults(func=cmd_search)
    li = sub.add_parser("listing")
    li.add_argument("url")
    li.set_defaults(func=cmd_listing)
    a = ap.parse_args()
    try:
        print(json.dumps(a.func(a), ensure_ascii=False, indent=1))
    except urllib.error.HTTPError as e:
        print(json.dumps({"error": "HTTP %s from Mubawab for %s" % (e.code, e.url),
                          "hint": "Check the URL (area slugs keep their accents, e.g. guéliz), or open the page in the browser instead."}))
        sys.exit(2)
    except urllib.error.URLError as e:
        print(json.dumps({"error": "Could not reach Mubawab: %s" % e.reason}))
        sys.exit(2)


if __name__ == "__main__":
    main()
