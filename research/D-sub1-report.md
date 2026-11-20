TASK GIVEN:
Research task (read-only web research; do NOT write any files; return findings as your final message in markdown). Today is 18 Nov 2026.

GOAL: document, for a property-comparables tool, the mechanics of Moroccan real-estate listing sites so a tool can pull apartment comparables (for sale and for rent) for a given city/neighbourhood. Accuracy matters more than coverage: only report what you actually observed by fetching the page with WebFetch (load it via ToolSearch "select:WebFetch,WebSearch"). If a fetch returns 403/404/JS-shell, say exactly that — do not guess, and do NOT try to get around blocks (no spoofed user agents, no curl workarounds).

SITES: Mubawab (mubawab.ma), Avito (avito.ma), Sarouty (sarouty.ma), Agenz (agenz.ma), Yakeey (yakeey.com). Also briefly check: Mouldar (mouldar.com price index pages), Trovit/Mitula aggregators, bank repossession / auction sources (e.g. "biens saisis" pages of Attijariwafa / CIH / BMCE "vente aux enchères immobilier Maroc", the justice ministry's judicial-auction portal), and the DGI "référentiel des prix de l'immobilier" (is there a searchable online version; which cities incl. Marrakech; year of last update).

What I already know (don't re-do, build on it):
- https://www.mubawab.ma/fr/st/marrakech/appartements-a-vendre works with WebFetch: ~2,955 results, cards show price (DH), m², pièces/chambres, neighbourhood; listing URLs like /fr/a/{id}/{slug} and /fr/pa/{id}/{slug}; link to price guide at https://www.mubawab.ma/fr/study-guide and estimator /fr/estimate-price. I did NOT find the neighbourhood-level URL pattern, the rental pattern, the holiday-rental pattern, or pagination.
- https://www.avito.ma/fr/marrakech/appartements-à_vendre → HTTP 403 to WebFetch.
- https://agenz.ma/fr/prix-immobilier-maroc works: city-average price/m² (apartments 2026: Casablanca 12,503; Rabat 12,392; Marrakech 8,885; Tanger-Assilah 8,029 MAD/m²); city pages at /fr/prix-immobilier-maroc/{city}; listings at /fr/acheter and /fr/louer. Neighbourhood page pattern unknown.
- https://yakeey.com/fr-ma/prix-immobilier → 403.
- https://www.sarouty.ma/acheter/marrakech/appartements-a-vendre.html returned a category landing page with no listings; pattern /acheter/{locality}/appartements-a-vendre/ seen.

FOR EACH SITE report:
1. Exact working URL pattern for: apartments for sale in a city; in a neighbourhood (test with Marrakech + Guéliz and Hivernage; also Casablanca + Maarif or Tangier + Malabata if quick); apartments for long-term rent; holiday/short-term rentals if a separate category; pagination parameter. Give 1–2 concrete URLs you fetched successfully for each.
2. Whether list pages show price, surface (m²), rooms/bedrooms, neighbourhood, date posted; whether a detail page shows them.
3. Whether the content is readable via plain WebFetch (server-rendered HTML) or blocked (403) / JS-only / login required.
4. For the price-guide pages (Mubawab study-guide / "guide des prix", Agenz city + neighbourhood pages, Yakeey, Mouldar): the

=====REPORT=====
# Moroccan listing sites: mechanics for a comparables tool

Fetched with WebFetch on 18 Nov 2026. Three of the five sites are not usable this way: Avito and Yakeey return 403 site-wide, and Sarouty serves pages with no listings. Mubawab and Agenz are readable. The WebSearch budget ran out mid-task, so some "other sources" items rest on search snippets only and are flagged.

## Mubawab (mubawab.ma): readable, server-rendered

| Item | Pattern / finding | Fetched example |
|---|---|---|
| Sale, city | `/fr/st/{city}/appartements-a-vendre` | `/fr/st/marrakech/appartements-a-vendre` (2,955 results) |
| Sale, neighbourhood | `/fr/sd/{city}/{quartier}/appartements-a-vendre` | `/fr/sd/marrakech/guéliz/…` (870), `/hivernage/` (198), `/mhamid/` (100), `/agdal/` (181), `/majorelle/` (63), `/route-de-l'ourika/` (38), `/camp-al-ghoul/` (90), `/fr/sd/casablanca/maârif/…` (184), `/fr/sd/tanger/malabata/…` (110) |
| Long-term rent | swap in `appartements-a-louer` | `/fr/st/marrakech/appartements-a-louer` (2,389); `/fr/sd/marrakech/guéliz/appartements-a-louer` (555); Hivernage (221); Mhamid (46) |
| Holiday rent | swap in `appartements-vacational` | `/fr/st/marrakech/appartements-vacational` (169); `/fr/sd/marrakech/guéliz/appartements-vacational` (79) |
| Pagination | suffix `:p:N`, about 33 cards per page | `…/appartements-a-vendre:p:2`; `…/guéliz/appartements-a-louer:p:2` (different listing ids from page 1) |
| Detail | `/fr/a/{id}/{slug}`, `/fr/pa/{id}/{slug}`; `/fr/p/{id}` is a new-build project | `/fr/pa/8154983/…`, `/fr/a/8437045/…` |

- **Slugs:** accents are required. `gueliz` and `maarif` return 404; `guéliz` and `maârif` work. Spaces become hyphens and the apostrophe is kept.
- **Targa:** `targa` and `targa-ménara` both return 404; no working slug found.
- **List cards:** price (DH, sometimes EUR only), m², pièces, chambres, neighbourhood. No posting date. Rent cards carry no "/mois" label; holiday cards show "DH/jour".
- **Detail page:** price, m², pièces, chambres, salles de bain, type, état, standing, sometimes étage. No date. Furnished status appears only in the title or description.
- **Project cards:** every list page injects `/fr/p/` cards from other areas; filter them out.
- **Rent pages mix in day rates:** the Mhamid rent page has many 250–600 DH cards.
- **Price pairing:** in WebFetch's text the price comes before the card title. On the Guéliz sale page the extractor paired prices one card late (card 1 is EUR-priced). I re-paired and confirmed on the detail page of 8154983 (828,000 DH, 60 m²).
- **Price guide:** `/fr/study-guide` loads as an unrendered template ("Traitement en cours…") with no numbers, links or methodology.

## Agenz (agenz.ma): readable, server-rendered

| Item | Pattern | Fetched example |
|---|---|---|
| Sale | `/fr/acheter/immo-{city}/vente-appartements[/{quartier}]` | `/fr/acheter/immo-marrakech/vente-appartements/gueliz` (96), `/hivernage` (41), `/targa` (5) |
| Rent | `/fr/louer/immo-{city}/location-appartements[/{quartier}]` | `/fr/louer/immo-marrakech/location-appartements/gueliz` (40) |
| Pagination | `?page=N` | `/fr/acheter/immo-marrakech/vente-appartements?page=2` (241 total; the page title said "page 3", so indexing is unclear) |
| Detail | `/fr/annonces/immo-{city}/{vente\|location}-{type}/{quartier}/{id}` | seen in links only; no detail page fetched |
| Price guide | `/fr/prix-immobilier-maroc/{city}[/{commune}]` | `/marrakech`, `/marrakech/gueliz`, `/marrakech/menara`, `/marrakech/tassoultante` |

- **Cards:** price ("DH / mois" for rent), m², chambres, bathrooms, "City, Quartier", relative date ("Il y a 3 jours"), Meublé / Non meublé on rentals.
- **Page size:** pages run to about 130k characters and WebFetch reads the first 100k, so use `offset` for the rest.
- **Loose neighbourhood filter:** the Guéliz page included Camp Al Ghoul, Samlalia and Daoudiat; the Hivernage page included Mhamid and Prestigia; the Targa page appends "Résultats similaires à proximité". Filter on the card's own label.
- **No neighbourhood-level price pages:** quartier figures appear only as table rows on city and commune pages.

## Avito, Yakeey, Sarouty

| Site | Result |
|---|---|
| Avito | 403 on `https://www.avito.ma/` and on `/fr/marrakech/appartements-à_vendre`. Nothing observed. |
| Yakeey | 403 on `https://yakeey.com/` and on `/fr-ma/prix-immobilier`. Nothing observed. |
| Sarouty | 200, but every URL returned a landing page with filters and SEO text and no listing cards, counts or pagination. Tried `/acheter/marrakech/appartements-a-vendre/`, `…-a-vendre.html?page=2`, `…/appartements-a-vendre-gueliz.html`, `/louer/marrakech/appartements-a-louer/`, `/en/buy/marrakech/gueliz/apartments-for-sale/`. An old detail URL (`/acheter/appartement-a-vendre-marrakech-gueliz-720239.html`) returned 410. |

## Price guide numbers (apartments, sale, MAD/m²)

Agenz shows no rent figures anywhere. Its stated basis is mixed, not purely asking or transaction prices: "Référentiel des prix immobilier basé sur les données publiques, offres immobilières et transactions partenaires". City and commune pages say "Dernière mise à jour le 29/01/2026"; the national page shows no date.

| Area | Agenz figure | Agenz page |
|---|---|---|
| Hivernage | 17,465 | `/marrakech`, `/marrakech/menara` |
| Agdal | 13,853 | `/marrakech` |
| Guéliz (quartier) | 12,620 | `/marrakech`, `/marrakech/gueliz` |
| Gueliz (commune, "Prix au m² moyen") | 10,508 | `/marrakech/gueliz` |
| Majorelle | 12,602 | `/marrakech` |
| Mhamid | 5,831 on the Ménara page; 5,524 on the Tassoultante page | `/marrakech/menara`, `/marrakech/tassoultante` |
| Targa | not shown | — |
| Route de l'Ourika | not shown (Tassoultante commune average 6,872) | `/marrakech/tassoultante` |
| Casablanca / Rabat / Marrakech / Tanger-Assilah / Agadir | 12,503 / 12,392 / 8,885 / 8,029 / 7,935 | `/fr/prix-immobilier-maroc` |

- **ReaConsult (third party, not one of the five sites):** undated "2026" indicative ranges, basis not stated. "Hivernage 12 700 – 19 100 MAD/m²"; "Guéliz 9 900 – 15 300 MAD/m²"; Targa / Route Ourika 8,000–12,000. No rents. Source: `reaconsult.ma/tendances-et-conseils-en-immobilier/barometre-prix-immobilier-marrakech-2026-par-quartier`.
- **Mouldar:** pattern `/en/pi/price-index/{buy|rent}/apartment/{city}[-with-two-bedrooms]`. Rolling three months of listings: "these values reflect asking prices and may differ from final transaction prices".
  - Marrakech apartment rent: average and median 6,000 MAD, 70 MAD/m², with only 2 properties in the distribution.
  - Marrakech 2-bed rent: 6,500 MAD from 1 property.
  - Marrakech apartment sale index: zeros. Too thin to use.
- **Mubawab guide and Yakeey:** no numbers obtainable.

## Mubawab first-page medians (asking prices, first page only, fetched 18 Nov 2026)

| Area | Sale, median DH/m² | 2-bedroom long-term rent, median DH/month |
|---|---|---|
| Guéliz | about 22,000 (n=30; range 13,068–38,065) | 9,500 (n=20; 15 furnished, 1 unfurnished, 4 unstated) |
| Hivernage | about 23,900 (n=25) | 10,500 (n=17; 9 furnished, 7 unfurnished, 1 unstated) |
| Mhamid | about 8,800 (n=29) | about 5,500 (n=6, all furnished; low confidence) |

- **Guéliz sale exclusions:** one EUR-priced card, one project card, and listing 8275966 (16,500,000 DH for 95 m², confirmed on its detail page, probably a typo).
- **Hivernage sale exclusions:** 6 EUR-priced cards, one project card, one card with no surface.
- **Hivernage rent:** the extractor flagged price-to-card pairing as uncertain for the lower half of the page; one EUR card excluded.
- **Mhamid rent:** I dropped day-rate cards, Prestigia and a professional-use listing.
- **Gap to Agenz:** the Guéliz and Hivernage sale medians are far above Agenz's figures. The first page is heavy with new-build, off-plan and furnished studio listings.
- **Agenz cross-check:** Guéliz-labelled 2-bed rents on its first 12 cards were 9,200, 10,000, 12,000 and 14,000 DH/month.

## Other sources

- **DGI référentiel:**
  - A PDF copy hosted by Medias24 is titled "Référentiel des Prix des Transactions Immobilières de Marrakech … Edition Juillet 2015". It is at `annoncesjudiciaires.medias24.com//images/pdfville/Referentiel_des_prix_des_transactions_immobilieres_de_Marrakech_DGI.pdf`.
  - It covers 68 zones, with price grids by zone code, property type and état, and landmark tables rather than neighbourhood names.
  - Examples: MA-GZ10 (Avenue Ménara / Place Bab Jdid / Av. Mly El Hassan; that this is Hivernage is my reading) apartments 15,000 ancien / 18,000 récent / 20,000 neuf. MA-GZ11: 8,000 / 9,500 / 11,000. MA-ME8 (Mhamid 7 and 9): 6,000 / 6,500 / 7,000. MA-MK1 (Résidence Parc d'Agdal): appartement sécurisé 14,000–14,500.
  - The PDF describes a clickable map on the DGI portal. The portal page `tax.gov.ma/wps/portal/DGI/Referentiels-des-prix-de-l_immobilier/` returned "Aucun contenu trouvé", so I found no working searchable version and no city list.
  - Search snippets only (the articles returned 403): Medias24 reported in July 2020 that the DGI provisionally suspended applying the référentiel, and in 2019 that a joint DGI/ANCFCC référentiel started in Casablanca.
- **Judicial auctions:**
  - `annoncesjudiciaires.medias24.com` loads. Its table has Type de bien, Consistance, Superficie, Lieu, Date vente and Mise à prix (DH); pagination is `/?limitstart=40`; detail pages are `/annonce{id}.html`. Marrakech appears, and the latest sale date shown was 28-12-2026.
  - `mahakim.ma` failed with a TLS certificate error.
  - The justice ministry's planned unified platform is known from a search snippet only (Medias24, July 2024; 403 on fetch).
- **Bank repossessions:** no Attijariwafa, CIH or BMCE page found. Bladi (6 Sep 2025) says bank and finance-company auctions are promoted on social networks and names no portal.
- **Aggregators:** `immobilier.trovit.ma` returned 401. `immobilier.mitula.ma` did not resolve (a guessed hostname).

## Not verified

- Avito and Yakeey: everything.
- Sarouty: listings, fields and pagination.
- Mubawab: guide and "tensiomètre locatif" figures; a Targa slug; whether a `gueliz`-style unaccented alias exists elsewhere.
- Agenz: detail-page fields; the `?page` index base; Targa and Route de l'Ourika prices; any rent index.
- DGI: current status, last update after 2015, and cities covered.
- Any official justice-ministry auction portal or bank repossession pages.
- EUR-priced Mubawab cards were left out of the medians rather than converted.