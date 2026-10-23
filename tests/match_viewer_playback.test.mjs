import test from 'node:test';
import assert from 'node:assert/strict';
import {Playback, videoTime} from '../tools/match_viewer/static/playback.mjs';

test('elapsed time determines frame at every speed, regardless of redraw count', () => {
  for (const speed of [.25,.5,1,2]) {
    const clock = new Playback(199319,25); clock.speed = speed; clock.seek(100,500); clock.play(500);
    for (let now=500;now<2500;now+=7) clock.frameAt(now);
    assert.equal(clock.frameAt(2500),100+Math.floor(2*25*speed));
  }
});
test('pause, seek, resume and half boundaries preserve one exact frame', () => {
  const clock = new Playback(199319,25); clock.seek(90651,0); clock.play(0);
  assert.equal(clock.frameAt(40),90652);
  clock.pause(40); assert.equal(clock.frameAt(5000),90652);
  clock.seek(110808,5000); clock.play(5000); assert.equal(clock.frameAt(5040),110809);
  clock.seek(199318,6000); assert.equal(clock.frameAt(200000),199318);
  for (const invalid of [-1,199319,1.5,NaN]) assert.throws(() => clock.seek(invalid,0),RangeError);
});
test('video time is derived from the zero-based frame with exact hundredths', () => {
  assert.equal(videoTime(0,25),'00:00.00');
  assert.equal(videoTime(26,25),'00:01.04');
  assert.equal(videoTime(199318,25),'132:52.72');
});
