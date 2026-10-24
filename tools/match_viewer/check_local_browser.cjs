// Opt-in local checks: no screenshots, traces, rows, coordinates or labels are exported.
const {chromium} = require('playwright');
const {performance} = require('node:perf_hooks');
const fs = require('node:fs/promises');
const path = require('node:path');
const {installBallProbe,ballMatchesFrame} = require('./browser_checks.cjs');

async function main() {
  const port = Number(process.argv[2] || '8768');
  if (!Number.isInteger(port) || port < 1 || port > 65535) throw new Error('Invalid port.');
  const url = `http://127.0.0.1:${port}`;
  let stage = 'launch', browser;
  try {
    browser = await chromium.launch({headless:true,
      ...(process.env.VIEWER_BROWSER_CHANNEL ? {channel:process.env.VIEWER_BROWSER_CHANNEL} : {})});
    const context = await browser.newContext({viewport:{width:1440,height:1000}});
    let externalRequests = 0, browserErrors = 0;
    await context.route('**/*', route => {
      if (new URL(route.request().url()).origin !== url) {externalRequests++; return route.abort();}
      return route.continue();
    });
    const page = await context.newPage();
    await installBallProbe(page);
    page.on('pageerror', () => browserErrors++);
    stage = 'initial source and rendering';
    await page.goto(url);
    await page.waitForFunction(() => !document.querySelector('#play').disabled && document.querySelector('#loading').hidden);
    await page.evaluate(() => document.fonts.ready);
    const themeLoaded = await page.evaluate(() =>
      getComputedStyle(document.body).backgroundColor==='rgb(11, 14, 44)' &&
      [...document.fonts].filter(face => face.status==='loaded').length===4);
    if (!themeLoaded) throw new Error();
    const initial = await page.evaluate(async () => {
      const meta = await (await fetch('/api/meta')).json();
      return {ready:meta.status==='ready',frames:meta.n_frames,hasPredictions:meta.has_predictions,
        initialAligned:document.querySelector('#frame').textContent===meta.initial_frame.toLocaleString('en-US')};
    });
    if (!initial.ready || !initial.hasPredictions || !initial.initialAligned) throw new Error();
    stage = 'frame alignment and full-video navigation';
    const durations = [];
    const frames = [0, initial.frames-1, 11185, 18684, 90651, 90652, 100000, 110808, 113742, 190197];
    for (let index=1;index<=30;index++) frames.push(Math.floor((initial.frames-1)*index/31));
    for (const frame of frames) {
      const started = performance.now();
      await page.locator('#jump').fill(String(frame));
      await page.locator('#jump-button').click();
      await page.waitForFunction(expected => document.querySelector('#frame').textContent===expected.toLocaleString('en-US'),frame);
      const aligned = await page.evaluate(async expected => {
        const row = (await (await fetch(`/api/frames?start=${expected}&count=1`)).json()).frames[0];
        const context = await (await fetch(`/api/context?frame=${expected}`)).json();
        const recentLabels = [...document.querySelectorAll('#recent-spells .spell-key')].map(key=>key.dataset.label);
        return row.frame===expected && document.querySelector('#label').textContent===(row.label ?? '—') &&
          document.querySelector('#hud-frame').textContent===String(expected).padStart(6,'0') &&
          context.end_frame===expected+1 && recentLabels.join('')===context.spells.slice(-3).reverse().map(spell=>spell.label).join('') &&
          document.querySelector('#home-percent').textContent===(context.home_percent===null ? '—' : `${context.home_percent}%`) &&
          document.querySelector('#observed').textContent.split(' / ')[0]===String(row.players.filter(Boolean).length) &&
          document.querySelector('#ball-status').textContent===(row.ball ? 'Observed' : 'No observation');
      },frame);
      if (!aligned || !await ballMatchesFrame(page,frame)) throw new Error();
      const estimatesAligned = await page.evaluate(async expected => {
        const row = (await (await fetch(`/api/frames?start=${expected}&count=1`)).json()).frames[0];
        return document.querySelector('#estimated').textContent===String(row.player_estimates.filter(Boolean).length) &&
          row.player_estimates.every((point,slot)=>point===null || row.players[slot]===null);
      },frame);
      if (!estimatesAligned) throw new Error();
      durations.push(performance.now()-started);
    }
    stage = 'rendered player estimate and original comparison';
    // Locate a sample locally; its index and coordinates never enter the report.
    const estimateFrame = await page.evaluate(async () => {
      const meta = await (await fetch('/api/meta')).json();
      for (let start=meta.initial_frame;start<meta.n_frames;start+=250) {
        const rows = (await (await fetch(`/api/frames?start=${start}&count=250`)).json()).frames;
        const found = rows.find(row=>row.player_estimates.some(Boolean));
        if (found) return found.frame;
      }
      return null;
    });
    if (estimateFrame===null) throw new Error();
    await page.locator('#jump').fill(String(estimateFrame)); await page.locator('#jump-button').click();
    await page.waitForFunction(expected=>document.querySelector('#frame').textContent===expected.toLocaleString('en-US'),estimateFrame);
    if (Number(await page.locator('#estimated').textContent())<1 || !await ballMatchesFrame(page,estimateFrame)) throw new Error();
    const observedBeforeToggle = await page.locator('#observed').textContent();
    await page.locator('#estimate-players').uncheck();
    if (await page.locator('#estimated').textContent()!=='Off' ||
        await page.locator('#observed').textContent()!==observedBeforeToggle || !await ballMatchesFrame(page,estimateFrame)) throw new Error();
    await page.locator('#estimate-players').check();
    if (Number(await page.locator('#estimated').textContent())<1) throw new Error();
    stage = 'playback and pause';
    await page.locator('#jump').fill('11185'); await page.locator('#jump-button').click();
    await page.waitForFunction(() => document.querySelector('#frame').textContent==='11,185');
    await page.locator('#play').click(); await page.waitForTimeout(1500); await page.locator('#play').click();
    const paused = await page.locator('#frame').textContent();
    if (paused==='11,185') throw new Error();
    await page.waitForTimeout(250);
    if (paused!==await page.locator('#frame').textContent()) throw new Error();
    stage = 'mobile layout';
    await page.setViewportSize({width:390,height:844});
    if (!await page.evaluate(() => document.documentElement.scrollWidth<=innerWidth)) throw new Error();
    if (externalRequests || browserErrors) throw new Error();
    durations.sort((a,b)=>a-b);
    const summary = {status:'passed', source:'authorised local viewer', browser:browser.version(),
      framesAvailable:initial.frames,hasPredictions:initial.hasPredictions,
      initialFrameAligned:initial.initialAligned,seekChecks:frames.length,
      websiteThemeAndLocalFontsLoaded:themeLoaded,labelWindowAligned:true,
      trackingPredictionAndInspectorAligned:true,playAndPausePassed:true,mobileLayoutPassed:true,
      ballCanvasMatchesSource:true,playerEstimatesAligned:true,estimateTogglePassed:true,
      nonemptyEstimateComparedWithOriginal:true,
      externalRequests,browserErrors,
      seekMsP50:Math.round(durations[Math.floor(durations.length*.5)]),
      seekMsP95:Math.round(durations[Math.floor(durations.length*.95)])};
    const output = path.resolve(__dirname,'../../salidas/viewer-real/browser-verification.json');
    await fs.mkdir(path.dirname(output),{recursive:true});
    await fs.writeFile(output,JSON.stringify(summary,null,2)+'\n');
    console.log(JSON.stringify(summary,null,2));
  } catch {
    console.log(JSON.stringify({status:'failed',stage,details:'Input-derived details are suppressed.'}));
    process.exitCode=1;
  } finally {
    if (browser) await browser.close();
  }
}
main().catch(() => {console.log('Local browser verification could not start; details suppressed.');process.exitCode=1;});
