// Morocco deal desk — page logic. Kept in its own file so the page can forbid inline scripts.
if (location.hostname.endsWith('github.io')) location.replace('https://morocco-deal-desk.vercel.app/');   // the old copy forwards to the live site

const $ = s => document.querySelector(s);
const el = (tag, attrs = {}, ...kids) => { const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) { if (k === 'class') e.className = v; else if (k === 'html') e.innerHTML = v; else e.setAttribute(k, v); }
  for (const k of kids.flat(3)) if (k != null && k !== false) e.append(k.nodeType ? k : document.createTextNode(k)); return e; };
const SYM = {GBP: '£', EUR: '€', USD: '$'};
const n0 = x => x == null || isNaN(x) ? '—' : Math.round(x).toLocaleString('en-GB');
const pct = (x, d = 0) => x == null || isNaN(x) ? '—' : (x * 100).toFixed(d) + '%';
let HOME = 'GBP', FX = 1, BUDGET_HOME = null;
// home(): a dirham amount shown in the buyer's own currency
const home = (x, signed = false) => { if (x == null || isNaN(x)) return '—'; const v = Math.round(x / FX), a = Math.abs(v).toLocaleString('en-GB');
  return (v < 0 ? '−⁠' : signed ? '+⁠' : '') + (SYM[HOME] || HOME + ' ') + a; };
