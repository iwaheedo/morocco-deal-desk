# Estimating rental income honestly

The purchase model is arithmetic; the rental inputs are judgement. Most bad deals come from an optimistic nightly rate multiplied by an optimistic occupancy. This file is how to set the three scenarios (bear / base / bull) from evidence, and where the evidence comes from.

Sources: `research/notes-D.md`, `D-sub1-report.md`, `D-sub2-report.md` in the data folder; the user's own dashboard snapshot in `morocco-str/data.js` (AirROI public pages, updated 5 Nov 2026).

Contents: 1 Market numbers · 2 Getting comparables · 3 Setting short-let scenarios · 4 Long-let scenarios · 5 Sale comparables · 6 Is short-letting allowed · 7 Running costs · 8 Risk context

## 1. Market numbers (12 months to Oct 2026, AirROI; averages across all active listings)

| Market | Revenue per listing (MAD/yr) | Occupancy | Nightly rate (MAD) | Active listings | Low month as % of best |
|---|---|---|---|---|---|
| Marrakech | 164,193 | 40% | 1,535 | 11,901 | 66% |
| Taghazout | 139,899 | 45% | 1,056 | 674 | 48% |
| Essaouira | 124,322 | 39% | 1,098 | 1,872 | 50% |
| Tangier | 87,404 | 36% | 974 | 3,951 | 31% |
| Agadir | 86,358 | 39% | 832 | 2,763 | 45% |
| **Rabat** | 85,738 | 37.5% | 940 | 2,030 (+68% in a year) | 48% |
| Fez | 66,867 | 31% | 753 | 715 | 61% |
| Casablanca | 63,008 | 35% | 754 | 3,446 | 54% |
| Morocco overall | 107,000 | 36% | 1,140 | 42,600 | — |

Rabat detail (same source):
- By size — studio: 639 MAD a night, 39%; 1-bed: 791, 40%; **2-bed: 1,052, 38%, median revenue 75,500**; 3-bed: 1,373, 36%.
- Spread across listings — occupancy: bottom quarter 19%, median 38%, top quarter 62%, top tenth 78%. Nightly rate: 535 / 760 / 1,080 / 1,515.
- Seasons — high (Jul–Aug, Dec): 47% at 964; shoulder: 42% at 920; low (Feb–Mar, Nov): 37% at 870.
- Areas with most activity: Agdal, Old Medina, Hay Riad, Chellah, L'Océan, Rabat Ville.

How the trackers differ: AirROI averages *every* active listing, including ones blocked half the year, so it reads low. Airbtics' Rabat median was 51% occupancy at 799 MAD; AirDNA showed Marrakech at 57%. A well-run, always-available flat should beat the AirROI average, which is why it is the **bear** case, not the base.

Direction of travel (press, July 2026): revenue per listing rising about 11% a year in Rabat while Marrakech stalls; listings are growing faster than visitor numbers almost everywhere (national arrivals +14% in 2025, +5% in Jan–Sep 2026).

If `~/Desktop/Other random coding/morocco-str/data.js` exists, read it for fresher or fuller figures (it carries its own snapshot date) and say which date you used. To refresh a city by hand, read its AirROI page (`airroi.com/airbnb-data/morocco/<region>/<city>`) or Airbtics' free city summary once — these are published pages.

Ground rules the user set while building that dashboard: Airbnb's public search may be read through the real browser, at low volume, for their own research — that is how the dashboard's listing file was collected. Calling Airbnb's internal API from a script is out (it was blocked, and it means evading bot detection). AirROI's terms forbid scraping its site; its paid API (`morocco-str/fetch_listings.py`) spends the user's credit, so ask first. Stop if a site challenges or blocks you.

## 2. Getting comparables

**Mubawab** (reads without a browser — use `scripts/mubawab.py`):
- `listing <url>` returns the listing plus ready-made search URLs for the same neighbourhood.
- `search <url> [<url> …]` reads the first page of each search (about 33 cards) with price per m² statistics.
- Sale: `/fr/sd/<city>/<area>/appartements-a-vendre`. Long let: `…-a-louer`. Holiday let: `…-vacational` (prices per night). City-wide: `/fr/st/<city>/…`.
- Area slugs keep their accents (`guéliz`, `maârif`); unaccented versions return 404.
- Only first pages: the site's robots.txt disallows paginated and filtered URLs. To widen, add the neighbouring area's URL or the city URL.
- Watch for: euro-priced cards (pass `--fx-eur`), developer project cards (excluded automatically), day rates mixed into long-let pages, typos (flagged as suspect outliers), new-build and off-plan adverts crowding the first page (`--exclude-new-build`).

