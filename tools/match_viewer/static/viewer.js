import { Playback, videoTime } from '/playback.mjs';

const $ = id => document.getElementById(id);
const canvas = $('pitch'), ctx = canvas.getContext('2d');
const theme = getComputedStyle(document.documentElement);
const colours = {H: theme.getPropertyValue('--home').trim(), A: theme.getPropertyValue('--away').trim(),
  D: theme.getPropertyValue('--dead').trim(), X: theme.getPropertyValue('--muted').trim()};
const ballColour = theme.getPropertyValue('--ball').trim();
const descriptions = {H: 'Home in possession', A: 'Away in possession', D: 'Dead ball', X: 'Model abstention'};
const BLOCK = 125, MAX_CACHE = 4;
const cache = new Map(), pending = new Map();
let meta, clock, displayed = 0, epoch = 0, busy = false;
let contextController;
let currentRow;

async function api(path, options = {}) {
  const response = await fetch(path, {cache: 'no-store', credentials: 'omit', ...options});
  const value = await response.json();
  if (!response.ok) throw new Error(value.message || 'Local source is unavailable.');
  return value;
}

async function blockAt(frame) {
  const start = Math.floor(frame / BLOCK) * BLOCK;
  if (cache.has(start)) {
    const rows = cache.get(start); cache.delete(start); cache.set(start, rows); return rows;
  }
  if (!pending.has(start)) {
    // Rapid scrubbing cannot accumulate an unbounded queue of old requests.
    if (pending.size >= 2) {
      const oldest = pending.keys().next().value;
      pending.get(oldest).controller.abort(); pending.delete(oldest);
    }
    const controller = new AbortController();
    const entry = {controller};
    const task = fetch(`/api/frames?start=${start}&count=${BLOCK}`, {
      cache:'no-store', credentials:'omit', signal:controller.signal
    }).then(async response => {
      const value = await response.json();
      if (!response.ok) throw new Error(value.message || 'Local source is unavailable.');
      cache.set(start, value.frames);
      while (cache.size > MAX_CACHE) cache.delete(cache.keys().next().value);
      return value.frames;
    }).finally(() => {if (pending.get(start) === entry) pending.delete(start);});
    entry.task = task; pending.set(start, entry);
  }
  return pending.get(start).task;
}

function periodAt(frame) {
  const block = meta.blocks.find(([, start, end]) => start <= frame && frame <= end);
  return block ? `HALF ${block[0]}` : 'BETWEEN PERIODS / OUTSIDE PLAY';
}

function draw(row) {
  currentRow = row;
  const [length, width] = meta.pitch;
  const padding = 34, scale = Math.min((canvas.width - 2 * padding) / length, (canvas.height - 2 * padding) / width);
  const left = (canvas.width - length * scale) / 2, top = (canvas.height - width * scale) / 2;
  const point = ([x, y]) => [left + x * scale, top + y * scale];
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.fillStyle = 'rgba(243,238,230,.025)';
  for (let i = 0; i < 14; i += 2) ctx.fillRect(left + i * length * scale / 14, top, length * scale / 14, width * scale);
  ctx.strokeStyle = 'rgba(243,238,230,.26)'; ctx.lineWidth = Math.max(1,scale*.16);
  function rect(x,y,w,h) { const [px,py] = point([x,y]); ctx.strokeRect(px,py,w*scale,h*scale); }
  function circle(x,y,r,a0=0,a1=Math.PI*2) { const [px,py] = point([x,y]); ctx.beginPath(); ctx.arc(px,py,r*scale,a0,a1); ctx.stroke(); }
  function spot(x,y) { const [px,py] = point([x,y]); ctx.beginPath(); ctx.arc(px,py,.35*scale,0,Math.PI*2); ctx.fillStyle='rgba(243,238,230,.26)'; ctx.fill(); }
  rect(0,0,length,width); rect(length/2,0,0,width); circle(length/2,width/2,9.15);
  for (const side of [0,1]) {
    rect(side ? length-16.5 : 0,(width-40.32)/2,16.5,40.32);
    rect(side ? length-5.5 : 0,(width-18.32)/2,5.5,18.32);
    rect(side ? length : -2,(width-7.32)/2,2,7.32);
    spot(side ? length-11 : 11,width/2);
    const arc = Math.acos(5.5/9.15);
    circle(side ? length-11 : 11,width/2,9.15,side ? Math.PI-arc : -arc,side ? Math.PI+arc : arc);
  }
  spot(length/2,width/2);
  let estimated = 0;
  if ($('estimate-players').checked) {
    (row.player_estimates ?? []).forEach((xy, index) => {
      if (!xy || row.players[index]) return;
      estimated++;
      const [x,y] = point(xy);
      ctx.save(); ctx.strokeStyle = colours[meta.slot_teams[index]];
      ctx.lineWidth = scale*.22; ctx.globalAlpha = .7*(row.player_estimate_fade?.[index] ?? 1); ctx.setLineDash([scale*.35,scale*.23]);
      ctx.beginPath(); ctx.arc(x,y,.95*scale,0,Math.PI*2); ctx.stroke(); ctx.restore();
    });
  }
  let out = 0;
  row.players.forEach((xy, index) => {
    if (!xy) return;
    const [x,y] = point(xy);
    const outside = xy[0]<0 || xy[0]>length || xy[1]<0 || xy[1]>width;
    if (outside) out++;
    ctx.beginPath(); ctx.arc(x,y,.95*scale,0,Math.PI*2); ctx.fillStyle = colours[meta.slot_teams[index]]; ctx.fill();
  });
  if (row.ball) {
    const [x,y] = point(row.ball);
    if (row.ball[0]<0 || row.ball[0]>length || row.ball[1]<0 || row.ball[1]>width) out++;
    ctx.shadowColor = ballColour; ctx.shadowBlur = scale*1.6;
    ctx.beginPath(); ctx.arc(x,y,.62*scale,0,Math.PI*2); ctx.fillStyle = ballColour; ctx.fill();
    ctx.shadowBlur = 0;
  }
  $('label').textContent = row.label ?? '—';
  $('label-description').textContent = descriptions[row.label] ?? 'No prediction loaded';
  $('possession').dataset.label = row.label ?? 'none';
  $('frame').textContent = row.frame.toLocaleString('en-US');
  $('hud-frame').textContent = String(row.frame).padStart(6,'0');
  $('time').textContent = $('timeline-time').textContent = videoTime(row.frame, meta.fps);
  $('observed').textContent = `${row.players.filter(Boolean).length} / ${meta.slot_ids.length}`;
  $('estimated').textContent = $('estimate-players').checked ? String(estimated) : 'Off';
  $('ball-status').textContent = row.ball ? 'Observed' : 'No observation';
  $('ball-missing').hidden = Boolean(row.ball);
  $('period').textContent = periodAt(row.frame);
  $('timeline').value = row.frame; $('jump').value = row.frame;
  $('message').textContent = out ? `${out} observation(s) outside the pitch. Coordinates are preserved; distant points may be outside the viewport.` : meta.synthetic ? 'Synthetic demo · invented tracking and model labels.' : 'Local source · original observations and model labels.';
  displayed = row.frame;
  $('previous').disabled = displayed === 0;
  $('next').disabled = displayed === meta.n_frames-1;
}

