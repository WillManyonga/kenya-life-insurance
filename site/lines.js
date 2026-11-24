// Business-line dashboards: claims ratios, market share, business mix, insurer profile.
// Reads data/lines.json (built by src/kli/dashboard.py). Every ratio is a sum over a sum,
// never an average of ratios. Figures are IRA's year-to-date, unaudited, KSh thousands.
(function () {
  let L, P = [], LINES = [], INS = [], ready = false;
  const DEFAULT_CO = 'sanlam_life';
  const MEASURE = {
    lr: { label: 'Loss ratio (claims ÷ net premium)', num: ['cl'], den: 'np', lowerIsBetter: true },
    po: { label: 'Paid out per KSh 100 gross premium', num: ['tb'], den: 'gp', lowerIsBetter: true },
    cr: { label: 'Cost to run per KSh 100 gross premium', num: ['co', 'me'], den: 'gp', lowerIsBetter: true },
  };
  const SERIES = n => css(`--series-${(n % 8) + 1}`);
  const lineColor = id => SERIES(LINES.findIndex(l => l.id === id));
  const short = window.short || (n => n);

  // ---------- data access ----------
  const val = (s, line, m, k) => { const a = L.streams[s].lines[line]?.[m]; return a ? a[k] : null; };
  const filed = (s, k) => !L.streams[s].not_filed.includes(k) && !(L.streams[s].suspect || []).includes(k);
  const gp = (s, line, k) => val(s, line, 'gp', k);
  function sum(line, m, k, only) {
    let t = 0, any = false;
    for (const s of only || INS) { if (!filed(s, k)) continue; const v = val(s, line, m, k); if (v != null) { t += v; any = true; } }
    return any ? t : null;
  }
  // For risk lines the loss ratio counts claims; for savings lines (and the total) the benefits paid
  // are mostly annuities, maturities and surrenders, so the loss ratio counts all benefits.
  const SAVINGS = new Set(['annuities', 'pensions', 'investments', 'total']);
  const MIN = 50000; // KSh 50m (figures are in thousands): below this a company's ratio is not shown
  function ratioOf(getter, mkey, line, minDen = 0) {
    const M = MEASURE[mkey]; const d = getter(M.den); if (!d || d <= minDen) return null;
    const num = mkey === 'lr' && SAVINGS.has(line) ? ['tb'] : M.num;
    return num.reduce((a, m) => a + (getter(m) || 0), 0) / d;
  }
  const mRatio = (line, k, mk) => ratioOf(m => sum(line, m, k), mk, line);
  const sRatio = (s, line, k, mk) => filed(s, k) ? ratioOf(m => val(s, line, m, k), mk, line, MIN) : null;
  const q4 = y => P.indexOf(`${y}Q4`);
  const fullYears = () => [...new Set(P.filter(p => p.endsWith('Q4')).map(p => +p.slice(0, 4)))];
  function cumulative(line, mk, y0, y1, s) {
    const ks = fullYears().filter(y => y >= y0 && y <= y1).map(q4);
    return ratioOf(m => ks.reduce((a, k) => a + ((s ? (filed(s, k) ? val(s, line, m, k) : 0) : sum(line, m, k)) || 0), 0), mk, line, s ? MIN : 0);
  }
  const sameLastYear = k => { const [y, q] = P[k].split('Q'); return P.indexOf(`${+y - 1}Q${q}`); };
  const share = (s, line, k) => { const t = sum(line, 'gp', k); const v = filed(s, k) ? gp(s, line, k) : null; return t && v != null ? v / t : null; };
  function ranked(line, k) { return INS.filter(s => filed(s, k) && (gp(s, line, k) || 0) > 0).sort((a, b) => gp(b, line, k) - gp(a, line, k)); }
  const name = s => L.streams[s].name;
  const label = p => p.endsWith('Q4') ? p.slice(0, 4) : `${p.slice(0, 4)} ${['', 'Q1', 'H1', '9M', ''][+p.slice(5)]}`;
  const bn = v => v == null ? 'n/a' : v >= 1e6 ? (v / 1e6).toFixed(v >= 1e7 ? 1 : 2) + 'bn' : (v / 1e3).toFixed(0) + 'm';
  const per100 = v => v == null || !isFinite(v) ? 'n/a' : (v * 100).toFixed(1);
  const pp = v => v == null || !isFinite(v) ? 'n/a' : (v >= 0 ? '+' : '') + (v * 100).toFixed(1) + '%';

  // ---------- small chart helpers ----------
  function lineChart(svg, xs, series, opt = {}) {
    svg.innerHTML = ''; const W = opt.w || 640, H = opt.h || 240, Lm = 40, R = opt.r || 70, T = 12, B = 26;
    svg.setAttribute('viewBox', `0 0 ${W} ${H}`);
    const all = series.flatMap(s => s.values).filter(v => v != null && isFinite(v));
    if (!all.length) { el('text', { x: W / 2, y: H / 2, 'text-anchor': 'middle' }, svg).textContent = 'No data'; return; }
    const yt = ticks(Math.min(0, ...all), Math.max(...all), 4), xp = i => Lm + (xs.length < 2 ? 0 : i / (xs.length - 1)) * (W - Lm - R);
    const yp = v => H - B - (v - yt[0]) / (yt.at(-1) - yt[0]) * (H - T - B);
    yt.forEach(v => { el('line', { x1: Lm, x2: W - R, y1: yp(v), y2: yp(v), stroke: css('--grid') }, svg); el('text', { x: Lm - 6, y: yp(v) + 4, 'text-anchor': 'end' }, svg).textContent = opt.fmt ? opt.fmt(v) : v; });
    const every = Math.ceil(xs.length / 10);
    xs.forEach((x, i) => { if (i % every === 0 || i === xs.length - 1) el('text', { x: xp(i), y: H - 8, 'text-anchor': 'middle' }, svg).textContent = x; });
    series.forEach(s => {
      let d = '', pen = false;
      s.values.forEach((v, i) => { if (v == null || !isFinite(v)) { pen = false; return; } d += (pen ? 'L' : 'M') + xp(i) + ' ' + yp(v); pen = true; });
      el('path', { d, fill: 'none', stroke: s.color, 'stroke-width': s.width || 2, 'stroke-dasharray': s.dash || '', 'stroke-linejoin': 'round' }, svg);
    });
    // end labels, nudged apart so they never overlap
    const ends = series.map(s => { const last = s.values.reduce((a, v, i) => v != null && isFinite(v) ? i : a, -1); return last < 0 || !s.label ? null : { s, x: xp(last) + 6, y: yp(s.values[last]) + 4 }; })
      .filter(Boolean).sort((a, b) => a.y - b.y);
    for (let i = 1; i < ends.length; i++) if (ends[i].y - ends[i - 1].y < 13) ends[i].y = ends[i - 1].y + 13;
    ends.forEach(e => { el('text', { x: e.x, y: e.y, style: `fill:${css('--text-primary')}` }, svg).textContent = e.s.label; });
    // hover: one hit column per x
    xs.forEach((x, i) => {
      const r = el('rect', { x: xp(i) - (W - Lm - R) / xs.length / 2, y: T, width: (W - Lm - R) / Math.max(1, xs.length - 1), height: H - T - B, fill: 'transparent' }, svg);
      r.onmousemove = e => tip(e, `<b>${x}</b><br>` + series.map(s => `<i class="sw" style="background:${s.color}"></i>${s.name}: ${opt.fmt ? opt.fmt(s.values[i]) : s.values[i]}`).join('<br>'));
      r.onmouseleave = untip;
    });
  }
  function stack100(svg, rows, keys, colors, opt = {}) {
    // rows: [{label, parts:{key:value}}] -> horizontal 100% bars
    svg.innerHTML = ''; const W = 1150, Lm = opt.left || 170, R = 10, rowH = 26, T = 4, H = T + rows.length * rowH + 22;
    svg.setAttribute('viewBox', `0 0 ${W} ${H}`); const x = f => Lm + f * (W - Lm - R);
    [0, .25, .5, .75, 1].forEach(f => { el('text', { x: x(f), y: H - 6, 'text-anchor': 'middle' }, svg).textContent = (f * 100) + '%'; });
    rows.forEach((r, i) => {
      const y = T + i * rowH, tot = keys.reduce((a, k) => a + Math.max(0, r.parts[k] || 0), 0);
      el('text', { x: Lm - 8, y: y + 15, 'text-anchor': 'end', style: `fill:${css('--text-primary')};${r.bold ? 'font-weight:600' : ''}` }, svg).textContent = r.label.length > 34 ? r.label.slice(0, 33) + '…' : r.label;
      let acc = 0; if (!tot) return;
      keys.forEach((k, j) => {
        const f = Math.max(0, r.parts[k] || 0) / tot; if (!f) return;
        const b = el('rect', { x: x(acc) + 1, y: y + 3, width: Math.max(0, x(acc + f) - x(acc) - 2), height: rowH - 8, fill: colors[j], rx: 2 }, svg);
        b.onmousemove = e => tip(e, `<b>${r.label}</b><br>${opt.names[j]}: ${(f * 100).toFixed(1)}% (KSh ${bn(r.parts[k])})`); b.onmouseleave = untip;
        if (f > .07) el('text', { x: x(acc + f / 2), y: y + 15.5, 'text-anchor': 'middle', style: `fill:${j === 3 ? '#0b0b0b' : '#fff'};font-size:10px` }, svg).textContent = Math.round(f * 100) + '%';
        acc += f;
      });
    });
  }
  function divColor(diff, lowerIsBetter) {
    // blue = better than market, red = worse; grey at par; saturates at 25 points
    if (diff == null) return 'transparent';
    const good = lowerIsBetter ? diff < 0 : diff > 0, t = Math.min(1, Math.abs(diff) / .25);
    const a = hex(css('--div-mid')), b = hex(good ? css('--series-1') : css('--series-8'));
    return `rgb(${a.map((c, i) => Math.round(c + (b[i] - c) * t)).join(',')})`;
  }
  const hex = h => [1, 3, 5].map(i => parseInt(h.slice(i, i + 2), 16));
  const card = (grid, cls, html) => { const d = document.createElement('div'); d.className = 'card ' + (cls || ''); d.innerHTML = html; grid.appendChild(d); return d; };
  const legend = items => `<div class="legend">${items.map(([c, t]) => `<span><i class="sw" style="background:${c}"></i>${t}</span>`).join('')}</div>`;

  // ---------- state ----------
  const st = () => ({ k: +$('lp').value, y0: +$('ly0').value, y1: +$('ly1').value, co: $('lco').value, mk: $('lm').value });

  // ---------- Claims by business line ----------
  function drawClaims() {
    const { k, y0, y1, co, mk } = st(), M = MEASURE[mk], g = $('claimsGrid'); g.innerHTML = '';
    const yrs = fullYears().filter(y => y >= y0 && y <= y1), ks = yrs.map(q4);
    const head = card(g, 'wide', `<h2>${M.label}: market by business line, ${yrs[0]}–${yrs.at(-1)}</h2>
      <p class="note">Each panel: the market (blue) and ${short(name(co))} (orange, dashed), full-year figures. The cumulative figure is total claims over total premium across the whole window, so large years weigh more. Claims as IRA prints them look net of reinsurance (group life claims are about a third of gross premium but two thirds of net), so the loss ratio uses net premium. For annuities, pensions, investments and the total, the loss ratio counts all benefits paid (annuities, maturities, surrenders, bonuses). A company's ratio is not shown where its premium in the line is under KSh 50m.</p>
      <div class="mini" id="cMinis"></div>`);
    const minis = head.querySelector('#cMinis');
    LINES.forEach(l => {
      const box = document.createElement('div'); minis.appendChild(box);
      const cm = cumulative(l.id, mk, y0, y1), cs = cumulative(l.id, mk, y0, y1, co);
      box.innerHTML = `<h2 style="font-size:13px">${l.label}</h2><p class="note" style="margin:0">Cumulative: market <b>${per100(cm)}</b> · ${short(name(co))} <b>${per100(cs)}</b> · ${label(P[k])} snapshot: market <b>${per100(mRatio(l.id, k, mk))}</b></p>`;
      const svg = document.createElementNS(NS, 'svg'); box.appendChild(svg);
      lineChart(svg, yrs.map(String), [
        { name: 'Market', values: ks.map(kk => { const v = mRatio(l.id, kk, mk); return v == null ? null : v * 100; }), color: css('--series-1'), label: 'Market' },
        { name: short(name(co)), values: ks.map(kk => { const r = sRatio(co, l.id, kk, mk); return r == null ? null : r * 100; }), color: css('--series-2'), dash: '5 3', label: short(name(co)).split(' ')[0] },
      ], { w: 380, h: 210, fmt: v => v == null || !isFinite(v) ? 'n/a' : v.toFixed(0), r: 64 });
    });

    // lollipop panels: the 12 biggest writers of each line, as in Kwanusu's motor/medical view
    const LIM = mk === 'cr' ? 80 : 150;
    let overAll = [];
    const panels = LINES.filter(l => l.id !== 'total').map(l => {
      const m = mRatio(l.id, k, mk), writers = ranked(l.id, k).filter(s => (gp(s, l.id, k) || 0) >= MIN);
      const top = writers.slice(0, 12); if (!top.includes(co) && writers.includes(co)) top.push(co);
      const vals = top.map(s => sRatio(s, l.id, k, mk) * 100).filter(v => isFinite(v));
      const max = Math.max(LIM, Math.min(250, Math.ceil(Math.max(0, ...vals) / 50) * 50));
      const x = v => Math.max(0, Math.min(100, v / max * 100));
      const rows = top.map(s => {
        const r = sRatio(s, l.id, k, mk), v = r == null ? null : r * 100, over = v != null && v > 100;
        if (over) overAll.push(`${short(name(s))} (${l.label.toLowerCase()}, ${v.toFixed(0)})`);
        const label = v == null ? '' : `<span class="v" style="left:calc(${x(v)}% + ${v > max * .85 ? '-44px' : '9px'});${over ? 'color:var(--bad-ink)' : ''}">${v > max ? '›' : ''}${v.toFixed(1)}</span>`;
        return `<div class="lrow" title="${name(s)}: ${per100(r)} per KSh 100; premium KSh ${bn(gp(s, l.id, k))}"><span class="nm" style="${s === co ? 'color:var(--series-2)' : ''}">${short(name(s))}</span><span class="wr">${bn(gp(s, l.id, k))}</span>
          <span class="track"><span class="mk" style="left:${x(m * 100)}%"></span>${mk !== 'cr' ? `<span class="ref" style="left:${x(100)}%"></span>` : ''}${v == null ? '' : `<span class="stem" style="width:${x(v)}%"></span><span class="dot${over && mk !== 'cr' ? ' over' : ''}" style="left:${x(v)}%"></span>${label}`}</span></div>`;
      }).join('');
      const ticksH = [0, 50, 100, 150, 200, 250].filter(t => t <= max).map(t => `<span style="left:${x(t)}%">${t}</span>`).join('');
      return `<div class="lp"><h3>${l.label}</h3><p class="avg">Market ${per100(m)} · ${writers.length} insurers write it</p>
        <div class="lrow"><span class="nm" style="font-weight:400;color:var(--text-muted)">Insurer</span><span class="wr">Written</span><span class="axis">${ticksH}</span></div>${rows}</div>`;
    }).join('');
    const lc = card(g, 'wide', '');
    const headline = mk === 'cr' ? `Cost to run per KSh 100 of gross premium, ${label(P[k])}` :
      overAll.length ? `Benefits outran premiums at ${overAll.length} of the biggest writers, ${label(P[k])}` : `No big writer paid out more than its premium, ${label(P[k])}`;
    lc.innerHTML = `<h2>${headline}</h2><p class="note">${M.label} for the 12 biggest writers of each line by gross premium (plus ${short(name(co))}, in orange, if outside them). ${overAll.length && mk !== 'cr' ? 'Above 100: ' + overAll.slice(0, 6).join('; ') + (overAll.length > 6 ? '…' : '') + '.' : ''}</p>
      ${legend([[css('--series-7'), 'Ratio per KSh 100'], [css('--series-8'), 'Above 100: more paid out than premium']])}<p class="note" style="margin:0 0 10px">Solid line: 100. Dashed line: the market average for the line. Grey figure: the insurer's gross premium in the line. Insurers writing under KSh 50m in a line are left out.</p><div class="lolli">${panels}</div>`;

    // snapshot + cumulative table
    const ly = sameLastYear(k);
    const rows = LINES.map(l => [l.label, bn(sum(l.id, 'gp', k)), per100(mRatio(l.id, k, mk)), ly >= 0 ? per100(mRatio(l.id, ly, mk)) : 'n/a',
      per100(cumulative(l.id, mk, y0, y1)), per100(sRatio(co, l.id, k, mk)), per100(cumulative(l.id, mk, y0, y1, co))]);
    card(g, 'wide', `<h2>Snapshot ${label(P[k])} and cumulative ${y0}–${y1}</h2><p class="note">${M.label}, per KSh 100. Snapshot periods are year to date.</p>` +
      table(['Business line', `Market premium ${label(P[k])} (KSh)`, `Market ${label(P[k])}`, ly >= 0 ? `Market ${label(P[ly])}` : 'Last year', `Market cumulative`, `${short(name(co))} ${label(P[k])}`, `${short(name(co))} cumulative`], rows));

    // heatmap insurers x lines
    const top = ranked('total', k).slice(0, 18);
    const hdr = ['Insurer', ...LINES.map(l => l.label)];
    const body = top.map(s => {
      const cells = LINES.map(l => {
        const p = gp(s, l.id, k) || 0, r = p >= 50000 ? sRatio(s, l.id, k, mk) : null, m = mRatio(l.id, k, mk);
        const bg = divColor(r == null || m == null ? null : r - m, M.lowerIsBetter);
        const strong = r != null && m != null && Math.abs(r - m) > .15;
        return `<td style="background:${bg};${strong ? 'color:#fff' : ''}" title="${name(s)} · ${l.label}: ${per100(r)} vs market ${per100(m)} (premium KSh ${bn(p)})">${r == null ? '·' : per100(r)}</td>`;
      }).join('');
      return `<tr class="${s === co ? 'hl' : ''}"><td>${name(s)}</td>${cells}</tr>`;
    }).join('');
    const mrow = `<tr class="hl"><td>Market (all ${ranked('total', k).length} insurers)</td>${LINES.map(l => `<td>${per100(mRatio(l.id, k, mk))}</td>`).join('')}</tr>`;
    card(g, 'wide', `<h2>Who runs better or worse than the market, ${label(P[k])}</h2>
      <p class="note">${M.label}, per KSh 100. Blue: better than the market in that line; red: worse; grey: close to the market. A dot means the insurer wrote less than KSh 50m in the line, too little for a meaningful ratio. Insurers ranked by total premium.</p>
      <table class="heat"><tr>${hdr.map(h => `<th>${h}</th>`).join('')}</tr>${body}${mrow}</table>`);
  }

  // ---------- Market share ----------
  function drawShare() {
    const { k, y0, y1, co } = st(), g = $('shareGrid'); g.innerHTML = '';
    const yrs = fullYears().filter(y => y >= y0 && y <= y1), ks = yrs.map(q4);
    const latestPeers = ranked('total', k).filter(s => s !== co).slice(0, 5);
    const c1 = card(g, 'wide', `<h2>Market share of gross premium, ${yrs[0]}–${yrs.at(-1)}</h2>
      <p class="note">${short(name(co))} against the five largest insurers in ${label(P[k])}. Full-year gross premium; change the highlighted insurer above.</p>`);
    const svg = document.createElementNS(NS, 'svg'); c1.appendChild(svg);
    const ser = [co, ...latestPeers].map((s, i) => ({ name: short(name(s)), label: short(name(s)), color: SERIES(i), width: i === 0 ? 3 : 1.5, dash: i === 0 ? '' : '',
      values: ks.map(kk => { const v = share(s, 'total', kk); return v == null ? null : v * 100; }) }));
    lineChart(svg, yrs.map(String), ser, { w: 1100, h: 340, fmt: v => v == null || !isFinite(v) ? 'n/a' : v.toFixed(1) + '%', r: 120 });

    // share and rank table across years
    const all = ranked('total', k);
    const rows = all.slice(0, 20).concat(all.includes(co) && all.indexOf(co) >= 20 ? [co] : []).map(s => {
      const cells = ks.map(kk => { const r = ranked('total', kk), sh = share(s, 'total', kk); return sh == null || sh === 0 ? '–' : `${(sh * 100).toFixed(1)}% <span class="note">#${r.indexOf(s) + 1}</span>`; });
      const a = share(s, 'total', ks[0]), b = share(s, 'total', ks.at(-1));
      const ch = a != null && b != null ? (b - a) * 100 : null;
      return `<tr class="${s === co ? 'hl' : ''}"><td>${name(s)}</td>${cells.map(c => `<td>${c}</td>`).join('')}<td class="${ch > 0 ? 'delta-good' : ch < 0 ? 'delta-bad' : ''}">${ch == null ? '–' : (ch > 0 ? '+' : '') + ch.toFixed(1) + ' pts'}</td><td>${(share(s, 'total', k) * 100 || 0).toFixed(1)}%</td></tr>`;
    }).join('');
    card(g, 'wide', `<h2>Share and rank by year</h2><p class="note">Share of insurers' gross premium (life reinsurers excluded); # is the rank that year. Ordered by ${label(P[k])} premium.</p>
      <table><tr><th>Insurer</th>${yrs.map(y => `<th>${y}</th>`).join('')}<th>Change</th><th>${label(P[k])}</th></tr>${rows}</table>`);

    // highlighted insurer's share by business line over time
    const lines = LINES.filter(l => l.id !== 'total');
    const c3 = card(g, '', `<h2>${short(name(co))}: share of each business line</h2><p class="note">Share of the market's premium in each line, full years.</p>${legend(lines.map(l => [lineColor(l.id), l.label]))}`);
    const s3 = document.createElementNS(NS, 'svg'); c3.appendChild(s3);
    lineChart(s3, yrs.map(String), lines.map(l => ({ name: l.label, color: lineColor(l.id), values: ks.map(kk => { const v = share(co, l.id, kk); return v == null ? null : v * 100; }) })), { h: 260, fmt: v => v == null || !isFinite(v) ? 'n/a' : v.toFixed(1) + '%', r: 20 });

    // movers: biggest share gains and losses over the window
    const mv = INS.map(s => { const a = share(s, 'total', ks[0]), b = share(s, 'total', ks.at(-1)); return { s, d: a != null && b != null ? b - a : null }; }).filter(x => x.d != null).sort((a, b) => b.d - a.d);
    card(g, '', `<h2>Biggest share movers, ${yrs[0]}–${yrs.at(-1)}</h2>` +
      table(['Insurer', `${yrs[0]}`, `${yrs.at(-1)}`, 'Change'], [...mv.slice(0, 5), ...mv.slice(-5)].map(x => [name(x.s), (share(x.s, 'total', ks[0]) * 100).toFixed(1) + '%', (share(x.s, 'total', ks.at(-1)) * 100).toFixed(1) + '%',
        `<span class="${x.d > 0 ? 'delta-good' : 'delta-bad'}">${x.d > 0 ? '+' : ''}${(x.d * 100).toFixed(1)} pts</span>`])));
  }

  // ---------- Business mix ----------
  function drawMix() {
    const { k, y0, y1, co } = st(), g = $('mixGrid'); g.innerHTML = '';
    const lines = LINES.filter(l => l.id !== 'total'), keys = lines.map(l => l.id), cols = lines.map(l => lineColor(l.id)), names = lines.map(l => l.label);
    const yrs = fullYears().filter(y => y >= y0 && y <= y1);
    const periods = [...yrs.map(q4), k].filter((v, i, a) => a.indexOf(v) === i);
    const c1 = card(g, 'wide', `<h2>Share of market premium by business type</h2><p class="note">Each bar is one year's gross premium split by line (latest bar is ${label(P[k])} year to date).</p>${legend(lines.map(l => [lineColor(l.id), l.label]))}`);
    const s1 = document.createElementNS(NS, 'svg'); c1.appendChild(s1);
    stack100(s1, periods.map(kk => ({ label: `${label(P[kk])} · KSh ${bn(sum('total', 'gp', kk))}`, parts: Object.fromEntries(keys.map(id => [id, sum(id, 'gp', kk)])) })), keys, cols, { names, left: 170 });

    const top = ranked('total', k).slice(0, 15); if (!top.includes(co) && ranked('total', k).includes(co)) top.push(co);
    const c2 = card(g, 'wide', `<h2>What the largest insurers write, ${label(P[k])}</h2><p class="note">Each insurer's premium split by business line, ordered by total premium.</p>${legend(lines.map(l => [lineColor(l.id), l.label]))}`);
    const s2 = document.createElementNS(NS, 'svg'); c2.appendChild(s2);
    stack100(s2, [...top.map(s => ({ label: `${ranked('total', k).indexOf(s) + 1}. ${name(s)}`, bold: s === co, parts: Object.fromEntries(keys.map(id => [id, filed(s, k) ? gp(s, id, k) : 0])) })),
      { label: 'All insurers', bold: true, parts: Object.fromEntries(keys.map(id => [id, sum(id, 'gp', k)])) }], keys, cols, { names, left: 260 });

    const ks = yrs.map(q4), n = yrs.length - 1;
    card(g, 'wide', `<h2>Premium by business line, KSh</h2>` + table(['Business line', ...yrs.map(String), `CAGR ${yrs[0]}–${yrs.at(-1)}`],
      LINES.map(l => { const a = sum(l.id, 'gp', ks[0]), b = sum(l.id, 'gp', ks.at(-1)); return [l.label, ...ks.map(kk => bn(sum(l.id, 'gp', kk))), a > 0 && b > 0 && n > 0 ? pp(Math.pow(b / a, 1 / n) - 1) : 'n/a']; })));
  }

  // ---------- Insurer profile ----------
  function drawProfile() {
    const { k, co, mk } = st(), g = $('profileGrid'), ly = sameLastYear(k); g.innerHTML = '';
    const r = ranked('total', k), rank = r.indexOf(co) + 1, prem = filed(co, k) ? gp(co, 'total', k) : null, prev = ly >= 0 ? gp(co, 'total', ly) : null;
    const po = sRatio(co, 'total', k, 'po'), cr = sRatio(co, 'total', k, 'cr'), lr = sRatio(co, 'total', k, 'lr');
    const mpo = mRatio('total', k, 'po'), mcr = mRatio('total', k, 'cr'), mlr = mRatio('total', k, 'lr');
    const fb = val(co, 'total', 'fb', k), fc = val(co, 'total', 'fc', k), pbt = L.streams[co].pbt[k];
    const vs = (a, b) => a == null || b == null ? '' : `<span class="${a <= b ? 'delta-good' : 'delta-bad'}"> (market ${per100(b)})</span>`;
    $('profileTiles').innerHTML = [
      [`KSh ${bn(prem)}`, `Gross premium ${label(P[k])} · #${rank || '–'} of ${r.length} · ${prem ? (share(co, 'total', k) * 100).toFixed(1) : '–'}% share`],
      [prev ? pp(prem / prev - 1) : 'n/a', `Growth on ${ly >= 0 ? label(P[ly]) : 'last year'} (market ${ly >= 0 ? pp(sum('total', 'gp', k) / sum('total', 'gp', ly) - 1) : 'n/a'})`],
      [per100(lr), `Loss ratio${vs(lr, mlr)}`], [per100(po), `Paid out per KSh 100 gross${vs(po, mpo)}`], [per100(cr), `Cost to run per KSh 100 gross${vs(cr, mcr)}`],
      [`KSh ${bn(fc)}`, `Life fund · ${fb ? pp(fc / fb - 1) : 'n/a'} this year (market ${pp(sum('total', 'fc', k) / sum('total', 'fb', k) - 1)})`],
      [pbt == null ? 'n/a' : `KSh ${bn(pbt)}`, `Profit before tax${+P[k].slice(0, 4) >= 2024 ? ' (IFRS 17)' : ''}`],
    ].map(([b, s]) => `<div class="tile"><b>${b}</b><span>${s}</span></div>`).join('');

    const lines = LINES.filter(l => l.id !== 'total');
    const rows = lines.map(l => {
      const p = gp(co, l.id, k) || 0, pl = ly >= 0 ? gp(co, l.id, ly) : null, rl = ranked(l.id, k), ri = rl.indexOf(co) + 1;
      const rr = p >= 50000 ? sRatio(co, l.id, k, mk) : null, mr = mRatio(l.id, k, mk);
      const w = prem ? Math.max(0, p / prem) : 0;
      return `<tr><td>${l.label}</td><td style="text-align:left"><span style="display:inline-block;height:10px;border-radius:2px;background:${lineColor(l.id)};width:${Math.round(w * 160)}px;vertical-align:-1px"></span> KSh ${bn(p)} · ${(w * 100).toFixed(0)}%</td>
        <td>${pl ? pp(p / pl - 1) : '–'}</td><td>${ri ? `#${ri} of ${rl.length}` : '–'}</td><td>${p ? (share(co, l.id, k) * 100).toFixed(1) + '%' : '–'}</td>
        <td style="background:${divColor(rr == null || mr == null ? null : rr - mr, true)}">${per100(rr)}</td><td>${per100(mr)}</td></tr>`;
    }).join('');
    card(g, 'wide', `<h2>${name(co)}: what it writes, ${label(P[k])}</h2><p class="note">${MEASURE[mk].label} by line against the market (blue better, red worse).</p>
      <table><tr><th>Line</th><th style="text-align:left">Premium and share of book</th><th>vs ${ly >= 0 ? label(P[ly]) : 'last year'}</th><th>Rank</th><th>Market share</th><th>${mk.toUpperCase()}</th><th>Market</th></tr>${rows}</table>`);

    const yrs = fullYears(), ks = yrs.map(q4);
    const c2 = card(g, '', `<h2>Market share and loss ratio over time</h2>${legend([[css('--series-1'), 'Market share %'], [css('--series-2'), 'Loss ratio %, all business']])}<p class="note">Two separate charts, so each keeps its own scale.</p>`);
    const a = document.createElementNS(NS, 'svg'), b = document.createElementNS(NS, 'svg'); c2.appendChild(a); c2.appendChild(b);
    lineChart(a, yrs.map(String), [{ name: 'Share', values: ks.map(kk => (share(co, 'total', kk) || 0) * 100 || null), color: css('--series-1') }], { h: 160, fmt: v => v == null || !isFinite(v) ? 'n/a' : v.toFixed(1) + '%', r: 20 });
    lineChart(b, yrs.map(String), [{ name: short(name(co)), values: ks.map(kk => { const v = sRatio(co, 'total', kk, 'lr'); return v == null ? null : v * 100; }), color: css('--series-2'), label: '' },
      { name: 'Market', values: ks.map(kk => mRatio('total', kk, 'lr') * 100), color: css('--text-muted'), dash: '4 3', label: 'Market' }], { h: 160, fmt: v => v == null || !isFinite(v) ? 'n/a' : v.toFixed(0), r: 50 });

    // peer table in the style of the Kwanusu life table
    const top = r.slice(0, 12); if (!top.includes(co) && rank) top.push(co);
    const shade = (v, m) => `background:${divColor(v == null || m == null ? null : v - m, true)}`;
    const shadeUp = (v, m) => `background:${divColor(v == null || m == null ? null : m - v, true)}`;
    const peer = top.map(s => {
      const p = gp(s, 'total', k), po2 = sRatio(s, 'total', k, 'po'), cr2 = sRatio(s, 'total', k, 'cr'), f1 = val(s, 'total', 'fc', k), f0 = val(s, 'total', 'fb', k), fg = f0 ? f1 / f0 - 1 : null;
      return `<tr class="${s === co ? 'hl' : ''}"><td>${r.indexOf(s) + 1}. ${name(s)}</td><td>${bn(p)}</td><td style="${shade(po2, mpo)}">${per100(po2)}</td><td style="${shade(cr2, mcr)}">${per100(cr2)}</td><td>${bn(f1)}</td><td style="${shadeUp(fg, sum('total', 'fc', k) / sum('total', 'fb', k) - 1)}">${pp(fg)}</td></tr>`;
    }).join('');
    card(g, '', `<h2>Peers, ${label(P[k])}</h2><p class="note">Blue better than the market, red worse. Paid out = claims, surrenders, bonuses, annuities. Cost = commissions + management expenses.</p>
      <table><tr><th>Insurer</th><th>Premium</th><th>Paid out /100</th><th>Cost /100</th><th>Life fund</th><th>Fund growth</th></tr>${peer}
      <tr class="hl"><td>All ${r.length} insurers</td><td>${bn(sum('total', 'gp', k))}</td><td>${per100(mpo)}</td><td>${per100(mcr)}</td><td>${bn(sum('total', 'fc', k))}</td><td>${pp(sum('total', 'fc', k) / sum('total', 'fb', k) - 1)}</td></tr></table>`);
  }

  // ---------- wiring ----------
  const DRAW = { claims: drawClaims, share: drawShare, mix: drawMix, profile: drawProfile };
  let active = 'overview';
  function show(tab) {
    active = tab;
    document.querySelectorAll('#tabs button').forEach(b => b.setAttribute('aria-selected', String(b.dataset.tab === tab)));
    document.querySelectorAll('section[id^=tab-]').forEach(s => s.hidden = s.id !== 'tab-' + tab);
    document.querySelector('.bar:not(#lbar)').hidden = tab !== 'overview';
    $('lbar').hidden = tab === 'overview';
    $('lm').parentElement.hidden = tab === 'share' || tab === 'mix';
    if (tab !== 'overview') { if (ready) DRAW[tab](); }
    try { history.replaceState(null, '', '#' + tab); } catch (e) {}
  }
  document.querySelectorAll('#tabs button').forEach(b => b.onclick = () => show(b.dataset.tab));
  fetch('data/lines.json').then(r => r.json()).then(d => {
    L = d; P = d.periods; LINES = d.lines; INS = Object.keys(d.streams);
    $('lp').innerHTML = P.map((p, i) => `<option value="${i}">${label(p)}${p.endsWith('Q4') ? ' (full year)' : ' (year to date)'}</option>`).reverse().join('');
    const fy = fullYears();
    $('ly0').innerHTML = fy.map(y => `<option>${y}</option>`).join(''); $('ly1').innerHTML = $('ly0').innerHTML;
    $('ly0').value = fy[0]; $('ly1').value = fy.at(-1);
    const k = P.length - 1;
    $('lco').innerHTML = ranked('total', k).map(s => `<option value="${s}">${name(s)}</option>`).join('');
    if (L.streams[DEFAULT_CO]) $('lco').value = DEFAULT_CO;
    ['lp', 'ly0', 'ly1', 'lco', 'lm'].forEach(id => $(id).addEventListener('change', () => active !== 'overview' && DRAW[active]()));
    ready = true;
    const h = (location.hash || '').slice(1); if (DRAW[h]) show(h);
    window.addEventListener('hashchange', () => { const t = location.hash.slice(1); if (DRAW[t] || t === 'overview') show(t); });
  }).catch(e => { $('claimsGrid').textContent = 'Could not load data/lines.json: ' + e; });
})();
