# Money: buying costs, mortgages, getting money in and out, tax

Verified 18–20 Nov 2026. Sources and quotes: `research/A-costs-legal.md`, `B-financing-fx.md`, `C-taxes.md` in the data folder. The numbers the model actually uses live in `assets/defaults.json` — this file explains them. Confidence: **H** primary text, **M** good secondary, **L** commercial/assumption.

Contents: 1 Buying costs · 2 Mortgages · 3 Islamic finance · 4 Money in and out · 5 Currency · 6 Tax while you own · 7 Tax when you sell · 8 Home-country (UK) tax · 9 What changes each year

## 1. Buying costs (buyer pays)

| Item | Rate | Conf. |
|---|---|---|
| Registration duty | **4%** of the declared price (bare land 5%) | H |
| Land registry | **1.5%** + 100 MAD | H |
| Notary's fee | about **1%**, negotiable, + **20% VAT** on the fee | M / H |
| Certificates, stamps, preliminary-contract duty | about 1,900 MAD | M |
| **Total, cash purchase** | **≈ 6.8%** (1,500,000 MAD → 102,500) | H |
| Mortgage registration | 0.5% on the first 250,000 MAD of the loan, 1.5% above, + ~600 MAD; bank file fee ≤ 0.1% | H / M |
| **Total with a 70% loan** | **≈ 7.8%** | H |
| Agent, if any | commonly 2.5% incl. VAT — agree in writing | L |
| Untraceable/cash payment | **+2%** of that part since 1 July 2026 | H |

**None of this can be borrowed.** Cash needed = deposit + all costs + furnishing, all wired from abroad.

Many online "frais de notaire" simulators still use 10% VAT and a flat mortgage rate; they are out of date. Use `build_tracker.py`.

## 2. Mortgages

**Who can borrow what**

| | Legal ceiling | What banks publish | Model default |
|---|---|---|---|
| Foreign non-resident | 80% of price since 1 Jan 2026 (IGOC 2026); was 70% | Bank of Africa 50% / 25 yrs; CIH 70% / **15 yrs**; Banque Populaire 70% / 25 yrs | **60%** |
| Moroccan abroad (MRE) | 80% | 70–80% | 70% |
| Moroccan resident | none | up to 90–100% | 80% |

- A foreign non-resident must sign a sworn statement that they own **no residence in Morocco**. A second property needs specific Office des Changes authorisation. MRE have no such limit. **H**
- The loan is capped as a share of the *price*; the rest, and all fees, must come from abroad. Repayments must also come from abroad or a convertible-dirham account. **H**
- Typical conditions: repayments under about a third of income; loan ending by about age 70; proof of foreign income with sworn translations. **M/L**

**Rates (late 2026)**
- Central bank policy rate **2.25%** (unchanged since March 2025; held 22 Sept 2026; next decision 15 Dec 2026). **H**
- Official average on new home loans: **4.53%** (Q2 2026). Rates are quoted **before a 10% VAT on interest**; with insurance the average all-in cost was about **5.5%** (Feb 2026). **H/M**
- Model default for a foreign non-resident: 5.0% before VAT = 5.5% paid. The premium over the average is a prudence assumption.
- **97% of new loans are fixed for the full term.** The video's "always fix" is right, and is what the market does. Variable rates reset yearly with no statutory cap. **H**
- Rates are freely negotiated: get three written offers.

**The paperwork that binds**
- An *accord de principe* is a conditional pre-approval — the consumer law does not mention it. **H**
- The **written offer** (*offre préalable*) binds the bank: open at least **15 days**; you may not accept before **day 10**; the loan lapses if the purchase is not completed within 4 months. **H**
- The sale contract is by law conditional on the loan for at least a month, with the deposit refundable if the loan is refused — still write it in. **H**
- Early repayment: always allowed; charge capped at one month's interest and 2% of the balance. **H/M**
- Compulsory life/disability insurance: about 0.40% of the loan a year. Whether a UK resident is accepted by the bank's insurer is unverified — ask early. **M**

