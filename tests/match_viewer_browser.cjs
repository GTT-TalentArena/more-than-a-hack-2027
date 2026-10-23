// End-to-end checks launch their own synthetic-only servers. No match files are read.
const assert = require('node:assert/strict');
const {spawn} = require('node:child_process');
const fs = require('node:fs/promises');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
const {chromium} = require(require.resolve('playwright', {paths:[path.join(root,'tools','match_viewer')]}));
const servers = [];
const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
async function start(port, extra = []) {
  const processHandle = spawn(process.env.VIEWER_PYTHON || 'python',
    ['-m','tools.match_viewer','--synthetic','--port',String(port), ...extra],
    {cwd:root, stdio:'ignore', windowsHide:true});
  servers.push(processHandle);
  const url = `http://127.0.0.1:${port}`;
  for (let i=0;i<150;i++) {
    if (processHandle.exitCode !== null) throw new Error('Synthetic server exited.');
    try { if ((await fetch(url+'/api/meta')).ok) return url; } catch {}
    await delay(100);
  }
  throw new Error('Synthetic server did not start.');
}

async function main() {
  let browser;
  try {
    const url = await start(8766);
    const noPredictions = await start(8767,['--no-predictions']);
    browser = await chromium.launch({headless:true,
      ...(process.env.VIEWER_BROWSER_CHANNEL ? {channel:process.env.VIEWER_BROWSER_CHANNEL} : {})});
    const page = await browser.newPage({viewport:{width:1440,height:1000},deviceScaleFactor:1});
    const external = [], errors = [];
    page.on('request', request => {if (!request.url().startsWith(url+'/')) external.push(request.url());});
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(url);
    await page.locator('#play').waitFor({state:'visible'});
    await page.waitForFunction(() => !document.querySelector('#play').disabled && document.querySelector('#loading').hidden);
    async function jump(frame, label) {
      await page.locator('#jump').fill(String(frame)); await page.locator('#jump-button').click();
      await page.waitForFunction(expected => document.querySelector('#frame').textContent === expected.toLocaleString('en-US'),frame);
      assert.equal(await page.locator('#label').textContent(),label);
    }
    await jump(100,'H'); assert.equal(await page.locator('#ball-status').textContent(),'No observation');
    await jump(350,'A'); assert.equal(await page.locator('#observed').textContent(),'21 / 22');
    await jump(550,'D'); assert.match(await page.locator('#message').textContent(),/outside the pitch/);
    await jump(700,'X'); assert.equal(await page.locator('#observed').textContent(),'0 / 22');
    await jump(850,'A'); assert.equal(await page.locator('#period').textContent(),'HALF 2');
    await jump(1499,'H'); assert.equal(await page.locator('#next').isDisabled(),true);
    await jump(0,'H'); assert.equal(await page.locator('#previous').isDisabled(),true);
    await page.locator('#next').click(); await page.waitForFunction(() => document.querySelector('#frame').textContent==='1');
    await page.locator('#previous').click(); await page.waitForFunction(() => document.querySelector('#frame').textContent==='0');
    await page.locator('#play').click(); await delay(500); await page.locator('#play').click();
    const paused = Number((await page.locator('#frame').textContent()).replaceAll(',',''));
    assert.ok(paused>=3 && paused<40); await delay(200);
    assert.equal(Number((await page.locator('#frame').textContent()).replaceAll(',','')),paused);
    for (const speed of ['0.25','0.5','1','2']) await page.locator('#speed').selectOption(speed);
    await page.route('**/api/frames?start=625&count=125', async route => {await delay(650); await route.continue();});
    await page.locator('#jump').fill('700'); await page.locator('#jump-button').click();
    await jump(1000,'H'); await delay(900);
    assert.equal(await page.locator('#frame').textContent(),'1,000');
    assert.equal(await page.locator('#label').textContent(),'H');
    await page.unroute('**/api/frames?start=625&count=125');
    // Pause a transport fetch that has not returned yet; the last displayed frame stays visible.
    await page.route('**/api/frames?start=1250&count=125', async route => {await delay(650); await route.continue();});
    await jump(1249,'D');
    await page.locator('#play').click();
    await page.waitForFunction(() => !document.querySelector('#loading').hidden);
    await page.locator('#play').click();
    await delay(750);
    assert.equal(await page.locator('#frame').textContent(),'1,249');
    assert.equal(await page.locator('#loading').isHidden(),true);
    await page.unroute('**/api/frames?start=1250&count=125');
    await jump(180,'H');
    const output = path.join(root,'salidas','viewer-browser'); await fs.mkdir(output,{recursive:true});
    await page.screenshot({path:path.join(output,'synthetic-desktop.png'),fullPage:true});
    await page.setViewportSize({width:390,height:844});
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),true);
    await page.screenshot({path:path.join(output,'synthetic-mobile.png'),fullPage:true});
    assert.deepEqual(external,[]); assert.deepEqual(errors,[]);
    const empty = await browser.newPage(); await empty.goto(noPredictions);
    await empty.waitForFunction(() => document.querySelector('#loading').hidden);
    assert.equal(await empty.locator('#label-description').textContent(),'No prediction loaded');
    assert.equal(await empty.locator('#label').textContent(),'—');
    console.log(JSON.stringify({result:'pass',source:'synthetic only',externalRequests:external.length,
      browserErrors:errors.length,checks:['H/A/D/X','no prediction','missing ball/player','half boundaries',
      'first/last frame','step','pause/play','pause during loading','speed controls','stale seek response','mobile layout'],
      browser:browser.version()},null,2));
  } finally {
    if (browser) await browser.close();
    for (const server of servers) server.kill();
  }
}
main().catch(error => {console.error(error);process.exitCode=1;});