function drawContext(context) {
  const strip = $('possession-strip'), stripCtx = strip.getContext('2d');
  stripCtx.clearRect(0,0,strip.width,strip.height);
  const maximum = meta.fps*40;
  const offset = maximum-(context.end_frame-context.start_frame);
  for (const spell of context.spells) {
    const x = (offset+spell.start_frame-context.start_frame)/maximum*strip.width;
    const width = (spell.end_frame-spell.start_frame)/maximum*strip.width;
    stripCtx.fillStyle = colours[spell.label];
    stripCtx.globalAlpha = spell.label==='X' ? .35 : 1;
    stripCtx.fillRect(x,0,width,strip.height);
  }
  stripCtx.globalAlpha = 1;
  $('window-duration').textContent = '−40 S';
  const share = $('share-bar'), shareCtx = share.getContext('2d');
  shareCtx.clearRect(0,0,share.width,share.height);
  const home = context.home_percent;
  $('home-percent').textContent = home===null ? '—' : `${home}%`;
  $('away-percent').textContent = home===null ? '—' : `${100-home}%`;
  if (home!==null) {
    shareCtx.fillStyle = colours.A; shareCtx.fillRect(0,0,share.width,share.height);
    shareCtx.fillStyle = colours.H; shareCtx.fillRect(0,0,share.width*home/100,share.height);
  }
  const list = $('recent-spells'); list.replaceChildren();
  for (const spell of context.spells.slice(-3).reverse()) {
    const item = document.createElement('li');
    const key = document.createElement('i'); key.className='spell-key'; key.dataset.label=spell.label;
    const label = document.createElement('span'); label.textContent=spell.label;
    const range = document.createElement('span'); range.className='spell-range';
    range.textContent=`${String(spell.start_frame).padStart(6,'0')}→${String(spell.end_frame-1).padStart(6,'0')}`;
    const duration = document.createElement('span'); duration.className='spell-duration';
    duration.textContent=`${((spell.end_frame-spell.start_frame)/meta.fps).toFixed(1)}s`;
    item.append(key,label,range,duration); list.append(item);
  }
  if (!context.spells.length) {
    const empty = document.createElement('li'); empty.className='empty-spells';
    empty.textContent='No prediction loaded'; list.append(empty);
  }
}

function setPlaying(value) {
  clock.seek(displayed, performance.now());
  if (value) clock.play(performance.now()); else clock.pause(performance.now());
  $('loading').hidden = true;
  $('play').textContent = clock.playing ? 'Pause' : 'Play';
  $('play').setAttribute('aria-label',clock.playing ? 'Pause' : 'Play');
  $('play').title = `${clock.playing ? 'Pause' : 'Play'} (Space)`;
}

