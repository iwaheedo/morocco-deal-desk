"""Reference deal model for Moroccan residential property.

All money is in MAD (Moroccan dirham); percentages are fractions (0.04 = 4%).
This is the *reference* implementation: build_tracker.py writes the same logic
as live spreadsheet formulas, then checks that the recalculated spreadsheet
agrees with the numbers computed here. If you change a formula in one place,
change it in the other, then run build_tracker.py (it fails loudly on any mismatch).
"""
from statistics import median

SCEN = ("bear", "base", "bull")


def pmt(rate_annual, years, principal):
    """Monthly repayment on a standard annuity (capital + interest) loan."""
    n = int(round(years * 12))
    if principal <= 0 or n <= 0:
        return 0.0
    r = rate_annual / 12.0
    if abs(r) < 1e-12:
        return principal / n
    return principal * r / (1 - (1 + r) ** -n)


def loan_balance(rate_annual, years, principal, months_paid):
    """Outstanding capital after `months_paid` monthly payments."""
    n = int(round(years * 12))
    if principal <= 0 or months_paid >= n:
        return 0.0
    r = rate_annual / 12.0
    if abs(r) < 1e-12:
        return principal * (1 - months_paid / n)
    p = pmt(rate_annual, years, principal)
    g = (1 + r) ** months_paid
    return principal * g - p * (g - 1) / r


def irr_flat(cash_out, annual_cf, n, terminal):
    """Annual IRR of: -cash_out now, annual_cf at the end of each of n years, plus
    `terminal` at the end of year n. Same equation Excel's RATE() solves.
    Returns None when there is no solution between -99% and +1000%."""
    if cash_out <= 0:
        return None

    def npv(r):
        if abs(r) < 1e-12:
            return -cash_out + annual_cf * n + terminal
        return -cash_out + annual_cf * (1 - (1 + r) ** -n) / r + terminal * (1 + r) ** -n

    lo, hi = -0.99, 10.0
    f_lo, f_hi = npv(lo), npv(hi)
    if f_lo * f_hi > 0:
        return None
    for _ in range(200):
        mid = (lo + hi) / 2
        f_mid = npv(mid)
        if f_lo * f_mid <= 0:
            hi = mid
        else:
            lo, f_lo = mid, f_mid
    return (lo + hi) / 2


def income_tax_scale(n, A):
    """Moroccan progressive income-tax scale applied to net taxable income `n`."""
    lim = [A["ir_l0"], A["ir_l1"], A["ir_l2"], A["ir_l3"], A["ir_l4"]]
    rate = [A["ir_r1"], A["ir_r2"], A["ir_r3"], A["ir_r4"], A["ir_r5"]]
    tax = 0.0
    for i in range(4):
        tax += rate[i] * max(0.0, min(n, lim[i + 1]) - lim[i])
    return tax + rate[4] * max(0.0, n - lim[4])


BUYER_TYPES = ("foreign_non_resident", "mre", "moroccan_resident")


def resolve_assumptions(rows, profile):
    """defaults.json rows + profile.json -> ({key: value}, buyer_type, home_currency).
    Mirrors build_tracker.load_inputs, for callers that only need the numbers."""
    buyer_type = profile.get("buyer_type") or "foreign_non_resident"
    home = (profile.get("home_currency") or "GBP").upper()
    A = {r["key"]: r["value"] for r in rows if not r.get("derived")}
    for k, v in (profile.get("overrides") or {}).items():
        if not k.startswith("_") and k in A:
            A[k] = v
    A["ltv"] = A["ltv_" + buyer_type]
    A["rate"] = A["rate_" + buyer_type]
    A["rate_eff"] = A["rate"] * (1 + A["interest_vat"])
    A["fx_home"] = A["fx_" + home.lower()]
    return A, buyer_type, home


def _num(x, default=0.0):
    return default if x is None else float(x)


def _scen(d, default=0.0):
    d = d or {}
    return {s: _num(d.get(s), default) for s in SCEN}


def _div(a, b):
    return a / b if b else None


