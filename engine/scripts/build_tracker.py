#!/usr/bin/env python3
"""Build 'Morocco Property Tracker.xlsx' from the property records.

    python3 build_tracker.py [--data-dir DIR] [--no-verify] [--metrics-only]

Reads   <data-dir>/profile.json          buyer profile + assumption overrides (optional)
        <data-dir>/properties/*.json     one record per property (see assets/property.schema.md)
        <skill>/assets/defaults.json     sourced default assumptions
        <skill>/assets/due_diligence.json
Writes  <data-dir>/Morocco Property Tracker.xlsx   (live formulas; edit the blue cells)
Prints  a JSON summary on stdout: every computed metric per property, plus the
        result of the self-check (spreadsheet formulas recalculated with LibreOffice
        and compared with the reference model in deal_model.py).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DATA_DIR = Path.home() / "Desktop" / "Other random coding" / "morocco-property"
WORKBOOK_NAME = "Morocco Property Tracker.xlsx"


def _bootstrap():
    """openpyxl lives in a private venv inside the skill folder; create it on first use."""
    try:
        import openpyxl  # noqa: F401
        return
    except ImportError:
        pass
    venv = SKILL_DIR / ".venv"
    py = venv / "bin" / "python"
    if os.environ.get("MOROCCO_PROPERTY_BOOTSTRAPPED"):
        sys.exit("openpyxl is still missing after setup. Run: %s -m pip install openpyxl" % py)
    if not py.exists():
        subprocess.check_call([sys.executable, "-m", "venv", str(venv)])
    try:
        subprocess.check_call([str(py), "-c", "import openpyxl"], stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        subprocess.check_call([str(py), "-m", "pip", "install", "--quiet", "--disable-pip-version-check", "openpyxl"])
    os.environ["MOROCCO_PROPERTY_BOOTSTRAPPED"] = "1"
    os.execv(str(py), [str(py)] + sys.argv)


_bootstrap()

from openpyxl import Workbook, load_workbook  # noqa: E402
from openpyxl.formatting.rule import CellIsRule, FormulaRule  # noqa: E402
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side  # noqa: E402
from openpyxl.utils import get_column_letter  # noqa: E402
from openpyxl.worksheet.datavalidation import DataValidation  # noqa: E402
from openpyxl.worksheet.properties import PageSetupProperties  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
import deal_model  # noqa: E402

SCEN = deal_model.SCEN
SC_COL = {"bear": "B", "base": "C", "bull": "D"}
CCY_SYMBOL = {"GBP": "£", "EUR": "€", "USD": "$"}
BUYER_TYPES = ("foreign_non_resident", "mre", "moroccan_resident")

# ---------- styles ----------
FONT = "Arial"
F_BASE = Font(name=FONT, size=10)
F_BOLD = Font(name=FONT, size=10, bold=True)
F_INPUT = Font(name=FONT, size=10, color="0000FF")
F_LINK = Font(name=FONT, size=10, color="008000")
F_NOTE = Font(name=FONT, size=9, italic=True, color="595959")
F_TITLE = Font(name=FONT, size=14, bold=True)
F_SUB = Font(name=FONT, size=10, color="595959")
F_SECTION = Font(name=FONT, size=11, bold=True, color="FFFFFF")
F_HEAD = Font(name=FONT, size=10, bold=True)
F_URL = Font(name=FONT, size=10, color="0563C1", underline="single")
FILL_SECTION = PatternFill("solid", fgColor="1F4E5F")
FILL_HEAD = PatternFill("solid", fgColor="D9E2E7")
FILL_INPUT = PatternFill("solid", fgColor="FFF9DB")
FILL_KEY = PatternFill("solid", fgColor="E8F1EC")
FILL_GREEN = PatternFill("solid", fgColor="C6EFCE")
FILL_AMBER = PatternFill("solid", fgColor="FFEB9C")
FILL_RED = PatternFill("solid", fgColor="FFC7CE")
THIN = Side(style="thin", color="BFBFBF")
WRAP = Alignment(wrap_text=True, vertical="top")
TOP = Alignment(vertical="top")

FMT = {
    "mad": '#,##0;[Red]-#,##0;"-"',
    "pct": '0.0%;[Red]-0.0%;"-"',
    "pct2": '0.00%;[Red]-0.00%;"-"',
    "num": '#,##0.0;[Red]-#,##0.0;"-"',
    "int": '#,##0;[Red]-#,##0;"-"',
    "fx": "0.0000",
    "x": '0.00"x"',
    "text": "@",
}


def home_fmt(ccy):
    s = CCY_SYMBOL.get(ccy, ccy + " ")
    return '"%s"#,##0;[Red]-"%s"#,##0;"-"' % (s, s)


PLACEHOLDER = re.compile(r"\{([A-Za-z0-9_]+(?::[A-Za-z0-9_]+)?)\}")


def die(msg):
    print(json.dumps({"error": msg}, ensure_ascii=False))
    sys.exit(2)


# =====================================================================
# Loading
# =====================================================================
def load_inputs(data_dir: Path):
    profile_path = data_dir / "profile.json"
    profile = json.loads(profile_path.read_text(encoding="utf-8")) if profile_path.exists() else {}
    spec = json.loads((SKILL_DIR / "assets" / "defaults.json").read_text(encoding="utf-8"))
    dd = json.loads((SKILL_DIR / "assets" / "due_diligence.json").read_text(encoding="utf-8"))

    buyer_type = profile.get("buyer_type") or "foreign_non_resident"
    if buyer_type not in BUYER_TYPES:
        die("profile.json buyer_type must be one of %s" % ", ".join(BUYER_TYPES))
    home = (profile.get("home_currency") or "GBP").upper()
    overrides = {k: v for k, v in (profile.get("overrides") or {}).items() if not k.startswith("_")}

    rows = spec["assumptions"]
    known = {r["key"] for r in rows}
    unknown = set(overrides) - known
    if unknown:
        die("profile.json overrides has unknown assumption keys: %s" % ", ".join(sorted(unknown)))
    for r in rows:
        if r["key"] in overrides and not r.get("derived"):
            r["source"] = "YOUR OVERRIDE in profile.json (default was %s). %s" % (r["value"], r.get("source", ""))
            r["value"] = overrides[r["key"]]
            r["overridden"] = True

    A = {r["key"]: r["value"] for r in rows if not r.get("derived")}
    if "fx_" + home.lower() not in A:
        die("No exchange rate for home currency %s in defaults.json (need key fx_%s)" % (home, home.lower()))
    A["ltv"] = A["ltv_" + buyer_type]
    A["rate"] = A["rate_" + buyer_type]
    A["rate_eff"] = A["rate"] * (1 + A["interest_vat"])
    A["fx_home"] = A["fx_" + home.lower()]

    props = []
    pdir = data_dir / "properties"
    for f in sorted(pdir.glob("*.json")) if pdir.exists() else []:
        try:
            p = json.loads(f.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            die("%s is not valid JSON: %s" % (f.name, e))
        p.setdefault("id", f.stem)
        p["_file"] = f.name
        problems = []
        if not isinstance(p.get("asking_price_mad"), (int, float)) or p["asking_price_mad"] <= 0:
            problems.append("asking_price_mad must be a positive number (MAD)")
        if p.get("surface_m2") is not None and (not isinstance(p["surface_m2"], (int, float)) or p["surface_m2"] <= 0):
            problems.append("surface_m2 must be a positive number or null")
        for sec, fld, lo, hi in (("str", "occupancy", 0, 1),):
            for sc, v in ((p.get(sec) or {}).get(fld) or {}).items():
                if v is not None and not (lo <= v <= hi):
                    problems.append("%s.%s.%s must be a fraction between 0 and 1 (e.g. 0.55)" % (sec, fld, sc))
        if p.get("agent_fee_pct") is not None and not (0 <= p["agent_fee_pct"] <= 0.1):
            problems.append("agent_fee_pct must be a fraction (0.025 = 2.5%)")
        if problems:
            die("%s: %s" % (f.name, "; ".join(problems)))
        props.append(p)
    props.sort(key=lambda p: (str(p.get("added") or ""), str(p.get("added_at") or ""), str(p["id"])))
    return profile, spec, rows, A, dd, props, buyer_type, home


# =====================================================================
# Layout engine: rows are added by key; formulas refer to keys, never to
# hand-typed cell addresses, so inserting a row can't silently break a formula.
# =====================================================================
class Layout:
    def __init__(self, a_rows):
        self.a_rows = a_rows
        self.items = []
        self.cells = {}   # key -> ("single", row, col) | ("scen", row, None)
        self.ranges = {}  # key -> (col, first_row, last_row)
        self.row = 1

    def _add(self, **kw):
        kw["row"] = self.row
        self.items.append(kw)
        self.row += 1
        return kw

    def title(self, text, sub=None):
        self._add(kind="title", text=text)
        if sub:
            self._add(kind="sub", text=sub)

    def section(self, text):
        self.blank()
        self._add(kind="section", text=text)

    def blank(self):
        self._add(kind="blank")

    def header(self, cols):
        self._add(kind="header", cols=cols)

    def text(self, key, label, value, note="", url=None):
        it = self._add(kind="text", key=key, label=label, value=value, note=note, url=url)
        if key:
            self.cells[key] = ("single", it["row"], "B")

    def single(self, key, label, spec, fmt="mad", note="", bold=False):
        it = self._add(kind="single", key=key, label=label, spec=spec, fmt=fmt, note=note, bold=bold)
        self.cells[key] = ("single", it["row"], "B")

    def scen(self, key, label, spec, fmt="mad", note="", bold=False):
        it = self._add(kind="scen", key=key, label=label, spec=spec, fmt=fmt, note=note, bold=bold)
        self.cells[key] = ("scen", it["row"], None)

    def triple(self, keys, label, formulas, fmt="mad", note="", bold=False):
        it = self._add(kind="triple", keys=keys, label=label, formulas=formulas, fmt=fmt, note=note, bold=bold)
        for k, col in zip(keys, "BCD"):
            if k:
                self.cells[k] = ("single", it["row"], col)

    def table_row(self, values, fmts, note="", input_cols="BC"):
        return self._add(kind="trow", values=values, fmts=fmts, note=note, input_cols=input_cols)

    def note_row(self, text):
        self._add(kind="noterow", text=text)

    def addr(self, key, sc=None, absolute=False):
        kind, row, col = self.cells[key]
        if kind == "scen":
            col = SC_COL[sc or "base"]
        return ("$%s$%d" if absolute else "%s%d") % (col, row)

    def resolve(self, f, col=None):
        def rep(m):
            tok = m.group(1)
            if tok.startswith("A:"):
                return "Assumptions!$B$%d" % self.a_rows[tok[2:]]
            if tok.startswith("rng:"):
                c, r1, r2 = self.ranges[tok[4:]]
                return "$%s$%d:$%s$%d" % (c, r1, c, r2)
            if ":" in tok:
                key, sc = tok.split(":")
                return "$%s$%d" % (SC_COL[sc], self.cells[key][1])
            kind, row, c = self.cells[tok]
            if kind == "single":
                return "$%s$%d" % (c, row)
            if col is None:
                raise ValueError("scenario row {%s} used in a single-cell formula; write {%s:base}" % (tok, tok))
            return "%s$%d" % (col, row)

        return PLACEHOLDER.sub(rep, f)


def _is_formula(v):
    return isinstance(v, str) and v.startswith("=")


def _is_pure_link(v):
    return _is_formula(v) and re.fullmatch(r"=\{A:[A-Za-z0-9_]+\}", v) is not None


def _put(ws, ref, value, fmt=None, font=F_BASE, fill=None, align=None):
    c = ws[ref]
    c.value = value
    c.font = font
    if fmt:
        c.number_format = fmt
    if fill:
        c.fill = fill
    c.alignment = align or TOP
    return c


def _value_cell(ws, L, ref, spec, fmt, col, bold=False, hfmt=None):
    numfmt = hfmt if fmt == "home" else FMT.get(fmt, fmt)
    if _is_formula(spec):
        font = F_LINK if _is_pure_link(spec) else (F_BOLD if bold else F_BASE)
        _put(ws, ref, L.resolve(spec, col), numfmt, font, FILL_KEY if bold else None)
    else:
        _put(ws, ref, spec, numfmt, F_INPUT, FILL_INPUT)


def render(ws, L, hfmt, widths=(48, 17, 17, 17, 78)):
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w
    for it in L.items:
        r, k = it["row"], it["kind"]
        if k == "title":
            _put(ws, "A%d" % r, it["text"], font=F_TITLE)
        elif k == "sub":
            _put(ws, "A%d" % r, it["text"], font=F_SUB)
        elif k == "section":
            for col in "ABCDE":
                _put(ws, "%s%d" % (col, r), it["text"] if col == "A" else None, font=F_SECTION, fill=FILL_SECTION)
        elif k == "header":
            for col, text in zip("ABCDE", it["cols"]):
                _put(ws, "%s%d" % (col, r), text, font=F_HEAD, fill=FILL_HEAD,
                     align=Alignment(horizontal="left" if col in "AE" else "right", wrap_text=True, vertical="center"))
        elif k == "text":
            _put(ws, "A%d" % r, it["label"])
            c = _put(ws, "B%d" % r, it["value"], font=F_URL if it.get("url") else F_INPUT, align=TOP)
            if it.get("url"):
                c.hyperlink = it["url"]
            if it["note"]:
                _put(ws, "E%d" % r, it["note"], font=F_NOTE, align=WRAP)
        elif k == "single":
            _put(ws, "A%d" % r, it["label"], font=F_BOLD if it["bold"] else F_BASE)
            _value_cell(ws, L, "B%d" % r, it["spec"], it["fmt"], None, it["bold"], hfmt)
            if it["note"]:
                _put(ws, "E%d" % r, it["note"], font=F_NOTE, align=WRAP)
        elif k == "scen":
            _put(ws, "A%d" % r, it["label"], font=F_BOLD if it["bold"] else F_BASE)
            for sc in SCEN:
                col = SC_COL[sc]
                spec = it["spec"][sc] if isinstance(it["spec"], dict) else it["spec"]
                _value_cell(ws, L, "%s%d" % (col, r), spec, it["fmt"], col, it["bold"], hfmt)
            if it["note"]:
                _put(ws, "E%d" % r, it["note"], font=F_NOTE, align=WRAP)
        elif k == "triple":
            _put(ws, "A%d" % r, it["label"], font=F_BOLD if it.get("bold") else F_BASE)
            for col, f in zip("BCD", it["formulas"]):
                if f is not None:
                    _value_cell(ws, L, "%s%d" % (col, r), f, it["fmt"], None, bool(it.get("bold")), hfmt)
            if it["note"]:
                _put(ws, "E%d" % r, it["note"], font=F_NOTE, align=WRAP)
        elif k == "trow":
            for col, v, fmt in zip("ABCD", it["values"], it["fmts"]):
                if col == "A":
                    _put(ws, "A%d" % r, v, font=F_INPUT, align=WRAP)
                elif _is_formula(v):
                    _put(ws, "%s%d" % (col, r), L.resolve(v, col), FMT.get(fmt, fmt), F_BASE)
                else:
                    _put(ws, "%s%d" % (col, r), v, FMT.get(fmt, fmt), F_INPUT,
                         FILL_INPUT if col in it["input_cols"] else None)
            note = it["note"]
            if note:
                c = _put(ws, "E%d" % r, note, font=F_URL if str(note).startswith("http") else F_NOTE, align=WRAP)
                if str(note).startswith("http"):
                    c.hyperlink = str(note).split()[0]
        elif k == "noterow":
            _put(ws, "A%d" % r, it["text"], font=F_NOTE, align=WRAP)
            ws.merge_cells("A%d:E%d" % (r, r))
            ws.row_dimensions[r].height = 15 * max(1, min(6, len(it["text"]) // 150 + 1))


# =====================================================================
# Sheets
# =====================================================================
def build_assumptions(wb, rows, buyer_type, home, as_of):
    ws = wb.create_sheet("Assumptions")
    for col, w in zip("ABCD", (60, 22, 96, 14)):
        ws.column_dimensions[col].width = w
    _put(ws, "A1", "Assumptions — shared by every property sheet", font=F_TITLE)
    _put(ws, "A2", "Blue cells are inputs you can change; every property sheet recalculates. "
                   "Defaults were checked against the sources shown on %s — re-check anything marked low confidence, "
                   "and anything older than ~6 months, before relying on it." % as_of, font=F_SUB)
    _put(ws, "A4", "Buyer type")
    _put(ws, "B4", buyer_type, font=F_INPUT, fill=FILL_INPUT)
    _put(ws, "C4", "foreign_non_resident · mre (Moroccan living abroad) · moroccan_resident — drives the loan-to-value row below.",
         font=F_NOTE)
    dv = DataValidation(type="list", formula1='"%s"' % ",".join(BUYER_TYPES), allow_blank=False)
    ws.add_data_validation(dv)
    dv.add("B4")
    _put(ws, "A5", "Home currency")
    _put(ws, "B5", home, font=F_BASE)
    _put(ws, "C5", "Set in profile.json (home_currency), then rebuild. Money is modelled in MAD and shown in %s where useful." % home,
         font=F_NOTE)

    a_rows, r, group = {}, 7, None
    for it in rows:
        if it["group"] != group:
            group = it["group"]
            r += 1
            for col, text in zip("ABCD", (group, "Value", "Source / basis", "Confidence")):
                _put(ws, "%s%d" % (col, r), text, font=F_SECTION, fill=FILL_SECTION)
            r += 1
        a_rows[it["key"]] = r
        it["_row"] = r
        r += 1
    for it in rows:
        r = it["_row"]
        _put(ws, "A%d" % r, it["label"])
        fmt = FMT.get(it.get("fmt", "num"), it.get("fmt"))
        if it.get("derived"):
            if it["key"] in ("ltv", "rate"):
                k = it["key"]
                f = '=IF($B$4="mre",$B$%d,IF($B$4="moroccan_resident",$B$%d,$B$%d))' % (
                    a_rows[k + "_mre"], a_rows[k + "_moroccan_resident"], a_rows[k + "_foreign_non_resident"])
            elif it["key"] == "rate_eff":
                f = "=$B$%d*(1+$B$%d)" % (a_rows["rate"], a_rows["interest_vat"])
            elif it["key"] == "fx_home":
                f = "=$B$%d" % a_rows["fx_" + home.lower()]
            else:
                die("unknown derived assumption %s" % it["key"])
            _put(ws, "B%d" % r, f, fmt, F_BOLD, FILL_KEY)
        else:
            _put(ws, "B%d" % r, it["value"], fmt, F_INPUT, FILL_INPUT)
        _put(ws, "C%d" % r, it.get("source", ""), font=F_NOTE, align=WRAP)
        _put(ws, "D%d" % r, it.get("confidence", ""), font=F_NOTE)
    ws.freeze_panes = "B4"
    return ws, a_rows


def sheet_name(idx, p):
    label = p.get("short_name") or p.get("neighbourhood") or p.get("city") or p["id"]
    label = re.sub(r"[\[\]\:\*\?\/\\']", " ", str(label)).strip()
    return ("P%02d %s" % (idx, label))[:31].strip()


def build_property(wb, name, p, a_rows, dd, home, hfmt):
    ws = wb.create_sheet(name)
    L = Layout(a_rows)
    H = home
    title = p.get("title") or p["id"]
    L.title("%s — %s" % (name.split(" ")[0], title),
            "All money in MAD unless marked %s. Yellow cells with blue text are inputs; black cells are formulas; green cells pull from the Assumptions sheet." % H)

    # ---- 1. listing ----
    L.section("1. The listing")
    L.text("verdict", "Verdict", (p.get("verdict") or "not assessed").upper(), p.get("verdict_reason") or "")
    L.text(None, "Listing", p.get("source_url") or "(no link)", url=p.get("source_url"))
    L.text(None, "Location", ", ".join(x for x in (p.get("neighbourhood"), p.get("city")) if x) or "unknown", p.get("address_note") or "")
    L.text(None, "Type / bedrooms / bathrooms", "%s / %s / %s" % (p.get("property_type") or "?", _q(p.get("bedrooms")), _q(p.get("bathrooms"))))
    L.text(None, "Floor / lift / year built", "%s / %s / %s" % (_q(p.get("floor")), _yn(p.get("lift")), _q(p.get("year_built"))))
    L.text(None, "Condition / furnished", "%s / %s" % (p.get("condition") or "?", _yn(p.get("furnished"))))
    L.text("title_status", "Title status", p.get("title_status") or "unknown",
           "titre_foncier = registered title (what you want) · requisition = registration pending · melkia = unregistered (avoid unless a lawyer clears it) · unknown = ASK before anything else")
    L.text(None, "Off-plan?", _yn(p.get("off_plan")), "Off-plan (VEFA): staged payments, no ordinary mortgage until the title exists, developer risk.")
    L.text(None, "Seller / contact", "%s%s" % (p.get("seller_type") or "?", (" — " + p["contact"]) if p.get("contact") else ""))
    L.text(None, "Added / listing date", "%s / %s" % (p.get("added") or "?", p.get("listing_date") or "?"))
    L.single("asking", "Asking price", p["asking_price_mad"], "mad", p.get("asking_note") or "From the listing.")
    L.single("asking_home", "Asking price (%s)" % H, "={asking}/{A:fx_home}", "home")
    L.single("surface", "Surface (m²)", p.get("surface_m2"), "num", p.get("surface_note") or "Habitable surface from the listing — confirm on the title certificate; terraces are often added in.")
    L.single("furniture_value", "Value of included furniture/fit-out", p.get("furniture_value_mad") or 0, "mad",
             "What it would cost you to furnish to this standard. Only count it if an inventory will be written into the contract.")
    syn = p.get("syndic_mad_month")
    L.single("syndic_month", "Building service charge (syndic) per month",
             syn if syn is not None else "={surface}*{A:syndic_per_m2}", "mad",
             "From the listing/agent." if syn is not None else "NOT STATED — estimated from Assumptions. Ask for the last syndic statement.")

    # ---- the video's own deal analysis, with the checked version beside it ----
    L.section("★ Analyse the deal — the video's method, per month")
    L.header(["Per month, MAD", "The video's way", "Checked", "", "What differs"])
    bills = "-{A:utilities_month}-{A:internet_month}-{A:subs_month}"
    L.triple(("v_adr", "c_adr", None), "Nightly rate (middle of the comparable range)", ("={adr:base}", "={adr:base}", None), "mad",
             "From comparable Airbnb listings nearby — section 4 and table 8b.")
    L.triple(("v_nights", "c_nights", None), "Nights booked", ("=30*{A:video_occ}", "=365*{occ:base}/12", None), "num",
             "The video assumes 70% occupancy (21 nights) every month. Checked uses the evidence-based base case.")
    L.triple(("v_rev", "c_rev", None), "Revenue", ("={v_adr}*{v_nights}", "={gross:base}/12", None), "mad", "", bold=True)
    L.triple(("v_mort", "c_mort", None), "Mortgage",
             ("=IF({loan}>0,IF({A:rate}=0,{loan}/({A:term_years}*12),-PMT({A:rate}/12,{A:term_years}*12,{loan})),0)", "={debt_service}/12", None), "mad",
             "Both are full repayment loans at the fixed rate. Checked adds the 10% VAT on interest and compulsory insurance.")
    L.triple(("v_mgmt", "c_mgmt", None), "Management company", ("={v_rev}*{A:video_mgmt_pct}", "={mgmt:base}/12", None), "mad",
             "The video uses 10%. Quotes for full service run 20–30%.")
    L.triple((None, None, None), "Electricity and water", ("={A:utilities_month}", "={A:utilities_month}", None))
    L.triple((None, None, None), "Internet", ("={A:internet_month}", "={A:internet_month}", None))
    L.triple((None, None, None), "TV subscription", ("={A:subs_month}", "={A:subs_month}", None))
    L.triple((None, None, None), "Cleaning", ("=0", "=0", None), "mad", "Charged to the guest, as in the video.")
    L.triple((None, "c_platform", None), "Airbnb / Booking fee", ("=0", "={platform:base}/12", None), "mad", "Not in the video.")
    L.triple((None, "c_syndic", None), "Building service charge (syndic)", ("=0", "={syndic_month}", None), "mad", "Not in the video.")
    L.triple((None, "c_upkeep", None), "Upkeep, linen, insurance", ("=0", "=({maint:base}+{insurance_y:base})/12", None), "mad", "Not in the video.")
    L.triple((None, "c_ma_tax", None), "Moroccan taxes", ("=0", "=({local_tax:base}+{tax:base}+{owner_tax_y:base})/12", None), "mad", "Not in the video.")
    L.triple((None, "c_home_tax", None), "Home-country tax top-up", ("=0", "=({home_tax:base}-{relief:base})/12", None), "mad", "Not in the video. After relief on the mortgage interest.")
    L.triple(("v_profit", "c_profit", None), "PROFIT per month",
             ("={v_rev}-{v_mort}-{v_mgmt}" + bills,
              "={c_rev}-{c_mort}-{c_mgmt}" + bills + "-{c_platform}-{c_syndic}-{c_upkeep}-{c_ma_tax}-{c_home_tax}", None), "mad",
             "Checked equals the base-case cash flow after mortgage in section 4.", bold=True)
    L.triple(("v_profit_home", "c_profit_home", None), "PROFIT per month (%s)" % H, ("={v_profit}/{A:fx_home}", "={c_profit}/{A:fx_home}", None), "home", "", bold=True)
    L.triple(("v_profit_cont", None, None), "  with the video's optional 10% contingency", ("={v_profit}-{A:video_contingency_pct}*{v_rev}", None, None), "mad",
             "He mentions holding back 10% in case things go wrong.")
    L.triple((None, None, None), "Cash you put in (%s): deposit + all fees + furnishing" % H, ("={cash_needed_m_home}", "={cash_needed_m_home}", None), "home")

    # ---- 2. price check ----
    L.section("2. Is the price right?  (price per m² against the area)")
    L.single("ask_m2", "Asking price per m²", '=IF({surface}>0,{asking}/{surface},"")', "mad")
    L.single("ask_m2_exfurn", "Asking price per m², excluding furniture", '=IF({surface}>0,({asking}-{furniture_value})/{surface},"")', "mad")
    L.single("comp_count", "Comparable listings found", "=COUNT({rng:sale_m2})", "int", "Table 8a below. Fewer than 5 = weak evidence.")
    L.single("comp_median_m2", "Comparables: median asking price per m²", '=IF({comp_count}>0,MEDIAN({rng:sale_m2}),"")', "mad")
    L.single("comp_min_m2", "Comparables: lowest per m²", '=IF({comp_count}>0,MIN({rng:sale_m2}),"")', "mad")
    L.single("comp_max_m2", "Comparables: highest per m²", '=IF({comp_count}>0,MAX({rng:sale_m2}),"")', "mad")
    area = p.get("area_price_per_m2") or {}
    basis = area.get("basis") or ""
    for k, src, lab in (("low", "comp_min_m2", "low"), ("mid", "comp_median_m2", "mid"), ("high", "comp_max_m2", "high")):
        if area.get(k) is not None:
            spec, note = area[k], "Entered directly. " + basis
        else:
            spec = '=IF({comp_count}>0,{%s}*(1-{A:asking_discount}),"")' % src
            note = "Comparables' asking price less the usual asking-to-sold discount (Assumptions)."
        L.single("area_" + k, "Area transaction price per m² — %s" % lab, spec, "mad", note)
    for k in ("low", "mid", "high"):
        L.single("fair_" + k, "Fair value — %s" % k, '=IF(AND(ISNUMBER({area_%s}),{surface}>0),{area_%s}*{surface}+{furniture_value},"")' % (k, k), "mad",
                 "Area price per m² × surface + furniture." if k == "low" else "", bold=(k == "mid"))
    L.single("ask_vs_mid", "Asking per m² (ex-furniture) vs area mid",
             '=IF(AND(ISNUMBER({area_mid}),ISNUMBER({ask_m2_exfurn})),IF({area_mid}>0,{ask_m2_exfurn}/{area_mid}-1,""),"")', "pct",
             "Positive = asking above what the area supports.", bold=True)
    L.single("asking_over_fair", "Asking price vs fair value (mid)", '=IF(ISNUMBER({fair_mid}),IF({fair_mid}>0,{asking}/{fair_mid}-1,""),"")', "pct")
    offer = p.get("offer") or {}
    onote = offer.get("note") or ""
    L.single("offer_open", "Offer — opening", offer.get("opening_mad") if offer.get("opening_mad") is not None else "={offer_target}*(1-{A:opening_offer_discount})", "mad", onote)
    L.single("offer_target", "Offer — target (what you expect to pay)",
             offer.get("target_mad") if offer.get("target_mad") is not None else "=IF(ISNUMBER({fair_mid}),MIN({asking},{fair_mid}),{asking})", "mad",
             "Default: the lower of asking and fair value (mid).", bold=True)
    L.single("offer_walk", "Offer — walk-away ceiling",
             offer.get("walk_away_mad") if offer.get("walk_away_mad") is not None else "=IF(ISNUMBER({fair_high}),MIN({asking},{fair_high}),{asking})", "mad")
    L.single("price", "PRICE USED IN THE MODEL BELOW", p.get("model_price_mad") if p.get("model_price_mad") is not None else "={offer_target}", "mad",
             "Everything below is calculated at this price. Type a number here to test a different price.", bold=True)

    # ---- 3. cash to buy ----
    L.section("3. Cash needed to buy")
    L.single("reg", "Registration duty", "={price}*{A:reg_duty_pct}")
    L.single("cf", "Land registry (conservation foncière)", "={price}*{A:cf_pct}+{A:cf_fixed}")
    L.single("notary", "Notary fee incl. VAT", "=MAX({price}*{A:notary_pct},{A:notary_min})*(1+{A:notary_vat})")
    L.single("misc", "Stamps, certificates, file costs", "={A:misc_fixed}")
    ap = p.get("agent_fee_pct")
    L.single("agent_pct", "Buyer-side agent commission (%)", ap if ap is not None else "={A:agent_buyer_pct}", "pct2",
             "0% if bought direct from the owner. Agree it in writing BEFORE the viewing.")
    L.single("agent", "Agent commission incl. VAT", "={price}*{agent_pct}*(1+{A:agent_vat})")
    L.single("closing_total", "Total buying costs", "={reg}+{cf}+{notary}+{misc}+{agent}", bold=True)
    L.single("closing_pct", "Buying costs as % of price", '=IF({price}>0,{closing_total}/{price},"")', "pct")
    L.single("furnishing", "Furnishing / equipment you must add", p.get("furnishing_mad") or 0, "mad", p.get("furnishing_note") or "")
    L.single("renovation", "Renovation / repairs", p.get("renovation_mad") or 0, "mad", p.get("renovation_note") or "")
    L.single("total_cost", "All-in cost of the property", "={price}+{closing_total}+{furnishing}+{renovation}", bold=True)
    L.blank()
    L.single("cash_needed_c", "CASH PURCHASE — cash needed", "={total_cost}*(1+{A:fx_cost_pct})", "mad",
             "Includes the cost of converting and wiring money to Morocco.", bold=True)
    L.single("cash_needed_c_home", "CASH PURCHASE — cash needed (%s)" % H, "={cash_needed_c}/{A:fx_home}", "home", bold=True)
    L.blank()
    L.single("loan", "Mortgage — loan amount", "={price}*{A:ltv}", "mad", "Loan-to-value from Assumptions for your buyer type. Fees are never financed.")
    L.single("deposit", "Mortgage — deposit", "={price}-{loan}")
    L.single("mort_costs", "Mortgage — set-up costs (registration + bank file fee)", "=MIN({loan},{A:mort_reg_slice})*{A:mort_reg_low_pct}+MAX(0,{loan}-{A:mort_reg_slice})*{A:mort_reg_pct}"
             "+{loan}*{A:bank_fee_pct}+IF({loan}>0,{A:mort_fixed},0)", "mad",
             "Land-registry fee for the mortgage (charged by slice), bank file fee, stamps.")
    L.single("cash_needed_m", "WITH MORTGAGE — cash needed",
             "=({deposit}+{closing_total}+{mort_costs}+{furnishing}+{renovation})*(1+{A:fx_cost_pct})", "mad", bold=True)
    L.single("cash_needed_m_home", "WITH MORTGAGE — cash needed (%s)" % H, "={cash_needed_m}/{A:fx_home}", "home", bold=True)
    L.single("pmt_month", "Mortgage — monthly repayment (capital + interest)",
             "=IF({loan}>0,IF({A:rate_eff}=0,{loan}/({A:term_years}*12),-PMT({A:rate_eff}/12,{A:term_years}*12,{loan})),0)", "mad",
             "Full repayment loan at the rate INCLUDING the 10% VAT on interest. (An interest-only figure would be far lower and is not what Moroccan banks offer.)")
    L.single("ins_month", "Mortgage — compulsory insurance per month", "={loan}*{A:loan_ins_pct}/12")
    L.single("debt_service", "Mortgage — total cost per year", "=({pmt_month}+{ins_month})*12", bold=True)
    L.single("interest_y", "Mortgage — interest per year, averaged over the loan", "=IF({loan}>0,{pmt_month}*12-{loan}/{A:term_years},0)", "mad",
             "Includes the VAT on interest. Higher in the early years, lower later; your home-country relief is worked on this.")
    L.single("ds_pct", "Mortgage cost as % of the price", '=IF({price}>0,{debt_service}/{price},"")', "pct",
             "The hurdle: unless the flat's net income is a bigger share of the price than this, you top it up from your own pocket every month.")

    # ---- 4. STR ----
    s = p.get("str") or {}
    adr, occ = s.get("adr_mad") or {}, s.get("occupancy") or {}
    L.section("4. Short-term rental (Airbnb / Booking) — three scenarios")
    L.header(["Per year, MAD", "Bear", "Base", "Bull", "Basis"])
    L.scen("adr", "Average nightly rate achieved (MAD)", {sc: adr.get(sc) or 0 for sc in SCEN}, "mad",
           s.get("adr_note") or "From the short-let comparables in table 8b. Year-round average, not peak-season price.")
    L.scen("occ", "Occupancy (share of nights booked, year-round)", {sc: occ.get(sc) or 0 for sc in SCEN}, "pct",
           s.get("occupancy_note") or "Year-round average including low season.")
    L.scen("nights", "Nights booked", "=365*{occ}", "int")
    L.scen("gross", "Gross booking revenue", "={adr}*{nights}", "mad", "Excludes cleaning fees charged to guests (assumed to cover cleaning cost).", bold=True)
    L.scen("platform", "Platform fees (Airbnb / Booking)", "={gross}*{A:platform_pct}")
    L.scen("mgmt", "Management company", "={gross}*{A:mgmt_pct}")
    L.scen("maint", "Maintenance, linen, replacements", "={gross}*{A:str_maint_pct}")
    L.scen("local_tax", "Communal / local taxes on the let", "={gross}*{A:str_local_tax_pct}", "mad",
           "Estimate — see Assumptions. Not creditable against home-country tax, so treated as a running cost.")
    L.scen("syndic_y", "Building service charge (syndic)", "={syndic_month}*12")
    L.scen("utilities_y", "Electricity + water", "={A:utilities_month}*12")
    L.scen("internet_y", "Internet + TV subscriptions", "=({A:internet_month}+{A:subs_month})*12")
    L.scen("insurance_y", "Home insurance", "={A:insurance_year}")
    L.scen("owner_tax_y", "Housing tax if you also use it yourself", "={price}*{A:owner_use_tax_pct}")
    L.scen("opex", "Total running costs", "={platform}+{mgmt}+{maint}+{local_tax}+{syndic_y}+{utilities_y}+{internet_y}+{insurance_y}+{owner_tax_y}")
    L.scen("noi", "Income before tax and mortgage", "={gross}-{opex}", bold=True)
    L.scen("tax", "Moroccan income tax on the rental", "={gross}*{A:str_income_tax_pct}", "mad",
           "A central ESTIMATE: how short lets are taxed is unsettled (see Assumptions). Confirm with a Moroccan tax adviser.")
    L.scen("home_tax", "Home-country tax top-up (estimate)", "=MAX(0,{A:home_tax_rate}*{noi}-{tax})", "mad",
           "Your home country taxes this income too and credits Moroccan tax. Rough: marginal rate × income before tax, less Moroccan tax. A cash buyer's figure; relief on mortgage interest is below.")
    L.scen("net", "NET INCOME, cash buyer (after all tax)", "={noi}-{tax}-{home_tax}", bold=True)
    L.scen("net_month_c", "  per month", "={net}/12")
    L.scen("net_month_c_home", "  per month (%s)" % H, "={net_month_c}/{A:fx_home}", "home")
    L.scen("gross_yield", "Gross yield (revenue ÷ price)", '=IF(AND({price}>0,{gross}>0),{gross}/{price},"")', "pct", "The flattering number agents quote.")
    L.scen("net_yield_c", "NET YIELD, cash buyer (net income ÷ all-in cost)", '=IF(AND({total_cost}>0,{gross}>0),{net}/{total_cost},"")', "pct",
           "The honest number. Compare with what the same cash earns elsewhere.", bold=True)
    L.scen("be_occ_c", "Break-even occupancy, cash buyer",
           '=IF({adr}*(1-{var_share})>0,{fixed_y}/({adr}*365*(1-{var_share})),"")', "pct", "Occupancy at which income after Moroccan tax is zero.")
    L.blank()
    L.scen("ds_row", "Mortgage cost per year", "={debt_service}")
    L.scen("relief", "Home-country tax saved on the mortgage interest", "=MIN({home_tax},{A:home_interest_relief_pct}*MIN({interest_y},MAX({noi},0)))", "mad",
           "In the UK, 20% of the interest comes off the tax bill. It can only cancel tax that would otherwise be due.")
    L.scen("cf_m", "CASH FLOW after mortgage", "={net}-{debt_service}+{relief}", bold=True)
    L.scen("cf_m_month", "  per month", "={cf_m}/12")
    L.scen("cf_m_month_home", "  per month (%s)" % H, "={cf_m_month}/{A:fx_home}", "home")
    L.scen("coc_m", "Cash-on-cash return (cash flow ÷ cash you put in)", '=IF(AND({cash_needed_m}>0,{gross}>0),{cf_m}/{cash_needed_m},"")', "pct", bold=True)
    L.scen("dscr", "Cover: income before tax ÷ mortgage cost", '=IF(AND({debt_service}>0,{gross}>0),{noi}/{debt_service},"")', "x",
           "Below 1.0x the rent does not pay the mortgage. Below ~1.25x is thin.")
    L.scen("be_occ_m", "Break-even occupancy with mortgage",
           '=IF({adr}*(1-{var_share})>0,({fixed_y}+{debt_service})/({adr}*365*(1-{var_share})),"")', "pct",
           "Occupancy needed to cover running costs, Moroccan tax and the mortgage. If the market average is below this, the deal loses money.", bold=True)
    L.single("var_ex_tax", "(helper) share of revenue taken by percentage costs", "={A:platform_pct}+{A:mgmt_pct}+{A:str_maint_pct}+{A:str_local_tax_pct}", "pct")
    L.single("var_share", "(helper) the same plus Moroccan income tax", "={var_ex_tax}+{A:str_income_tax_pct}", "pct")
    L.single("fixed_y", "(helper) fixed running costs per year",
             "={syndic_month}*12+{A:utilities_month}*12+({A:internet_month}+{A:subs_month})*12+{A:insurance_year}+{price}*{A:owner_use_tax_pct}")

    # ---- 5. LTR ----
    lt = p.get("ltr") or {}
    rent = lt.get("rent_mad_month") or {}
    L.section("5. Long-term let instead — three scenarios")
    L.header(["Per year, MAD", "Bear", "Base", "Bull", "Basis"])
    L.scen("rent", "Monthly rent (MAD)", {sc: rent.get(sc) or 0 for sc in SCEN}, "mad", lt.get("rent_note") or "From the long-let comparables in table 8c.")
    L.scen("ltr_gross", "Rent collected (after vacancy)", "={rent}*12*(1-{A:ltr_vacancy})", "mad", bold=True)
    L.scen("ltr_mgmt", "Letting agent / management", "={ltr_gross}*{A:ltr_mgmt_pct}")
    L.scen("ltr_maint", "Maintenance", "={ltr_gross}*{A:ltr_maint_pct}")
    L.scen("ltr_syndic", "Syndic paid by owner", "={syndic_month}*12*{A:ltr_owner_pays_syndic}")
    L.scen("ltr_ins", "Home insurance", "={A:insurance_year}")
    L.scen("ltr_tsc", "Communal services tax (TSC) on the rent", "={ltr_gross}*{A:tsc_rate}*{A:ltr_owner_pays_tsc}", "mad",
           "Legally the owner's. Some leases recharge it to the tenant.")
    L.scen("ltr_opex", "Total running costs", "={ltr_mgmt}+{ltr_maint}+{ltr_syndic}+{ltr_ins}+{ltr_tsc}")
    L.scen("ltr_noi", "Income before tax and mortgage", "={ltr_gross}-{ltr_opex}", bold=True)
    L.scen("ltr_taxable", "Taxable rent after the 40% flat allowance", "={ltr_gross}*(1-{A:rf_abatement})")
    L.scen("ltr_tax", "Moroccan income tax on rent (progressive scale)",
           "={A:ir_r1}*MAX(0,MIN({ltr_taxable},{A:ir_l1})-{A:ir_l0})+{A:ir_r2}*MAX(0,MIN({ltr_taxable},{A:ir_l2})-{A:ir_l1})"
           "+{A:ir_r3}*MAX(0,MIN({ltr_taxable},{A:ir_l3})-{A:ir_l2})+{A:ir_r4}*MAX(0,MIN({ltr_taxable},{A:ir_l4})-{A:ir_l3})"
           "+{A:ir_r5}*MAX(0,{ltr_taxable}-{A:ir_l4})", "mad", "Assumes this is your only Moroccan income.")
    L.scen("ltr_home_tax", "Home-country tax top-up (estimate)", "=MAX(0,{A:home_tax_rate}*{ltr_noi}-{ltr_tax})")
    L.scen("ltr_net", "NET INCOME, cash buyer (after all tax)", "={ltr_noi}-{ltr_tax}-{ltr_home_tax}", bold=True)
    L.scen("ltr_net_yield", "NET YIELD, cash buyer", '=IF(AND({total_cost}>0,{ltr_gross}>0),{ltr_net}/{total_cost},"")', "pct", bold=True)
    L.scen("ltr_relief", "Home-country tax saved on the mortgage interest", "=MIN({ltr_home_tax},{A:home_interest_relief_pct}*MIN({interest_y},MAX({ltr_noi},0)))")
    L.scen("ltr_cf_m", "Cash flow after mortgage", "={ltr_net}-{debt_service}+{ltr_relief}")

    # ---- 6. stress ----
    L.section("6. Stress tests on the base short-let case")
    L.header(["What if…", "Bookings / yr", "Net income / yr (cash buyer)", "Cash flow / yr after mortgage", ""])
    a_s, o_s = "{adr:base}*(1-{A:stress_adr_pct})", "MAX({occ:base}-{A:stress_occ_pts},0)"
    L.single("ds_stress", "(helper) mortgage cost per year at the stressed rate",
             "=(IF({loan}>0,-PMT(({A:rate_eff}+{A:stress_rate_pts})/12,{A:term_years}*12,{loan}),0)+{ins_month})*12", "mad",
             "Relevant if the bank's offer comes in above the assumed rate, or on a variable rate.")
    net_f = ("=({g}*(1-{var_ex_tax})-{fixed_y})-{g}*{A:str_income_tax_pct}"
             "-MAX(0,{A:home_tax_rate}*({g}*(1-{var_ex_tax})-{fixed_y})-{g}*{A:str_income_tax_pct})")
    relief_f = ("MIN(MAX(0,{A:home_tax_rate}*({g}*(1-{var_ex_tax})-{fixed_y})-{g}*{A:str_income_tax_pct}),"
                "{A:home_interest_relief_pct}*MIN({interest_y},MAX({g}*(1-{var_ex_tax})-{fixed_y},0)))")
    for key, lab, gross_f, ds in (
        ("base", "Base case", "={adr:base}*365*{occ:base}", "{debt_service}"),
        ("occ", "Occupancy falls (size set in Assumptions)", "={adr:base}*365*" + o_s, "{debt_service}"),
        ("adr", "Nightly rate falls", "=" + a_s + "*365*{occ:base}", "{debt_service}"),
        ("both", "Both fall together", "=" + a_s + "*365*" + o_s, "{debt_service}"),
        ("rate", "Mortgage rate higher than assumed", "={adr:base}*365*{occ:base}", "{ds_stress}"),
        ("all", "All three at once", "=" + a_s + "*365*" + o_s, "{ds_stress}"),
    ):
        gk, nk, ck = "st_%s_gross" % key, "st_%s_net" % key, "st_%s_cf" % key
        L.triple((gk, nk, ck), lab, (gross_f, net_f.replace("{g}", "{%s}" % gk), ("={%s}-%s+" % (nk, ds)) + relief_f.replace("{g}", "{%s}" % gk)))

    # ---- 7. ten-year view ----
    L.section("7. Ten-year view (base short-let income held flat; sale in year 10)")
    L.header(["", "Prices flat-ish", "Middle", "Optimistic", "Basis"])
    L.scen("growth", "Price growth per year", {sc: "={A:growth_%s}" % sc for sc in SCEN}, "pct",
           "Nominal. See Assumptions for what Moroccan prices have actually done.")
    L.scen("sale", "Sale price in year 10", "={price}*(1+{growth})^10")
    L.scen("sale_costs", "Selling costs (agent)", "={sale}*{A:sale_agent_pct}")
    L.scen("tpi", "Capital gains tax on sale (TPI)",
           "=MAX({A:tpi_rate}*MAX({sale}-{sale_costs}-{cost_base},0),{A:tpi_min_pct}*{sale})", "mad",
           "Greater of 20% of the gain and 3% of the sale price (the 3% floor usually applies).")
    L.scen("home_cgt", "Home-country capital gains tax top-up (estimate)",
           "=MAX(0,{A:home_cgt_rate}*MAX({sale}-{sale_costs}-{price}-{closing_total}-{renovation},0)-{tpi})", "mad",
           "Rough: home-country rate on the gain in dirhams, less Moroccan tax. Exchange-rate moves can add or remove gain.")
    L.scen("proceeds_c", "Net sale proceeds, cash buyer", "={sale}-{sale_costs}-{tpi}-{home_cgt}")
    L.scen("profit_c", "Total 10-year profit, cash buyer", "={proceeds_c}+10*{net:base}-{cash_needed_c}", bold=True)
    L.scen("irr_c", "Annual return (IRR), cash buyer", '=IFERROR(RATE(10,{net:base},-{cash_needed_c},{proceeds_c}),"")', "pct", bold=True)
    L.scen("proceeds_m", "Net sale proceeds after repaying the loan", "={proceeds_c}-{loan_bal_10}")
    L.scen("profit_m", "Total 10-year profit, with mortgage", "={proceeds_m}+10*{cf_m:base}-{cash_needed_m}", bold=True)
    L.scen("irr_m", "Annual return (IRR), with mortgage", '=IFERROR(RATE(10,{cf_m:base},-{cash_needed_m},{proceeds_m}),"")', "pct", bold=True)
    L.single("cost_base", "(helper) cost base for capital gains tax",
             "={price}*(1+MAX({closing_pct},{A:tpi_cost_flat_pct}))+{renovation}", "mad",
             "Price + buying costs (flat allowance or actual, whichever is higher) + invoiced works. Indexation ignored (conservative).")
    L.single("loan_bal_10", "(helper) loan still owed after 10 years",
             "=IF({loan}>0,IF({A:term_years}<=10,0,IF({A:rate_eff}=0,{loan}*(1-10/{A:term_years}),"
             "{loan}*(1+{A:rate_eff}/12)^120-{pmt_month}*((1+{A:rate_eff}/12)^120-1)/({A:rate_eff}/12))),0)")
    L.note_row("All returns are in dirhams. Your return in %s also depends on the exchange rate when you bring money home, "
               "and on being able to prove the money came in as foreign currency (keep the bank's transfer certificates)." % H)

    # ---- 8. comparables ----
    L.section("8a. Comparable properties for sale (asking prices)")
    L.header(["Comparable", "Asking price (MAD)", "Surface (m²)", "MAD per m²", "Link / note"])
    comps = p.get("comps_sale") or []
    first = L.row
    for c in comps + [{}] * 3:
        r = L.row
        L.table_row([c.get("desc"), c.get("price_mad"), c.get("surface_m2"),
                     '=IF(AND(ISNUMBER(B%d),ISNUMBER(C%d)),IF(C%d>0,B%d/C%d,""),"")' % (r, r, r, r, r)],
                    ["text", "mad", "num", "mad"], " ".join(x for x in (c.get("url"), c.get("note")) if x))
    L.ranges["sale_m2"] = ("D", first, L.row - 1)

    L.section("8b. Comparable short lets (what guests actually pay nearby)")
    L.header(["Comparable", "Nightly rate (MAD)", "Bedrooms", "Reviews", "Link / note"])
    scomps = s.get("comps") or []
    first = L.row
    for c in scomps + [{}] * 3:
        L.table_row([c.get("desc"), c.get("nightly_mad"), c.get("bedrooms"), c.get("reviews")],
                    ["text", "mad", "int", "int"], " ".join(x for x in (c.get("url"), c.get("note")) if x), input_cols="BCD")
    L.ranges["str_rate"] = ("B", first, L.row - 1)
    L.single("str_comp_median", "Median nightly rate of comparables", '=IF(COUNT({rng:str_rate})>0,MEDIAN({rng:str_rate}),"")', "mad",
             "Listed prices. Achieved rates run lower once discounts and empty nights are counted.")

    L.section("8c. Comparable long lets")
    L.header(["Comparable", "Rent per month (MAD)", "Surface (m²)", "MAD per m² per month", "Link / note"])
    lcomps = lt.get("comps") or []
    first = L.row
    for c in lcomps + [{}] * 3:
        r = L.row
        L.table_row([c.get("desc"), c.get("rent_mad_month"), c.get("surface_m2"),
                     '=IF(AND(ISNUMBER(B%d),ISNUMBER(C%d)),IF(C%d>0,B%d/C%d,""),"")' % (r, r, r, r, r)],
                    ["text", "mad", "num", "num"], " ".join(x for x in (c.get("url"), c.get("note")) if x))
    L.ranges["ltr_rent"] = ("B", first, L.row - 1)
    L.single("ltr_comp_median", "Median monthly rent of comparables", '=IF(COUNT({rng:ltr_rent})>0,MEDIAN({rng:ltr_rent}),"")', "mad")

    # ---- 9. flags, unknowns, due diligence ----
    L.section("9. Flags and open questions")
    flags = p.get("flags") or []
    n_red = sum(1 for f in flags if f.get("severity") == "red")
    n_amber = sum(1 for f in flags if f.get("severity") == "amber")
    L.single("n_red", "Red flags", n_red, "int")
    L.single("n_amber", "Amber flags", n_amber, "int")
    flag_first = L.row
    for f in flags:
        L.text(None, (f.get("severity") or "note").upper(), "", f.get("text") or "")
    flag_last = L.row - 1
    for u in p.get("unknowns") or []:
        L.text(None, "UNKNOWN — ask", "", u)

    L.section("10. Due-diligence checklist")
    L.header(["Check", "Status", "", "", "Why it matters / notes"])
    status = p.get("due_diligence") or {}
    dd_first = L.row
    for item in dd:
        st = status.get(item["key"]) or {}
        if isinstance(st, str):
            st = {"status": st}
        note = item["why"] + ((" — NOTE: " + st["note"]) if st.get("note") else "")
        L.text(None, "[%s] %s" % (item["stage"], item["item"]), st.get("status") or "todo", note)
    dd_last = L.row - 1

    render(ws, L, hfmt)

    # row heights for wrapped notes, conditional colours, validation
    for it in L.items:
        if it["kind"] in ("text", "single", "scen", "triple", "trow") and it.get("note"):
            n = len(str(it["note"]))
            if n > 95:
                ws.row_dimensions[it["row"]].height = min(90, 13 * (n // 95 + 1))
    if flag_last >= flag_first:
        rng = "A%d:A%d" % (flag_first, flag_last)
        ws.conditional_formatting.add(rng, FormulaRule(formula=['LEFT($A%d,3)="RED"' % flag_first], fill=FILL_RED))
        ws.conditional_formatting.add(rng, FormulaRule(formula=['LEFT($A%d,5)="AMBER"' % flag_first], fill=FILL_AMBER))
    if dd_last >= dd_first:
        rng = "B%d:B%d" % (dd_first, dd_last)
        dv = DataValidation(type="list", formula1='"todo,asked,ok,problem,n/a"', allow_blank=True)
        ws.add_data_validation(dv)
        dv.add(rng)
        for word, fill in (("ok", FILL_GREEN), ("problem", FILL_RED), ("asked", FILL_AMBER)):
            ws.conditional_formatting.add(rng, CellIsRule(operator="equal", formula=['"%s"' % word], fill=fill))
    vr = L.cells["verdict"][1]
    _verdict_colours(ws, "B%d" % vr)
    ws.freeze_panes = "B3"
    ws.sheet_view.zoomScale = 110
    return ws, L


def _verdict_colours(ws, rng):
    first = rng.split(":")[0]
    for word, fill in (("PURSUE", FILL_GREEN), ("CONDITIONAL", FILL_AMBER), ("PASS", FILL_RED)):
        ws.conditional_formatting.add(rng, FormulaRule(formula=['LEFT(%s,%d)="%s"' % (first, len(word), word)], fill=fill))


def _q(v):
    return "?" if v is None else str(v)


def _yn(v):
    return "?" if v is None else ("yes" if v else "no")


COMPARE_COLS = [
    # header, width, format, key or callable(p, name, L) -> value/formula
    ("#", 5, "text", None),
    ("Property", 34, "text", None),
    ("City / area", 22, "text", None),
    ("Beds", 6, "int", None),
    ("m²", 7, "num", "surface"),
    ("Asking (MAD)", 14, "mad", "asking"),
    ("Asking ({H})", 12, "home", "asking_home"),
    ("Asking MAD/m²", 12, "mad", "ask_m2"),
    ("vs area mid", 10, "pct", "ask_vs_mid"),
    ("Price modelled (MAD)", 14, "mad", "price"),
    ("Cash needed, cash purchase ({H})", 15, "home", "cash_needed_c_home"),
    ("Cash needed, with mortgage ({H})", 15, "home", "cash_needed_m_home"),
    ("Profit / month THE VIDEO'S WAY ({H})", 15, "home", "v_profit_home"),
    ("Short-let net yield, cash — BASE", 12, "pct", ("net_yield_c", "base")),
    ("Short-let net yield, cash — BEAR", 12, "pct", ("net_yield_c", "bear")),
    ("Cash flow / month after mortgage — BASE ({H})", 15, "home", ("cf_m_month_home", "base")),
    ("Cash flow / month after mortgage — BEAR ({H})", 15, "home", ("cf_m_month_home", "bear")),
    ("Cash-on-cash, mortgage — BASE", 12, "pct", ("coc_m", "base")),
    ("Break-even occupancy, mortgage", 12, "pct", ("be_occ_m", "base")),
    ("Long-let net yield, cash — BASE", 12, "pct", ("ltr_net_yield", "base")),
    ("10-yr IRR, cash, middle growth", 12, "pct", ("irr_c", "base")),
    ("Title", 14, "text", "title_status"),
    ("Red flags", 7, "int", "n_red"),
    ("Verdict", 14, "text", "verdict"),
    ("Added", 11, "text", None),
]


def build_compare(ws, entries, home, hfmt, as_of):
    _put(ws, "A1", "Morocco property tracker — side by side", font=F_TITLE)
    _put(ws, "A2", "Built %s. Every number links to that property's own sheet (click the name). Change inputs there or on the "
                   "Assumptions sheet, not here. BEAR = pessimistic case; judge deals on bear and base, never on bull." % as_of, font=F_SUB)
    hr = 4
    for i, (head, width, _fmt, _key) in enumerate(COMPARE_COLS, start=1):
        col = get_column_letter(i)
        ws.column_dimensions[col].width = width
        _put(ws, "%s%d" % (col, hr), head.replace("{H}", home), font=F_HEAD, fill=FILL_HEAD,
             align=Alignment(wrap_text=True, vertical="center", horizontal="center"))
    ws.row_dimensions[hr].height = 58
    r = hr
    for name, p, L in entries:
        r += 1
        q = "'%s'!" % name
        for i, (head, _w, fmt, key) in enumerate(COMPARE_COLS, start=1):
            ref = "%s%d" % (get_column_letter(i), r)
            numfmt = hfmt if fmt == "home" else FMT.get(fmt)
            if head == "#":
                _put(ws, ref, name.split(" ")[0])
            elif head == "Property":
                title = (p.get("title") or p["id"]).replace('"', "'")[:120]
                _put(ws, ref, '=HYPERLINK("#%sA1","%s")' % (q, title), font=F_URL)
            elif head == "City / area":
                _put(ws, ref, ", ".join(x for x in (p.get("neighbourhood"), p.get("city")) if x))
            elif head == "Beds":
                _put(ws, ref, p.get("bedrooms"), numfmt)
            elif head == "Added":
                _put(ws, ref, p.get("added"))
            else:
                k, sc = key if isinstance(key, tuple) else (key, None)
                _put(ws, ref, "=%s%s" % (q, L.addr(k, sc, absolute=True)), numfmt, F_LINK)
    if entries:
        last = r
        cols = {h: get_column_letter(i) for i, (h, *_rest) in enumerate(COMPARE_COLS, start=1)}
        _verdict_colours(ws, "%s%d:%s%d" % (cols["Verdict"], hr + 1, cols["Verdict"], last))
        for h in ("Cash flow / month after mortgage — BASE ({H})", "Cash flow / month after mortgage — BEAR ({H})"):
            rng = "%s%d:%s%d" % (cols[h], hr + 1, cols[h], last)
            ws.conditional_formatting.add(rng, CellIsRule(operator="lessThan", formula=["0"], fill=FILL_RED))
        rng = "%s%d:%s%d" % (cols["Red flags"], hr + 1, cols["Red flags"], last)
        ws.conditional_formatting.add(rng, CellIsRule(operator="greaterThan", formula=["0"], fill=FILL_RED))
        rng = "%s%d:%s%d" % (cols["vs area mid"], hr + 1, cols["vs area mid"], last)
        ws.conditional_formatting.add(rng, CellIsRule(operator="greaterThan", formula=["0.1"], fill=FILL_AMBER))
        ws.conditional_formatting.add(rng, CellIsRule(operator="lessThan", formula=["-0.05"], fill=FILL_GREEN))
        ws.auto_filter.ref = "A%d:%s%d" % (hr, get_column_letter(len(COMPARE_COLS)), last)
    else:
        _put(ws, "A6", "No properties yet. Add a record to the properties folder and rebuild.", font=F_NOTE)
    ws.freeze_panes = "C%d" % (hr + 1)


def build_readme(wb, home, as_of):
    ws = wb.create_sheet("Read me")
    ws.column_dimensions["A"].width = 120
    lines = [
        ("How to read this workbook", F_TITLE),
        ("", F_BASE),
        ("Compare — one row per property, side by side. Start here.", F_BASE),
        ("Assumptions — tax rates, fees, mortgage terms, running costs, with the source of each. Change a blue cell and every property updates.", F_BASE),
        ("P01, P02 … — one sheet per property: price check, cash needed, short-let and long-let income in three scenarios, stress tests, 10-year view, comparables, flags and the due-diligence checklist.", F_BASE),
        ("", F_BASE),
        ("Colour code", F_BOLD),
        ("Blue text on yellow = an input you can change.   Black = a formula.   Green = pulled from another sheet.", F_BASE),
        ("", F_BASE),
        ("Three rules for using the numbers", F_BOLD),
        ("1. Judge a deal on the BEAR and BASE columns. The bull column shows what has to go right, nothing more.", F_BASE),
        ("2. 'Net yield' already deducts platform fees, management, syndic, utilities, insurance, maintenance, Moroccan taxes and an estimate of home-country tax. Gross yield does not, and is the number sellers quote.", F_BASE),
        ("3. Returns are in dirhams. Your return in %s also depends on the exchange rate and on documenting that your money entered Morocco as foreign currency." % home, F_BASE),
        ("", F_BASE),
        ("This workbook is rebuilt from the JSON records in the 'properties' folder each time the skill runs. Edits typed directly into it are for what-if testing: "
         "they are overwritten by the next rebuild. To make a change stick, tell Claude (it updates the record) or edit profile.json.", F_BASE),
        ("", F_BASE),
        ("Not legal, tax or financial advice. Before paying any deposit: have a notary you chose yourself check the title, and have a Moroccan tax adviser confirm the rental-tax treatment. "
         "Defaults last verified %s." % as_of, F_NOTE),
    ]
    for i, (text, font) in enumerate(lines, start=1):
        c = _put(ws, "A%d" % i, text, font=font, align=WRAP)
        if len(text) > 130:
            ws.row_dimensions[i].height = 14 * (len(text) // 130 + 1)
    return ws


# =====================================================================
# Self-check: recalculate with LibreOffice, compare with the reference model
# =====================================================================
def find_soffice():
    for cand in (shutil.which("soffice"), shutil.which("libreoffice"),
                 "/Applications/LibreOffice.app/Contents/MacOS/soffice"):
        if cand and Path(cand).exists():
            return cand
    return None


def recalc_copy(xlsx: Path, tmp: Path):
    soffice = find_soffice()
    if not soffice:
        return None, "LibreOffice not found — formulas were not independently recalculated"
    profile = tmp / "lo_profile"
    out = tmp / "out"
    out.mkdir()
    src = tmp / "in.xlsx"
    shutil.copy(xlsx, src)
    cmd = [soffice, "--headless", "--norestore", "--nolockcheck", "-env:UserInstallation=%s" % profile.as_uri(),
           "--convert-to", "xlsx:Calc MS Excel 2007 XML", "--outdir", str(out), str(src)]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    except subprocess.TimeoutExpired:
        return None, "LibreOffice timed out"
    result = out / "in.xlsx"
    if not result.exists():
        return None, "LibreOffice did not produce a file: %s" % ((res.stderr or res.stdout or "").strip()[:300])
    return result, None


ERR = re.compile(r"^(#(DIV/0!|N/A|NAME\?|NULL!|NUM!|REF!|VALUE!)|Err:\d+)")


def _close(a, b, tol):
    return abs(a - b) <= tol * max(1.0, abs(a), abs(b))


def verify(xlsx: Path, entries, results):
    report = {"verified": False, "cells_checked": 0, "mismatches": [], "formula_errors": [], "note": None}
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        recalced, err = recalc_copy(xlsx, tmp)
        if err:
            report["note"] = err
            return report
        wb = load_workbook(recalced, data_only=True)
        for ws in wb.worksheets:
            for row in ws.iter_rows():
                for c in row:
                    if isinstance(c.value, str) and ERR.match(c.value):
                        report["formula_errors"].append("%s!%s = %s" % (ws.title, c.coordinate, c.value))
        for (name, p, L), model in zip(entries, results):
            ws = wb[name]
            for key, (kind, row, col) in L.cells.items():
                if key not in model:
                    continue
                expected = model[key]
                targets = [(SC_COL[sc], expected[sc] if isinstance(expected, dict) else expected, sc) for sc in SCEN] \
                    if kind == "scen" else [(col, expected, None)]
                for c, exp, sc in targets:
                    if isinstance(exp, dict) or isinstance(exp, str):
                        continue
                    got = ws["%s%d" % (c, row)].value
                    got = None if got == "" else got
                    report["cells_checked"] += 1
                    label = "%s!%s%d (%s%s)" % (name, c, row, key, ":" + sc if sc else "")
                    if exp is None and got is None:
                        continue
                    if exp is None or got is None or not isinstance(got, (int, float)):
                        report["mismatches"].append("%s: model=%r sheet=%r" % (label, exp, got))
                    elif not _close(float(got), float(exp), 1e-4 if key.startswith("irr") else 1e-7):
                        report["mismatches"].append("%s: model=%.6f sheet=%.6f" % (label, exp, got))
        report["verified"] = not report["mismatches"] and not report["formula_errors"]
        try:
            inject_cached_values(xlsx, wb)
        except Exception as e:  # cosmetic only: previews show blanks until opened in a spreadsheet app
            report["note"] = "Could not store calculated values for previews (%s); the file is still correct when opened." % e
    return report


CELL_RE = re.compile(r'<c r="([A-Z]+[0-9]+)"([^>]*?)>(<f>.*?</f>|<f/>)(?:<v>[^<]*</v>|<v\s*/>)?</c>', re.S)


def inject_cached_values(xlsx: Path, computed_wb):
    """openpyxl writes formulas without results, so file previews show empty cells.
    Copy the results LibreOffice computed into the file next to each formula."""
    from xml.sax.saxutils import escape

    names = computed_wb.sheetnames
    tmp_out = xlsx.with_suffix(".tmp.xlsx")
    with zipfile.ZipFile(xlsx) as zin, zipfile.ZipFile(tmp_out, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            m = re.fullmatch(r"xl/worksheets/sheet(\d+)\.xml", item.filename)
            if m and int(m.group(1)) <= len(names):
                ws = computed_wb[names[int(m.group(1)) - 1]]

                def rep(mm, ws=ws):
                    ref, attrs, f = mm.group(1), mm.group(2), mm.group(3)
                    v = ws[ref].value
                    attrs = re.sub(r'\s+t="[^"]*"', "", attrs)
                    if v is None or v == "":
                        return '<c r="%s"%s t="str">%s<v></v></c>' % (ref, attrs, f)
                    if isinstance(v, bool):
                        return '<c r="%s"%s t="b">%s<v>%d</v></c>' % (ref, attrs, f, int(v))
                    if isinstance(v, (int, float)):
                        return '<c r="%s"%s>%s<v>%r</v></c>' % (ref, attrs, f, v)
                    return '<c r="%s"%s t="str">%s<v>%s</v></c>' % (ref, attrs, f, escape(str(v)))

                data = CELL_RE.sub(rep, data.decode("utf-8")).encode("utf-8")
            zout.writestr(item, data)
    load_workbook(tmp_out)  # raises if we damaged the file
    os.replace(tmp_out, xlsx)


# =====================================================================
def _round(v):
    if isinstance(v, dict):
        return {k: _round(x) for k, x in v.items()}
    if isinstance(v, float):
        return round(v, 4) if abs(v) < 10 else round(v, 0)
    return v


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data-dir", default=str(DEFAULT_DATA_DIR))
    ap.add_argument("--no-verify", action="store_true", help="skip the LibreOffice recalculation self-check")
    ap.add_argument("--metrics-only", action="store_true", help="print the metrics, do not write the workbook")
    args = ap.parse_args()
    data_dir = Path(args.data_dir).expanduser()
    if not data_dir.exists():
        die("data folder %s does not exist" % data_dir)

    profile, spec, rows, A, dd, props, buyer_type, home = load_inputs(data_dir)
    as_of = spec.get("as_of", "?")
    hfmt = home_fmt(home)
    results = [deal_model.compute(p, A) for p in props]

    summary = {"data_dir": str(data_dir), "buyer_type": buyer_type, "home_currency": home,
               "fx_mad_per_home": A["fx_home"], "defaults_as_of": as_of,
               "profile_found": (data_dir / "profile.json").exists(), "properties": []}

    entries, out = [], data_dir / WORKBOOK_NAME
    if not args.metrics_only:
        wb = Workbook()
        compare = wb.active
        compare.title = "Compare"
        _ws, a_rows = build_assumptions(wb, rows, buyer_type, home, as_of)
        for i, p in enumerate(props, start=1):
            name = sheet_name(i, p)
            _ws, L = build_property(wb, name, p, a_rows, dd, home, hfmt)
            entries.append((name, p, L))
        build_compare(compare, entries, home, hfmt, dt.date.today().isoformat())
        build_readme(wb, home, as_of)
        for ws in wb.worksheets:   # print / PDF: landscape, one page wide
            ws.sheet_properties.pageSetUpPr = PageSetupProperties(fitToPage=True)
            ws.page_setup.orientation = "landscape"
            ws.page_setup.fitToWidth = 1
            ws.page_setup.fitToHeight = 0
        wb.calculation.fullCalcOnLoad = True
        try:
            wb.save(out)
        except PermissionError:
            die("Could not write %s — close it in Excel/Numbers and run again." % out)
        summary["workbook"] = str(out)
        summary["check"] = ({"verified": False, "note": "skipped (--no-verify)"} if args.no_verify
                            else verify(out, entries, results))

    for i, (p, model) in enumerate(zip(props, results), start=1):
        summary["properties"].append({"id": p["id"], "file": p["_file"], "sheet": sheet_name(i, p),
                                      "title": p.get("title"), "metrics": _round(model)})
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    chk = summary.get("check") or {}
    if chk.get("mismatches") or chk.get("formula_errors"):
        sys.exit(1)


if __name__ == "__main__":
    main()