// Every dirham figure on the page carries its home-currency twin: dual() for a cell, both() inside a sentence.
const dual = (x, signed = false) => x == null || isNaN(x) ? '—' : [(x < 0 ? '−' : signed ? '+' : '') + n0(Math.abs(x)) + ' MAD', el('small', {class: 'hc'}, home(x, signed))];
const less = x => !x || Math.round(x) === 0 ? ['0 MAD', el('small', {class: 'hc'}, home(0))] : dual(-Math.abs(x));
const both = (x, unit = '') => x == null || isNaN(x) ? '—' : `${x < 0 ? '−' : ''}${n0(Math.abs(x))} MAD${unit} (${home(x)})`;
const madS = x => (x < 0 ? '−' : '+') + n0(Math.abs(x)) + ' MAD';
const cls = x => x >= 0 ? 'pos' : 'neg';
const esc = v => String(v == null ? '' : v).replace(/[&<>"]/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
const day = s => { const d = new Date(s); return isNaN(d) ? s : d.toLocaleDateString('en-GB', {day: 'numeric', month: 'short'}); };

let LIVE = true;
async function api(path, opts) { const r = await fetch(path, opts); const j = await r.json().catch(() => ({error: 'The app returned something unreadable.'}));
  if (!r.ok) throw new Error(j.error || ('Request failed (' + r.status + ')')); return j; }

async function loadProfile() {
  const p = await api('/api/profile'); HOME = p.home_currency; FX = p.fx_home; LIVE = p.live_progress !== false; BUDGET_HOME = p.budget_home || null;
  if (p.spreadsheet === false) { $('#sheetlink').textContent = ''; $('.hint').textContent = 'Reads Mubawab listings. Takes about 20 seconds: it reads the advert, then finds comparable flats for sale and the Airbnbs around it in your atlas.'; }
  const who = {foreign_non_resident: 'Foreign buyer', mre: 'Moroccan living abroad', moroccan_resident: 'Moroccan resident'}[p.buyer_type] || p.buyer_type;
  if (p.ltv == null) { $('#terms').textContent = who; return; }
  const s = SYM[HOME] || HOME;
  $('#terms').innerHTML = `<b>${esc(who)}</b> · ${esc(p.financing)}<br>Loan <b>${pct(p.ltv)}</b> over <b>${p.term_years} yrs</b> · fixed <b>${pct(p.rate, 2)}</b> (${pct(p.rate_eff, 2)} with VAT)<br>` +
    (p.budget_home ? `Your limit: <b>${s}${n0(p.budget_home)} a month</b> out of pocket (${n0(p.budget_home * p.fx_home)} MAD)<br>` : '') +
    `Home tax <b>${pct(p.home_tax_rate)}</b> · ${s}1 = <b>${p.fx_home.toFixed(2)} MAD</b>`;
}

function receipt(title, tag, lines, total, extra) {
  return el('section', {class: 'receipt'},
    el('header', {}, title), el('div', {class: 'tag'}, tag),
    lines.map(([label, value, kind]) => el('div', {class: 'row ' + (kind || '')}, el('span', {}, label), el('span', {class: 'n'}, value))),
    el('div', {class: 'total'}, el('span', {class: 'lab'}, total >= 0 ? 'Left over per month' : 'You put in per month'), el('span', {class: 'big ' + cls(total)}, home(total, true))),
    el('div', {class: 'row muted'}, el('span', {}, 'in dirhams'), el('span', {class: 'n'}, (total < 0 ? '−' : '+') + n0(Math.abs(total)) + ' MAD')),
    extra ? el('div', {class: 'small'}, extra) : null);
}

const STAMP = {pass: 'PASS', conditional: 'MAYBE', pursue: 'PURSUE'};
const VERDICT_LINE = {'WITHIN YOUR BUDGET': 'inside your monthly limit', 'WITHIN BUDGET IF YOU NEGOTIATE': 'inside your limit, but only at a lower price', 'TIGHT': 'inside your limit, but a weak year breaks it',
  'OVER YOUR BUDGET': 'over your monthly limit as it stands', 'OFF-PLAN': 'off-plan, so a mortgage will not work yet', 'NO NEARBY AIRBNB DATA': 'income unproven — no Airbnbs near it in your atlas', 'WITHIN BUDGET, PRICE UNCHECKED': 'inside your monthly limit, but the price is unchecked', 'CHECK THE TITLE': 'the numbers work for cash; check the title'};

function render(run) {
  const box = $('#result'); box.innerHTML = '';
  const out = {append: (...kids) => box.append(...kids.flat(3).filter(k => k != null && k !== false))};
  HOME = run.home_currency || HOME; FX = run.fx_home || FX;
  if (run.failed) { out.append(el('div', {class: 'flat'}, el('div', {}, el('h2', {}, 'This link was not analysed'), el('div', {class: 'sub'}, run.url || '')), el('div', {class: 'stamp pass'}, 'NOT READ')), el('p', {class: 'why'}, run.error || '')); mark(run); return; }
  const m = run.metrics, r = run.record, t = run.terms, x = run.extras || {}, ev = run.evidence || {};
  const verdict = (r.verdict || 'conditional').toLowerCase();
  const row = (label, value, kind) => el('div', {class: 'row ' + (kind || '')}, el('span', {}, label), el('span', {class: 'n'}, value));
  const sum = (...rows) => el('div', {class: 'sum'}, rows.flat().filter(Boolean));
  const say = html => el('p', {class: 'say', html});
  const plain = html => el('p', {class: 'plain', html});
  const sub = text => el('h3', {class: 'sub'}, text);
  const step = (n, title, ...kids) => el('section', {class: 'step'}, el('div', {class: 'num'}, n), el('div', {}, el('h2', {}, title), kids));
  const tbl = (heads, rows) => el('div', {class: 'scroll'}, el('table', {}, el('thead', {}, el('tr', {}, heads.map(h => el('th', {class: h[1] || ''}, h[0])))), el('tbody', {}, rows.map(c => el('tr', {}, c.map((v, i) => el('td', {class: heads[i][1] || ''}, v)))))));
  const S = ev.str || {}, near = S.method === 'nearby_listings', newMethod = x.topup != null;
  const budget = x.budget_mad || 0;
  const top = x.topup || {bear: Math.max(0, -m.cf_m_month.bear), base: Math.max(0, -m.cf_m_month.base), bull: Math.max(0, -m.cf_m_month.bull)};
  const putIn = v => v > 0.5 ? ['you put in ' + home(v), el('small', {class: 'hc'}, n0(v) + ' MAD')] : ['nothing — it covers itself', el('small', {class: 'hc'}, '0 MAD')];
  const label = r.verdict_label || STAMP[verdict] || verdict.toUpperCase();

  out.append(
    el('div', {class: 'flat'},
      el('div', {}, el('h2', {}, r.title || 'Flat'),
        el('div', {class: 'sub'}, `Asking ${both(m.asking)} · `, /^https?:/.test(run.url || '') ? el('a', {href: run.url, target: '_blank', rel: 'noopener'}, 'open the advert') : '',
          ` · checked ${new Date(run.at).toLocaleString('en-GB', {dateStyle: 'medium', timeStyle: 'short'})}`)),
      el('div', {class: 'stamp ' + verdict}, label)),
    el('p', {class: 'why'}, (r.verdict_reason || '').replace(/^Automatic first pass\. /, '')),
    newMethod ? null : el('p', {class: 'old'}, 'This entry was analysed before 21 November, with city-wide averages and a simple profit-or-pass test. Paste the link again to judge it against your monthly limit using the Airbnbs around it.'));

  // 1 — the flat
  out.append(step(1, 'The flat you found',
    say('The video starts with the search: find a flat on Mubawab, Avito or a Facebook group and write down what the advert says.'),
    sum(row('Where', [r.neighbourhood, r.city].filter(Boolean).join(', ') || '—'), row('Asking price', dual(m.asking)),
        row('Size', m.surface ? n0(m.surface) + ' m²' : 'not in the advert'), row('Bedrooms / bathrooms', (r.bedrooms ?? '?') + ' / ' + (r.bathrooms ?? '?')),
        row('Furnished', r.furnished ? 'yes, says the advert' : 'not mentioned'), r.contact ? row('Selling', r.contact) : null)));

  // 2 — three questions
  const offPlan = !!r.off_plan;
  out.append(step(2, 'Three questions before you view',
    say('He asks the agent these before travelling. A wrong answer ends it there.'),
    el('ul', {class: 'qa'},
      el('li', {}, el('span', {html: '<b>Is it titled?</b> A registered title (titre foncier) proves who owns it. Untitled property (“melkia”) can be claimed by someone else later.'}), el('span', {class: 'a ask'}, r.title_status && r.title_status !== 'unknown' ? r.title_status : 'not in the advert — ask')),
      el('li', {}, el('span', {html: '<b>Is it off-plan?</b> Not built yet means paying in stages, no rent until it is finished, and usually no mortgage.'}), el('span', {class: 'a ' + (offPlan ? 'bad' : 'ok')}, offPlan ? 'looks off-plan' : 'no — finished flat')),
      el('li', {}, el('span', {html: '<b>Exactly where is it?</b> You need the building, not just the area, to compare it with nearby Airbnbs.'}), el('span', {class: 'a ask'}, 'area only — ask for a map pin')))));

  // ---- the sum, in the order you would work it out: buying, mortgage, costs, occupancy, nightly price, revenue, profit
  const row3 = (label, a, b, kind) => el('div', {class: 'row3 ' + (kind || '')}, el('span', {}, label), el('span', {class: 'n' + (a === 'not counted' ? ' no' : '')}, a), el('span', {class: 'n'}, b));
  const head3 = (b = 'Real numbers') => row3('', "Video's way", b, 'head');
  const nComps = (r.comps_sale || []).length, agz = ev.agenz, mk = ev.market || {};
  const insM = (m.insurance_y || 0) / 12, repairsM = ((m.maint || {}).base || 0) / 12;
  const fixedV = m.v_mort + t.utilities_month + t.internet_month + t.subs_month;
  const fixedC = m.c_mort + t.utilities_month + t.internet_month + t.subs_month + m.c_syndic + insM;
  const cityName = mk.city ? mk.city[0].toUpperCase() + mk.city.slice(1) : 'Morocco';
  const N = x.notary;

  // 3 — buying
  out.append(step(3, 'Buying: what it is worth and what it costs to buy',
    say('Morocco prices flats by the square metre. Divide the asking price by the size and compare with what the area goes for. “Just because the owner wants that doesn’t mean it’s worth that.”'),
    m.surface ? sum(
      row('Asking price ÷ size', `${n0(m.asking)} MAD ÷ ${n0(m.surface)} m²`), row('= asking price per m²', dual(m.ask_m2), 'eq'),
      m.comp_median_m2 ? row(`Similar flats nearby ask, per m² (${nComps} adverts, middle one)`, dual(m.comp_median_m2)) : null,
      agz ? row('Published reference for the area, per m² (Agenz)', dual(agz.mad_per_m2)) : null,
      m.area_mid ? row('What the area supports, per m²', dual(m.area_mid)) : null,
      m.fair_mid ? row(`× ${n0(m.surface)} m² = a fair price`, dual(m.fair_mid), 'eq') : null) : plain('The advert gives no size, so the price cannot be checked per square metre. Ask for the surface on the title.'),
    m.surface && !m.fair_mid ? plain('There is <b>no reliable price evidence for this neighbourhood</b> yet, so the sums use the asking price as it stands. Ask 7–8 local agents what similar flats actually sold for before you offer.') : null,
    m.fair_mid ? plain(`The asking price is <b>${pct(Math.abs(m.asking_over_fair))} ${m.asking_over_fair >= 0 ? 'above' : 'below'}</b> that. Open at <b>${both(m.offer_open)}</b>, aim for <b>${both(m.offer_target)}</b>, walk away above <b>${both(m.offer_walk)}</b>. These are <b>asking</b> prices: he messages 7–8 local agents to learn what flats actually sold for.`) : null,
    sub('Notary simulator: the bill on completion day'),
    say('In the video he types the price into an online notary simulator to get the fees. This is the same sum at the official 2026 rates, one line at a time, so you can see where each dirham goes.'),
    N ? sum(row('Price you expect to pay', dual(N.price)),
        N.lines.map(([l, v]) => row(l, dual(v))),
        row(`= paid through the notary (${pct(N.share, 2)} of the price)`, dual(N.total), 'eq'))
      : sum(row('Price you expect to pay', dual(m.price)), row('Registration tax (4%)', dual(m.reg)), row('Land registry (1.5%)', dual(m.cf)), row('Notary, VAT and stamps', dual(m.notary + m.misc)),
            row('= paid through the notary', dual(m.reg + m.cf + m.notary + m.misc), 'eq')),
    N && N.example ? plain(`Cross-check: the worked example in a Moroccan fee guide (Wafir, 2026) for a ${both(N.example.price)} flat comes to about ${pct(N.example.guide_share, 1)} of the price; these lines give ${pct(N.example.share, 2)} on the same flat. The two public simulators could not be used directly (one turns away automated visitors, the one in the video has been taken offline). Any simulator is an estimate: the <b>exact</b> figure is the notary’s own written quote (“décompte des frais”), which you ask for before signing anything.`) : null,
    sub('Everything it costs to buy'),
    sum(row('Price you expect to pay', dual(m.price)), row('Notary’s bill (above)', dual(m.reg + m.cf + m.notary + m.misc)), row('Estate agent (2.5% of the price)', dual(m.agent)),
        m.furnishing ? row('Furniture to make it ready for guests (estimate)', dual(m.furnishing)) : null,
        m.renovation ? row('Building work', dual(m.renovation)) : null,
        row('= total cost of buying it', dual(m.total_cost), 'eq'))));

  // 4 — mortgage
  const paper = m.closing_total + m.mort_costs + m.furnishing + m.renovation, fxCost = m.cash_needed_m - m.deposit - paper;
  out.append(step(4, 'Mortgage: what the bank lends and what you bring',
    say('The bank lends part of the price. The fees are never lent, so they come out of your pocket on top of the deposit. He says always take the fixed rate, never the variable one.'),
    sum(row(`Bank lends (${pct(t.ltv)} of the price)`, dual(m.loan)), row(`Your deposit (${pct(1 - t.ltv)})`, dual(m.deposit)),
        row('+ notary’s bill and estate agent (step 3)', dual(m.closing_total)),
        N ? N.mortgage_lines.filter(l => l[1] > 0.5).map(([l, v]) => row('+ ' + l, dual(v))) : row('+ mortgage paperwork', dual(m.mort_costs)),
        (m.furnishing + m.renovation) ? row('+ furniture and building work', dual(m.furnishing + m.renovation)) : null,
        fxCost > 1 ? row('+ cost of changing your money into dirhams', dual(fxCost)) : null,
        row('= cash you need on day one', dual(m.cash_needed_m), 'eq')),
    el('div', {style: 'height:12px'}),
    sum(row('Interest rate, fixed for the whole loan', pct(t.rate, 2) + '  (today’s average in Morocco)'), row('Length of the loan', t.term_years + ' years'),
        row('= repayment every month', dual(m.v_mort), 'eq'),
        row('Real cost with tax on the interest + the bank’s insurance', dual(m.c_mort)))));

  // 5 — all the costs
  out.append(step(5, 'All the costs, every month',
    say('The bills that arrive whether or not anyone is staying. The video counts four of them.'),
    sum(head3(),
        row3('Mortgage', dual(m.v_mort), dual(m.c_mort)), row3('Electricity and water', dual(t.utilities_month), dual(t.utilities_month)),
        row3('Internet', dual(t.internet_month), dual(t.internet_month)), row3('TV subscription', dual(t.subs_month), dual(t.subs_month)),
        row3('Building service charge', 'not counted', dual(m.c_syndic)), row3('Home insurance', 'not counted', dual(insM)),
        row3('= fixed costs every month', dual(fixedV), dual(fixedC), 'eq')),
    plain(`On top of these, some costs are a <b>slice of whatever guests pay</b>, so they are worked out in step 9 once the revenue is known: a manager (the video says ${pct(t.video_mgmt_pct)}; real quotes are about ${pct(t.mgmt_pct)}), Airbnb’s fee (${pct(t.platform_pct, 1)}), repairs and linen, and tax. Cleaning is charged to the guest.`)));

  // 6 — occupancy
  const nightsM = 365 * m.occ.base / 12, O = S.occupancy_open_nights, R = S.revenue_month_mad, P = S.price_mad, NY = S.nights_year, RC = S.review_check, CAL = S.calendar;
  const atlas = S.atlas_url ? el('p', {class: 'small'}, el('a', {href: S.atlas_url, target: '_blank', rel: 'noopener'}, 'Open your atlas'), ` to see these listings on the map. Data collected ${S.collected_on || ''}.`) : null;
  out.append(step(6, 'Occupancy: how many nights get booked',
    say('Occupancy is the share of nights someone is paying to stay. It is the number that decides everything' + (near ? ', so it is read straight off the Airbnbs around this flat in your atlas, not taken from a city average.' : '.')),
    near ? sum(
      row('Airbnbs compared', `${S.matches} ${S.where || ''}`),
      row('Booked, of the nights their calendar is open', `${pct(O.p25)} / ${pct(O.median)} / ${pct(O.p75)}`),
      row('', 'weakest quarter / middle / best quarter', 'muted'),
      row('Nights a typical host keeps the calendar open', `${S.open_nights} a year`),
      row('= nights the middle listing sells', `${n0(NY.base)} a year · ${(NY.base / 12).toFixed(1)} a month`, 'eq'),
      RC ? row(`Second check: ${n0(RC.per_year)} reviews a year points to`, `${n0(Math.round(RC.nights_low / 10) * 10)}–${n0(Math.round(RC.nights_high / 10) * 10)} nights a year`) : null,
      CAL ? row(`Calendars already taken, ${day(CAL.from)} to ${day(CAL.to)}`, pct(CAL.median_taken)) : null) : null,
    near ? el('div', {style: 'height:12px'}) : null,
    sum(head3(near ? 'Nearby Airbnbs' : 'Real numbers'),
        row3('Share of the year booked', pct(t.video_occ), pct(m.occ.base)),
        row3('= nights booked a month', (m.v_nights).toFixed(0), nightsM.toFixed(1), 'eq')),
    near ? plain(`The video assumes <b>${pct(t.video_occ)}</b>, which is ${(m.v_nights).toFixed(0)} nights a month. The middle Airbnb around this flat sells about <b>${nightsM.toFixed(1)} nights a month</b>. A weak year here means the weakest quarter of them (${(NY.bear / 12).toFixed(1)} nights a month); a strong year means the best quarter (${(NY.bull / 12).toFixed(1)}).` +
        (RC && RC.verdict === 'lower' ? ` <b>The review counts point lower than the atlas figure</b>, so treat ${nightsM.toFixed(1)} nights as the hopeful end for this size of flat.` : RC && RC.verdict === 'agrees' ? ' The review counts agree with the atlas figure.' : ''))
         : plain(`The video uses <b>${pct(t.video_occ)}</b>. Airbnb flats in ${esc(cityName)} are booked about <b>${pct(mk.occ)}</b> of the time on average. <b>Your atlas has no listings near this flat</b>, so this step rests on the city average, which is weak evidence.`),
    near ? atlas : null));

  // 7 — nightly price
  out.append(step(7, 'How much you can charge per night',
    say('He looks at Airbnbs near the flat, compares them with it, and picks a price in the middle of the range.'),
    near ? sum(row('Cheaper quarter of nearby listings charge up to', dual(P.p25)), row('Middle listing — the price used', dual(m.adr.base), 'eq'), row('Dearer quarter charge at least', dual(P.p75)))
         : sum(row('Cheaper end of similar places', dual(m.adr.bear)), row('Middle — the price used', dual(m.adr.base), 'eq'), row('Top end', dual(m.adr.bull))),
    el('p', {class: 'plain'}, (r.str || {}).adr_note || '')));

  // 8 — revenue
  out.append(step(8, 'Total revenue per month',
    say('Nightly price × nights booked.'),
    sum(head3(near ? 'Nearby Airbnbs' : 'Real numbers'),
        row3('Nightly price', dual(m.v_adr), dual(m.c_adr)), row3('× nights booked a month', (m.v_nights).toFixed(0), nightsM.toFixed(1)),
        row3('= money coming in each month', dual(m.v_rev), dual(m.c_rev), 'eq')),
    near ? [sub(`What the ${S.matches} Airbnbs around it take in a month (your atlas)`),
      sum(row('Weak year: the weakest quarter take this or less', dual(R.p25)), row('Typical year: the middle listing — used in the sum', dual(R.median), 'eq'),
          row('Strong year: the best quarter take this or more', dual(R.p75)),
          S.potential_month_mad ? row(`Revenue potential: the middle price, booked ${pct(S.top_quarter_occupancy)} of the whole year`, dual(S.potential_month_mad)) : null),
      plain(`Each listing’s revenue is the atlas’s own figure: its nightly price × its occupancy × the ${S.open_nights} nights a typical host keeps the calendar open. “Revenue potential” is what the atlas shows for a flat run all year at the occupancy the best quarter of the city reaches — a ceiling, not a plan.`)] : null));

  // 9 — profit or loss
  const gapBars = x.gap ? (() => { const topG = Math.max(...x.gap.map(g => g[1]), 1), tot = x.gap.reduce((a, g) => a + g[1], 0);
    return [sub(`Why the two answers are ${both(tot)} a month apart`),
      el('div', {class: 'gap'}, x.gap.filter(g => g[1] > 0.5).map(([l, v]) => el('div', {class: 'bar'}, el('span', {}, l), el('span', {}, el('i', {style: `width:${Math.max(1, v / topG * 100)}%`})), el('span', {class: 'n'}, dual(v))))),
      plain(x.real_costs_at_video_occ == null ? '' : x.real_costs_at_video_occ < 0 ? `Even if the flat did fill ${pct(t.video_occ)} of nights, the real costs would leave you <b>${both(-x.real_costs_at_video_occ)} a month short</b>.` : `If the flat did fill ${pct(t.video_occ)} of nights, it would make <b>${both(x.real_costs_at_video_occ)} a month</b> after real costs.`)]; })() : [];
  out.append(step(9, 'Profit or loss per month',
    say('Money coming in, minus the fixed costs, minus the slices of each booking. What is left is yours — or what you have to put in.'),
    el('div', {class: 'receipts'},
      receipt("The video's way", `${pct(t.video_occ)} of nights booked, a ${pct(t.video_mgmt_pct)} manager, four bills.`, [
        ['Money coming in', dual(m.v_rev), 'rev'], ['Fixed costs (step 5)', less(fixedV)], ['Manager ' + pct(t.video_mgmt_pct), less(m.v_mgmt)],
        ['Airbnb fee, repairs, tax', 'not counted', 'muted']], m.v_profit, `If he holds back his optional 10% for surprises: ${both(m.v_profit_cont)} a month.`),
      receipt(near ? 'With the Airbnbs around it' : 'With real numbers', near ? 'The middle nearby listing’s takings and every cost.' : 'Real booking levels and every cost.', [
        ['Money coming in', dual(m.c_rev), 'rev'], ['Fixed costs (step 5)', less(fixedC)], ['Manager ' + pct(t.mgmt_pct), less(m.c_mgmt)],
        ['Airbnb takes ' + pct(t.platform_pct, 1), less(m.c_platform)], ['Repairs and linen', less(repairsM)], ['Tax in Morocco', less(m.c_ma_tax)], ['Tax at home', less(m.c_home_tax)]],
        m.c_profit, `Weak year ${home(m.cf_m_month.bear, true)} (${madS(m.cf_m_month.bear)}), strong year ${home(m.cf_m_month.bull, true)} (${madS(m.cf_m_month.bull)}) a month.`)),
    budget ? [sub(`Against your limit of ${home(budget)} a month`),
      sum(row('Your limit', [home(budget), el('small', {class: 'hc'}, n0(budget) + ' MAD')]),
          row('Typical year', putIn(top.base), 'eq'), row('Weak year', putIn(top.bear)), row('Strong year', putIn(top.bull)),
          x.topup_at_asking != null && Math.abs(m.price - m.asking) > 1 ? row('Typical year, if you paid the full asking price', putIn(x.topup_at_asking)) : null,
          row(top.base <= budget ? '= room to spare in a typical year' : '= over your limit in a typical year', [home(Math.abs(budget - top.base)), el('small', {class: 'hc'}, n0(Math.abs(budget - top.base)) + ' MAD')], 'eq ' + (top.base <= budget ? 'good' : 'bad')))] : null,
    gapBars));

  // 10 — is the Airbnb play robust?
  if (newMethod) {
    const st = x.stress || {}, pb = x.plan_b, pot = x.potential;
    const share = x.nearby_n ? x.nearby_ok / x.nearby_n : null;
    out.append(step(10, 'Is the Airbnb play robust?',
      say('A monthly top-up is fine by you, so the question is how sure the income is. These are the ways it could go wrong, and what each would cost you a month.'),
      sum(budget && x.rev_for_budget != null ? row(`Money the flat must take each month to keep you at ${home(budget)}`, dual(x.rev_for_budget)) : null,
          x.nearby_n ? row('Nearby Airbnbs that take at least that', `${x.nearby_ok} of ${x.nearby_n}  (${pct(share)})`, 'eq') : row('Nearby Airbnbs that take at least that', 'no nearby listings in your atlas', 'bad'),
          row('Weak year (the weakest quarter of nearby listings)', putIn(top.bear)),
          st.occ_pts ? row(`Bookings fall a further ${Math.round(st.occ_pts * 100)} points of the year`, putIn(st.occ_down)) : null,
          st.price_pct ? row(`Nightly price falls ${pct(st.price_pct)}`, putIn(st.price_down)) : null,
          st.occ_pts ? row('Both at once', putIn(st.both)) : null,
          x.empty_month != null ? row('A month with no guests at all', putIn(x.empty_month)) : null,
          pb ? row(`Plan B: an ordinary long let at ${both(pb.rent)} a month`, pb.topup > 0.5 ? putIn(pb.topup) : ['leaves you ' + home(pb.left), el('small', {class: 'hc'}, n0(pb.left) + ' MAD')]) : row('Plan B: an ordinary long let', 'no rents found nearby to judge'),
          pot ? row('Best case: the atlas’s revenue potential', pot.topup > 0.5 ? putIn(pot.topup) : ['leaves you ' + home(pot.left), el('small', {class: 'hc'}, n0(pot.left) + ' MAD')]) : null,
          row('Mortgage rate', 'fixed: the repayment cannot rise')),
      plain(robustLine(x, top, budget, near, pb))));

    // 11 — when the flat is yours
    const tl = x.timeline || [], terms = x.terms || [], yrs = x.term_years || t.term_years;
    out.append(step(11, 'When the flat is yours',
      say(`You said a monthly top-up is fine if the flat ends up yours. This is the road there on a ${yrs}-year loan, in a typical year.`),
      tbl([['After'], ['Loan left', 'n'], ['You own', 'n'], ['Put in so far', 'n']],
        tl.map(p => [p.year + ' years', dual(p.loan_left), pct(p.owned_share), dual(p.paid_in)])),
      el('div', {style: 'height:12px'}),
      sum(row('Cash in on day one (deposit, fees, furniture)', dual(m.cash_needed_m)),
          row(`Top-ups over ${yrs} years at ${home(top.base)} a month`, dual(x.topup_total)),
          row('= everything you will have put in', dual(x.cash_in_total), 'eq'),
          row('What you own outright at the end, at today’s price', dual(m.price)),
          m.growth && m.growth.base ? row(`The same flat if prices rise ${pct(m.growth.base, 1)} a year (an assumption)`, dual(m.price * Math.pow(1 + m.growth.base, yrs))) : null,
          row('Then the flat pays you, each month after costs and tax', dual(x.income_after_payoff_month))),
      plain('No rise in the flat’s value or in rents is counted here; both would improve this. Furniture is replaced out of the repairs line.'),
      terms.length ? [sub('A shorter loan gets you there sooner but costs more each month'),
        tbl([['Loan over'], ['Repayment a month', 'n'], ['You put in a month', 'n'], ['Your limit', 'n']],
          terms.map(o => [o.years + ' years', dual(o.repayment), dual(o.topup), budget ? (o.topup <= budget ? 'inside' : 'over by ' + home(o.topup - budget)) : '—']))] : null,
      top.base > budget && budget && (x.deposit_for_budget || x.price_for_budget) ? [sub('What would bring it inside your limit'),
        sum(x.deposit_for_budget ? row(`A bigger deposit: ${pct(x.deposit_share_for_budget)} of the price instead of ${pct(1 - t.ltv)}`, dual(x.deposit_for_budget)) : null,
            x.price_for_budget ? row(`Or a lower price: ${pct(x.price_for_budget / m.asking)} of the asking price`, dual(x.price_for_budget)) : null)] : null,
      plain(`If you sold after ten years instead, counting everything paid in and the sale: <b>${m.profit_m.base < 0 ? 'a loss of about ' + both(-m.profit_m.base) : 'a gain of about ' + both(m.profit_m.base)}</b>, with a range from ${both(m.profit_m.bear)} to ${both(m.profit_m.bull)} depending on where prices go.`)));
  }

  // verdict
  const flags = r.flags || [];
  const copy = el('button', {class: 'quiet', type: 'button'}, 'Copy the French');
  copy.onclick = async () => { try { await navigator.clipboard.writeText(run.message_fr); copy.textContent = 'Copied'; } catch (e) { copy.textContent = 'Select and copy by hand'; } setTimeout(() => copy.textContent = 'Copy the French', 1800); };
  out.append(step(newMethod ? 12 : 10, 'Verdict: ' + (VERDICT_LINE[label] || {pass: 'pass on this one', conditional: 'maybe — if the conditions are met', pursue: 'worth pursuing'}[verdict] || verdict),
    el('p', {class: 'plain', style: 'margin-top:0'}, (r.verdict_reason || '').replace(/^Automatic first pass\. /, '')),
    el('div', {style: 'height:12px'}),
    sum(row('To cover itself with no top-up, it would need booking', pct(m.be_occ_m.base) + ' of the year'), row(near ? 'The middle nearby Airbnb manages' : 'Typical for the city', pct(near ? m.occ.base : mk.occ)),
        row('Or a nightly price of', x.be_adr_at_base_occ ? dual(x.be_adr_at_base_occ) : '—'),
        row('Or a purchase price of', x.be_price ? dual(x.be_price) : 'no price works on this loan'),
        row('If you bought with cash instead, each month', dual(m.net.base / 12, true))),
    el('h3', {style: 'margin-top:18px'}, 'Watch out for'), el('ul', {class: 'flags'}, flags.map(f => el('li', {class: f.severity}, el('b', {}, (f.severity || '').toUpperCase()), f.text))),
    el('h3', {style: 'margin-top:18px'}, 'If you want to look closer: send the agent this'), el('pre', {}, run.message_fr || ''), el('p', {class: 'small'}, run.message_en || ''), copy));

  const link = c => /^https?:\/\//.test(c.url || '') ? el('a', {href: c.url, target: '_blank', rel: 'noopener'}, c.desc || 'listing') : (c.desc || '');
  const sale = r.comps_sale || [], stc = (r.str || {}).comps || [], lt = (r.ltr || {}).comps || [];
  out.append(el('h2', {}, 'The evidence used'),
    el('details', {}, el('summary', {}, near ? `Airbnbs around the flat: the ${stc.length} with the most reviews, of ${S.matches} compared` : `Airbnbs and holiday lets compared (${stc.length})`), el('div', {}, el('p', {class: 'small'}, (r.str || {}).occupancy_note || ''),
      tbl([['Listing'], ['Per night', 'n'], ['Booked', 'n'], ['Reviews', 'n']], stc.map(c => [link(c), dual(c.nightly_mad), c.occ != null ? pct(c.occ) : '—', c.reviews ?? '—'])))),
    el('details', {}, el('summary', {}, `Flats for sale nearby (${sale.length})`), el('div', {}, el('p', {class: 'small'}, (r.area_price_per_m2 || {}).basis || 'Asking prices from adverts, less the assumed 10% between asking and sold.'),
      tbl([['Flat'], ['Asking', 'n'], ['m²', 'n'], ['Per m²', 'n']], sale.map(c => [link(c), dual(c.price_mad), n0(c.surface_m2), dual(c.price_mad / c.surface_m2)])))),
    el('details', {}, el('summary', {}, `Flats to rent nearby (${lt.length})`), el('div', {}, el('p', {class: 'small'}, (r.ltr || {}).rent_note || 'No long-let comparables found.'),
      tbl([['Flat'], ['Rent a month', 'n'], ['m²', 'n']], lt.map(c => [link(c), dual(c.rent_mad_month), n0(c.surface_m2)])))),
    el('p', {class: 'small'}, run.check && run.check.verified ? `Sums checked: ${run.check.cells_checked} spreadsheet cells recalculated independently and matched.` : 'Sums come from the reference model; the spreadsheet re-check did not run this time.'));
  mark(run);
}

// One plain sentence on how sturdy the income looks, built only from the figures shown in step 10.
function robustLine(x, top, budget, near, pb) {
  const bits = [];
  if (!near) bits.push('<b>Not robust yet:</b> there are no Airbnbs near this flat in your atlas, so the income is a guess from city averages.');
  else if (budget && x.nearby_n) { const s = x.nearby_ok / x.nearby_n;
    bits.push(s >= 0.6 ? `<b>Sturdy:</b> ${x.nearby_ok} of the ${x.nearby_n} Airbnbs around it already take enough to keep you inside your limit, so you do not need to beat the neighbours.`
      : s >= 0.4 ? `<b>Finely balanced:</b> about half the Airbnbs around it (${x.nearby_ok} of ${x.nearby_n}) take enough to keep you inside your limit. You need to run it at least as well as the middle one.`
      : `<b>Fragile:</b> only ${x.nearby_ok} of the ${x.nearby_n} Airbnbs around it take enough to keep you inside your limit. The plan only works if this flat beats most of its neighbours.`); }
  if (budget && top.bear > budget) bits.push(`A weak year costs ${home(top.bear)} a month, ${home(top.bear - budget)} over your limit.`);
  if (pb) bits.push(pb.topup < top.base - 1 ? `Note that an ordinary long let would cost you less each month (${home(pb.topup)}) than the typical Airbnb year (${home(top.base)}), so the Airbnb only earns its extra work if it does better than the middle listing.`
    : `If short lets were ever stopped in the building, an ordinary long let would cost you ${home(pb.topup)} a month.`);
  bits.push('The rule on short lets in private flats is still unsettled in Morocco, and the building’s own rules can forbid them: confirm both before you rely on any of this.');
  return bits.join(' ');
}
const mark = run => document.querySelectorAll('#history tbody tr').forEach(tr => tr.classList.toggle('on', tr.dataset.id === run.run_id));

async function loadHistory(openLatest) {
  const rows = await api('/api/history'), tb = $('#history tbody'); tb.innerHTML = '';
  if (!rows.length) { tb.append(el('tr', {}, el('td', {colspan: 9, style: 'color:var(--soft);cursor:default'}, 'Nothing yet. Paste a Mubawab link above to check your first flat.'))); return; }
  for (const h of rows) { const s = SYM[h.home_currency] || '', fx = h.fx_home || FX;
    const money = v => (v < 0 ? '−' : '+') + s + Math.abs(Math.round(v)).toLocaleString('en-GB');
    const two = v => v == null ? '—' : [n0(v) + ' MAD', el('small', {class: 'hc'}, s + n0(v / fx))];
    const when = new Date(h.at).toLocaleString('en-GB', {dateStyle: 'medium', timeStyle: 'short'});
    const advert = /^https?:\/\//.test(h.url || '') ? el('a', {href: h.url, target: '_blank', rel: 'noopener'}, 'open') : '';
    if (advert) advert.onclick = e => e.stopPropagation();
    const fits = h.nearby_n ? `${h.nearby_ok} of ${h.nearby_n}` : '—';
    const tr = h.failed
      ? el('tr', {tabindex: 0, 'data-id': h.run_id}, el('td', {}, when), el('td', {colspan: 6, style: 'color:var(--soft)'}, 'Not analysed — ' + (h.error || 'the link could not be read')), el('td', {}, el('span', {class: 'pill'}, 'not read')), el('td', {}, advert))
      : el('tr', {tabindex: 0, 'data-id': h.run_id}, el('td', {}, when), el('td', {}, h.title || '—'),
          el('td', {class: 'n'}, two(h.asking_mad)), el('td', {class: 'n'}, h.ask_m2 ? two(h.ask_m2) : '—'), el('td', {class: 'n ' + cls(h.video_profit_home)}, money(h.video_profit_home)),
          el('td', {class: 'n ' + cls(h.checked_profit_home)}, money(h.checked_profit_home)), el('td', {class: 'n'}, fits),
          el('td', {}, el('span', {class: 'pill ' + (h.verdict_label ? (h.verdict || '') : '')}, h.verdict_label ? h.verdict_label.toLowerCase() : 'old method — paste again')), el('td', {}, advert));
    const open = async () => { try { render(await api('/api/run?id=' + encodeURIComponent(h.run_id))); window.scrollTo({top: $('#result').offsetTop - 10, behavior: 'smooth'}); } catch (e) { fail(e.message); } };
    tr.onclick = open; tr.onkeydown = e => { if (e.key === 'Enter') open(); };
    tb.append(tr); }
  if (openLatest) { const first = rows.find(h => !h.failed) || rows[0]; render(await api('/api/run?id=' + encodeURIComponent(first.run_id))); }
}

const fail = msg => { const s = $('#status'); s.className = 'status err'; s.textContent = msg; };
$('#f').addEventListener('submit', async e => {
  e.preventDefault();
  const btn = $('#go'), s = $('#status'); btn.disabled = true; s.className = 'status';
  const t0 = Date.now();
  const tick = setInterval(async () => { if (!LIVE) { s.innerHTML = '<span class="dot"></span>Reading the advert, then the flats and Airbnbs around it… ' + Math.round((Date.now() - t0) / 1000) + 's'; return; }
    try { const p = await api('/api/progress'); if (p.msg) s.innerHTML = '<span class="dot"></span>' + esc(p.msg) + '…'; } catch (_) {} }, 700);
  s.innerHTML = '<span class="dot"></span>Starting…';
  try { const run = await api('/api/analyse', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({url: $('#url').value})});
    clearInterval(tick); s.textContent = 'Done.'; render(run); await loadHistory(false); mark(run); $('#url').value = ''; }
  catch (err) { fail(err.message); try { await loadHistory(false); } catch (_) {} }
  finally { clearInterval(tick); btn.disabled = false; }
});
(async () => {
  try { await loadProfile(); await loadHistory(true); } catch (e) { fail(e.message); }
  if (!$('#result').children.length) $('#result').append(el('div', {class: 'empty'}, 'Your first result will appear here: the video’s sum, the sum from the Airbnbs around the flat, and how it sits against your monthly limit.')); })();
