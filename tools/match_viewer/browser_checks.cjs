// Canvas instrumentation stays inside the local page. Return booleans only.
async function installBallProbe(page) {
  await page.addInitScript(() => {
    const prototype = CanvasRenderingContext2D.prototype;
    const original = {clearRect:prototype.clearRect, arc:prototype.arc, fill:prototype.fill};
    window.__viewerBallProbe = {arcs:[],current:null};
    prototype.clearRect = function (...args) {
      if (this.canvas.id==='pitch') window.__viewerBallProbe.arcs=[];
      return original.clearRect.apply(this,args);
    };
    prototype.arc = function (...args) {
      if (this.canvas.id==='pitch') window.__viewerBallProbe.current=args.slice(0,3);
      return original.arc.apply(this,args);
    };
    prototype.fill = function (...args) {
      if (this.canvas.id==='pitch' && this.fillStyle.toLowerCase()==='#e8ff2e')
        window.__viewerBallProbe.arcs.push(window.__viewerBallProbe.current);
      return original.fill.apply(this,args);
    };
  });
}

async function ballMatchesFrame(page, frame) {
  return page.evaluate(async expected => {
    const row = (await (await fetch(`/api/frames?start=${expected}&count=1`)).json()).frames[0];
    const meta = await (await fetch('/api/meta')).json();
    const arcs = window.__viewerBallProbe.arcs;
    if (row.ball===null) return arcs.length===0;
    if (arcs.length!==1) return false;
    const canvas = document.querySelector('#pitch');
    const scale = Math.min((canvas.width-68)/meta.pitch[0],(canvas.height-68)/meta.pitch[1]);
    const expectedPoint = [(canvas.width-meta.pitch[0]*scale)/2+row.ball[0]*scale,
      (canvas.height-meta.pitch[1]*scale)/2+row.ball[1]*scale,.62*scale];
    return expectedPoint.every((value,index)=>Math.abs(value-arcs[0][index])<1e-7);
  },frame);
}

module.exports = {installBallProbe,ballMatchesFrame};