async function show(frame, generation) {
  const start = Math.floor(frame/BLOCK)*BLOCK;
  const waiting = !cache.has(start);
  if (waiting) { $('loading').textContent = 'Loading frame window…'; $('loading').hidden = false; }
  contextController?.abort();
  const controller = new AbortController(); contextController = controller;
  try {
    const [rows, context] = await Promise.all([blockAt(frame),api(`/api/context?frame=${frame}`,{signal:controller.signal})]);
    if (generation !== epoch) return;
    draw(rows[frame-start]); drawContext(context); $('loading').hidden = true;
    if (waiting) clock.seek(frame, performance.now());
    const next = start + BLOCK;
    if (next < meta.n_frames && pending.size < 2) blockAt(next).catch(() => {});
  } catch (error) {
    if (generation !== epoch) return;
    setPlaying(false); $('loading').hidden = false; $('loading').textContent = error.message;
    $('message').textContent = 'Source unavailable. Verify the local files and restart if they changed.';
  }
}

async function seek(frame) {
  if (!Number.isInteger(frame) || frame < 0 || frame >= meta.n_frames) {
    $('message').textContent = `Enter a whole frame from 0 to ${meta.n_frames-1}.`; return;
  }
  setPlaying(false); clock.seek(frame, performance.now()); const generation = ++epoch;
  await show(frame, generation);
}

function tick(now) {
  requestAnimationFrame(tick);
  if (!clock || !clock.playing || busy) return;
  const target = clock.frameAt(now);
  if (target === displayed) return;
  busy = true;
  const generation = epoch;
  show(target, generation).finally(() => {
    busy = false;
    if (generation === epoch && displayed === meta.n_frames-1) setPlaying(false);
  });
}

async function initialise() {
  try {
    while (true) {
      meta = await api('/api/meta');
      if (meta.status === 'error') throw new Error(meta.message);
      if (meta.status === 'ready') break;
      $('loading').textContent = `Validating and indexing local tracking… ${Math.floor(meta.progress*100)}%`;
      await new Promise(resolve => setTimeout(resolve, 300));
    }
    clock = new Playback(meta.n_frames, meta.fps);
    $('source').textContent = meta.synthetic ? 'SYNTHETIC DEMO / NO MATCH DATA' : 'TACTICAL TRACKING / LOCAL FILES';
    $('source-note').textContent = meta.synthetic
      ? 'An invented match to explore the viewer. No real match data is included.'
      : `Positions: tactical ATD. ${meta.has_predictions ? 'Possession: loaded model CSV (startup snapshot).' : 'No prediction CSV loaded.'} Files stay local; restart to change inputs.`;
    $('teams').textContent = `${meta.teams[0]}  /  ${meta.teams[1]}`;
    $('home-name').textContent = meta.teams[0]; $('away-name').textContent = meta.teams[1];
    $('dimensions').textContent = `${meta.pitch[0]} × ${meta.pitch[1]} m · ${meta.fps} fps`;
    $('hud-fps').textContent = ` · ${meta.fps} FPS`;
    $('timeline').max = $('jump').max = meta.n_frames-1;
    $('duration').textContent = `${videoTime(meta.n_frames-1,meta.fps)} · ${meta.n_frames.toLocaleString('en-US')} frames`;
    for (const id of ['play','previous','next','timeline','jump','jump-button','speed','estimate-players']) $(id).disabled = false;
    $('estimate-players').addEventListener('change', () => {if (currentRow) draw(currentRow);});
    const initialFrame = meta.initial_frame ?? 0;
    clock.seek(initialFrame, performance.now());
    await show(initialFrame,epoch);
    $('play').addEventListener('click', () => {
      epoch++;
      if (displayed === meta.n_frames-1) { seek(0); return; }
      setPlaying(!clock.playing);
    });
    $('previous').addEventListener('click', () => seek(displayed-1));
    $('next').addEventListener('click', () => seek(displayed+1));
    $('timeline').addEventListener('input', event => seek(Number(event.target.value)));
    $('jump-form').addEventListener('submit', event => {event.preventDefault(); seek(Number($('jump').value));});
    $('speed').addEventListener('change', event => { epoch++; clock.seek(displayed,performance.now()); clock.speed = Number(event.target.value); });
    document.addEventListener('keydown', event => {
      if (/INPUT|SELECT|BUTTON|TEXTAREA/.test(event.target.tagName) || event.ctrlKey || event.metaKey || event.altKey) return;
      if (event.code === 'Space') {event.preventDefault(); $('play').click();}
      if (event.key === 'ArrowRight') {event.preventDefault(); seek(Math.min(meta.n_frames-1,displayed+1));}
      if (event.key === 'ArrowLeft') {event.preventDefault(); seek(Math.max(0,displayed-1));}
    });
    document.addEventListener('visibilitychange', () => { if (document.hidden && clock.playing) {epoch++; setPlaying(false);} });
    requestAnimationFrame(tick);
  } catch (error) {
    $('loading').textContent = error.message; $('message').textContent = 'Source could not be loaded. Fix the local inputs and restart.';
  }
}

initialise();
