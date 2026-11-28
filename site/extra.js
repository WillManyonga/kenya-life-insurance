// Claims settlement and Registered insurers tabs. Reads data/claims.json and data/registry.json,
// built by kli.sitedata from IRA's claims settlement statistics and its register of insurers.
// Uses the shared chart helpers from lines.js (window.KLI.h) so the look matches the other tabs.
(function () {
  const $ = id => document.getElementById(id);
  const wait = f => (window.KLI && KLI.h ? f() : setTimeout(() => wait(f), 50));
  wait(() => {
    const H = KLI.h, { card, legend, lineChart, stack100, divColor } = H;
    const fmtK = v => v == null || !isFinite(v) ? 'n/a' : Math.abs(v) >= 1e6 ? (v / 1e6).toFixed(1) + 'm' : Math.abs(v) >= 1e3 ? Math.round(v / 1e3) + 'k' : String(Math.round(v));
    const fmtN = v => v == null || !isFinite(v) ? 'n/a' : Math.round(v).toLocaleString('en-GB');
    const pct = (v, d = 1) => v == null || !isFinite(v) ? 'n/a' : (v * 100).toFixed(d) + '%';
    const kshAmt = v => v == null ? 'n/a' : 'KSh ' + H.bn(v);   // amounts are KSh thousands, as in the accounts
    const qlab = p => `${p.slice(0, 4)} Q${p.slice(5)}`;
    const BUS = { long_term: 'Long-term (life) claims', general_liability: 'General: liability claims', general_non_liability: 'General: non-liability claims' };
    const MIN_OPEN = 50;   // an insurer is compared in a quarter only with at least 50 claims open

    // ================================================================ claims settlement
    let C = null, cState = { b: 'long_term', k: null, y: null, co: 'sanlam_life' };
    const mk = (b, u, f, k) => C.market[b]?.[u]?.[f]?.[k] ?? null;
    const sv = (s, b, u, f, k) => C.streams[s]?.[b]?.[u]?.[f]?.[k] ?? null;
    const nm = s => C.names[s] || s;
    const ratio = (p, a) => p != null && a ? p / a : null;
    function median(xs) { const a = xs.filter(v => v != null && isFinite(v)).sort((x, y) => x - y); if (!a.length) return null; const m = a.length >> 1; return a.length % 2 ? a[m] : (a[m - 1] + a[m]) / 2; }
    const insurersIn = (b, k) => Object.keys(C.streams).filter(s => (sv(s, b, 'number', 'a', k) || 0) >= MIN_OPEN);
    const medianRatio = (b, k) => median(insurersIn(b, k).map(s => ratio(sv(s, b, 'number', 'p', k), sv(s, b, 'number', 'a', k))));
    const yearKs = y => C.periods.map((p, i) => [p, i]).filter(([p]) => +p.slice(0, 4) === y).map(([, i]) => i);
    function pooled(s, b, ks, f = 'p') { // a year's claims paid over the year's open claims, quarter by quarter
      let n = 0, d = 0, any = false;
      ks.forEach(k => { const a = s ? sv(s, b, 'number', 'a', k) : mk(b, 'number', 'a', k), x = s ? sv(s, b, 'number', f, k) : mk(b, 'number', f, k); if (a && x != null) { n += x; d += a; any = true; } });
      return any && d ? n / d : null;
    }
    const declinedOf = (s, b, k) => { const g = f => (s ? sv(s, b, 'number', f, k) : mk(b, 'number', f, k)) || 0; return g('d') + g('dc'); };

    function drawClaims() {
      const g = $('settleGrid'), tiles = $('settleTiles'); g.innerHTML = ''; tiles.innerHTML = '';
      if (!C) { g.innerHTML = '<p class="note">The claims settlement data has not been built yet. It is added by the next data refresh.</p>'; return; }
      const { b } = cState, k = +cState.k, y = +cState.y, co = cState.co, P = C.periods, xs = P.map(qlab);
      const pm = ratio(mk(b, 'number', 'p', k), mk(b, 'number', 'a', k)), med = medianRatio(b, k);
      const pc = ratio(sv(co, b, 'number', 'p', k), sv(co, b, 'number', 'a', k));
      const out = mk(b, 'number', 'cl', k), paid = mk(b, 'number', 'p', k), outA = mk(b, 'amount', 'cl', k);
      const dec = ratio(declinedOf(null, b, k), mk(b, 'number', 'a', k));
      tiles.innerHTML = [
        [pct(pm), `Market payment ratio, ${qlab(P[k])}: claims paid ÷ claims open`],
        [pct(med), `Median insurer (insurers with ${MIN_OPEN}+ claims open)`],
        [pct(pc), `${nm(co)}${pc != null && med != null ? ` · ${pc >= med ? 'above' : 'below'} the median` : ''}`],
        [fmtN(out), `Claims still open at the end of the quarter${outA != null ? ` · ${kshAmt(outA)}` : ''}`],
        [paid ? (out / paid).toFixed(1) : 'n/a', 'Quarters to clear the queue at this quarter\'s pace'],
        [pct(dec), 'Share of open claims declined or closed as no claim'],
      ].map(([v, t]) => `<div class="tile"><b>${v}</b><span>${t}</span></div>`).join('');

      // 1. payment ratio over time
      const c1 = card(g, 'wide', `<h2>How much of what is claimed gets paid each quarter</h2>
        ${legend([[H.css('--series-1'), 'Market'], [H.css('--text-muted'), 'Median insurer'], [H.css('--series-2'), nm(co)]])}`);
      const s1 = document.createElementNS(H.NS, 'svg'); c1.appendChild(s1);
      lineChart(s1, xs, [
        { name: 'Market', values: P.map((_, i) => { const r = ratio(mk(b, 'number', 'p', i), mk(b, 'number', 'a', i)); return r == null ? null : r * 100; }), color: H.css('--series-1'), label: 'Market' },
        { name: 'Median insurer', values: P.map((_, i) => { const m = medianRatio(b, i); return m == null ? null : m * 100; }), color: H.css('--text-muted'), dash: '4 3', label: 'Median' },
        { name: nm(co), values: P.map((_, i) => { const r = ratio(sv(co, b, 'number', 'p', i), sv(co, b, 'number', 'a', i)); return r == null ? null : r * 100; }), color: H.css('--series-2'), label: H.short(nm(co)) },
      ], { w: 1150, h: 260, fmt: v => v == null || !isFinite(v) ? 'n/a' : v.toFixed(0) + '%', r: 120 });
      c1.insertAdjacentHTML('beforeend', `<p class="note">IRA's payment ratio: claims paid in the quarter ÷ claims open in the quarter (paid + declined + closed as no claim + still open at the end). Gaps are quarters IRA did not publish as a claims workbook (Q1–Q3 2021, Q1–Q2 2022).</p>`);

      // 2. the queue: new claims and claims still open (two charts, one scale each)
      const c2 = card(g, '', `<h2>Claims reported in the quarter</h2>`);
      const s2 = document.createElementNS(H.NS, 'svg'); c2.appendChild(s2);
      lineChart(s2, xs, [{ name: 'Reported', values: P.map((_, i) => mk(b, 'number', 'i', i)), color: H.css('--series-1'), label: '' }], { h: 200, fmt: fmtK, r: 20 });
      const c3 = card(g, '', `<h2>Claims still open at the end of the quarter</h2>`);
      const s3 = document.createElementNS(H.NS, 'svg'); c3.appendChild(s3);
      lineChart(s3, xs, [{ name: 'Open', values: P.map((_, i) => mk(b, 'number', 'cl', i)), color: H.css('--series-2'), label: '' }], { h: 200, fmt: fmtK, r: 20 });

      // 3. delays: the queue in quarters of payments
      const c4 = card(g, '', `<h2>Delays: quarters needed to clear the open claims</h2>${legend([[H.css('--series-1'), 'Market'], [H.css('--series-2'), nm(co)]])}`);
      const s4 = document.createElementNS(H.NS, 'svg'); c4.appendChild(s4);
      lineChart(s4, xs, [
        { name: 'Market', values: P.map((_, i) => { const p = mk(b, 'number', 'p', i); return p ? mk(b, 'number', 'cl', i) / p : null; }), color: H.css('--series-1'), label: 'Market' },
        { name: nm(co), values: P.map((_, i) => { const p = sv(co, b, 'number', 'p', i); return p ? sv(co, b, 'number', 'cl', i) / p : null; }), color: H.css('--series-2'), label: H.short(nm(co)) },
      ], { h: 200, fmt: v => v == null || !isFinite(v) ? 'n/a' : v.toFixed(2), r: 90 });
      c4.insertAdjacentHTML('beforeend', '<p class="note">Claims open at the quarter end ÷ claims paid in the quarter. IRA does not publish how long each claim has been open, so this is the best measure of delay its tables allow.</p>');

      // 4. amounts, from Q4 2022
      const hasAmt = P.some((_, i) => mk(b, 'amount', 'p', i) != null);
      const c5 = card(g, '', `<h2>Average claim paid, KSh</h2>`);
      if (hasAmt) {
        const s5 = document.createElementNS(H.NS, 'svg'); c5.appendChild(s5);
        lineChart(s5, xs, [
          { name: 'Market', values: P.map((_, i) => { const a = mk(b, 'amount', 'p', i), n = mk(b, 'number', 'p', i); return a != null && n ? a * 1000 / n : null; }), color: H.css('--series-1'), label: 'Market' },
          { name: nm(co), values: P.map((_, i) => { const a = sv(co, b, 'amount', 'p', i), n = sv(co, b, 'number', 'p', i); return a != null && n ? a * 1000 / n : null; }), color: H.css('--series-2'), label: H.short(nm(co)) },
        ], { h: 200, fmt: v => v == null || !isFinite(v) ? 'n/a' : (v >= 1e6 ? (v / 1e6).toFixed(1) + 'm' : Math.round(v / 1e3) + 'k'), r: 90 });
        c5.insertAdjacentHTML('beforeend', '<p class="note">Amount paid ÷ number of claims paid. IRA prints amounts from Q4 2022.</p>');
      } else c5.insertAdjacentHTML('beforeend', '<p class="note">IRA prints claim amounts from Q4 2022 only.</p>');

      // 5. every insurer's year, against the median (pooled over the year's quarters)
      const ks = yearKs(y).filter(kk => mk(b, 'number', 'a', kk) != null), all = Object.keys(C.streams).map(s => {
        const open = ks.reduce((a, kk) => a + (sv(s, b, 'number', 'a', kk) || 0), 0);
        return { s, r: pooled(s, b, ks), dec: (() => { let n = 0, d = 0; ks.forEach(kk => { const a = sv(s, b, 'number', 'a', kk); if (a) { n += declinedOf(s, b, kk); d += a; } }); return d ? n / d : null; })(),
          open, avg: open / Math.max(1, ks.filter(kk => sv(s, b, 'number', 'a', kk) != null).length), last: sv(s, b, 'number', 'cl', ks.at(-1)) };
      }).filter(x => x.r != null && x.avg >= MIN_OPEN).sort((a, b2) => b2.r - a.r);
      const medY = median(all.map(x => x.r)), mktY = pooled(null, b, ks);
      const c6 = card(g, 'wide', `<h2>Every insurer's payment ratio, ${y}</h2>
        ${legend([[H.css('--series-1'), 'At or above the median insurer'], [H.css('--series-2'), 'Below the median']])}`);
      const s6 = document.createElementNS(H.NS, 'svg'); c6.appendChild(s6);
      { const W = 1150, L = 290, R = 70, rowH = 22, T = 8, Hh = T + all.length * rowH + 26; s6.setAttribute('viewBox', `0 0 ${W} ${Hh}`);
        const x = v => L + v * (W - L - R);
        [0, .25, .5, .75, 1].forEach(v => { H.el('line', { x1: x(v), x2: x(v), y1: T, y2: Hh - 22, stroke: H.css('--grid') }, s6); H.el('text', { x: x(v), y: Hh - 6, 'text-anchor': 'middle' }, s6).textContent = (v * 100) + '%'; });
        if (medY != null) { H.el('line', { x1: x(medY), x2: x(medY), y1: T, y2: Hh - 22, stroke: H.css('--text-primary'), 'stroke-dasharray': '4 3' }, s6);
          H.el('text', { x: x(medY) + 4, y: T + 10 }, s6).textContent = `Median ${pct(medY)}`; }
        all.forEach((r, i) => {
          const yy = T + i * rowH, on = r.s === co, col = r.r >= medY ? H.css('--series-1') : H.css('--series-2');
          H.el('text', { x: L - 8, y: yy + 15, 'text-anchor': 'end', style: on ? `fill:${H.css('--text-primary')};font-weight:600` : '' }, s6).textContent = `${i + 1}. ${nm(r.s)}`;
          H.el('line', { x1: x(0), x2: x(Math.min(1, r.r)), y1: yy + 11, y2: yy + 11, stroke: col, 'stroke-opacity': on ? 1 : .45, 'stroke-width': 2 }, s6);
          const d = H.el('circle', { cx: x(Math.min(1, r.r)), cy: yy + 11, r: on ? 6 : 4.5, fill: col }, s6);
          d.onmousemove = e => H.tip(e, `<b>${nm(r.s)}</b><br>Paid ${pct(r.r)} of open claims in ${y}<br>Declined or closed as no claim ${pct(r.dec)}<br>Still open at ${qlab(P[ks.at(-1)])}: ${fmtN(r.last)}`); d.onmouseleave = H.untip;
          H.el('text', { x: W - 4, y: yy + 15, 'text-anchor': 'end', style: on ? `fill:${H.css('--text-primary')};font-weight:600` : '' }, s6).textContent = pct(r.r);
        });
      }
      c6.insertAdjacentHTML('beforeend', `<p class="note">${y}${ks.length < 4 ? ` (${ks.length} published quarter${ks.length > 1 ? 's' : ''})` : ''}: the year's claims paid ÷ the year's open claims, quarter by quarter. Market ${pct(mktY)}. Insurers with fewer than ${MIN_OPEN} claims open on average are left out. A low ratio can reflect a book of slow claims as much as slow payment.</p>
        <details class="tl"><summary>Table view</summary>${H.table(['Insurer', 'Payment ratio', 'Declined or closed', 'Claims open (sum of quarters)', `Still open at ${qlab(P[ks.at(-1)])}`],
          all.map(r => [nm(r.s), pct(r.r), pct(r.dec), fmtN(r.open), fmtN(r.last)]))}</details>`);

      // 6. where the open claims went, selected quarter
      const top = Object.keys(C.streams).filter(s => sv(s, b, 'number', 'a', k)).sort((a, b2) => sv(b2, b, 'number', 'a', k) - sv(a, b, 'number', 'a', k)).slice(0, 15);
      if (co && sv(co, b, 'number', 'a', k) && !top.includes(co)) top.push(co);
      const keys = ['p', 'd', 'c', 'cl'], cols = [H.css('--series-1'), H.css('--series-2'), H.css('--series-4'), H.css('--text-muted')], names = ['Paid', 'Declined', 'Closed as no claim', 'Still open'];
      const c7 = card(g, 'wide', `<h2>Where each insurer's open claims went, ${qlab(P[k])}</h2>${legend(names.map((n2, i) => [cols[i], n2]))}`);
      const s7 = document.createElementNS(H.NS, 'svg'); c7.appendChild(s7);
      const part = (s, f) => s ? sv(s, b, 'number', f, k) : mk(b, 'number', f, k);
      stack100(s7, [...top.map(s => ({ label: nm(s), bold: s === co, parts: { p: part(s, 'p'), d: (part(s, 'd') || 0) + (part(s, 'dc') || 0), c: part(s, 'c'), cl: part(s, 'cl') } })),
        { label: 'All insurers', bold: true, parts: { p: part(null, 'p'), d: (part(null, 'd') || 0) + (part(null, 'dc') || 0), c: part(null, 'c'), cl: part(null, 'cl') } }],
        keys, cols, { names, left: 290, fmt: v => fmtN(v) + ' claims' });
      c7.insertAdjacentHTML('beforeend', '<p class="note">The 15 insurers with the most claims open in the quarter. In 2017 IRA printed declined and closed claims as one figure; it is shown as declined.</p>');
      drawDeclined(g, b, k, y, co);
    }

    // ---------------------------------------------------------------- declined claims
    let dScope = 'market', dUnit = 'n';
    const RLAB = { not_covered: 'Loss not covered by the policy', lapsed: 'Lapsed policy', unpaid_premium: 'Unpaid premiums', non_disclosure: 'Non-disclosure',
      time_barred: 'Time barred', documents: 'Missing documents', other: 'Other' };
    function drawDeclined(g, b, k, y, co) {
      const P = C.periods, xs = P.map(qlab), dec = (s, kk, u = 'number') => { const f = x => s ? sv(s, b, u, x, kk) : mk(b, u, x, kk); const a = f('d'), c2 = f('dc'); return a == null && c2 == null ? null : (a || 0) + (c2 || 0); };
      g.insertAdjacentHTML('beforeend', `<div class="wide" style="grid-column:1/-1;margin:18px 0 -4px"><h2 style="font-size:17px;margin:0">Declined claims</h2>
        <p class="note" style="margin:4px 0 0">Claims an insurer refused to pay, as IRA prints them each quarter. Few claims are declined, so a handful of insurers move the market figure.</p></div>`);

      // 1. declines each quarter: the highlighted insurer against the rest of the market
      const c1 = card(g, '', `<h2>Claims declined each quarter</h2>${legend([[H.css('--series-2'), nm(co)], [H.css('--series-1'), 'Rest of the market']])}`);
      const s1 = document.createElementNS(H.NS, 'svg'); c1.appendChild(s1);
      { const W = 600, Hh = 230, L = 44, R = 8, T = 10, B = 24, tot = P.map((_, i) => dec(null, i)), mine = P.map((_, i) => dec(co, i) || 0);
        const yt = H.ticks(0, Math.max(...tot.filter(v => v != null), 1), 4), ymax = yt.at(-1), slot = (W - L - R) / P.length, bw = Math.max(3, slot * .62), yp = v => Hh - B - v / ymax * (Hh - T - B);
        s1.setAttribute('viewBox', `0 0 ${W} ${Hh}`);
        yt.forEach(v => { H.el('line', { x1: L, x2: W - R, y1: yp(v), y2: yp(v), stroke: H.css('--grid') }, s1); H.el('text', { x: L - 6, y: yp(v) + 4, 'text-anchor': 'end' }, s1).textContent = fmtK(v); });
        P.forEach((p, i) => {
          const x = L + i * slot + (slot - bw) / 2;
          if (p.endsWith('Q1') && (+p.slice(0, 4)) % 2 === 1) H.el('text', { x: x + bw / 2, y: Hh - 6, 'text-anchor': 'middle' }, s1).textContent = p.slice(0, 4);
          if (tot[i] == null) return;
          const rest = Math.max(0, tot[i] - mine[i]);
          const r1 = H.el('rect', { x, y: yp(rest), width: bw, height: Math.max(0, yp(0) - yp(rest)), fill: H.css('--series-1'), 'fill-opacity': .85 }, s1);
          const r2 = H.el('rect', { x, y: yp(tot[i]), width: bw, height: Math.max(0, yp(rest) - yp(tot[i]) - (mine[i] && rest ? 1 : 0)), fill: H.css('--series-2') }, s1);
          [r1, r2].forEach(r => { r.onmousemove = e => H.tip(e, `<b>${qlab(p)}</b><br>${fmtN(tot[i])} claims declined<br>${nm(co)}: ${fmtN(mine[i])} (${pct(tot[i] ? mine[i] / tot[i] : null, 0)})`); r.onmouseleave = H.untip; });
        });
      }

      // 2. decline rate
      const c2 = card(g, '', `<h2>Share of open claims declined</h2>${legend([[H.css('--series-1'), 'Market'], [H.css('--series-2'), nm(co)]])}`);
      const s2 = document.createElementNS(H.NS, 'svg'); c2.appendChild(s2);
      lineChart(s2, xs, [
        { name: 'Market', values: P.map((_, i) => { const a = mk(b, 'number', 'a', i), d = dec(null, i); return a && d != null ? d / a * 100 : null; }), color: H.css('--series-1'), label: 'Market' },
        { name: nm(co), values: P.map((_, i) => { const a = sv(co, b, 'number', 'a', i), d = dec(co, i); return a && d != null ? d / a * 100 : null; }), color: H.css('--series-2'), label: H.short(nm(co)) },
      ], { h: 200, fmt: v => v == null || !isFinite(v) ? 'n/a' : v.toFixed(v < 1 ? 2 : 1) + '%', r: 90 });

      // 3. who declines most in the chosen year
      const ks = yearKs(y).filter(kk => mk(b, 'number', 'a', kk) != null);
      const mTot = ks.reduce((a, kk) => a + (dec(null, kk) || 0), 0), mOpen = ks.reduce((a, kk) => a + (mk(b, 'number', 'a', kk) || 0), 0);
      const mAmt = ks.reduce((a, kk) => a + (dec(null, kk, 'amount') || 0), 0), hasAmt = ks.some(kk => dec(null, kk, 'amount') != null);
      const rows = Object.keys(C.streams).map(s => {
        const d = ks.reduce((a, kk) => a + (dec(s, kk) || 0), 0), open = ks.reduce((a, kk) => a + (sv(s, b, 'number', 'a', kk) || 0), 0), amt = ks.reduce((a, kk) => a + (dec(s, kk, 'amount') || 0), 0);
        return { s, d, open, amt };
      }).filter(r => r.d > 0).sort((a, b2) => b2.d - a.d);
      const c3 = card(g, 'wide tl', `<h2>Who declines most, ${y}</h2>` + H.table(['Insurer', 'Claims declined', 'Share of the market\'s declines', 'Share of its open claims declined', ...(hasAmt ? ['Amount declined'] : [])],
        [...rows.map(r => [r.s === co ? `<b>${nm(r.s)}</b>` : nm(r.s), fmtN(r.d), pct(mTot ? r.d / mTot : null), pct(r.open ? r.d / r.open : null, 2), ...(hasAmt ? [kshAmt(r.amt)] : [])]),
         ['<b>All insurers</b>', `<b>${fmtN(mTot)}</b>`, '100%', pct(mOpen ? mTot / mOpen : null, 2), ...(hasAmt ? [kshAmt(mAmt)] : [])]]));
      c3.insertAdjacentHTML('beforeend', `<p class="note">${y}${ks.length < 4 ? ` (${ks.length} published quarter${ks.length > 1 ? 's' : ''})` : ''}. Insurers that declined no claims are not listed. Amounts are printed from Q4 2022. Change the year with the filter above.</p>`);

      // 4. why claims are declined
      const RS = C.reasons;
      const c4 = card(g, 'wide', `<h2>Why claims are declined</h2>
        <div style="display:flex;gap:12px;flex-wrap:wrap;margin:4px 0 8px">
          <label style="max-width:240px">Show<select class="ds"><option value="market">All insurers</option><option value="co">${nm(co)}</option></select></label>
          <label style="max-width:200px">Measure<select class="du"><option value="n">Number of claims</option><option value="a">Amount (KSh)</option></select></label></div>
        <div class="dl"></div>`);
      c4.querySelector('.ds').value = dScope; c4.querySelector('.du').value = dUnit;
      const s4 = document.createElementNS(H.NS, 'svg'); c4.appendChild(s4); const nt = document.createElement('div'); c4.appendChild(nt);
      const drawR = () => {
        s4.innerHTML = ''; nt.innerHTML = '';
        if (!RS || !RS.periods.length) { nt.innerHTML = '<p class="note">IRA has not published reasons for declined long-term claims.</p>'; return; }
        const src = dScope === 'market' ? RS.market : (RS.streams[co] || {}), pers = RS.periods.filter(p => src[p] && src[p].total && src[p].total[0] > 0);
        const ui = dUnit === 'n' ? 0 : 1, cols = [H.css('--series-1'), H.css('--series-2'), H.css('--series-3'), H.css('--series-4')];
        c4.querySelector('.dl').innerHTML = pers.length ? legend(pers.map((p, i) => [cols[i % 4], `${qlab(p)}: ${dUnit === 'n' ? fmtN(src[p].total[0]) + ' claims' : 'KSh ' + H.bn(src[p].total[1] / 1000)}`])) : '';
        if (!pers.length) { nt.innerHTML = `<p class="note">${dScope === 'market' ? 'No reasons published.' : `IRA's reasons tables show no declined claims for ${nm(co)} in the quarters it published (Q1 2022 and Q2 2023).`}</p>`; return; }
        const keys = RS.keys.filter(x => x !== 'total'), W = 1150, L = 230, R = 60, T = 6, grp = 16 * pers.length + 12, Hh = T + keys.length * grp + 24;
        s4.setAttribute('viewBox', `0 0 ${W} ${Hh}`);
        const sh = (p, x) => { const t = src[p].total[ui]; return t ? (src[p][x] ? src[p][x][ui] : 0) / t : 0; };
        const mx = Math.max(.1, ...pers.flatMap(p => keys.map(x => sh(p, x)))), top = Math.min(1, Math.ceil(mx * 5) / 5 || .2), xp = v => L + v / top * (W - L - R);
        for (let v = 0; v <= top + 1e-9; v += top / 4) { H.el('line', { x1: xp(v), x2: xp(v), y1: T, y2: Hh - 22, stroke: H.css('--grid') }, s4); H.el('text', { x: xp(v), y: Hh - 6, 'text-anchor': 'middle' }, s4).textContent = Math.round(v * 100) + '%'; }
        keys.forEach((x, i) => {
          const y0 = T + i * grp;
          H.el('text', { x: L - 10, y: y0 + grp / 2 + 2, 'text-anchor': 'end', style: `fill:${H.css('--text-primary')}` }, s4).textContent = RLAB[x];
          pers.forEach((p, j) => {
            const v = sh(p, x), yy = y0 + 6 + j * 16, raw = src[p][x] ? src[p][x][ui] : 0;
            const r = H.el('rect', { x: L, y: yy, width: Math.max(1, xp(v) - L), height: 12, rx: 2, fill: cols[j % 4], 'fill-opacity': .9 }, s4);
            r.onmousemove = e => H.tip(e, `<b>${RLAB[x]}</b>, ${qlab(p)}<br>${pct(v, 0)} of claims declined${dUnit === 'n' ? ` · ${fmtN(raw)} claims` : ` · KSh ${H.bn(raw / 1000)}`}`); r.onmouseleave = H.untip;
            H.el('text', { x: xp(v) + 6, y: yy + 10 }, s4).textContent = pct(v, 0);
          });
        });
        nt.innerHTML = `<p class="note">Share of declined claims by the reason the insurer gave. IRA published reasons for long-term claims only for Q1 2022 (reprinted unchanged in its Q3 2022 to Q1 2023 workbooks) and Q2 2023; from Q3 2023 the table is an empty template. New quarters appear here automatically if IRA fills it in again. The reasons cover fewer claims than the declines in IRA's movement table (145 against 181 in Q2 2023), and in Q2 2023 Equity Life accounts for 85 of the 113 "not covered".</p>`;
      };
      c4.querySelector('.ds').onchange = e => { dScope = e.target.value; drawR(); };
      c4.querySelector('.du').onchange = e => { dUnit = e.target.value; drawR(); };
      drawR();
    }

    function initClaims() {
      const P = C.periods;
      $('cb').innerHTML = C.businesses.map(b => `<option value="${b}">${BUS[b] || b}</option>`).join('');
      const pub = new Set(C.published || P);
      $('cq').innerHTML = P.map((p, i) => pub.has(p) ? `<option value="${i}">${qlab(p)}</option>` : '').reverse().join('');
      const yrs = [...new Set(P.filter(p => pub.has(p)).map(p => +p.slice(0, 4)))];
      $('cy').innerHTML = yrs.map(y => `<option>${y}</option>`).reverse().join('');
      const full = yrs.filter(y => yearKs(y).filter(k => pub.has(P[k])).length === 4);
      cState.k = P.length - 1; cState.y = full.length ? full.at(-1) : yrs.at(-1);
      const ins = Object.keys(C.streams).sort((a, b) => nm(a).localeCompare(nm(b)));
      $('cco').innerHTML = ins.map(s => `<option value="${s}">${nm(s)}</option>`).join('');
      if (!C.streams[cState.co]) cState.co = ins[0];
      $('cb').value = cState.b; $('cq').value = cState.k; $('cy').value = cState.y; $('cco').value = cState.co;
      [['cb', 'b'], ['cq', 'k'], ['cy', 'y'], ['cco', 'co']].forEach(([id, key]) => $(id).onchange = e => { cState[key] = e.target.value; drawClaims(); });
    }

    // ================================================================ registered insurers
    let R = null, rState = { y: null, t: 'all', q: '' };
    const CLASS = { '31': 'Life assurance', '32': 'Annuities', '33a': 'Personal pension', '33b': 'Deposit administration', '34': 'Group life', '35': 'Group credit',
      '36': 'Permanent health', '37a': 'Unit-linked investments', '37b': 'Non-linked investments' };
    const classes = c => c ? c.split(', ').map(k => `<span title="${CLASS[k] || ''}">${k}</span>`).join(', ') : '';
    const TYPE = { long_term: 'Long-term', composite: 'Composite (long-term and general)', general: 'General', reinsurer: 'Reinsurer', microinsurer: 'Microinsurer', liaison_office: 'Liaison office' };
    function drawRegistry() {
      const g = $('regGrid'), tiles = $('regTiles'); g.innerHTML = ''; tiles.innerHTML = '';
      if (!R) { g.innerHTML = '<p class="note">The register has not been built yet.</p>'; return; }
      const y = +rState.y, yrs = R.years, prev = yrs.filter(v => v < y).at(-1), next = yrs.filter(v => v > y)[0];
      const of = yy => R.rows.filter(r => r.y === yy && (rState.t === 'all' || r.t === rState.t));
      const key = r => r.id || r.n.toLowerCase().replace(/\b(limited|ltd|company|co)\b\.?/g, '').replace(/[^a-z]/g, '');
      const cur = of(y), pk = new Set(prev ? of(prev).map(key) : []), nk = new Set(next ? of(next).map(key) : []);
      const isNew = r => prev && !pk.has(key(r)), leaves = r => next && !nk.has(key(r));
      const lt = cur.filter(r => r.t === 'long_term').length, cp = cur.filter(r => r.t === 'composite').length;
      const pr = R.printed[String(y)] || {};
      tiles.innerHTML = [
        [cur.length, `Life companies registered in ${y}${rState.t !== 'all' ? ` (${TYPE[rState.t]})` : ''}`],
        [lt, `Long-term insurers${pr.long_term != null ? ` · IRA's count ${pr.long_term}` : ''}`],
        [cp, `Composite insurers${pr.composite != null ? ` · IRA's count ${pr.composite}` : ''}`],
        [prev ? cur.filter(isNew).length : 'n/a', prev ? `New since ${prev}` : 'First year in the register'],
        [next ? cur.filter(leaves).length : 'n/a', next ? `Not listed in ${next}` : 'Latest year'],
      ].map(([v, t]) => `<div class="tile"><b>${v}</b><span>${t}</span></div>`).join('');

      // count by year
      const c1 = card(g, 'wide', `<h2>Registered life companies by year</h2>${legend([[H.css('--series-1'), 'Long-term'], [H.css('--series-3'), 'Composite']])}`);
      const s1 = document.createElementNS(H.NS, 'svg'); c1.appendChild(s1);
      { const W = 1150, Hh = 220, L = 40, Rm = 10, T = 16, B = 26, allY = [...new Set([...yrs, ...Object.keys(R.printed).map(Number)])].sort();
        const vals = allY.map(yy => { const rr = R.rows.filter(r => r.y === yy); return { y: yy, lt: rr.filter(r => r.t === 'long_term').length, cp: rr.filter(r => r.t === 'composite').length, have: rr.length > 0, pr: R.printed[String(yy)] }; });
        const max = Math.max(...vals.map(v => Math.max(v.lt + v.cp, (v.pr?.long_term || 0) + (v.pr?.composite || 0))), 1), yt = H.ticks(0, max, 4);
        s1.setAttribute('viewBox', `0 0 ${W} ${Hh}`); const slot = (W - L - Rm) / vals.length, bw = slot * .5, yp = v => Hh - B - v / yt.at(-1) * (Hh - T - B);
        yt.forEach(v => { H.el('line', { x1: L, x2: W - Rm, y1: yp(v), y2: yp(v), stroke: H.css('--grid') }, s1); H.el('text', { x: L - 6, y: yp(v) + 4, 'text-anchor': 'end' }, s1).textContent = v; });
        vals.forEach((v, i) => {
          const x = L + i * slot + (slot - bw) / 2, sel = v.y === y;
          H.el('text', { x: x + bw / 2, y: Hh - 8, 'text-anchor': 'middle', style: sel ? `fill:${H.css('--text-primary')};font-weight:600` : '' }, s1).textContent = v.y;
          if (!v.have) {
            const n = (v.pr?.long_term || 0) + (v.pr?.composite || 0);
            if (n) { H.el('rect', { x, y: yp(n), width: bw, height: yp(0) - yp(n), fill: 'none', stroke: H.css('--text-muted'), 'stroke-dasharray': '3 3', rx: 2 }, s1);
              H.el('text', { x: x + bw / 2, y: yp(n) - 5, 'text-anchor': 'middle' }, s1).textContent = `${n}*`; }
            return;
          }
          const r1 = H.el('rect', { x, y: yp(v.lt), width: bw, height: yp(0) - yp(v.lt), fill: H.css('--series-1'), 'fill-opacity': sel ? 1 : .7, rx: 2 }, s1);
          const r2 = H.el('rect', { x, y: yp(v.lt + v.cp), width: bw, height: Math.max(0, yp(v.lt) - yp(v.lt + v.cp) - 2), fill: H.css('--series-3'), 'fill-opacity': sel ? 1 : .7, rx: 2 }, s1);
          [r1, r2].forEach(r => { r.onmousemove = e => H.tip(e, `<b>${v.y}</b><br>Long-term ${v.lt}${v.pr?.long_term != null ? ` (IRA's count ${v.pr.long_term})` : ''}<br>Composite ${v.cp}${v.pr?.composite != null ? ` (IRA's count ${v.pr.composite})` : ''}`); r.onmouseleave = H.untip; r.style.cursor = 'pointer'; r.onclick = () => { rState.y = v.y; $('ry').value = v.y; drawRegistry(); }; });
          H.el('text', { x: x + bw / 2, y: yp(v.lt + v.cp) - 5, 'text-anchor': 'middle', style: `fill:${H.css('--text-primary')}` }, s1).textContent = v.lt + v.cp;
        });
      }
      c1.insertAdjacentHTML('beforeend', `<p class="note">From the directory of insurers in each IRA annual report, and IRA's licence lists from 2025. * IRA published no list for that year; the dashed bar is its printed count. Click a bar to open that year.</p>`);

      // the list for the year
      const q = rState.q.toLowerCase(), rows = cur.filter(r => !q || r.n.toLowerCase().includes(q)).sort((a, b) => a.n.localeCompare(b.n));
      const status = r => isNew(r) ? `<span class="delta-good">New since ${prev}</span>` : leaves(r) ? `<span class="delta-bad">Not listed in ${next}</span>` : '';
      const c2 = card(g, 'wide tl', `<h2>Life companies registered in ${y}</h2>` +
        H.table(['Company', 'Type', 'In the explorer as', 'Change', ...(rows.some(r => r.c) ? ['Authorised classes'] : [])],
          rows.map(r => [r.n, TYPE[r.t] || r.t, r.id ? (R.names[r.id] || r.id) : '<span class="note">not matched</span>', status(r), ...(rows.some(x => x.c) ? [classes(r.c)] : [])])));
      c2.insertAdjacentHTML('beforeend', `<p class="note">Source: ${[...new Set(cur.map(r => r.src))].join('; ')}. A company is matched to the explorer by the same name rules as the accounts, so renamed companies appear under their current name.${rows.some(x => x.c) ? ' Classes (from the licence lists): ' + Object.entries(CLASS).map(([k, v]) => `${k} ${v.toLowerCase()}`).join(', ') + '.' : ''}</p>`);

      // who joined and left, every year
      const ch = [];
      yrs.forEach((yy, i) => { if (!i) return; const a = R.rows.filter(r => r.y === yrs[i - 1]), b2 = R.rows.filter(r => r.y === yy), ak = new Set(a.map(key)), bk = new Set(b2.map(key));
        ch.push([`${yrs[i - 1]} → ${yy}`, b2.filter(r => !ak.has(key(r))).map(r => r.n).join('; ') || '–', a.filter(r => !bk.has(key(r))).map(r => r.n).join('; ') || '–']); });
      card(g, 'wide tl', `<h2>Entries and exits between published years</h2>` + H.table(['Years', 'Listed for the first time', 'No longer listed'], ch) +
        '<p class="note">Name changes appear as one entry and one exit when the new name does not match the explorer\'s name rules. 2019 has no published list.</p>');
    }
    function initRegistry() {
      $('ry').innerHTML = R.years.map(y => `<option>${y}</option>`).reverse().join('');
      rState.y = R.years.at(-1); $('ry').value = rState.y;
      $('ry').onchange = e => { rState.y = e.target.value; drawRegistry(); };
      $('rt').onchange = e => { rState.t = e.target.value; drawRegistry(); };
      $('rq').oninput = e => { rState.q = e.target.value; drawRegistry(); };
    }

    Promise.all([fetch('data/claims.json').then(r => r.ok ? r.json() : null).catch(() => null),
                 fetch('data/registry.json').then(r => r.ok ? r.json() : null).catch(() => null)]).then(([c, r]) => {
      C = c; R = r;
      if (C) initClaims();
      if (R) initRegistry();
      KLI.addTab('settlement', drawClaims);
      KLI.addTab('registry', drawRegistry);
    });
  });
})();
