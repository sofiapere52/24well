"use strict";
// The wheel handler, pan/reset plugin and refetch helpers below are copied
// from ../HS5/static/app.js. Only the request/response adapter and one-plot
// rendering are specific to 24 WELL GUI. uPlot 1.6.30 is bundled locally.
const byId=$;
let previewCharts=[],previewState={totalT0:0,totalT1:0,inOverview:false};
let zoomDebounceTimer=null,zoomFetchAbort=null,isSyncingZoom=false;
let previewRequest=0,previewParams=null,previewWell=null;
const PREVIEW_DEBOUNCE_MS=250,PREVIEW_ZOOM_FULL_EPS=.001;
const appendLogLine=message=>{$('plotNote').textContent=message;};
function destroyPreviewCharts(){for(const c of previewCharts)c.destroy();previewCharts=[];}
window.invalidatePreview=()=>{
  previewRequest++;previewParams=null;
  if(zoomFetchAbort)zoomFetchAbort.abort();if(zoomDebounceTimer)clearTimeout(zoomDebounceTimer);
  destroyPreviewCharts();$('plotNote').textContent='Settings changed — preview again.';
};
async function fetchPreview(zoomWindow){
  if(!previewParams)throw new DOMException('Preview settings changed','AbortError');
  const request=++previewRequest,config=previewParams;
  if(zoomFetchAbort)zoomFetchAbort.abort();zoomFetchAbort=new AbortController();
  let start=0,end=null;
  if(zoomWindow){start=Math.max(0,zoomWindow[0]);end=Math.min(previewState.totalT1,zoomWindow[1]);if(end<=start)throw new Error('Pan back within the protocol time range');}
  const r=await fetch('/api/preview',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({params:config,well:previewWell,start,end}),signal:zoomFetchAbort.signal});
  const out=await r.json();if(!r.ok)throw new Error(out.detail||'Preview unavailable');
  if(request!==previewRequest||config!==previewParams)throw new DOMException('Stale preview','AbortError');
  $('plotNote').textContent=out.note+` ${out.sample_rate_hz.toLocaleString()} samples/s · ${out.samples.toLocaleString()} samples per on block.`;
  return {...out,t_seconds:out.time,ch1:out.currents_by_well[config.wells[0]],ch2:config.wells[1]?out.currents_by_well[config.wells[1]]:null,y_max:config.amplitude_ma};
}
function onPreviewWheelCapture(e) {
  if (!previewCharts.length) return;
  const wrap =
    e.target && e.target.closest && e.target.closest(".uplot-wrap");
  if (!wrap) return;
  const sec = byId("preview-section");
  if (!sec || !sec.contains(wrap)) return;

  e.preventDefault();
  e.stopPropagation();
  try {
    e.stopImmediatePropagation();
  } catch (_) {}

  const u = previewCharts[0];
  if (!u.scales || !u.scales.x) return;
  const over = u.over;
  const xMin = u.scales.x.min;
  const xMax = u.scales.x.max;
  if (xMin == null || xMax == null) return;
  const xRange = xMax - xMin;
  if (xRange <= 0) return;

  const rect = over.getBoundingClientRect();
  const wpx = rect.width || 1;
  let lx = e.clientX - rect.left;
  lx = Math.min(Math.max(0, lx), wpx);
  const cursorX = xMin + (lx / wpx) * xRange;

  let dy = e.deltaY;
  if (e.deltaMode === 1) dy *= 16;
  if (e.deltaMode === 2) dy *= wpx;
  const step = Math.min(2, Math.abs(dy) / 100 + 0.15);
  const factor = dy < 0 ? Math.pow(0.92, step) : Math.pow(1 / 0.92, step);

  const newRange = xRange * factor;
  const leftPct = (cursorX - xMin) / xRange;
  const newMin = cursorX - leftPct * newRange;
  const newMax = newMin + newRange;
  u.setScale("x", { min: newMin, max: newMax });
}

function wirePreviewWheelCapture() {
  document.addEventListener("wheel", onPreviewWheelCapture, {
    capture: true,
    passive: false,
  });
}

function isFullRange(xMin, xMax) {
  const total = previewState.totalT1 - previewState.totalT0;
  if (total <= 0) return true;
  const visible = xMax - xMin;
  return (
    visible >= total * (1 - PREVIEW_ZOOM_FULL_EPS) &&
    xMin <= previewState.totalT0 + total * PREVIEW_ZOOM_FULL_EPS &&
    xMax >= previewState.totalT1 - total * PREVIEW_ZOOM_FULL_EPS
  );
}

function scheduleZoomRefetch(xMin, xMax) {
  if (zoomDebounceTimer) clearTimeout(zoomDebounceTimer);
  zoomDebounceTimer = setTimeout(async () => {
    if (!previewCharts.length) return;
    try {
      if (isFullRange(xMin, xMax)) {
        // User zoomed all the way back out: rebuild the tiled overview
        // (rather than asking the server for a window that covers
        // everything, which would be wasteful).
        if (!previewState.inOverview) {
          const out = await fetchPreview(null);
          drawPreviewUplot(out);
        }
        return;
      }
      const out = await fetchPreview([xMin, xMax]);
      // A windowed response carries data ONLY for [xMin, xMax]; update
      // existing charts in-place so the user's zoom level is preserved.
      updateChartsData(out, /*preserveScales=*/ true);
      previewState.inOverview = false;
    } catch (e) {
      if (e && e.name !== "AbortError") {
        appendLogLine("Preview refresh failed: " + (e.message || e));
      }
    }
  }, PREVIEW_DEBOUNCE_MS);
}

