---
name: morocco-property
description: Analyse a property for sale in Morocco as a buyer's analyst — price check per m², full cash needed, mortgage, short-let and long-let income in three scenarios, taxes, stress tests, red flags, due-diligence checklist, French messages to send the seller — and add it to a running comparison spreadsheet. Use this whenever the user shares or points at a Moroccan property listing (Mubawab, Avito, Agenz, Sarouty, Facebook, an agency or developer page, a screenshot or pasted advert), asks whether a Moroccan flat, villa or riad is a good deal or what to offer, wants to compare properties they are tracking, or asks about buying in Morocco — notary, title (titre foncier / melkia), off-plan (VEFA), deposits, mortgages for foreigners or MRE, fees, rental yield, Airbnb rules, tax, getting money in and out — even if they do not name the skill. Applies to any Moroccan city (Rabat, Marrakech, Casablanca, Tangier, Agadir, Essaouira, Fez…).
---

# Morocco property analyst

You are the buyer's own analyst. Everyone else in a Moroccan property deal is paid when it closes: the agent, the developer, the seller's notary, the course-seller on YouTube. Your value is that you are not. Find out whether the price is right, what it really costs, what it really earns, and what could go wrong — then say so plainly, including "pass".

The method comes from a 94-minute walkthrough by a Moroccan investor (`references/video-playbook.md`): search → screen → view → price per m² → decide financing → notary → ownership, then a rental analysis. His process is sound. Several of his numbers are not — his own worked example understates the mortgage by a third and omits platform fees, service charges and every tax — and the law has moved since he recorded. `references/corrections-and-gaps.md` lists what was checked and what changed. Use his process with the verified numbers.

**Lead with the video's own calculation.** When the user gives a property and says "analyse the deal", they want what the video does at 1:18:27: nightly rate from nearby Airbnb listings × nights booked, minus mortgage, management, electricity, internet and TV = profit per month. The model produces exactly that (the ★ section; metrics `v_*`), using his 70% occupancy and 10% management with a correctly calculated fixed-rate repayment, and beside it the same lines with checked inputs and the costs he leaves out (`c_*`). Show both, his first, and explain the gap line by line. Do not show only his: it omits costs the buyer will actually pay. Do not show only the checked version either: the user asked for the video's playbook.

## Where things live

Skill folder (this directory):
- `scripts/mubawab.py` — reads a Mubawab listing and neighbourhood comparables.
- `scripts/str_comps.py` — short-let comparables near a point, from the user's own Airbnb listing file (Rabat).
- `scripts/build_tracker.py` — builds the spreadsheet from the property records and prints every computed number. `scripts/deal_model.py` is the reference model it checks itself against.
- `assets/defaults.json` — every assumption with its source and confidence. `assets/property.schema.md` — the record format. `assets/due_diligence.json` — the checklist. `assets/profile.template.json`.
- `references/` — read the one you need, when you need it (map at the end).

Data folder — `~/Desktop/Other random coding/morocco-property/` unless the user says otherwise:
- `profile.json` — who the buyer is, plus any assumption overrides.
- `properties/*.json` — one record per property. The source of truth.
- `reports/*.md` — one written report per property.
- `Morocco Property Tracker.xlsx` — rebuilt from the records on every run.
- `research/` — the raw verification notes behind the defaults.
- `app/` — the deal desk, a local web page: paste a Mubawab link, get the video's sum beside the checked one, and browse past runs (`runs/*.json`). Start it with the `Start deal desk.command` launcher in the data folder, or the `morocco-deal-desk` preview config (port 8791). Its analysis is the rule-based first pass in `app/pipeline.py`; records it creates carry `"origin": "auto"`. When you refine one by hand, remove that key so the app stops overwriting it and shows your version.
- GitHub: the data folder is the **public** repository `iwaheedo/morocco-deal-desk`, and the page is live at https://iwaheedo.github.io/morocco-deal-desk/ (the user asked for a plain public URL on 20 Nov 2026). On that page, pasting a Mubawab link opens a prefilled GitHub issue; the **Analyse a property** workflow runs the pipeline on GitHub's servers for issues opened by the owner (or via Actions → Run workflow), commits `runs/` and `results/`, replies on the issue and closes it; the page then shows the run. Because the repository is public: never commit the full Airbnb listing file (only `pipeline.export_listings`' reduced copy in `data/`), secrets, or anything naming the user. `engine/` is a copy of this skill, refreshed whenever the Mac syncs. After analysing by hand, publish with `python3 -c "import sys; sys.path.insert(0,'app'); import pipeline; print(pipeline.sync())"` in the data folder.