def compute(p, A):
    """p: property record (assets/property.schema.md). A: {assumption_key: value}.
    Returns a flat dict of results; scenario results are dicts keyed bear/base/bull."""
    o = {}
    asking = _num(p.get("asking_price_mad"))
    surface = _num(p.get("surface_m2"))
    furn_val = _num(p.get("furniture_value_mad"))
    o["asking"], o["surface"], o["furniture_value"] = asking, (surface or None), furn_val

    syn = p.get("syndic_mad_month")
    o["syndic_month"] = float(syn) if syn is not None else surface * A["syndic_per_m2"]

    # ---------- price check ----------
    o["ask_m2"] = _div(asking, surface)
    o["ask_m2_exfurn"] = _div(asking - furn_val, surface)
    comps = [c for c in (p.get("comps_sale") or []) if c.get("price_mad") and c.get("surface_m2")]
    m2s = [c["price_mad"] / c["surface_m2"] for c in comps]
    o["comp_count"] = len(m2s)
    o["comp_median_m2"] = median(m2s) if m2s else None
    o["comp_min_m2"] = min(m2s) if m2s else None
    o["comp_max_m2"] = max(m2s) if m2s else None
    area = p.get("area_price_per_m2") or {}
    for k, src in (("low", "comp_min_m2"), ("mid", "comp_median_m2"), ("high", "comp_max_m2")):
        if area.get(k) is not None:
            o["area_" + k] = float(area[k])
        elif o[src] is not None:
            o["area_" + k] = o[src] * (1 - A["asking_discount"])
        else:
            o["area_" + k] = None
    for k in ("low", "mid", "high"):
        a = o["area_" + k]
        o["fair_" + k] = None if (a is None or surface <= 0) else a * surface + furn_val
    o["ask_vs_mid"] = None if not o["area_mid"] or o["ask_m2_exfurn"] is None else o["ask_m2_exfurn"] / o["area_mid"] - 1
    o["asking_over_fair"] = None if not o["fair_mid"] else asking / o["fair_mid"] - 1

    offer = p.get("offer") or {}
    if offer.get("target_mad") is not None:
        o["offer_target"] = float(offer["target_mad"])
    else:
        o["offer_target"] = min(asking, o["fair_mid"]) if o["fair_mid"] is not None else asking
    if offer.get("opening_mad") is not None:
        o["offer_open"] = float(offer["opening_mad"])
    else:
        o["offer_open"] = o["offer_target"] * (1 - A["opening_offer_discount"])
    if offer.get("walk_away_mad") is not None:
        o["offer_walk"] = float(offer["walk_away_mad"])
    else:
        o["offer_walk"] = min(asking, o["fair_high"]) if o["fair_high"] is not None else asking

    price = float(p["model_price_mad"]) if p.get("model_price_mad") is not None else o["offer_target"]
    o["price"] = price

    # ---------- cash to buy ----------
    o["reg"] = price * A["reg_duty_pct"]
    o["cf"] = price * A["cf_pct"] + A["cf_fixed"]
    o["notary"] = max(price * A["notary_pct"], A["notary_min"]) * (1 + A["notary_vat"])
    o["misc"] = A["misc_fixed"]
    agent_pct = p.get("agent_fee_pct")
    o["agent_pct"] = float(agent_pct) if agent_pct is not None else A["agent_buyer_pct"]
    o["agent"] = price * o["agent_pct"] * (1 + A["agent_vat"])
    o["closing_total"] = o["reg"] + o["cf"] + o["notary"] + o["misc"] + o["agent"]
    o["closing_pct"] = _div(o["closing_total"], price)
    o["furnishing"] = _num(p.get("furnishing_mad"))
    o["renovation"] = _num(p.get("renovation_mad"))
    o["total_cost"] = price + o["closing_total"] + o["furnishing"] + o["renovation"]
    fx = A["fx_cost_pct"]
    o["cash_needed_c"] = o["total_cost"] * (1 + fx)
    o["cash_needed_c_home"] = o["cash_needed_c"] / A["fx_home"]

    loan = price * A["ltv"]
    o["loan"] = loan
    o["deposit"] = price - loan
    o["mort_costs"] = (min(loan, A["mort_reg_slice"]) * A["mort_reg_low_pct"]
                       + max(0.0, loan - A["mort_reg_slice"]) * A["mort_reg_pct"]
                       + loan * A["bank_fee_pct"] + (A["mort_fixed"] if loan > 0 else 0.0))
    o["cash_needed_m"] = (o["deposit"] + o["closing_total"] + o["mort_costs"] + o["furnishing"] + o["renovation"]) * (1 + fx)
    o["cash_needed_m_home"] = o["cash_needed_m"] / A["fx_home"]
    o["pmt_month"] = pmt(A["rate_eff"], A["term_years"], loan)
    o["ins_month"] = loan * A["loan_ins_pct"] / 12
    o["debt_service"] = (o["pmt_month"] + o["ins_month"]) * 12
    # average interest a year over the life of the loan (with the VAT on it): what the home-country relief is worked on
    o["interest_y"] = (o["pmt_month"] * 12 - loan / A["term_years"]) if loan > 0 else 0.0
    rr = A.get("home_interest_relief_pct", 0.0)

    def relief(noi, home):
        """Home-country tax saved because part of the mortgage interest comes off the tax bill; never more than the tax itself."""
        return min(home, rr * min(o["interest_y"], max(noi, 0.0)))
    o["ds_pct"] = _div(o["debt_service"], price)

    # ---------- short-term rental ----------
    s = p.get("str") or {}
    adr, occ = _scen(s.get("adr_mad")), _scen(s.get("occupancy"))
    o["adr"], o["occ"] = adr, occ
    h = A["home_tax_rate"]
    o["syndic_y"] = o["syndic_month"] * 12
    o["utilities_y"] = A["utilities_month"] * 12
    o["internet_y"] = (A["internet_month"] + A["subs_month"]) * 12
    o["insurance_y"] = A["insurance_year"]
    o["owner_tax_y"] = price * A["owner_use_tax_pct"]
    o["fixed_y"] = o["syndic_y"] + o["utilities_y"] + o["internet_y"] + o["insurance_y"] + o["owner_tax_y"]
    o["var_ex_tax"] = A["platform_pct"] + A["mgmt_pct"] + A["str_maint_pct"] + A["str_local_tax_pct"]
    o["var_share"] = o["var_ex_tax"] + A["str_income_tax_pct"]

    def after_tax(gross):
        """(income before tax, Moroccan tax, home-country top-up, net) for a year's gross bookings."""
        noi = gross * (1 - o["var_ex_tax"]) - o["fixed_y"]
        tax = gross * A["str_income_tax_pct"]
        home = max(0.0, h * noi - tax)
        return noi, tax, home, noi - tax - home

    for k in ("nights", "gross", "platform", "mgmt", "maint", "local_tax", "opex", "noi", "tax", "home_tax", "relief", "net", "gross_yield",
              "net_yield_c", "net_month_c", "cf_m", "cf_m_month", "coc_m", "dscr", "be_occ_c", "be_occ_m"):
        o[k] = {}
    for sc in SCEN:
        g = adr[sc] * 365 * occ[sc]
        noi, tax, home, net = after_tax(g)
        o["nights"][sc] = 365 * occ[sc]
        o["gross"][sc] = g
        o["platform"][sc] = g * A["platform_pct"]
        o["mgmt"][sc] = g * A["mgmt_pct"]
        o["maint"][sc] = g * A["str_maint_pct"]
        o["local_tax"][sc] = g * A["str_local_tax_pct"]
        o["opex"][sc] = o["platform"][sc] + o["mgmt"][sc] + o["maint"][sc] + o["local_tax"][sc] + o["fixed_y"]
        o["noi"][sc], o["tax"][sc], o["home_tax"][sc], o["net"][sc] = noi, tax, home, net
        o["gross_yield"][sc] = _div(g, price) if g > 0 else None
        o["net_yield_c"][sc] = _div(net, o["total_cost"]) if g > 0 else None
        o["net_month_c"][sc] = net / 12
        o["relief"][sc] = relief(noi, home)
        o["cf_m"][sc] = net - o["debt_service"] + o["relief"][sc]
        o["cf_m_month"][sc] = o["cf_m"][sc] / 12
        o["coc_m"][sc] = _div(o["cf_m"][sc], o["cash_needed_m"]) if g > 0 else None
        o["dscr"][sc] = _div(noi, o["debt_service"]) if g > 0 else None
        denom = adr[sc] * 365 * (1 - o["var_share"])
        o["be_occ_c"][sc] = _div(o["fixed_y"], denom) if denom > 0 else None
        o["be_occ_m"][sc] = _div(o["fixed_y"] + o["debt_service"], denom) if denom > 0 else None

    # ---------- "analyse the deal" exactly as the video does it, per month ----------
    # His steps: nightly rate x nights booked - mortgage - management - electricity - internet - TV.
    # Mortgage here is a proper repayment at the headline fixed rate (he quoted interest only by mistake).
    o["v_adr"] = adr["base"]
    o["v_nights"] = 30 * A["video_occ"]
    o["v_rev"] = o["v_adr"] * o["v_nights"]
    o["v_mort"] = pmt(A["rate"], A["term_years"], loan)
    o["v_mgmt"] = o["v_rev"] * A["video_mgmt_pct"]
    o["v_profit"] = o["v_rev"] - o["v_mort"] - o["v_mgmt"] - A["utilities_month"] - A["internet_month"] - A["subs_month"]
    o["v_profit_home"] = o["v_profit"] / A["fx_home"]
    o["v_profit_cont"] = o["v_profit"] - A["video_contingency_pct"] * o["v_rev"]
    # the same lines with the checked base case (must reconcile to cf_m_month["base"])
    o["c_adr"] = adr["base"]
    o["c_nights"] = 365 * occ["base"] / 12
    o["c_rev"] = o["gross"]["base"] / 12
    o["c_mort"] = o["debt_service"] / 12
    o["c_mgmt"] = o["mgmt"]["base"] / 12
    o["c_platform"] = o["platform"]["base"] / 12
    o["c_syndic"] = o["syndic_month"]
    o["c_upkeep"] = (o["maint"]["base"] + o["insurance_y"]) / 12
    o["c_ma_tax"] = (o["local_tax"]["base"] + o["tax"]["base"] + o["owner_tax_y"]) / 12
    o["c_home_tax"] = (o["home_tax"]["base"] - o["relief"]["base"]) / 12
    o["c_profit"] = (o["c_rev"] - o["c_mort"] - o["c_mgmt"] - A["utilities_month"] - A["internet_month"] - A["subs_month"]
                     - o["c_platform"] - o["c_syndic"] - o["c_upkeep"] - o["c_ma_tax"] - o["c_home_tax"])
    o["c_profit_home"] = o["c_profit"] / A["fx_home"]
    assert abs(o["c_profit"] - o["cf_m_month"]["base"]) < 1e-6, "video-layout checked profit must equal base cash flow"

    # ---------- long-term let ----------
    lt = p.get("ltr") or {}
    rent = _scen(lt.get("rent_mad_month"))
    o["rent"] = rent
    for k in ("ltr_gross", "ltr_mgmt", "ltr_maint", "ltr_tsc", "ltr_opex", "ltr_noi", "ltr_tax", "ltr_home_tax",
              "ltr_net", "ltr_net_yield", "ltr_relief", "ltr_cf_m"):
        o[k] = {}
    o["ltr_syndic"] = o["syndic_y"] * A["ltr_owner_pays_syndic"]
    for sc in SCEN:
        g = rent[sc] * 12 * (1 - A["ltr_vacancy"])
        o["ltr_gross"][sc] = g
        o["ltr_mgmt"][sc] = g * A["ltr_mgmt_pct"]
        o["ltr_maint"][sc] = g * A["ltr_maint_pct"]
        o["ltr_tsc"][sc] = g * A["tsc_rate"] * A["ltr_owner_pays_tsc"]
        o["ltr_opex"][sc] = o["ltr_mgmt"][sc] + o["ltr_maint"][sc] + o["ltr_syndic"] + o["insurance_y"] + o["ltr_tsc"][sc]
        o["ltr_noi"][sc] = g - o["ltr_opex"][sc]
        o["ltr_tax"][sc] = income_tax_scale(g * (1 - A["rf_abatement"]), A)
        o["ltr_home_tax"][sc] = max(0.0, h * o["ltr_noi"][sc] - o["ltr_tax"][sc])
        o["ltr_net"][sc] = o["ltr_noi"][sc] - o["ltr_tax"][sc] - o["ltr_home_tax"][sc]
        o["ltr_net_yield"][sc] = _div(o["ltr_net"][sc], o["total_cost"]) if g > 0 else None
        o["ltr_relief"][sc] = relief(o["ltr_noi"][sc], o["ltr_home_tax"][sc])
        o["ltr_cf_m"][sc] = o["ltr_net"][sc] - o["debt_service"] + o["ltr_relief"][sc]

    # ---------- stress tests on the base short-let case ----------
    a0, c0 = adr["base"], occ["base"]
    a1, c1 = a0 * (1 - A["stress_adr_pct"]), max(c0 - A["stress_occ_pts"], 0.0)
    ds_stress = (pmt(A["rate_eff"] + A["stress_rate_pts"], A["term_years"], loan) + o["ins_month"]) * 12
    o["ds_stress"] = ds_stress
    for key, (a, c, ds) in {"base": (a0, c0, o["debt_service"]), "occ": (a0, c1, o["debt_service"]),
                            "adr": (a1, c0, o["debt_service"]), "both": (a1, c1, o["debt_service"]),
                            "rate": (a0, c0, ds_stress), "all": (a1, c1, ds_stress)}.items():
        g = a * 365 * c
        noi_s, _tax_s, home_s, net = after_tax(g)
        o["st_%s_gross" % key] = g
        o["st_%s_net" % key] = net
        o["st_%s_cf" % key] = net - ds + relief(noi_s, home_s)

    # ---------- 10-year view (base short-let income held flat) ----------
    N = 10
    for k in ("growth", "sale", "sale_costs", "tpi", "home_cgt", "proceeds_c", "proceeds_m", "profit_c", "profit_m",
              "irr_c", "irr_m"):
        o[k] = {}
    o["cost_base"] = price * (1 + max(o["closing_pct"] or 0.0, A["tpi_cost_flat_pct"])) + o["renovation"]
    o["loan_bal_10"] = loan_balance(A["rate_eff"], A["term_years"], loan, N * 12)
    for sc in SCEN:
        g = A["growth_" + sc]
        sale = price * (1 + g) ** N
        costs = sale * A["sale_agent_pct"]
        tpi = max(A["tpi_rate"] * max(sale - costs - o["cost_base"], 0.0), A["tpi_min_pct"] * sale)
        real_gain = max(sale - costs - price - o["closing_total"] - o["renovation"], 0.0)
        home_cgt = max(0.0, A["home_cgt_rate"] * real_gain - tpi)
        o["growth"][sc], o["sale"][sc], o["sale_costs"][sc] = g, sale, costs
        o["tpi"][sc], o["home_cgt"][sc] = tpi, home_cgt
        o["proceeds_c"][sc] = sale - costs - tpi - home_cgt
        o["proceeds_m"][sc] = o["proceeds_c"][sc] - o["loan_bal_10"]
        o["profit_c"][sc] = o["proceeds_c"][sc] + N * o["net"]["base"] - o["cash_needed_c"]
        o["profit_m"][sc] = o["proceeds_m"][sc] + N * o["cf_m"]["base"] - o["cash_needed_m"]
        o["irr_c"][sc] = irr_flat(o["cash_needed_c"], o["net"]["base"], N, o["proceeds_c"][sc])
        o["irr_m"][sc] = irr_flat(o["cash_needed_m"], o["cf_m"]["base"], N, o["proceeds_m"][sc])
    return o
