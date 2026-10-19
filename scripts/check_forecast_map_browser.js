// Browser checks for the forecast map page (scripts/forecast_map_page.html), run by scripts/check_forecast_map.py when node and playwright are there:
//   node scripts/check_forecast_map_browser.js DIR     (DIR holds uk_live_4.html, en_live_4.html, uk_live_1.html and uk_replay_0.html; SHOTS=DIR2 saves screenshots)
// Headless Chromium: no request when the page is opened, the top five for each horizon, selection by mouse and keyboard, the big number, the three bars with the threshold,
// the history chart (and what it says when there is none), the how-to popover, the freshness pill (with a fixed clock), and on a phone the bottom sheet.
const fs = require('fs');
const path = require('path');
let chromium;
try { ({ chromium } = require('playwright')); } catch (e) { ({ chromium } = require('/opt/node-tools/node_modules/playwright')); }

const dir = process.argv[2], shots = process.env.SHOTS || '';
let failed = 0;
const ok = (c, m) => { if (!c) failed++; console.log((c ? 'ok    ' : 'FAIL  ') + m); };
const sleep = ms => new Promise(r => setTimeout(r, ms));
const url = f => 'file://' + path.join(dir, f);
const rd = async p => p.evaluate(() => JSON.parse(document.getElementById('data').textContent));