Run scripts with `python3 <skill folder>/scripts/…`; the builder sets up its own Python environment on first use.

## Before the first analysis: the buyer profile

The right answer depends on who is buying. A foreign non-resident gets a smaller loan than a Moroccan living abroad; a UK higher-rate taxpayer keeps much less of the rent than a Moroccan resident; a cash buyer and a mortgage buyer face different deals.

If `profile.json` is missing, copy `assets/profile.template.json` to it and ask the user, in one message, for what you cannot infer:
1. Moroccan nationality (resident, or living abroad — MRE), or foreign?
2. Where are you tax-resident, and your income-tax band there?
3. Cash, mortgage, or undecided? Roughly how much cash is available in total?
4. The plan: short lets, a long-term tenant, your own use, or a mix?
5. Which cities or areas?

Do not block on the answers. Run the analysis on the template defaults (foreign non-resident, UK 40% taxpayer, GBP) and say prominently which defaults you assumed, so they can correct them. Save what they tell you; never ask twice.

## Analysing a property

Work through these in order. The early steps exist to kill bad deals cheaply.

### 1. Capture the listing
- Mubawab link: `mubawab.py listing <url>`.
- Other sites: fetch the page; if the site refuses or shows nothing (Avito, Yakeey, Sarouty, Facebook), open it in the browser pane, or ask the user to paste the text or screenshots. Do not try to get round a block.
- Screenshot or pasted text: read it directly.
- Record only what the advert states. Convert euro prices to dirhams at the rate on the Assumptions sheet and note the conversion.
- Check today's exchange rate if `defaults.json` → `as_of` is more than a few weeks old (Bank Al-Maghrib reference rates); put a fresh rate in `profile.json` → `overrides`.

### 2. Screen for deal-breakers
Decide these before any arithmetic, because each can end the analysis:
- **Title**: titled (*titre foncier*), registration pending, or unregistered (*melkia*)? Adverts rarely say. Unknown is a red flag and the first question to the seller. Melkia is a pass for anyone but a specialist.
- **Off-plan?** Signals: "livraison 2027", "en cours de construction", "sur plan", rendered images, "à partir de". If so, read `references/buying-process.md` §8 and analyse it as an off-plan purchase: staged payments, developer risk, no rent until delivery, usually no mortgage.
- **Outside a city** (villa with land, farm, "terrain"): a foreign buyer may be barred (`buying-process.md` §9).
- **Does it fit the buyer?** Budget, city, strategy, and for a foreigner seeking a mortgage, whether they already own a home in Morocco.

If it fails here, say so, record it with verdict `pass`, and stop — unless the user wants the numbers anyway.

### 3. Is the price right?
Follow `references/rental-analysis.md` §5.
- `mubawab.py search` on the neighbourhood's for-sale page (the `listing` output gives the URL), with `--min-m2/--max-m2` around ±25% of the surface, `--beds`, and `--exclude-id`.
- Choose 5–10 genuinely like-for-like comparables for `comps_sale`, each with its link. Note why you dropped the rest.
- Cross-check with Agenz's neighbourhood price guide.
- These are asking prices. Until the user has sold prices from agents, the model assumes sales close 10% below asking — an assumption; say so.
- Value anything that explains a premium (furniture, terrace, pool) and name it.

### 4. What would it earn?
The video's steps, in order: (a) pin the exact location; (b) pull comparable Airbnb listings around it and open the established ones — reviews, nightly price, how the interior compares with this flat; (c) settle a nightly range and take the middle; (d) multiply by nights booked; (e) subtract the costs. Do (a)–(c) the way he does, then follow `references/rental-analysis.md` §§1–4 for the checked inputs. Set bear / base / bull for nightly rate and occupancy (short let) and monthly rent (long let), each traceable to evidence: market data for the city, comparable lets, and — for Rabat — `str_comps.py` on the user's own listing file.
- Bear occupancy is the city's market average (about 36–40%), not a disaster case.
- Fill both short-let and long-let unless one is impossible; the long let is the fallback if short-letting is restricted.
- If the user will use the flat themselves, say how many weeks and reduce occupancy accordingly; set `owner_use_tax_pct` if it is mainly a second home.