**Monthly repayment** is a standard annuity on the VAT-inclusive rate; always compute it with the model. (The video's example understated it by a third by quoting interest only.)

**Alternative**: raise the money at home (for example against UK property) and buy as a cash buyer. Debt in sterling against a dirham asset is a currency mismatch, but the whole purchase is then foreign-currency funded, which gives the cleanest right to take proceeds out. UK lenders do not normally lend against Moroccan property (unverified).

## 3. Islamic (participatory) finance

- The home product in Morocco is **Mourabaha**: the bank buys the property and resells it to you at cost plus a mark-up fixed at the outset, paid in instalments. 99% of participatory lending. **H**
- The video's "buy shares each month" structure (diminishing partnership) is the UK model and is not what Moroccan banks sell. **H**
- One measured all-in cost: **6.5%** vs 5.5% conventional (Feb 2026). **M**
- Deposit, terms and **eligibility of non-residents — foreign or MRE — are unverified** from any bank's own source. Ask Umnia Bank, Bank Assafa, Al Akhdar Bank, BTI Bank, Bank Al Yousr or a conventional bank's participatory window directly.

## 4. Money in and out (exchange control)

**In**
- Open a **convertible-dirham account** (or foreign-currency account) at a Moroccan bank. Wire funds from abroad.
- The bank issues a certificate of the foreign-currency sale (still called *Formule 2*) or debit advice. **Keep every one, for as long as you own the property.** No filing is required, but without them you cannot prove the right to take money out. **H**
- If the purchase falls through, unused funds can be sent back within a year.

**Out**

| | Foreign non-resident | MRE |
|---|---|---|
| Sale proceeds, bought with foreign currency | Freely transferable, including the gain, net of Moroccan tax | Same |
| Sale proceeds, part-financed by a dirham loan | Deposit brought from abroad + loan capital repaid from abroad + the gain | Same |
| Anything not covered | "Convertible term account": released in four yearly 25% slices | Stays in an ordinary dirham account, not transferable |
| Rental income | Transferable **whatever the financing**, on proof of tax paid and a dated lease | Only if the purchase was financed in foreign currency |

- Whether banks accept short-let platform income (no lease) for transfer is **unverified** — ask the bank before relying on it.
- Money paid under the table has no trail and can never leave.

## 5. Currency

- The dirham is pegged to a basket of **60% euro, 40% dollar**, within ±5%. Sterling is outside the basket, so GBP/MAD moves with sterling. **H**
- 17 Nov 2026 reference rates: **£1 = 13.154 MAD, €1 = 10.9623, $1 = 9.97**. Refresh from Bank Al-Maghrib (bkam.ma → cours de référence) at each analysis.
- Five-year range: GBP/MAD about **11.7–13.2**; EUR/MAD 10.2–11.2. Sterling is near the top. For stress tests use ±8%: a flat costing £100,000 at today's rate would cost about £105,000 at the five-year average rate (12.5) and about £112,000 at the five-year low (11.7).
- Returns in the model are in dirhams. Say so.

## 6. Tax while you own (non-resident individual)

A non-resident is taxed in Morocco on Moroccan income at the same rules as residents, must elect a tax address in Morocco, and files online. **H**

**Long-term unfurnished let**
- Tax base = **60% of gross rent** (40% flat allowance; no deduction of real costs or interest). **H**
- Progressive scale 2026: 0% to 40,000 · 10% to 60,000 · 20% to 80,000 · 30% to 100,000 · 34% to 180,000 · 37% above. **H**
- File and pay before **1 March** of the following year. A company tenant withholds 10% or 15% on account.
- Plus **communal services tax**: 10.5% of the rent, legally the owner's.
- Worked: rent 84,000 → tax on 50,400 = 1,040; TSC 8,820; total ≈ 11.7% of rent.
- The flat 10% / 15% "final" regime ended on 31 Dec 2022. PwC and Deloitte summaries still described it in 2026; they are wrong.
- The 2027 finance bill proposes raising the tax-free band to 60,000.

**Short-term furnished let — unsettled**

| View | Treatment | All-in on 180,000 MAD of bookings |
|---|---|---|
| Common practice | Declared as ordinary rent: 40% allowance, scale, plus communal tax | 13–19% |
| Tax office's written doctrine (2011 circular, never withdrawn) | A business: real costs deductible, business tax (10% of rental value after a 5-year exemption), accounts | 7–15% |
| Reclassified on audit with few costs accepted | Business, penalties, possibly VAT | 25–34% |

- VAT: furnished letting is in scope; individuals under **500,000 MAD** turnover appear exempt (medium-low confidence).
- Tourist tax (*taxe de séjour*) is collected from guests per person per night (range by category, 2–25 MAD); **Airbnb does not collect it in Morocco**.
- Enforcement has risen since 2024 (exchange-control audits of platform payouts; tax-office reminders before the 1 March deadline).
- Model default: **8% income tax + 7% local taxes = 15% of bookings**, range 8–25%. Always say this is an estimate needing a Moroccan tax adviser.

**Keeping it for yourself**: housing tax applies with no abatement on a second home — roughly 0.6–1.2% of price a year together with communal tax; about 0.2% for an MRE's main Moroccan home. A let property pays no housing tax.

No wealth tax; no inheritance or gift tax (1% registration on a post-death inventory, main home excluded). **M-H**

## 7. Tax when you sell

- **20% of the net gain**, same for everyone. **H**
- **Floor: 3% of the sale price**, even with no gain. **H**
- Gain = sale price − selling costs − (purchase price + buying costs + invoiced works + interest paid to an authorised lender) × an official inflation coefficient. Buying costs are taken at a flat **15%** unless actual costs are higher. **H**
- In practice the 3% floor applies unless the sale price exceeds roughly 1.5 × the purchase price.
- **Main-home exemption** needs 5 years' occupation and is **lost once the flat has been let**. A foreign non-resident's holiday flat probably never qualifies.
- File and pay within **30 days**. Without an advance ruling (*avis préalable*, requested within 30 days of the preliminary contract) the seller must lodge **5% of the price** provisionally; the excess is refunded if there is no reassessment. **H**
- Keep invoices for every improvement: they reduce the gain.

## 8. Home-country tax (UK resident)

- The UK–Morocco treaty lets Morocco tax the rent and the gain, and the UK tax its resident on the same, with **credit for Moroccan tax** (arts 6, 13, 22). **H**
- UK income tax applies to the UK-measured profit (actual expenses, not Morocco's 40% allowance) at 20 / 40 / 45% — announced to become 22 / 42 / 47% for property income from April 2027. Mortgage interest gets basic-rate relief only: 20% of it comes off the tax bill, capped at the profit (modelled as `home_interest_relief_pct`, on the loan's average yearly interest). The furnished-holiday-let regime ended in April 2025. **H/M**
- For a 40% taxpayer the UK bill usually exceeds the Moroccan one, so the total is roughly the UK charge. Moroccan *local* taxes are not creditable.
- UK capital gains tax on sale: 18% / 24% of the **sterling** gain, less Moroccan tax on the gain; £3,000 annual allowance. Exchange-rate movement creates or removes UK gain. **H**
- Report on the foreign pages of the tax return.
- The model's "home-country top-up" rows are a rough estimate: marginal rate × income before tax, minus Moroccan income tax. Set the rate in `profile.json`; set it to 0 for a Moroccan tax resident.
- Unverified: whether the 3% minimum Moroccan sale tax is creditable when Morocco computes no gain.

## 9. What changes each year — re-check when stale

| Item | When | Where |
|---|---|---|
| Finance law (tax rates, income-tax scale, registration duties) | Published late December; circular in January–February | tax.gov.ma |
| Exchange-control instruction (loan ceilings, transfers) | 1 January | oc.gov.ma |
| Policy rate | Quarterly (March, June, September, December) | bkam.ma |
| Average mortgage rates | Quarterly | bkam.ma, "taux débiteurs" |
| Exchange rates | Daily | bkam.ma, "cours de référence" |
| Short-let licensing rules | Pending — a decree was announced in Jan 2026 | Ministry of Tourism; press |
| Capital-gains inflation coefficients | February | Bulletin Officiel |

If `assets/defaults.json` → `as_of` is more than about six months old, or a January has passed since, re-verify the high-impact items (exchange rate, mortgage rate, tax scale, loan ceiling, short-let rules) before quoting numbers, and tell the user what you refreshed.
