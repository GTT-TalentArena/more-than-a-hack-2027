import { Playback, videoTime } from '/playback.mjs';

const $ = id => document.getElementById(id);
const canvas = $('pitch'), ctx = canvas.getContext('2d');
const colours = {H: '#e9ad64', A: '#86b9c9'};
const descriptions = {H: 'Home possession', A: 'Away possession', D: 'Dead ball', X: 'Model abstention'};
const BLOCK = 125, MAX_CACHE = 4;
const cache = new Map(), pending = new Map();
let meta, clock, displayed = 0, epoch = 0, busy = false;

async function api(path) {
  const response = await fetch(path, {cache: 'no-store', credentials: 'omit'});
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
  const [length, width] = meta.pitch;
  const padding = 66, scale = Math.min((canvas.width - 2 * padding) / length, (canvas.height - 2 * padding) / width);
  const left = (canvas.width - length * scale) / 2, top = (canvas.height - width * scale) / 2;
  const point = ([x, y]) => [left + x * scale, top + y * scale];
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.fillStyle = '#203b2f'; ctx.fillRect(left, top, length * scale, width * scale);
  ctx.fillStyle = '#ffffff03';
  for (let i = 0; i < 10; i += 2) ctx.fillRect(left + i * length * scale / 10, top, length * scale / 10, width * scale);
  ctx.strokeStyle = '#b4c5a76b'; ctx.lineWidth = 1.5;
  function rect(x,y,w,h) { const [px,py] = point([x,y]); ctx.strokeRect(px,py,w*scale,h*scale); }
  function circle(x,y,r) { const [px,py] = point([x,y]); ctx.beginPath(); ctx.arc(px,py,r*scale,0,Math.PI*2); ctx.stroke(); }
  rect(0,0,length,width); rect(length/2,0,0,width); circle(length/2,width/2,9.15);
  for (const side of [0,1]) {
    rect(side ? length-16.5 : 0,(width-40.32)/2,16.5,40.32);
    rect(side ? length-5.5 : 0,(width-18.32)/2,5.5,18.32);
    rect(side ? length : -2,(width-7.32)/2,2,7.32);
    circle(side ? length-11 : 11,width/2,.12);
  }
  circle(length/2,width/2,.12);
  let out = 0;
  row.players.forEach((xy, index) => {
    if (!xy) return;
    const [x,y] = point(xy);
    const outside = xy[0]<0 || xy[0]>length || xy[1]<0 || xy[1]>width;
    if (outside) out++;
    ctx.beginPath(); ctx.arc(x,y,8.5,0,Math.PI*2); ctx.fillStyle = colours[meta.slot_teams[index]]; ctx.fill();
    ctx.strokeStyle = '#101b16'; ctx.lineWidth = 2; ctx.stroke();
  });
  if (row.ball) {
    const [x,y] = point(row.ball);
    if (row.ball[0]<0 || row.ball[0]>length || row.ball[1]<0 || row.ball[1]>width) out++;
    ctx.beginPath(); ctx.arc(x,y,6,0,Math.PI*2); ctx.fillStyle = '#fff9e8'; ctx.fill();
    ctx.strokeStyle = '#101b16'; ctx.lineWidth = 2; ctx.stroke();
    ctx.beginPath(); ctx.arc(x,y,12,0,Math.PI*2); ctx.strokeStyle = '#fff9e866'; ctx.lineWidth = 1; ctx.stroke();
  }
  $('label').textContent = row.label ?? '—';
  $('label-description').textContent = descriptions[row.label] ?? 'No prediction loaded';
  $('possession').dataset.label = row.label ?? 'none';
  $('frame').textContent = row.frame.toLocaleString('en-US');
  $('time').textContent = $('timeline-time').textContent = videoTime(row.frame, meta.fps);
  $('observed').textContent = `${row.players.filter(Boolean).length} / ${meta.slot_ids.length}`;
  $('ball-status').textContent = row.ball ? 'Observed' : 'No observation';
  $('period').textContent = periodAt(row.frame);
  $('timeline').value = row.frame; $('jump').value = row.frame;
  $('message').textContent = out ? `${out} observation(s) outside the pitch. Coordinates are preserved; distant points may be outside the viewport.` : meta.synthetic ? 'Synthetic demo · invented tracking and model labels.' : 'Local source · original observations and model labels.';
  displayed = row.frame;
  $('previous').disabled = displayed === 0;
  $('next').disabled = displayed === meta.n_frames-1;
}

function setPlaying(value) {
  clock.seek(displayed, performance.now());
  if (value) clock.play(performance.now()); else clock.pause(performance.now());
  $('loading').hidden = true;
  $('play').textContent = clock.playing ? 'Pause' : 'Play';
}

async function show(frame, generation) {
  const start = Math.floor(frame/BLOCK)*BLOCK;
  const waiting = !cache.has(start);
  if (waiting) { $('loading').textContent = 'Loading frame window…'; $('loading').hidden = false; }
  try {
    const rows = await blockAt(frame);
    if (generation !== epoch) return;
    draw(rows[frame-start]); $('loading').hidden = true;
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
    $('source-note').textContent = meta.synthetic ? 'An invented match to explore the viewer. No real match data is included.' : 'Read-only session. Files stay on this computer. Restart the command to change inputs.';
    $('teams').textContent = `${meta.teams[0]}  /  ${meta.teams[1]}`;
    $('home-name').textContent = meta.teams[0]; $('away-name').textContent = meta.teams[1];
    $('dimensions').textContent = `${meta.pitch[0]} × ${meta.pitch[1]} m · ${meta.fps} fps`;
    $('timeline').max = $('jump').max = meta.n_frames-1;
    $('duration').textContent = `${videoTime(meta.n_frames-1,meta.fps)} · ${meta.n_frames.toLocaleString('en-US')} frames`;
    for (const id of ['play','previous','next','timeline','jump','jump-button','speed']) $(id).disabled = false;
    await show(0,epoch);
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