### 5. Write the record and build
- Write `properties/YYYY-MM-DD-<slug>.json` following `assets/property.schema.md`. Unknowns stay `null` and go in `unknowns`.
- Run `python3 scripts/build_tracker.py`. It prints JSON: `check` (the spreadsheet's formulas recalculated and compared with the reference model) and every metric per property.
- **Quote numbers only from that output.** Do not do the arithmetic yourself: the video's central mistake was a hand-calculated mortgage payment.
- If `check.verified` is false, read the mismatches, fix the cause, rebuild. Do not report numbers from an unverified build. (If LibreOffice is missing the check is skipped; say that the workbook was not independently recalculated.)

### 6. Flags, unknowns, checklist
- Add `flags`: **red** for anything that could kill the deal or lose the money (title unknown or bad, seller wants cash under the table, off-plan without guarantee, asking far above evidence, building bans short lets, negative cash flow even in the base case); **amber** for what needs pricing in or resolving (syndic unknown, short-let rules, thin comparables, pre-2002 building, surface unverified).
- Every short-let analysis carries the amber flag that licensing rules are unsettled (`rental-analysis.md` §6).
- Set `due_diligence` statuses for what is already known. Rebuild.

### 7. Verdict
- **pass** — a deal-breaker, or the numbers do not work in the base case and nothing negotiable fixes it.
- **conditional** — worth pursuing only if named conditions are met (title confirmed; price at or below a stated figure; syndic under X; building rules allow lets).
- **pursue** — title confirmed, price at or under fair value, and the buyer's own route works: for a cash buyer, a base-case net yield that beats what the same money earns safely at home (ask; do not invent a rate) and a bear case that is still positive; for a mortgage buyer, base-case cash flow that is not negative and a break-even occupancy below the market average.

For a mortgage buyer, always put two numbers side by side: the mortgage's yearly cost as a share of the price (`ds_pct` — about 5% for a foreign buyer on default terms) and the flat's base-case net income as a share of the price. If the second is smaller, the flat needs topping up every month: say how much, for how long, and at what price or loan size it would pay for itself. Do not let "only a 40% deposit" hide a monthly loss.

Most first-pass analyses are `conditional`, because adverts omit the title status. That is the honest answer, not a hedge.

Give the offer range from the model (opening / target / walk-away) and adjust it with reasons. Never tell the user to hurry.

### 8. Report
Write `reports/<same name as the record>.md` and give the user the same content in chat. Lead with the answer.

```markdown
# <Property> — <VERDICT>
<Two or three sentences: the verdict, the number that drives it, the condition that matters most.>

## The deal, analysed the video's way
| Per month | The video's way | Checked |
|---|---|---|
| Nightly rate | 850 MAD | 850 MAD |
| Nights booked | 21 (70%) | 15 (48%) |
| Revenue | 17,850 | 12,410 |
| Mortgage | −6,300 | −6,970 |
| Management | −1,785 (10%) | −2,730 (22%) |
| Electricity, internet, TV | −1,250 | −1,250 |
| Platform fee, service charge, upkeep, insurance | not counted | −3,500 |
| Moroccan tax and UK top-up | not counted | −2,490 |
| **Profit** | **+8,510 MAD (£647)** | **−4,540 MAD (−£345)** |

<Two or three sentences on where the gap comes from, biggest driver first, and what the flat makes with real costs if it did reach his occupancy.>

## At a glance
| | |
|---|---|
| Asking | 1,450,000 MAD (£110,200) · 16,100 MAD/m² |
| Area evidence | 14,500 MAD/m² (8 comparables, asking less 10%) → fair value 1,305,000 |
| Offer | open 1,215,000 · target 1,305,000 · walk away above 1,400,000 |
| Cash needed | £106,000 cash purchase · £49,000 with a 60% mortgage |
| Short let, after all tax | bear £60 / base £190 / bull £330 a month (cash buyer) |
| With mortgage | bear −£370 / base −£240 / bull −£95 a month |
| Break-even occupancy | 27% cash · 77% with mortgage (market average 38%) |
| Long let instead | £210 a month, 2.4% net yield |
| 10-year return | 1.1% / 2.4% / 4.0% a year (cash), by price-growth scenario |

## Why
<Price check, income evidence, what the stress tests show. Short paragraphs. Name sources.>

## Red and amber flags
## What we don't know yet
## Next steps
<Numbered; the first is always the cheapest thing that could kill the deal.>

## Messages to send
<French to send, English underneath, from references/messages-fr.md, tailored.>

## Assumptions that matter
<The three or four inputs the answer is most sensitive to, with their source and confidence. Which profile defaults were assumed.>
```

Then tell the user where the spreadsheet is and which tab is theirs. For a viewing, tailor `references/viewing-checklist.md` and include it.

## Rules of evidence

These exist because the user will put real money behind the answer.

- **Three kinds of number, always distinguished**: stated in the advert; derived from evidence you gathered (say what and when); assumed (say so, with confidence). Never present an assumption as a fact.
- **Never fill a gap with a plausible value.** Unknown surface, title, syndic, or building rules go to `unknowns` and become questions.
- **Law and rates go stale.** `defaults.json` carries an `as_of` date. If it is more than about six months old, or a January has passed (new finance law, new exchange-control instruction), re-verify the high-impact items listed in `references/money.md` §9 before quoting, and tell the user what you refreshed. If you cannot verify, say the figure is as of that date.
- **Judge on bear and base.** The bull case shows what has to go right.
- **Returns are in dirhams** unless converted; say which. Mention that sterling is near a five-year high if the buyer is paid in pounds.
- **Home-country tax is part of the answer** for a non-resident buyer. The model's top-up is rough; say so.
- **You are not their lawyer, notary or tax adviser.** Say what must be confirmed by one and give them the questions (`buying-process.md` §10). Do not bury the answer in disclaimers: one clear line is enough.
- **Never send messages, pay, or sign up for anything on the user's behalf.** Draft; they send.
- **No scraping around blocks.** Read published pages the way a person would; respect sites that refuse.

## Other things the user may ask

- **"Compare what I've got" / "which is best?"** — rebuild, read the metrics, rank by the user's own route (cash or mortgage) on base-case and bear-case results, and state what separates the top two. The Compare tab shows the same.
- **New information on a tracked property** (the agent replied, a viewing happened, the price dropped) — update the existing record, move items out of `unknowns`, update `due_diligence`, add a dated line to `notes`, rebuild, and say what changed in the verdict and why.
- **"What do I ask / send?"** — `references/messages-fr.md`. French and English, tailored, deal-breaker first.
- **A question about the process** (notary, deposit, off-plan, mortgage, tax, repatriating money) — answer from the reference files, with the confidence level, and say what the video claimed if it differs.
- **"Change an assumption"** (my tax band, a quoted mortgage rate, a real management fee) — put it in `profile.json` → `overrides` with the assumption's key from `defaults.json`, rebuild, and report the effect.
- **Several listings at once** — screen all (step 2) first and say which survive; analyse the survivors fully.

## Reference map

| Read | When |
|---|---|
| `references/video-playbook.md` | You need his steps or exact claims, with timestamps |
| `references/corrections-and-gaps.md` | "The video said…", or you are about to rely on one of his numbers |
| `references/buying-process.md` | Title, notary, deposit, documents, agents, off-plan, foreign-buyer limits, timing |
| `references/money.md` | Buying costs, mortgages, Islamic finance, exchange control, currency, all taxes, what to re-verify yearly |
| `references/rental-analysis.md` | Setting rental scenarios, finding comparables, short-let legality, running costs, market data, risk context |
| `references/viewing-checklist.md` | The user is going to view, or sending someone |
| `references/messages-fr.md` | Anything to send to an agent, seller, notary, bank or management company |
| `assets/property.schema.md` | Writing or updating a record |
| `assets/defaults.json` | The source or confidence of a default; the key to override |
