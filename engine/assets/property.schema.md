# Property record format

One JSON file per property in `<data-dir>/properties/`, named `YYYY-MM-DD-<short-slug>.json`.
`build_tracker.py` reads every file in that folder and rebuilds the workbook.

Rules:
- Money is **MAD** (dirhams). Convert euro/pound prices with the FX rate on the Assumptions sheet and say so in the matching `*_note` field.
- Percentages are **fractions**: `0.55` = 55%, `0.025` = 2.5%.
- Use `null` for anything you do not know. Never fill a gap with a guess; put the gap in `unknowns` so it becomes a question for the seller.
- Only `asking_price_mad` is strictly required, but a record without `surface_m2`, comparables and rental scenarios produces an almost empty sheet.

```jsonc
{
  "id": "gueliz-2br-majorelle",          // short, unique, stable
  "short_name": "Guéliz 2-bed",         // spreadsheet tab label (optional; ≤ 20 characters)
  "added": "2026-11-18",                // date you first analysed it
  "title": "2-bed, 87 m², new build near Jardin Majorelle",
  "source_url": "https://www.mubawab.ma/fr/pa/…",
  "listing_date": "2026-10-02",         // date posted, if shown
  "contact": "Agence X, +212 6…",

  "city": "Marrakech",
  "neighbourhood": "Guéliz",
  "address_note": "Advert says 5 min from Majorelle; exact building unknown",
  "property_type": "apartment",         // apartment | villa | riad | house | land | other
  "bedrooms": 2, "bathrooms": 2,
  "floor": 3, "lift": true,
  "year_built": 2025,
  "condition": "new",                   // new | good | dated | needs-work | under-construction
  "furnished": true,
  "title_status": "unknown",            // titre_foncier | requisition | melkia | unknown
  "off_plan": false,
  "seller_type": "agent",               // agent | owner | developer

  "asking_price_mad": 1500000,
  "asking_note": "Advertised at €140,000; converted at 10.72 MAD/EUR on 2026-11-18",
  "surface_m2": 87,
  "surface_note": "From advert; includes 9 m² terrace",
  "furniture_value_mad": 70000,         // only if furniture is included in the price
  "syndic_mad_month": null,             // null → estimated from Assumptions and flagged
  "agent_fee_pct": null,                // null → default from Assumptions; 0 if direct from owner

  "comps_sale": [                       // similar homes for sale nearby — asking prices
    {"desc": "2-bed 90 m², same street, 2019 build", "price_mad": 1400000, "surface_m2": 90,
     "url": "https://…", "note": "unfurnished"}
  ],
  "area_price_per_m2": {                // OPTIONAL override. Omit to derive low/mid/high from comps_sale
    "low": 13000, "mid": 14500, "high": 16000,   // minus the asking-to-sold discount.
    "basis": "3 agents quoted 13–16k for recent sales; Agenz estimate 12.6k"
  },
  "offer": {                            // OPTIONAL. Omit to use the defaults (target = min(asking, fair mid))
    "opening_mad": 1250000, "target_mad": 1330000, "walk_away_mad": 1400000,
    "note": "Why these numbers"
  },
  "model_price_mad": null,              // OPTIONAL. Price the cash-flow model runs at; default = offer target

  "furnishing_mad": 0,   "furnishing_note": "",
  "renovation_mad": 0,   "renovation_note": "",

  "str": {                              // short-term rental (Airbnb / Booking)
    "comps": [
      {"desc": "2-bed, pool, 4.8★", "nightly_mad": 760, "bedrooms": 2, "reviews": 41,
       "url": "https://www.airbnb.com/rooms/…", "note": "€71 for a midweek night in March"}
    ],
    "adr_mad":   {"bear": 550, "base": 680, "bull": 780},   // average nightly rate ACHIEVED over a year
    "adr_note":  "How you got from the comps to these",
    "occupancy": {"bear": 0.40, "base": 0.52, "bull": 0.63},
    "occupancy_note": "Source of the occupancy figures and their date"
  },
  "ltr": {                              // long-term let
    "comps": [{"desc": "2-bed 85 m² furnished", "rent_mad_month": 9000, "surface_m2": 85, "url": "https://…"}],
    "rent_mad_month": {"bear": 7500, "base": 8500, "bull": 9500},
    "rent_note": ""
  },

  "flags": [                            // red = could kill the deal; amber = price it in or resolve
    {"severity": "red",   "text": "Title status not stated in the advert"},
    {"severity": "amber", "text": "Syndic charge unknown; pool and concierge suggest it is high"}
  ],
  "unknowns": ["Is it titled (titre foncier)? Title number?", "Monthly syndic?"],
  "due_diligence": {                    // keys from assets/due_diligence.json; anything missing counts as "todo"
    "title_status_asked": {"status": "asked", "note": "WhatsApp sent 18 Nov"}
  },                                    // status: todo | asked | ok | problem | n/a

  "verdict": "conditional",             // pursue | conditional | pass
  "verdict_reason": "One or two sentences: the numbers and the single biggest condition.",
  "notes": "Free text; history of contact with the seller"
}
```

## Updating a record

When new facts arrive (the agent replies, a viewing happens, the price drops), edit the existing file — do not create a second one. Add a dated line to `notes`, move resolved items out of `unknowns`, update `due_diligence`, then rebuild.