**Agenz** (`agenz.ma`, readable with a normal page fetch):
- Price guide by neighbourhood: `/fr/prix-immobilier-maroc/<city>` — a blend of public data, adverts and partner transactions, last updated Jan 2026. The best free cross-check on asking prices. City averages for apartments: Casablanca 12,503 MAD/m², Rabat 12,392, Marrakech 8,885, Tangier 8,029, Agadir 7,935.
- Listings: `/fr/acheter/immo-<city>/vente-appartements/<area>` and `/fr/louer/immo-<city>/location-appartements/<area>`. Its area filter is loose — check each card's own label.

**Avito and Yakeey** refuse automated fetches; **Sarouty** serves no listings that way. If the user's listing is on one of them, open it in the browser pane or ask for a paste or screenshots. Never try to get round a block.

**Facebook groups**: ask the user to paste the post or a screenshot.

**The user's own Airbnb listing file** (Rabat only, for now): `scripts/str_comps.py --lat … --lng … --beds N` reads `morocco-str/listings.js` — about 1,700 Rabat listings with position, bedrooms, rating, review count and a one-night spot price — and returns the price spread of comparable entire homes within a radius, plus the best-established ones with links. No network access. Use `--min-reviews 5` to drop unproven listings. If the exact address is unknown, use the neighbourhood's centre and say so. The prices are one-night spot prices for nights still unbooked: take roughly 10–15% off before treating the median as an achieved rate.

**Airbnb / Booking** (for what guests pay, any city): open a search in the browser pane, as a person would, and read the visible results — for example `airbnb.com/s/<Area>--<City>--Morocco/homes?checkin=YYYY-MM-DD&checkout=YYYY-MM-DD&adults=2&min_bedrooms=2`. Sample two or three date windows (a high-season week, a low-season week, a midweek stay). Record 5–10 genuinely similar listings: title, bedrooms, rating, review count, total price ÷ nights. That is a handful of page views, not scraping; if the browser pane is unavailable, ask the user to paste what they see. The total a guest sees includes the cleaning fee, so the nightly rate the host earns is lower — knock off roughly 10%, and say so.

**The most valuable evidence** is a local management company's real 12-month statement for a similar flat (message template 6 in `messages-fr.md`). One of those outweighs any amount of browsing.

## 3. Setting short-let scenarios

Nightly rate (`adr_mad`) — the average actually achieved over a year, net of the cleaning fee:
- **Base**: median of the comparable listings' prices, less ~10%.
- **Bear**: the lower quartile, or the city average for that bedroom count.
- **Bull**: what the best genuinely comparable listings with many reviews charge.

Occupancy:
- **Bear**: the AirROI market average for the city (≈ 36–40%).
- **Base**: about 10 points above it (≈ 48–52%) — a professionally managed, always-available flat.
- **Bull**: the top-quarter level (≈ 60–65%).
- Never model the video's 70% as a base case. If a seller or agent quotes it, ask for a platform statement.

Sense-check: compare base revenue (rate × 365 × occupancy) with the city's average rate × average occupancy × 365 for that bedroom count (Rabat 2-bed: 1,052 × 38% × 365 ≈ 146,000 MAD). A base case well above that needs a specific reason (a pool, sea view, exceptional location) — say what would have to be true. The trackers' "revenue per listing" figures (Rabat 2-bed median 75,500) include listings open only part of the year, so they read low; quote them as what a typical host actually banks, not as the ceiling.

New listings take months to gather reviews; year one usually undershoots.

## 4. Long-let scenarios