function updateChartsData(out, preserveScales) {
  if (!previewCharts.length || !out || !out.t_seconds) return;
  const t = out.t_seconds;
  const reset = !preserveScales;
  // Suppress recursive setScale → broadcast → setScale loops when uPlot
  // auto-adjusts the scale during setData.
  isSyncingZoom = true;
  try {
    if (previewCharts[0]) previewCharts[0].setData([t, out.ch1], reset);
    if (previewCharts[1]) previewCharts[1].setData([t, out.ch2], reset);
    if (previewCharts[2] && out.sum_v) {
      previewCharts[2].setData([t, out.sum_v], reset);
    }
  } finally {
    isSyncingZoom = false;
  }
}

function broadcastZoomToOtherCharts(sourceChart, xMin, xMax) {
  if (isSyncingZoom) return;
  isSyncingZoom = true;
  try {
    previewCharts.forEach((c) => {
      if (c !== sourceChart) c.setScale("x", { min: xMin, max: xMax });
    });
  } finally {
    isSyncingZoom = false;
  }
}

// uPlot plugin: scroll-wheel zoom under cursor, click-drag pan,
// double-click → return to overview. Also wires up the cross-chart sync
// and the debounced refetch.
function makeZoomPanPlugin() {
  return {
    hooks: {
      ready: [(u) => {
        const over = u.over;
        const root = u.root;
        let pan = null;

        const onDown = (e) => {
          if (e.button !== 0) return;
          if (!u.scales || !u.scales.x) return;
          if (!root.contains(e.target)) return;
          pan = {
            startX: e.clientX,
            xMin: u.scales.x.min,
            xMax: u.scales.x.max,
            width: over.clientWidth || root.clientWidth || 1,
          };
          over.style.cursor = "grabbing";
        };

        const onMove = (e) => {
          if (!pan) return;
          const dx = e.clientX - pan.startX;
          const range = pan.xMax - pan.xMin;
          const dxVal = (dx / pan.width) * range;
          u.setScale("x", { min: pan.xMin - dxVal, max: pan.xMax - dxVal });
        };

        const onUp = () => {
          pan = null;
          over.style.cursor = "";
        };

        const onDbl = () => {
          // Reset = re-render the full overview (server-side rebuild so the
          // tiled all-reps view is restored, even if we were last in
          // windowed mode).
          fetchPreview(null)
            .then((out) => { if (out) drawPreviewUplot(out); })
            .catch((e) => {
              if (e && e.name !== "AbortError") {
                appendLogLine("Preview reset failed: " + (e.message || e));
              }
            });
        };

        root.addEventListener("mousedown", onDown);
        window.addEventListener("mousemove", onMove);
        window.addEventListener("mouseup", onUp);
        root.addEventListener("dblclick", onDbl);

        u._zoomPanCleanup = () => {
          root.removeEventListener("mousedown", onDown);
          window.removeEventListener("mousemove", onMove);
          window.removeEventListener("mouseup", onUp);
          root.removeEventListener("dblclick", onDbl);
        };
      }],
      destroy: [(u) => { if (u._zoomPanCleanup) u._zoomPanCleanup(); }],
      setScale: [(u, key) => {
        if (key !== "x") return;
        if (isSyncingZoom) return; // ignore programmatic broadcasts
        const xMin = u.scales.x.min;
        const xMax = u.scales.x.max;
        if (xMin == null || xMax == null) return;
        broadcastZoomToOtherCharts(u, xMin, xMax);
        scheduleZoomRefetch(xMin, xMax);
      }],
    },
  };
}

function chartWidth() {
  const wrap = byId("u-ch1");
  if (wrap) return Math.max(300, wrap.clientWidth - 2);
  return Math.max(300, Math.min(920, window.innerWidth - 48));
}

function drawPreviewUplot(out){
  destroyPreviewCharts();
  if(typeof uPlot==='undefined')throw new Error('Local plot library missing');
  const t=out.t_seconds,yMax=Math.max(out.y_max,1e-9);
  previewState={totalT0:t[0],totalT1:t.at(-1),inOverview:true};
  const options={width:chartWidth(),height:320,title:`${previewParams.wells[0]} · commanded current`,
    cursor:{drag:{x:false,y:false}},scales:{x:{time:false},y:{range:[-yMax*1.08,yMax*1.08]}},
    series:[{}, {stroke:'#216344',width:1,label:'mA'}],
    axes:[{stroke:'#42604e',grid:{stroke:'#cdded355'},label:'Time (s)',size:42},
          {stroke:'#42604e',grid:{stroke:'#cdded355'},label:'Amplitude (mA)',size:60}],
    legend:{show:false},plugins:[makeZoomPanPlugin()]};
  $('u-ch2').hidden=!out.ch2;
  isSyncingZoom=true;try{
    previewCharts.push(new uPlot(options,[t,out.ch1],$('u-ch1')));
    if(out.ch2)previewCharts.push(new uPlot({...options,title:`${previewParams.wells[1]} · commanded current`,series:[{},{stroke:'#437da0',width:1,label:'mA'}]},[t,out.ch2],$('u-ch2')));
  }finally{isSyncingZoom=false;}
}
wirePreviewWheelCapture();
action('preview',async()=>{previewParams=params();previewWell=$('previewWell').value;drawPreviewUplot(await fetchPreview(null));});
action('previewReset',async()=>{if(!previewParams){previewParams=params();previewWell=$('previewWell').value;}drawPreviewUplot(await fetchPreview(null));});
$('previewWell').onchange=()=>window.invalidatePreview();
new ResizeObserver(()=>{for(const c of previewCharts){const width=chartWidth();if(c.width!==width)c.setSize({width,height:320});}}).observe($('u-ch1'));
