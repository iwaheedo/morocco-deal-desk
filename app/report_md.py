"""Turn a run into a page GitHub can show on any device: results/<date>_<time>_<flat>_<VERDICT>.md

Every dirham figure is written with its home-currency twin beside it."""
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
    S = ev.get("str") or {}
    near = S.get("method") == "nearby_listings"

    def home(v, signed=False):
        if v is None:
            return "—"
        q = round(v / fx)
        return ("−" if q < 0 else "+" if signed else "") + sym + format(abs(q), ",")

    def both(v, unit="", signed=False):
        """A dirham amount with its home-currency twin."""
        if v is None:
            return "—"
        return "%s%s MAD%s (%s)" % ("−" if v < 0 else "+" if signed else "", _n(abs(v)), unit, home(v, signed))

    def less(v):
        return both(-abs(v)) if v and round(v) else "0 MAD (%s0)" % sym

    def put_in(v):
        return ("you put in %s (%s MAD)" % (home(v), _n(v))) if v and v > 0.5 else "nothing: it covers itself"

    label = r.get("verdict_label") or (r.get("verdict") or "conditional").upper()
    budget = x.get("budget_mad") or 0
    top = x.get("topup") or {k: max(0.0, -m["cf_m_month"][k]) for k in ("bear", "base", "bull")}
    nights = 365 * m["occ"]["base"] / 12
    L = ["# %s — %s" % (r.get("title") or "Flat", label), "", (r.get("verdict_reason") or ""), ""]
    L.append("Asking **%s** · %s · [open the advert](%s) · analysed %s"
             % (both(m["asking"]), both(m["ask_m2"], " per m²") if m.get("ask_m2") else "no surface given",
                run["url"].replace(" ", "%20"), run["at"].replace("T", " ")[:16]))
    L.append("")
    L.append("Loan: %s of the price over %s years, fixed %s (%s with VAT on interest). Price used: %s.%s"
             % (_pct(t["ltv"]), t["term_years"], _pct(t["rate"], 2), _pct(t["rate_eff"], 2), both(m["price"]),
                (" Your limit: %s a month out of pocket (%s MAD)." % (home(budget), _n(budget))) if budget else ""))

    # ---- buying
    N = x.get("notary")
    L += ["", "## Buying", ""]
    if m.get("fair_mid"):
        L.append("Fair price about **%s**: asking is %s %s it (%d comparable adverts%s). Open at %s, aim for %s, walk away above %s."
                 % (both(m["fair_mid"]), _pct(abs(m["asking_over_fair"])), "above" if m["asking_over_fair"] >= 0 else "below", len(r.get("comps_sale") or []),
                    (", Agenz reference %s" % both(ev["agenz"]["mad_per_m2"], " per m²")) if ev.get("agenz") else "",
                    both(m["offer_open"]), both(m["offer_target"]), both(m["offer_walk"])))
        L.append("")
    if N:
        L += ["| Notary simulator: the bill on completion day | |", "|---|---:|", "| Price you expect to pay | %s |" % both(N["price"])]
        L += ["| %s | %s |" % (lab, both(v)) for lab, v in N["lines"]]
        L += ["| **= paid through the notary (%s of the price)** | **%s** |" % (_pct(N["share"], 2), both(N["total"])),
              "| Estate agent | %s |" % both(m["agent"])]
        L += ["| %s | %s |" % (lab, both(v)) for lab, v in N["mortgage_lines"] if v > 0.5]
        if m.get("furnishing"):
            L.append("| Furniture (estimate) | %s |" % both(m["furnishing"]))
        L += ["| Your deposit (%s) | %s |" % (_pct(1 - t["ltv"]), both(m["deposit"])),
              "| **= cash you need on day one (with the cost of changing money)** | **%s** |" % both(m["cash_needed_m"]), ""]
        eg = N.get("example")
        if eg:
            L.append("Cross-check: a Moroccan fee guide's worked example (Wafir, 2026) for a %s flat comes to about %s; these lines give %s. "
                     "The exact figure is the notary's own written quote (“décompte des frais”); ask for it before signing anything."
                     % (both(eg["price"]), _pct(eg["guide_share"], 1), _pct(eg["share"], 2)))

    # ---- the monthly sum
    L += ["", "## The monthly sum: the video's way, and from the Airbnbs around it" if near else "## The monthly sum: the video's way, and checked", "",
          "| Per month | The video's way | %s |" % ("Nearby Airbnbs" if near else "Checked"), "|---|---:|---:|"]
    rows = [
        ("Nightly price", both(m["v_adr"]), both(m["c_adr"])),
        ("Nights booked", "%d (%s of the year)" % (round(m["v_nights"]), _pct(t["video_occ"])), "%.1f (%s of the year)" % (nights, _pct(m["occ"]["base"]))),
        ("**Money coming in**", "**%s**" % both(m["v_rev"]), "**%s**" % both(m["c_rev"])),
        ("Mortgage", less(m["v_mort"]), less(m["c_mort"]) + " with VAT + insurance"),
        ("Manager", "%s (%s)" % (less(m["v_mgmt"]), _pct(t["video_mgmt_pct"])), "%s (%s)" % (less(m["c_mgmt"]), _pct(t["mgmt_pct"]))),
        ("Electricity and water", less(t["utilities_month"]), less(t["utilities_month"])),
        ("Internet", less(t["internet_month"]), less(t["internet_month"])),
        ("TV subscription", less(t["subs_month"]), less(t["subs_month"])),
        ("Airbnb fee", "not counted", less(m["c_platform"])),
        ("Building service charge", "not counted", less(m["c_syndic"])),
        ("Upkeep, linen, insurance", "not counted", less(m["c_upkeep"])),
        ("Moroccan taxes", "not counted", less(m["c_ma_tax"])),
        ("Tax at home (after relief on mortgage interest)", "not counted", less(m["c_home_tax"])),
        ("**Left over (+) or put in (−)**", "**%s**" % both(m["v_profit"], signed=True), "**%s**" % both(m["c_profit"], signed=True)),
    ]
    L += ["| %s | %s | %s |" % row for row in rows]
    if near:
        O, R, P = S["occupancy_open_nights"], S["revenue_month_mad"], S["price_mad"]
        L += ["", "**Where the revenue comes from.** %d Airbnbs %s in your atlas (collected %s): booked %s / %s / %s of the nights their calendar is open, listed at %s / %s / %s a night, "
              "taking %s / %s / %s a month (weakest quarter / middle / best quarter). The middle one is the typical year."
              % (S["matches"], S.get("where") or "", S.get("collected_on"), _pct(O["p25"]), _pct(O["median"]), _pct(O["p75"]),
                 both(P["p25"]), both(P["median"]), both(P["p75"]), both(R["p25"]), both(R["median"]), both(R["p75"]))]
        if S.get("potential_month_mad"):
            L.append("The atlas's revenue potential (the middle price, booked %s of the whole year) is %s a month: a ceiling, not a plan."
                     % (_pct(S.get("top_quarter_occupancy")), both(S["potential_month_mad"])))

    # ---- the limit, robustness, the road to owning it
    if x.get("topup") is not None:
        if budget:
            L += ["", "## Against your limit of %s a month" % home(budget), "", "| | |", "|---|---|",
                  "| Typical year | %s |" % put_in(top["base"]), "| Weak year | %s |" % put_in(top["bear"]), "| Strong year | %s |" % put_in(top["bull"])]
            if x.get("topup_at_asking") is not None and abs(m["price"] - m["asking"]) > 1:
                L.append("| Typical year at the full asking price | %s |" % put_in(x["topup_at_asking"]))
        st, pb, pot = x.get("stress") or {}, x.get("plan_b"), x.get("potential")
        L += ["", "## Is the Airbnb play robust?", "", "| | |", "|---|---|"]
        if budget and x.get("rev_for_budget") is not None:
            L.append("| Money the flat must take each month to keep you at %s | %s |" % (home(budget), both(x["rev_for_budget"])))
        if x.get("nearby_n"):
            L.append("| Nearby Airbnbs that take at least that | **%d of %d** |" % (x["nearby_ok"], x["nearby_n"]))
        else:
            L.append("| Nearby Airbnbs that take at least that | none in your atlas near this flat |")
        if st.get("occ_pts"):
            L += ["| Bookings fall a further %d points of the year | %s |" % (round(st["occ_pts"] * 100), put_in(st["occ_down"])),
                  "| Nightly price falls %s | %s |" % (_pct(st["price_pct"]), put_in(st["price_down"])), "| Both at once | %s |" % put_in(st["both"])]
        if x.get("empty_month") is not None:
            L.append("| A month with no guests at all | %s |" % put_in(x["empty_month"]))
        if pb:
            L.append("| Plan B: an ordinary long let at %s a month | %s |" % (both(pb["rent"]), put_in(pb["topup"]) if pb["topup"] > 0.5 else "leaves you %s" % both(pb["left"])))
        if pot:
            L.append("| Best case: the atlas's revenue potential | %s |" % (put_in(pot["topup"]) if pot["topup"] > 0.5 else "leaves you %s" % both(pot["left"])))
        L.append("| Mortgage rate | fixed: the repayment cannot rise |")
        yrs = x.get("term_years") or t["term_years"]
        L += ["", "## When the flat is yours", "", "| After | Loan left | You own | Put in so far |", "|---|---:|---:|---:|"]
        L += ["| %d years | %s | %s | %s |" % (p["year"], both(p["loan_left"]), _pct(p["owned_share"]), both(p["paid_in"])) for p in x.get("timeline") or []]
        L += ["", "Cash in on day one %s + top-ups over %d years %s = **%s** put in. You then own the flat outright (%s at today's price) and it pays you about %s a month after costs and tax. No rise in prices or rents is counted."
              % (both(m["cash_needed_m"]), yrs, both(x["topup_total"]), both(x["cash_in_total"]), both(m["price"]), both(x["income_after_payoff_month"])), ""]
        L += ["| Loan over | Repayment a month | You put in a month |", "|---|---:|---:|"]
        L += ["| %d years | %s | %s |" % (o["years"], both(o["repayment"]), both(o["topup"])) for o in x.get("terms") or []]
        if top["base"] > budget and budget:
            fix = []
            if x.get("deposit_for_budget"):
                fix.append("a deposit of %s (%s of the price)" % (both(x["deposit_for_budget"]), _pct(x["deposit_share_for_budget"])))
            if x.get("price_for_budget"):
                fix.append("a price of %s" % both(x["price_for_budget"]))
            if fix:
                L += ["", "What would bring it inside your limit: " + " or ".join(fix) + "."]

    if x.get("gap"):
        L += ["", "## Why the video's answer is %s a month higher" % both(sum(g[1] for g in x["gap"])), "", "| | A month |", "|---|---:|"]
        L += ["| %s | %s |" % (g[0], both(g[1])) for g in x["gap"] if g[1] > 0.5]
    mk = ev.get("market") or {}
    L += ["", "## Other numbers", "", "| | |", "|---|---|"]
    facts = [
        ("To cover itself with no top-up", "%s of the year booked (%s)" % (_pct(m["be_occ_m"]["base"]),
            ("the middle nearby Airbnb manages %s" % _pct(m["occ"]["base"])) if near else ("the city averages %s" % _pct(mk.get("occ"))))),
        ("Or a nightly price of", both(x["be_adr_at_base_occ"]) if x.get("be_adr_at_base_occ") else "—"),
        ("Or a purchase price of", both(x["be_price"]) if x.get("be_price") else "none on these terms"),
        ("Ten years, then sell", "%s / %s / %s in total, for prices growing %s / %s / %s a year" % (
            both(m["profit_m"]["bear"], signed=True), both(m["profit_m"]["base"], signed=True), both(m["profit_m"]["bull"], signed=True),
            _pct(m["growth"]["bear"], 1), _pct(m["growth"]["base"], 1), _pct(m["growth"]["bull"], 1))),
        ("If bought for cash", "%s a month, %s net yield" % (both(m["net"]["base"] / 12, signed=True), _pct(m["net_yield_c"]["base"], 1))),
    ]
    L += ["| %s | %s |" % f for f in facts]
    L += ["", "## Flags", ""]
    L += ["- **%s** — %s" % ((f.get("severity") or "").upper(), f.get("text")) for f in (r.get("flags") or [])]
    L += ["", "## What the advert doesn't say", ""]
    L += ["%d. %s" % (i, u) for i, u in enumerate(r.get("unknowns") or [], 1)]
    L += ["", "## First message to the agent", "", "```text", run.get("message_fr") or "", "```", "", "*%s*" % (run.get("message_en") or "")]
    s = r.get("str") or {}
    L += ["", "## Evidence", "", "**Nightly price.** %s" % (s.get("adr_note") or ""), "", "**Occupancy.** %s" % (s.get("occupancy_note") or ""), ""]
    if s.get("comps"):
        L += ["| Airbnb / holiday-let comparable | Per night | Booked | Reviews |", "|---|---:|---:|---:|"]
        L += ["| %s | %s | %s | %s |" % (("[%s](%s)" % ((c.get("desc") or "").replace("|", "/"), c["url"])) if c.get("url") else (c.get("desc") or "").replace("|", "/"), both(c.get("nightly_mad")),
                                        _pct(c["occ"]) if c.get("occ") is not None else "—", c.get("reviews") if c.get("reviews") is not None else "—") for c in s["comps"]]
    if r.get("comps_sale"):
        L += ["", "**Price.** %s" % ((r.get("area_price_per_m2") or {}).get("basis") or "Asking prices from adverts, less the assumed 10% between asking and sold."), "",
              "| Flat for sale nearby | Asking | m² | Per m² |", "|---|---:|---:|---:|"]
        L += ["| [%s](%s) | %s | %s | %s |" % (c.get("desc"), (c.get("url") or "").replace(" ", "%20"), both(c["price_mad"]), _n(c["surface_m2"]), both(c["price_mad"] / c["surface_m2"])) for c in r["comps_sale"]]
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
                            _slug(r.get("verdict_label") or r.get("verdict") or "conditional").upper())
    (folder / name).write_text(render(run), encoding="utf-8")
    return "results/" + name
