// Playback follows elapsed time, independently of drawing frequency.
export class Playback {
  constructor(nFrames, fps) {
    this.nFrames = nFrames; this.fps = fps; this.speed = 1;
    this.playing = false; this.anchorFrame = 0; this.anchorTime = 0;
  }
  frameAt(now) {
    const elapsed = this.playing ? Math.max(0, now - this.anchorTime) / 1000 : 0;
    return Math.min(this.nFrames - 1, this.anchorFrame + Math.floor(elapsed * this.fps * this.speed));
  }
  seek(frame, now) {
    if (!Number.isInteger(frame) || frame < 0 || frame >= this.nFrames) throw new RangeError('Invalid video frame.');
    this.anchorFrame = frame; this.anchorTime = now;
  }
  pause(now) { this.seek(this.frameAt(now), now); this.playing = false; }
  play(now) { this.anchorTime = now; this.playing = true; }
}

export function videoTime(frame, fps) {
  const hundredths = Math.floor(frame * 100 / fps);
  const seconds = Math.floor(hundredths / 100);
  return `${String(Math.floor(seconds / 60)).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')}.${String(hundredths % 100).padStart(2, '0')}`;
}
