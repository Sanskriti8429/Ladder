PAGE = '''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ladder: market maker replay</title>
<style>
:root{--bg:#f4f5f7;--panel:#ffffff;--fg:#14171c;--mut:#6b7280;--line:#e4e6eb;--bid:#0f9d6b;--ask:#d64545;--accent:#2f6df6;--bidbg:rgba(15,157,107,.18);--askbg:rgba(214,69,69,.18)}
@media (prefers-color-scheme:dark){:root{--bg:#0d0f12;--panel:#15181d;--fg:#e8eaee;--mut:#8b93a1;--line:#252a32;--bid:#34d399;--ask:#f87171;--accent:#7aa7ff;--bidbg:rgba(52,211,153,.2);--askbg:rgba(248,113,113,.2)}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:14px/1.45 ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;font-variant-numeric:tabular-nums}
.wrap{max-width:1180px;margin:0 auto;padding:22px 16px 36px}
header{margin-bottom:14px}
h1{font-size:21px;margin:0 0 4px;letter-spacing:-.01em;display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.tag{font-size:11px;font-weight:600;letter-spacing:.04em;text-transform:uppercase;color:var(--mut);border:1px solid var(--line);border-radius:999px;padding:2px 9px}
.note{color:var(--mut);font-size:12.5px;max-width:760px}
.bar{display:flex;align-items:center;gap:12px;background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:10px 14px;margin-bottom:12px}
button{font:inherit;cursor:pointer;border:1px solid var(--line);background:var(--panel);color:var(--fg);border-radius:8px;padding:6px 14px}
button.primary{background:var(--accent);border-color:var(--accent);color:#fff;font-weight:600;min-width:84px}
input[type=range]{flex:1;accent-color:var(--accent);min-width:80px}
.seg{display:flex;border:1px solid var(--line);border-radius:8px;overflow:hidden}
.seg button{border:0;border-radius:0;padding:6px 11px;background:transparent;color:var(--mut)}
.seg button.on{background:var(--accent);color:#fff}
.clock{min-width:96px;text-align:right;color:var(--mut)}
.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:12px}
.kpi{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:12px 14px}
.kpi span{display:block;color:var(--mut);font-size:11.5px;text-transform:uppercase;letter-spacing:.05em}
.kpi b{font-size:27px;font-weight:650;letter-spacing:-.02em}
.pos{color:var(--bid)}
.neg{color:var(--ask)}
.grid{display:grid;grid-template-columns:minmax(290px,370px) 1fr;gap:12px;align-items:start}
.panel{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:12px 14px}
.panel h2{font-size:11.5px;font-weight:600;text-transform:uppercase;letter-spacing:.05em;color:var(--mut);margin:0 0 8px}
.right{display:grid;gap:12px}
.two{display:grid;grid-template-columns:1fr 1fr;gap:12px}
canvas{width:100%;display:block}
#price{height:290px}
#inv,#pnl{height:170px}
.legend{display:flex;gap:16px;flex-wrap:wrap;color:var(--mut);font-size:12px;margin-bottom:4px}
.legend i{display:inline-block;width:12px;height:3px;border-radius:2px;margin-right:6px;vertical-align:middle}
.legend i.dot{width:8px;height:8px;border-radius:50%}
.lad{display:grid;gap:2px}
.row{position:relative;display:grid;grid-template-columns:70px 1fr 44px 52px;align-items:center;height:25px;border-radius:4px;overflow:hidden}
.row .fill{position:absolute;top:0;bottom:0;right:0}
.row.ask .fill{background:var(--askbg)}
.row.bid .fill{background:var(--bidbg)}
.row i,.row em,.row u{position:relative;font-style:normal;text-decoration:none}
.row i{grid-column:1;padding-left:8px;font-weight:600}
.row.ask i{color:var(--ask)}
.row.bid i{color:var(--bid)}
.row em{grid-column:3;text-align:right}
.row u{grid-column:4;justify-self:center;font-size:10.5px;font-weight:700}
.row u:not(:empty){border:1px solid currentColor;border-radius:4px;padding:0 5px;line-height:15px}
.midrow{display:flex;justify-content:space-between;padding:7px 8px;margin:3px 0;border-top:1px solid var(--line);border-bottom:1px solid var(--line);font-weight:600}
.midrow span+span{color:var(--mut);font-weight:500}
@media (max-width:820px){.grid{grid-template-columns:1fr}.kpis{grid-template-columns:repeat(2,1fr)}.two{grid-template-columns:1fr}}
</style>
</head>
<body>
<div class="wrap">
<header>
<h1>ladder: market maker replay <span class="tag">synthetic book, not market data</span></h1>
<div class="note" id="note"></div>
</header>
<div class="bar">
<button class="primary" id="play">pause</button>
<input id="slider" type="range" min="0" value="0">
<span class="clock" id="clock"></span>
<div class="seg" id="speed"><button data-s="1">1x</button><button data-s="3" class="on">3x</button><button data-s="10">10x</button></div>
</div>
<div class="kpis">
<div class="kpi"><span>mid (ticks)</span><b id="k_mid"></b></div>
<div class="kpi"><span>inventory (units)</span><b id="k_inv"></b></div>
<div class="kpi"><span>profit and loss (ticks)</span><b id="k_pnl"></b></div>
<div class="kpi"><span>fills so far</span><b id="k_fills"></b></div>
</div>
<div class="grid">
<div class="panel"><h2>Order book</h2><div class="lad" id="ladder"></div></div>
<div class="right">
<div class="panel">
<h2>Price and our quotes (last 120 steps)</h2>
<div class="legend"><span><i style="background:var(--fg)"></i>mid</span><span><i style="background:var(--bid)"></i>our bid</span><span><i style="background:var(--ask)"></i>our ask</span><span><i class="dot" style="background:var(--bid)"></i>we bought</span><span><i class="dot" style="background:var(--ask)"></i>we sold</span></div>
<canvas id="price"></canvas>
</div>
<div class="two">
<div class="panel"><h2>Inventory</h2><canvas id="inv"></canvas></div>
<div class="panel"><h2>Profit and loss</h2><canvas id="pnl"></canvas></div>
</div>
</div>
</div>
</div>
<script>
const D = __DATA__;
const F = D.frames;
const N = F.length;
const WIN = 120;
const PADL = 46, PADR = 10, PADT = 8, PADB = 20;
const $ = id => document.getElementById(id);
const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
let t = 0, timer = null, speed = 3;

const cum = [];
let run = 0;
let maxQ = 1;
F.forEach(f => {
  run += f.fills.length;
  cum.push(run);
  f.asks.concat(f.bids).forEach(l => { if (l[1] > maxQ) maxQ = l[1]; });
});

$("note").textContent = D.note;
$("slider").max = N - 1;

let html = "";
for (let i = 0; i < 8; i++) html += '<div class="row ask"><div class="fill"></div><i></i><em></em><u></u></div>';
html += '<div class="midrow"><span id="m_mid"></span><span id="m_spr"></span></div>';
for (let i = 0; i < 8; i++) html += '<div class="row bid"><div class="fill"></div><i></i><em></em><u></u></div>';
$("ladder").innerHTML = html;
const askRows = $("ladder").querySelectorAll(".row.ask");
const bidRows = $("ladder").querySelectorAll(".row.bid");

function setRow(el, lvl, ours) {
  if (!lvl) { el.style.visibility = "hidden"; return; }
  el.style.visibility = "visible";
  el.querySelector("i").textContent = lvl[0];
  el.querySelector("em").textContent = lvl[1];
  el.querySelector("u").textContent = lvl[0] === ours ? "ours" : "";
  el.querySelector(".fill").style.width = (100 * lvl[1] / maxQ) + "%";
}

function drawLadder(f) {
  for (let k = 0; k < 8; k++) {
    setRow(askRows[k], f.asks[7 - k], f.ask_quote);
    setRow(bidRows[k], f.bids[k], f.bid_quote);
  }
  $("m_mid").textContent = "mid " + f.mid.toFixed(1);
  const sp = f.asks.length && f.bids.length ? f.asks[0][0] - f.bids[0][0] : 0;
  $("m_spr").textContent = "spread " + sp + (sp === 1 ? " tick" : " ticks");
}

function prep(id) {
  const c = $(id), r = c.getBoundingClientRect(), d = window.devicePixelRatio || 1;
  c.width = Math.round(r.width * d);
  c.height = Math.round(r.height * d);
  const g = c.getContext("2d");
  g.setTransform(d, 0, 0, d, 0, 0);
  return {g: g, w: r.width, h: r.height};
}

function grid(g, w, h, lo, hi, dec) {
  g.font = "11px ui-sans-serif, system-ui, sans-serif";
  g.textAlign = "right";
  g.textBaseline = "middle";
  for (let k = 0; k <= 3; k++) {
    const v = lo + (hi - lo) * k / 3;
    const y = h - PADB - (h - PADB - PADT) * k / 3;
    g.strokeStyle = css("--line");
    g.lineWidth = 1;
    g.beginPath();
    g.moveTo(PADL, y);
    g.lineTo(w - PADR, y);
    g.stroke();
    g.fillStyle = css("--mut");
    g.fillText(v.toFixed(dec), PADL - 6, y);
  }
}

function xlabels(g, w, h, a, b) {
  g.fillStyle = css("--mut");
  g.font = "11px ui-sans-serif, system-ui, sans-serif";
  g.textBaseline = "alphabetic";
  g.textAlign = "left";
  g.fillText("step " + a, PADL, h - 5);
  g.textAlign = "right";
  g.fillText("step " + b, w - PADR, h - 5);
}

function trace(g, X, Y, get, from, to, stepped) {
  g.beginPath();
  for (let i = from; i <= to; i++) {
    const x = X(i);
    if (i === from) {
      g.moveTo(x, Y(get(i)));
    } else if (stepped) {
      g.lineTo(x, Y(get(i - 1)));
      g.lineTo(x, Y(get(i)));
    } else {
      g.lineTo(x, Y(get(i)));
    }
  }
  g.stroke();
}

function drawPrice() {
  const c = prep("price"), g = c.g, w = c.w, h = c.h;
  const a = Math.max(0, t - WIN + 1);
  const b = Math.min(N - 1, a + WIN - 1);
  let lo = Infinity, hi = -Infinity;
  for (let i = a; i <= t; i++) {
    lo = Math.min(lo, F[i].bid_quote, F[i].mid);
    hi = Math.max(hi, F[i].ask_quote, F[i].mid);
  }
  if (hi - lo < 6) { const m = (hi + lo) / 2; lo = m - 3; hi = m + 3; }
  lo -= 0.5;
  hi += 0.5;
  const X = i => PADL + (w - PADL - PADR) * (i - a) / Math.max(1, b - a);
  const Y = v => h - PADB - (h - PADB - PADT) * (v - lo) / (hi - lo);
  grid(g, w, h, lo, hi, 1);
  g.globalAlpha = 0.16;
  g.fillStyle = css("--accent");
  g.beginPath();
  for (let i = a; i <= t; i++) {
    if (i === a) g.moveTo(X(i), Y(F[i].ask_quote)); else g.lineTo(X(i), Y(F[i].ask_quote));
  }
  for (let i = t; i >= a; i--) g.lineTo(X(i), Y(F[i].bid_quote));
  g.closePath();
  g.fill();
  g.globalAlpha = 1;
  g.lineJoin = "round";
  g.lineWidth = 1;
  g.strokeStyle = css("--ask");
  trace(g, X, Y, i => F[i].ask_quote, a, t, false);
  g.strokeStyle = css("--bid");
  trace(g, X, Y, i => F[i].bid_quote, a, t, false);
  g.lineWidth = 1.8;
  g.strokeStyle = css("--fg");
  trace(g, X, Y, i => F[i].mid, a, t, false);
  for (let i = a; i <= t; i++) {
    F[i].fills.forEach(m => {
      g.fillStyle = css(m[0] === "buy" ? "--bid" : "--ask");
      g.strokeStyle = css("--panel");
      g.lineWidth = 1.5;
      g.beginPath();
      g.arc(X(i), Y(m[1]), 4, 0, 6.2832);
      g.fill();
      g.stroke();
    });
  }
  xlabels(g, w, h, a, b);
}

function drawSeries(id, get, stepped, dec) {
  const c = prep(id), g = c.g, w = c.w, h = c.h;
  let lo = 0, hi = 0;
  for (let i = 0; i < N; i++) { const v = get(i); if (v < lo) lo = v; if (v > hi) hi = v; }
  const pad = Math.max(1, (hi - lo) * 0.08);
  lo -= pad;
  hi += pad;
  const X = i => PADL + (w - PADL - PADR) * i / Math.max(1, N - 1);
  const Y = v => h - PADB - (h - PADB - PADT) * (v - lo) / (hi - lo);
  grid(g, w, h, lo, hi, dec);
  g.setLineDash([4, 4]);
  g.strokeStyle = css("--mut");
  g.lineWidth = 1;
  g.beginPath();
  g.moveTo(PADL, Y(0));
  g.lineTo(w - PADR, Y(0));
  g.stroke();
  g.setLineDash([]);
  g.lineJoin = "round";
  g.strokeStyle = css("--accent");
  g.globalAlpha = 0.28;
  g.lineWidth = 1.25;
  trace(g, X, Y, get, 0, N - 1, stepped);
  g.globalAlpha = 1;
  g.lineWidth = 2;
  trace(g, X, Y, get, 0, t, stepped);
  g.setLineDash([3, 4]);
  g.strokeStyle = css("--mut");
  g.lineWidth = 1;
  g.beginPath();
  g.moveTo(X(t), PADT);
  g.lineTo(X(t), h - PADB);
  g.stroke();
  g.setLineDash([]);
  g.fillStyle = css("--accent");
  g.beginPath();
  g.arc(X(t), Y(get(t)), 4, 0, 6.2832);
  g.fill();
  xlabels(g, w, h, 0, N - 1);
}

function render() {
  const f = F[t];
  $("slider").value = t;
  $("clock").textContent = "step " + t + " / " + (N - 1);
  $("k_mid").textContent = f.mid.toFixed(1);
  $("k_inv").textContent = (f.q > 0 ? "+" : "") + f.q;
  const p = $("k_pnl");
  p.textContent = (f.pnl >= 0 ? "+" : "") + f.pnl.toFixed(1);
  p.className = f.pnl >= 0 ? "pos" : "neg";
  $("k_fills").textContent = cum[t];
  drawLadder(f);
  drawPrice();
  drawSeries("inv", i => F[i].q, true, 0);
  drawSeries("pnl", i => F[i].pnl, false, 0);
}

function pause() {
  clearInterval(timer);
  timer = null;
  $("play").textContent = t >= N - 1 ? "replay" : "play";
}

function play() {
  if (timer) return;
  if (t >= N - 1) t = 0;
  $("play").textContent = "pause";
  timer = setInterval(() => {
    t = Math.min(N - 1, t + speed);
    render();
    if (t >= N - 1) pause();
  }, 100);
}

$("play").onclick = () => { if (timer) pause(); else play(); };
$("slider").oninput = e => { t = +e.target.value; render(); if (!timer) pause(); };
document.querySelectorAll("#speed button").forEach(b => {
  b.onclick = () => {
    speed = +b.dataset.s;
    document.querySelectorAll("#speed button").forEach(x => x.classList.remove("on"));
    b.classList.add("on");
  };
});
document.addEventListener("keydown", e => {
  if (e.target.tagName === "INPUT") return;
  if (e.code === "Space") { e.preventDefault(); if (timer) pause(); else play(); }
  else if (e.code === "ArrowRight") { t = Math.min(N - 1, t + 1); render(); }
  else if (e.code === "ArrowLeft") { t = Math.max(0, t - 1); render(); }
  else if (e.code === "Home") { t = 0; render(); }
});
window.onresize = render;
render();
play();
</script>
</body>
</html>
'''