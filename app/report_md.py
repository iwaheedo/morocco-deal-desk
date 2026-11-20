"""Turn a run into a page GitHub can show on any device: results/<date>_<time>_<flat>_<VERDICT>.md"""
import re
import unicodedata
from pathlib import Path

SYM = {"GBP": "£", "EUR": "€", "USD": "$"}


def _n(x):
    return "—" if x is None else format(int(round(x)), ",")


def _pct(x, d=0):
    return "—" if x is None else ("%." + str(d) + "f%%") % (x * 100)


def _slug(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")[:48]


def render(run):
    m, r, t, x, ev = run["metrics"], run["record"], run["terms"], run.get("extras") or {}, run.get("evidence") or {}
    fx, sym = run["fx_home"], SYM.get(run["home_currency"], run["home_currency"] + " ")

    def home(v, signed=False):
        if v is None:
            return "—"
        q = round(v / fx)
        return ("−" if q < 0 else "+" if signed else "") + sym + format(abs(q), ",")

    def neg(v):
        return "−" + _n(v) if v else "0"

    verdict = (r.get("verdict") or "conditional").upper()
    L = []
    L.append("# %s — %s" % (r.get("title") or "Flat", verdict))
    L.append("")
    L.append(r.get("verdict_reason") or "")
    L.append("")
    L.append("Asking **%s MAD** (%s) · %s · [open the advert](%s) · analysed %s%s"
             % (_n(m["asking"]), home(m["asking"]), ("%s MAD/m²" % _n(m["ask_m2"])) if m.get("ask_m2") else "no surface given",
                run["url"].replace(" ", "%20"), run["at"].replace("T", " ")[:16], " · fuller analysis on file" if run.get("source") == "curated" else ""))
    L.append("")
    L.append("Loan terms: %s of the price over %s years, fixed %s (%s with VAT on interest). Price used: %s MAD."
             % (_pct(t["ltv"]), t["term_years"], _pct(t["rate"], 2), _pct(t["rate_eff"], 2), _n(m["price"])))
    L.append("")
    L.append("## The deal, the video's way and checked")
    L.append("")
    L.append("| Per month, MAD | The video's way | Checked |")
    L.append("|---|---:|---:|")
    rows = [
        ("Nightly rate", _n(m["v_adr"]), _n(m["c_adr"])),
        ("Nights booked", "%d (%s)" % (round(m["v_nights"]), _pct(t["video_occ"])), "%.1f (%s)" % (365 * m["occ"]["base"] / 12, _pct(m["occ"]["base"]))),
        ("**Revenue**", "**%s**" % _n(m["v_rev"]), "**%s**" % _n(m["c_rev"])),
        ("Mortgage", neg(m["v_mort"]), neg(m["c_mort"]) + " (with VAT + insurance)"),
        ("Management", "%s (%s)" % (neg(m["v_mgmt"]), _pct(t["video_mgmt_pct"])), "%s (%s)" % (neg(m["c_mgmt"]), _pct(t["mgmt_pct"]))),
        ("Electricity and water", neg(t["utilities_month"]), neg(t["utilities_month"])),
        ("Internet", neg(t["internet_month"]), neg(t["internet_month"])),
        ("TV subscription", neg(t["subs_month"]), neg(t["subs_month"])),
        ("Cleaning", "0 (charged to guest)", "0 (charged to guest)"),
        ("Airbnb fee", "not counted", neg(m["c_platform"])),
        ("Building service charge", "not counted", neg(m["c_syndic"])),
        ("Upkeep, linen, insurance", "not counted", neg(m["c_upkeep"])),
        ("Moroccan taxes", "not counted", neg(m["c_ma_tax"])),
        ("Home-country tax", "not counted", neg(m["c_home_tax"])),
        ("**Profit per month**", "**%s** (%s MAD)" % (home(m["v_profit"], True), _n(m["v_profit"])), "**%s** (%s MAD)" % (home(m["c_profit"], True), _n(m["c_profit"]))),
    ]
    L += ["| %s | %s | %s |" % row for row in rows]
    L.append("")
    L.append("Checked range: bear %s · bull %s a month. Cash you put in either way: **%s** (deposit %s, buying costs %s, mortgage set-up %s, furnishing %s MAD)."
             % (home(m["cf_m_month"]["bear"], True), home(m["cf_m_month"]["bull"], True), home(m["cash_needed_m"]),
                _n(m["deposit"]), _n(m["closing_total"]), _n(m["mort_costs"]), _n(m["furnishing"])))
    if x.get("gap"):
        L += ["", "## Where the %s a month goes" % home(sum(g[1] for g in x["gap"])), "", "| | MAD a month |", "|---|---:|"]
        L += ["| %s | %s |" % (g[0], _n(g[1])) for g in x["gap"] if g[1] > 0.5]
        rc = x.get("real_costs_at_video_occ")
        if rc is not None:
            L += ["", ("With every real cost counted, the flat still loses %s a month at the video's %s occupancy." % (home(-rc), _pct(t["video_occ"])))
                  if rc < 0 else ("With every real cost counted, the flat would make %s a month if it reached the video's %s occupancy." % (home(rc), _pct(t["video_occ"])))]
    mk = ev.get("market") or {}
    L += ["", "## The numbers behind it", "", "| | |", "|---|---|"]
    facts = [
        ("Fair value", ("≈ %s MAD — asking is %s %s it (%d comparable adverts%s)" % (
            _n(m["fair_mid"]), _pct(abs(m["asking_over_fair"])), "above" if m["asking_over_fair"] >= 0 else "below", len(r.get("comps_sale") or []),
            (", Agenz reference %s MAD/m²" % _n(ev["agenz"]["mad_per_m2"])) if ev.get("agenz") else "")) if m.get("fair_mid") else "not enough comparables"),
        ("Offer", "open %s · target %s · walk away above %s MAD" % (_n(m["offer_open"]), _n(m["offer_target"]), _n(m["offer_walk"]))),
        ("Mortgage", "%s MAD a month · %s MAD over %s years · costs %s of the price a year" % (_n(m["c_mort"]), _n(m["loan"]), t["term_years"], _pct(m["ds_pct"], 1))),
        ("Break-even occupancy", "%s (market average %s%s)" % (_pct(m["be_occ_m"]["base"]), _pct(mk.get("occ")), (" in " + mk["city"].title()) if mk.get("city") else "")),
        ("Nightly rate to break even", ("%s MAD at %s occupancy" % (_n(x["be_adr_at_base_occ"]), _pct(m["occ"]["base"]))) if x.get("be_adr_at_base_occ") else "—"),
        ("Nightly rate modelled", "%s / %s / %s MAD (bear / base / bull)" % (_n(m["adr"]["bear"]), _n(m["adr"]["base"]), _n(m["adr"]["bull"]))),
        ("Price that pays its own mortgage", ("%s MAD (%s of asking)" % (_n(x["be_price"]), _pct(x["be_price"] / m["asking"]))) if x.get("be_price") else "none on these terms"),
        ("Ten years, then sell", "%s / %s / %s in total, for prices growing %s / %s / %s a year" % (
            home(m["profit_m"]["bear"], True), home(m["profit_m"]["base"], True), home(m["profit_m"]["bull"], True),
            _pct(m["growth"]["bear"], 1), _pct(m["growth"]["base"], 1), _pct(m["growth"]["bull"], 1))),
        ("If bought for cash", "%s a month, %s net yield" % (home(m["net"]["base"] / 12, True), _pct(m["net_yield_c"]["base"], 1))),
    ]
    L += ["| %s | %s |" % f for f in facts]
    L += ["", "## Flags", ""]
    L += ["- **%s** — %s" % ((f.get("severity") or "").upper(), f.get("text")) for f in (r.get("flags") or [])]
    L += ["", "## What the advert doesn't say", ""]
    L += ["%d. %s" % (i, u) for i, u in enumerate(r.get("unknowns") or [], 1)]
    L += ["", "## First message to the agent", "", "```text", run.get("message_fr") or "", "```", "", "*%s*" % (run.get("message_en") or "")]
    s = r.get("str") or {}
    L += ["", "## Evidence", "", "**Nightly rate.** %s" % (s.get("adr_note") or ""), "", "**Occupancy.** %s" % (s.get("occupancy_note") or ""), ""]
    if s.get("comps"):
        L += ["| Airbnb / holiday-let comparable | Per night | Reviews |", "|---|---:|---:|"]
        L += ["| %s | %s MAD | %s |" % (("[%s](%s)" % (c.get("desc"), c["url"])) if c.get("url") else c.get("desc"), _n(c.get("nightly_mad")), c.get("reviews") if c.get("reviews") is not None else "—") for c in s["comps"]]
    if r.get("comps_sale"):
        L += ["", "**Price.** %s" % ((r.get("area_price_per_m2") or {}).get("basis") or "Asking prices from adverts, less the assumed 10% between asking and sold."), "",
              "| Flat for sale nearby | Asking | m² | MAD/m² |", "|---|---:|---:|---:|"]
        L += ["| [%s](%s) | %s | %s | %s |" % (c.get("desc"), (c.get("url") or "").replace(" ", "%20"), _n(c["price_mad"]), _n(c["surface_m2"]), _n(c["price_mad"] / c["surface_m2"])) for c in r["comps_sale"]]
    chk = run.get("check") or {}
    L += ["", "---", ("Sums checked: %s spreadsheet cells recalculated independently and matched." % chk.get("cells_checked")) if chk.get("verified")
          else "Sums not independently re-checked on this run.", "Automatic first pass, not legal, tax or financial advice. Run `%s`." % run["run_id"], ""]
    return "\n".join(L)


def save(run, folder):
    folder = Path(folder)
    folder.mkdir(exist_ok=True)
    r = run["record"]
    stamp = run["at"][:16].replace("T", "_").replace(":", "")
    name = "%s_%s_%s.md" % (stamp, _slug("%s %s %s-bed" % (r.get("city") or "", r.get("neighbourhood") or "", r.get("bedrooms") if r.get("bedrooms") is not None else "x")),
                            (r.get("verdict") or "conditional").upper())
    (folder / name).write_text(render(run), encoding="utf-8")
    return "results/" + name