- Use Mubawab `…-a-louer` and Agenz `louer` cards for the same area and bedroom count. Separate furnished from unfurnished; drop day rates.
- **Base** = median of comparable asking rents less ~5% for negotiation; bear and bull = lower and upper quartiles.
- Tenancy law (Law 67-12): rent increases capped at 8% every three years for housing (press, medium confidence); eviction is slow. A long let is steadier and cheaper to run but hard to exit.
- The model taxes long lets on the 2026 scale after the 40% allowance, plus 10.5% communal tax.

## 5. Sale comparables — is the price right?

The video's method is the right one: price per m² against what the area actually achieves.

1. Pull asking prices for similar flats (same area, ±25% surface, same bedroom count, similar age) with `mubawab.py search`. Put 5–10 real comparables in `comps_sale`, each with its link. Do not copy the whole page: pick the like-for-like ones and say why others were dropped.
2. Cross-check against Agenz's neighbourhood figure. If Mubawab's median is far above Agenz's, the first page is probably dominated by new-build and furnished stock.
3. Sold prices beat both: ask 7–8 agents (template 2) and put the cluster in `area_price_per_m2` with the basis. That overrides the default assumption that sales close 10% under asking, which is only a placeholder.
4. Adjust for what explains a premium — included furniture at replacement cost, a terrace, a pool, a newer building — and name it. No explanation, no premium.

## 6. Is short-letting allowed?

State of play, Nov 2026:
- **Law 80-14** makes running tourist accommodation subject to authorisation (arts 5 and 30), requires daily electronic declaration of guests (art. 36) and sets fines of **50,000–500,000 MAD** for operating without authorisation (art. 43). High confidence — read in the text.
- Its categories do not fit an investor-owned flat: "home-stay" means the host's own home; "tourist residence" is a classified commercial establishment. The orders that would create a licensing route for private lets **had not been published**. A specialist said in May 2026 that the specification needed to apply for a licence "still hasn't appeared".
- In January 2026 the housing ministry said a decree regulating buildings used for short lets is being prepared, to limit uncontrolled spread outside tourist areas.
- Enforcement so far has targeted undeclared income and guest registration (Marrakech, 2025), not closure of individual flats.

So: widely done, formally grey, and more likely to tighten than loosen. Every short-let analysis carries this as an **amber flag**, and a plan that only works as a short let should be tested against the long-let numbers as the fallback.

Building level: the co-ownership rules (*règlement de copropriété*) may restrict use. Read them before any deposit; ask the syndic how many flats are already short lets and whether neighbours have complained.

## 7. Running costs (defaults and their basis)

| Cost | Default | Basis |
|---|---|---|
| Platform fee | 15.5% of bookings | Airbnb's host-only fee, standard through 2026 |
| Management | 22% | Quotes of 20–30% (Marrakech), 20% (Rabat) |
| Upkeep, linen, supplies | 5% | AirROI cost model |
| Cleaning | recovered from guests | As the video assumes; if the manager's fee excludes cleaning, raise management |
| Syndic | from the listing, else 10 MAD/m²/month | Thin evidence; 400–1,200 MAD a month typical, more with pool and security |
| Electricity and water | 650 MAD a month | Assumption |
| Internet + TV | 600 MAD a month | Assumption |
| Insurance | 1,500 MAD a year | Assumption |
| Moroccan tax | 8% income + 7% local | See `money.md` §6 |

Self-managing from abroad is not realistic for short lets; do not delete the management line unless the user will live nearby.

## 8. Risk context to mention when relevant

- **Earthquake**: Sept 2023 damaged old and earthen buildings; modern concrete blocks in Guéliz were "almost intact". Building age matters: permit before 2002 (no mandatory seismic code), 2002–2014 (first code), after (tightened). Agadir highest hazard; Tangier and Marrakech next; Casablanca, Rabat, Essaouira lower.
- **Water**: Marrakech had restrictions in 2024; reservoirs recovered in 2026. Ask about the building's tank and pump.
- **Supply**: 60,000 more hotel beds planned nationally by 2030; short-let listings growing fast.
- **Demand**: 19.8 million arrivals in 2025; target 26 million by 2030; the 2030 World Cup host cities (candidates: Agadir, Casablanca, Fez, Marrakech, Rabat, Tangier) are not final. Airports are being expanded (Marrakech to 16 million passengers by about 2028; Rabat-Salé to 5 million).
- A World Cup is a few weeks of demand. Do not let it carry a valuation.