(async () => {
  const browser = await chromium.launch();
  async function open(file, w, h, opts) {
    opts = opts || {};
    const ctx = await browser.newContext({ viewport: { width: w, height: h }, hasTouch: !!opts.touch });
    const p = await ctx.newPage();
    p.problems = []; p.requests = [];
    p.on('request', r => { const u = r.url(); if (!u.startsWith('file:') && !u.startsWith('about:') && !u.startsWith('data:')) p.requests.push(u); });
    p.on('pageerror', e => p.problems.push(String(e)));
    p.on('console', m => { if (m.type() === 'error') p.problems.push(m.text()); });
    if (opts.time) await p.clock.install({ time: opts.time });
    await p.goto(url(file));
    return p;
  }
  const names = async p => p.$$eval('#top5 .row .rname span:first-child', e => e.map(x => x.textContent));
  const expectTop = (D, h) => D.units.filter(u => u.modelled).map((u, i) => ({ u, i })).sort((a, b) => (b.u.p[h] - a.u.p[h]) || (a.i - b.i)).slice(0, 5).map(x => x.u);

  // ------------------------------------------------------------------ desktop, Ukrainian, with history
  let p = await open('uk_live_4.html', 1440, 900);
  let D = await rd(p);
  ok(p.requests.length === 0, `desktop: no request at all when the page is opened (${p.requests.length})`);
  ok(p.problems.length === 0, `desktop: no script error or console error ${JSON.stringify(p.problems)}`);
  const box = async sel => p.evaluate(s => { const r = document.querySelector(s).getBoundingClientRect(); return { x: r.x, y: r.y, w: r.width, h: r.height, b: r.bottom, r: r.right }; }, sel);
  const L = { panel: await box('#panel'), map: await box('#map'), strip: await box('.strip'), top: await box('.topbar'), sub: await box('.brand-sub') };
  ok(L.panel.x > 900 && L.panel.w > 380 && L.panel.w < 430 && L.map.r <= L.panel.x + 1, `desktop: map on the left, side panel on the right (panel x ${Math.round(L.panel.x)}, width ${Math.round(L.panel.w)})`);
  ok(L.strip.b <= 900 + 0.5 && L.strip.h > 20 && L.top.y === 0, 'desktop: top bar at the top, footer line inside the window');
  ok(await p.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth && document.documentElement.scrollHeight <= window.innerHeight + 1), 'desktop: nothing scrolls, the page is exactly the window');
  ok(await p.evaluate(() => { const e = document.querySelector('.brand-sub'); return e.scrollWidth <= e.clientWidth + 1 && e.offsetHeight > 0; }) && (await p.textContent('.brand-sub')).includes('1, 3'), 'desktop: the sentence under the title is fully visible');
  ok((await p.textContent('.strip')).length > 30, 'desktop: the footer line (study model, follow official alerts) is visible without scrolling');
  ok(L.map.h > 450, `desktop: the map uses the height (${Math.round(L.map.h)} px)`);

  for (const h of [1, 3, 6]) {
    await p.click(`#seg button[data-h="${h}"]`);
    const want = expectTop(D, h), got = await names(p);
    ok(JSON.stringify(got) === JSON.stringify(want.map(u => u.name)), `default view, ${h} h: the five most probable oblasts in the right order (${got[0]} first)`);
    const pcs = await p.$$eval('#top5 .row .rpct', e => e.map(x => x.textContent));
    ok(JSON.stringify(pcs) === JSON.stringify(want.map(u => u.pc[h] + ' ' + (u.p[h] >= D.thr[h] ? '▲' : '▽'))), `default view, ${h} h: percentages and triangles right`);
    ok(await p.getAttribute('body', 'data-h') === String(h) && await p.getAttribute(`#seg button[data-h="${h}"]`, 'aria-checked') === 'true', `segmented control, ${h} h: pressed, map switched`);
  }
  ok((await p.$$('#all .row')).length === 24, 'default view: "all oblasts" lists all 24, hidden until opened');
  await p.click('#seg button[data-h="1"]');

  // hover and selection by mouse
  const iso = 'UA-63', u = D.units.find(x => x.iso === iso);
  await p.hover(`.u[data-iso="${iso}"] path`);
  const hovd = await p.evaluate(() => [document.getElementById('hl-hover').getAttribute('visibility'), document.getElementById('hl-hover').getAttribute('d') === document.getElementById('p-UA-63').getAttribute('d'), document.getElementById('readout').textContent]);
  ok(hovd[0] === 'visible' && hovd[1] && hovd[2].includes(u.name) && hovd[2].includes(u.pc['1']), `hover: the oblast is outlined and its name and number are shown in the corner of the map ("${hovd[2]}")`);
  ok((await p.$$('#top5')).length === 1, 'hover does not select');
  await p.mouse.move(5, 300);
  ok(await p.evaluate(() => document.getElementById('hl-hover').getAttribute('visibility') === 'hidden' && document.getElementById('readout').textContent === ''), 'moving away clears the hover outline and readout');
  await p.click(`.u[data-iso="${iso}"] path`);
  const sel = await p.evaluate(() => ({ h2: document.querySelector('#panelbody h2').textContent, big: document.querySelector('#big .bignum').textContent, unit: document.querySelector('#big .bigunit').textContent,
    thr: document.getElementById('thr').textContent, alert: document.getElementById('alertrow').className, alertText: document.getElementById('alertrow').textContent,
    pressed: document.querySelector('.u[data-iso="UA-63"]').getAttribute('aria-pressed'), selD: document.getElementById('hl-sel').getAttribute('d') === document.getElementById('p-UA-63').getAttribute('d'), selVis: document.getElementById('hl-sel').getAttribute('visibility'),
    live: document.getElementById('live').textContent, bars: [...document.querySelectorAll('#bars .brow')].map(b => ({ h: b.dataset.h, on: b.classList.contains('on'), w: b.querySelector('.track i').style.width, tick: b.querySelector('.tick').style.left, val: b.querySelector('.bval').textContent, label: b.querySelector('.blabel').textContent })) }));
  ok(sel.h2 === u.full && sel.big === u.pc['1'].slice(0, -1) && sel.unit === '%', `click selects: name "${sel.h2}" and the big percentage "${sel.big}%" for 1 h`);
  ok(sel.thr.includes(D.thrPc['1']) && sel.thr.startsWith(u.p['1'] >= D.thr['1'] ? '▲' : '▽'), `click selects: threshold chip says above/below with the threshold ("${sel.thr}")`);
  ok(sel.alert.includes('on') === u.now && sel.alertText.includes(D.S[u.now ? 'ui_alert_yes' : 'ui_alert_no']), `click selects: alert status right (${u.now ? 'running' : 'none'})`);
  ok(sel.pressed === 'true' && sel.selD && sel.selVis === 'visible' && sel.live.includes(u.name), 'click selects: aria-pressed, the selection outline on the right shape, the screen-reader text');
  ok(sel.bars.length === 3 && sel.bars.every((b, i) => { const h = [1, 3, 6][i]; return +b.h === h && Math.abs(parseFloat(b.w) - u.p[h] * 100) < 0.01 && Math.abs(parseFloat((b.tick.match(/calc\(([\d.]+)%/) || [0, 'x'])[1]) - D.thr[h] * 100) < 0.01 && b.val.startsWith(u.pc[h]); }) && sel.bars[0].on,
    'three bars for 1 / 3 / 6 h: width = probability, threshold tick at the threshold, value with triangle, the chosen horizon marked');
  // a probability within one point of the threshold shows one decimal too, so "25%" never looks below a "25.2%" threshold
  const nearU = D.units.find(x => x.iso === 'UA-71'), farU = D.units.find(x => x.iso === 'UA-59');
  await p.click('.u[data-iso="UA-71"] path');
  const nearTxt = await p.textContent('#thr'), t1 = D.thrPc['1'];
  ok(nearTxt.includes((nearU.p['1'] * 100).toFixed(1).replace('.', D.dec) + '%') && nearTxt.includes(t1) && nearTxt.startsWith('\u25b2'), `an oblast right at its threshold: the chip shows both with one decimal ("${nearTxt}")`);
  await p.click('.u[data-iso="UA-59"] path');
  const nearTxt2 = await p.textContent('#thr');
  ok(nearTxt2.startsWith('\u25bd') && nearTxt2.includes(t1) && nearTxt2.includes((farU.p['1'] * 100).toFixed(1).replace('.', D.dec) + '%'), `an oblast just below its threshold: "${nearTxt2}"`);
  await p.click('.u[data-iso="UA-63"] path');
  await p.click('.brow[data-h="6"]');
  ok(await p.evaluate(() => document.body.dataset.h === '6' && document.querySelector('#big .bignum').textContent) === u.pc['6'].slice(0, -1), 'clicking a bar switches the horizon (map, control and big number)');
  await p.click('#back');
  ok((await p.$$('#top5')).length === 1 && await p.evaluate(() => document.getElementById('hl-sel').getAttribute('visibility') === 'hidden'), 'back to all oblasts clears the selection');
  await p.click('#top5 .row');
  const first = expectTop(D, 6)[0];
  ok(await p.textContent('#panelbody h2') === first.full, `a row in the top five selects its oblast (${first.full})`);

  // history chart
  await p.click('#seg button[data-h="1"]');
  const hist = await p.evaluate(() => { const s = document.querySelector('#hist svg'); return s ? { circles: s.querySelectorAll('circle').length, pts: s.querySelector('polyline').getAttribute('points').split(' ').length, dashed: !!s.querySelector('line[stroke-dasharray]'), cap: document.querySelector('#hist .cap').textContent, label: s.getAttribute('aria-label') } : null; });
  ok(hist && hist.circles === 4 && hist.pts === 4 && hist.dashed && hist.cap.includes('4') && hist.cap.includes(D.history.runs[3].lbl), `history chart: one point per earlier run (4), the threshold as a dashed line, caption with the number of runs and the last run (${hist && hist.cap})`);
  const pts1 = await p.getAttribute('#hist polyline', 'points');
  await p.click('#seg button[data-h="3"]');
  ok(await p.getAttribute('#hist polyline', 'points') !== pts1, 'history chart follows the horizon');

  // keyboard
  await p.keyboard.press('Escape');
  ok((await p.$$('#top5')).length === 1, 'Escape clears the selection');
  await p.focus('.u[data-iso="UA-46"]');
  ok(await p.evaluate(() => document.getElementById('hl-hover').getAttribute('visibility') === 'visible' && document.getElementById('hl-hover').getAttribute('class').includes('focus')), 'keyboard focus on an oblast shows the focus outline');
  await p.keyboard.press('Enter');
  const lv = D.units.find(x => x.iso === 'UA-46');
  ok(await p.textContent('#panelbody h2') === lv.full, 'Enter on a focused oblast selects it');
  await p.keyboard.press('Escape');
  await p.focus('.u[data-iso="UA-46"]'); await p.keyboard.press('Space');
  ok(await p.textContent('#panelbody h2') === lv.full, 'Space on a focused oblast selects it');
  await p.keyboard.press('Escape');
  await p.focus('#seg button[aria-checked="true"]');
  await p.keyboard.press('Home'); const a1 = await p.getAttribute('body', 'data-h');
  await p.keyboard.press('ArrowRight'); const a2 = await p.getAttribute('body', 'data-h');
  await p.keyboard.press('End'); const a3 = await p.getAttribute('body', 'data-h');
  await p.keyboard.press('ArrowRight'); const a4 = await p.getAttribute('body', 'data-h');
  ok([a1, a2, a3, a4].join() === '1,3,6,1' && await p.evaluate(() => document.activeElement.closest('#seg') !== null), 'segmented control: arrow keys, Home and End move through 1 / 3 / 6 h and keep the focus');
  const tabs = await p.evaluate(() => [...document.querySelectorAll('#seg button')].map(b => b.tabIndex));
  ok(tabs.join() === '0,-1,-1', 'segmented control: only the pressed button is in the tab order (roving)');
  const order = await p.evaluate(() => [...document.querySelectorAll('.u[data-iso], #kchip, #seg button, #how')].filter(e => e.offsetParent !== null || e.closest('svg')).length);
  ok(order >= 27 + 3, `${order} controls are reachable with the keyboard (27 map units, the control, the how-to button)`);

  // popover
  await p.click('#how');
  ok(await p.evaluate(() => !document.getElementById('howpop').hidden && document.getElementById('how').getAttribute('aria-expanded') === 'true' && document.activeElement.id === 'howx'), 'how-to: opens, aria-expanded, focus moves into it');
  ok((await p.$$('#howpop dt')).length === 6 && (await p.textContent('#howpop')).length > 600, 'how-to: six explanations and the about section');
  await p.keyboard.press('Escape');
  ok(await p.evaluate(() => document.getElementById('howpop').hidden && document.activeElement.id === 'how'), 'how-to: Escape closes it and returns the focus to the button');
  await p.click('#how'); await p.mouse.click(60, 500);
  ok(await p.evaluate(() => document.getElementById('howpop').hidden), 'how-to: a click outside closes it');
  if (shots) { await p.click('.u[data-iso="UA-63"] path'); await p.mouse.move(700, 800); await p.screenshot({ path: path.join(shots, 'desktop_uk_selected.png') }); await p.keyboard.press('Escape'); await p.screenshot({ path: path.join(shots, 'desktop_uk_default.png') }); }
  await p.context().close();

  // ------------------------------------------------------------------ no raw decimal anywhere, in any state
  p = await open('uk_live_4.html', 1440, 900); D = await rd(p);
  const decimals = async () => p.evaluate(() => {
    const t = [document.body.innerText, ...[...document.querySelectorAll('[aria-label],[title]')].map(e => (e.getAttribute('aria-label') || '') + ' ' + (e.getAttribute('title') || '')), ...[...document.querySelectorAll('svg title')].map(e => e.textContent), document.getElementById('live').textContent].join(' | ');
    return (t.match(/.{10}\d\.\d+(?!\d*%).{6}/g) || []);
  });
  let dec = [];
  for (const h of [1, 3, 6]) { await p.click(`#seg button[data-h="${h}"]`); dec = dec.concat(await decimals()); }
  await p.click('.u[data-iso="UA-63"] path');
  for (const h of [1, 3, 6]) { await p.click(`#seg button[data-h="${h}"]`); dec = dec.concat(await decimals()); }
  await p.click('#how'); dec = dec.concat(await decimals());
  ok(dec.length === 0, `no raw decimal number on the page in any state: default, selected, all three horizons, popover open, titles and labels ${JSON.stringify(dec.slice(0, 3))}`);
  const pillTxt = await p.evaluate(() => [...document.querySelectorAll('.pills .pill')].map(e => e.textContent));
  ok(pillTxt.length === 3 && /\(Київ\)/.test(pillTxt[2]) && !/UTC/.test(pillTxt[2]), `the origin pill is short, Kyiv time only ("${pillTxt[2]}")`);
  ok(/UTC/.test(await p.textContent('#howpop')) && (await p.textContent('#howpop')).includes('12:00 UTC'), 'the how-to popover has the origin hour in UTC');
  ok(!/[\u2012-\u2015\u2212]/.test(await p.evaluate(() => document.body.innerText + [...document.querySelectorAll('[aria-label],[title]')].map(e => e.getAttribute('aria-label') + e.getAttribute('title')).join(''))), 'no long dash anywhere in the Ukrainian page');
  await p.context().close();

  // ------------------------------------------------------------------ labels never touch an oblast border
  async function labelReport(p, w, maxHidden, tag) {
    await sleep(450);
    const fit = await p.evaluate((w) => {
      const svg = document.getElementById('map'), ctm = svg.getScreenCTM(), inv = ctm.inverse(), k = ctm.a, pt = svg.createSVGPoint(), bad = [], px = [];
      let hidden = 0, scaled = 0, dropped = 0;
      const toSvg = (x, y) => { pt.x = x; pt.y = y; return pt.matrixTransform(inv); };
      for (const hz of [1, 3, 6]) {
        document.body.setAttribute('data-h', hz);
        for (const g of svg.querySelectorAll('.u')) {
          const l = g.querySelector('.lbls'); if (!l) continue;
          if (l.classList.contains('nolabel')) { if (hz === 1) hidden++; continue; }
          const els = [...l.querySelectorAll('text, circle')].filter(e => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; });
          if (!els.length) continue;
          let x0 = 1e9, y0 = 1e9, x1 = -1e9, y1 = -1e9;
          els.forEach(e => { const r = e.getBoundingClientRect(); x0 = Math.min(x0, r.left); y0 = Math.min(y0, r.top); x1 = Math.max(x1, r.right); y1 = Math.max(y1, r.bottom); });
          const m = 1.5, path = g.querySelector('path'); let off = 0;
          const pts = [];
          for (let x = x0 - m; x <= x1 + m; x += 2) { pts.push([x, y0 - m], [x, y1 + m]); }
          for (let y = y0 - m; y <= y1 + m; y += 2) { pts.push([x0 - m, y], [x1 + m, y]); }
          for (const [x, y] of pts) { const q = toSvg(x, y); if (!path.isPointInFill(q)) { off++; } }
          if (off) bad.push(g.dataset.iso + ' h' + hz + ' (' + off + ' of ' + pts.length + ' points of its outline are outside)');
          if (g.dataset.iso === 'UA-32') { const c = document.getElementById('p-UA-30').getBBox(), a = toSvg(x0 - m, y0 - m), b = toSvg(x1 + m, y1 + m); if (b.x > c.x && a.x < c.x + c.width && b.y > c.y && a.y < c.y + c.height) bad.push('UA-32 h' + hz + ' overlaps Kyiv City'); }
          const s = parseFloat(l.dataset.s) || 1;
          const nmEl = [...l.querySelectorAll('.nm')].find(e => e.getBoundingClientRect().width > 0), pcEl = [...l.querySelectorAll('.pc')].find(e => e.getBoundingClientRect().width > 0);
          if (nmEl) px.push(['name', g.dataset.iso, parseFloat(getComputedStyle(nmEl).fontSize) * s * k]);
          if (pcEl) px.push(['pct', g.dataset.iso, parseFloat(getComputedStyle(pcEl).fontSize) * s * k]);
          if (hz === 1) { if (s < 1) scaled++; if (/n/.test(l.dataset.s || '') && g.querySelector('.nm') && getComputedStyle(g.querySelector('.nm')).display === 'none' && w > 820) dropped++; }
        }
      }
      return { bad, hidden, scaled, dropped, minName: Math.min(...px.filter(a => a[0] === 'name').map(a => a[2]), 99), minPct: Math.min(...px.filter(a => a[0] === 'pct').map(a => a[2]), 99), k };
    }, w);
    ok(fit.bad.length === 0, `${tag}${w} px wide: no label touches or crosses an oblast border (3 horizons, 1.5 px clearance)${fit.bad.length ? ' ' + JSON.stringify(fit.bad.slice(0, 4)) : ''}`);
    ok(fit.hidden <= maxHidden, `${tag}${w} px wide: ${fit.hidden} label(s) left out because they cannot fit at a readable size (at most ${maxHidden}); ${fit.scaled} shrunk, ${fit.dropped} without the name`);
    ok(fit.minPct >= 4.8 && (w <= 820 || fit.minName >= 6.3 || fit.minName === 99), `${tag}${w} px wide: smallest text on the screen: name ${fit.minName === 99 ? 'none shown' : fit.minName.toFixed(1)} px, percentage ${fit.minPct.toFixed(1)} px`);
    if (shots && w === 1440) await p.screenshot({ path: path.join(shots, 'desktop_labels.png') });
  }
  for (const [w, h, maxHidden] of [[1440, 900, 0], [1920, 1080, 0], [1100, 720, 2], [390, 844, 10]]) {
    p = await open('uk_live_4.html', w, h);
    await labelReport(p, w, maxHidden, '');
    await p.context().close();
  }
  p = await open('en_live_4.html', 1440, 900); await labelReport(p, 1440, 0, 'English page, '); await p.context().close();
  p = await open('uk_live_4.html', 1440, 900);   // the same page resized: the labels are fitted again
  await p.setViewportSize({ width: 1100, height: 720 }); await labelReport(p, 1100, 2, 'after resizing to ');
  await p.setViewportSize({ width: 390, height: 844 }); await labelReport(p, 390, 10, 'after resizing to ');
  await p.setViewportSize({ width: 1440, height: 900 }); await labelReport(p, 1440, 0, 'after resizing back to ');
  await p.context().close();

  // ------------------------------------------------------------------ history says so when there is none
  for (const [file, key, what] of [['uk_live_1.html', 'ui_hist_none', 'only one run so far'], ['uk_replay_0.html', 'ui_hist_replay', 'a replay of a past hour']]) {
    p = await open(file, 1440, 900); D = await rd(p);
    await p.click('.u[data-iso="UA-63"] path');
    ok(await p.evaluate(() => !document.querySelector('#hist svg')) && await p.textContent('#hist .empty') === D.S[key], `history, ${what}: no chart, and the page says so ("${D.S[key].slice(0, 50)}...")`);
    await p.context().close();
  }

  // ------------------------------------------------------------------ freshness pill with a fixed clock
  p = await open('uk_live_4.html', 1440, 900); D = await rd(p); const made = Date.parse(D.made); await p.context().close();
  for (const [mins, cls, want] of [[0.2, 'ok', 'щойно'], [5, 'ok', '5 хв'], [30, 'warn', '30 хв'], [180, 'bad', '3 год'], [3000, 'bad', '2 дн']]) {
    p = await open('uk_live_4.html', 1440, 900, { time: made + mins * 60000 });
    const f = await p.evaluate(() => ({ c: document.getElementById('fresh').className, t: document.getElementById('fresh-text').textContent, title: document.getElementById('fresh').title }));
    ok(f.c.split(' ').includes(cls) && f.t.includes(want) && (cls === 'bad') === (f.title.length > 0), `freshness pill ${mins} min after the page was made: ${cls}, "${f.t}"${cls === 'bad' ? ', with the "run again" hint' : ''}`);
    await p.context().close();
  }
  p = await open('uk_live_4.html', 1440, 900, { time: made + 5 * 60000 });
  await p.clock.runFor(40 * 60000);
  ok((await p.evaluate(() => document.getElementById('fresh').className)).includes('warn'), 'freshness pill: it keeps counting while the page stays open (5 min -> 45 min turns amber)');
  await p.context().close();
  p = await open('uk_replay_0.html', 1440, 900);
  ok(await p.evaluate(() => !/\b(ok|warn|bad)\b/.test(document.getElementById('fresh').className) && document.getElementById('fresh-text').textContent.length > 5), 'freshness pill on a replay: neutral, says it is a replay');
  await p.context().close();

  // ------------------------------------------------------------------ English page
  p = await open('en_live_4.html', 1440, 900); D = await rd(p);
  ok(await p.evaluate(() => document.documentElement.lang) === 'en' && (await p.textContent('#panelbody h2')) === D.S.ui_top_title && (await names(p)).length === 5 && p.problems.length === 0 && p.requests.length === 0, 'English page: language, the top-five heading, five rows, no errors, no requests');
  await p.click('.u[data-iso="UA-63"] path');
  ok((await p.textContent('#panelbody h2')) === D.units.find(x => x.iso === 'UA-63').full && (await p.textContent('#hist .cap')).includes('4'), 'English page: selection and the history chart work');
  if (shots) { await p.screenshot({ path: path.join(shots, 'desktop_en_selected.png') }); }
  await p.context().close();

  // ------------------------------------------------------------------ phone: the panel is a bottom sheet
  p = await open('uk_live_4.html', 390, 844, { touch: true }); D = await rd(p);
  ok(p.requests.length === 0 && p.problems.length === 0, 'phone: no request, no error');
  ok(await p.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), 'phone: no horizontal scrolling');
  const ph = await p.evaluate(() => { const r = s => { const b = document.querySelector(s).getBoundingClientRect(); return { y: b.y, b: b.bottom, h: b.height, w: b.width }; };
    return { panel: r('#panel'), strip: r('.strip'), pos: getComputedStyle(document.getElementById('panel')).position, map: r('#map'), at: (() => { const s = document.querySelector('.strip').getBoundingClientRect(); const e = document.elementFromPoint(s.x + s.width / 2, s.y + s.height / 2); return !!(e && e.closest('.strip')); })() }; });
  ok(ph.pos === 'fixed' && ph.panel.h > 70 && ph.panel.h < 110 && Math.abs(ph.panel.b - ph.strip.y) < 2, `phone: the panel is a fixed bottom sheet, peeking (${Math.round(ph.panel.h)} px) just above the footer line`);
  ok(ph.strip.b <= 844.5 && ph.at && ph.strip.w >= 389, 'phone: the footer line (study model, follow official alerts) is at the bottom and not covered by the sheet');
  ok(await p.evaluate(() => [...document.querySelectorAll('.pills > *')].every(e => { const r = e.getBoundingClientRect(); return r.left >= 0 && r.right <= window.innerWidth && r.width > 0; })), 'phone: the pills (data age, model, origin hour, how to read) are all fully on the screen (they wrap, no sideways scrolling)');
  ok(ph.map.w >= 340 && ph.map.y > 100, `phone: the map fills the width (${Math.round(ph.map.w)} px)`);
  ok(await p.evaluate(() => { const k = document.getElementById('kchip'); const b = k.getBoundingClientRect(); return b.width > 60 && b.height >= 30 && getComputedStyle(document.querySelector('.callout')).display === 'none' && k.textContent.includes('%'); }), 'phone: Kyiv City is a button above the map (the call-out is for large screens)');
  if (shots) await p.screenshot({ path: path.join(shots, 'phone_uk_default.png') });
  await p.tap('#sheetbtn'); await sleep(450);
  const open1 = await p.evaluate(() => ({ s: document.body.dataset.sheet, h: document.getElementById('panel').getBoundingClientRect().height, e: document.getElementById('sheetbtn').getAttribute('aria-expanded'), rows: document.querySelectorAll('#top5 .row').length }));
  ok(open1.s === 'open' && open1.h > 300 && open1.e === 'true' && open1.rows === 5, `phone: tapping the handle opens the sheet (${Math.round(open1.h)} px) with the top five`);
  await p.tap('#sheetbtn'); await sleep(450);
  ok(await p.evaluate(() => document.body.dataset.sheet === 'peek' && document.getElementById('panel').getBoundingClientRect().height < 110), 'phone: tapping again closes it to the peek');
  await p.tap('.u[data-iso="UA-63"] path'); await sleep(450);
  const sp = await p.evaluate(() => ({ s: document.body.dataset.sheet, h2: document.querySelector('#panelbody h2').textContent, big: document.querySelector('#big .bignum').textContent, panelTop: document.getElementById('panel').getBoundingClientRect().y, unitB: document.getElementById('p-UA-63').getBoundingClientRect().bottom, title: document.getElementById('sheet-title').textContent }));
  const k = D.units.find(x => x.iso === 'UA-63');
  ok(sp.s === 'open' && sp.h2 === k.full && sp.big === k.pc['1'].slice(0, -1) && sp.title.includes(k.pc['1']), `phone: tapping an oblast opens the sheet with its big number ("${sp.h2}", ${sp.big}%)`);
  ok(sp.unitB < sp.panelTop, 'phone: the selected oblast is still visible above the open sheet');
  if (shots) await p.screenshot({ path: path.join(shots, 'phone_uk_selected.png') });
  await p.tap('#back'); await p.tap('#kchip'); await sleep(450);
  ok(await p.evaluate(() => document.querySelector('#panelbody h2').textContent) === D.units.find(x => x.iso === 'UA-30').full, 'phone: the Kyiv City button selects Kyiv City');
  await p.tap('#seg button[data-h="6"]');
  ok(await p.evaluate(() => document.body.dataset.h) === '6' && await p.evaluate(() => document.querySelector('#big .bignum').textContent) === D.units.find(x => x.iso === 'UA-30').pc['6'].slice(0, -1), 'phone: the 1 / 3 / 6 h control works by touch and updates the open panel');
  await p.tap('#how'); await sleep(100);
  ok(await p.evaluate(() => { const b = document.getElementById('howpop').getBoundingClientRect(); return !document.getElementById('howpop').hidden && b.left >= 0 && b.right <= window.innerWidth && b.bottom <= window.innerHeight; }), 'phone: the how-to popover fits on the screen');
  if (shots) { await p.tap('#howx'); await p.tap('#back'); await p.tap('#sheetbtn'); await sleep(450); await p.screenshot({ path: path.join(shots, 'phone_uk_open.png') }); }
  await p.context().close();
  await browser.close();
  process.exit(failed ? 1 : 0);
})().catch(e => { console.log('FAIL  the browser check crashed: ' + (e && e.stack || e)); process.exit(1); });
