import json
import sys

import numpy as np

from ladder.orderbook import OrderBook

EVENTS = 10
TARGET = 60
MM_BASE = 10 ** 9
STEPS = 400
SIGMA, K, G = 0.633, 1.92, 1.0
SEED = int(sys.argv[1]) if len(sys.argv) > 1 else 5

PAGE = '''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ladder replay</title>
<style>
:root{--bg:#fff;--fg:#1a1a1a;--mut:#667;--bid:#1a8f5a;--ask:#c23b3b;--line:#2a6fdb;--grid:#e3e3e8}
@media (prefers-color-scheme:dark){:root{--bg:#14161a;--fg:#e8e8ea;--mut:#9aa;--bid:#3ecf8e;--ask:#ff6b6b;--line:#6aa4ff;--grid:#2b2e35}}
body{margin:0;padding:16px;background:var(--bg);color:var(--fg);font:14px/1.4 system-ui,sans-serif}
h1{font-size:18px;margin:0 0 4px}
.sub{color:var(--mut);margin-bottom:6px}
.row{display:flex;gap:12px;flex-wrap:wrap}
.card{flex:1 1 320px;border:1px solid var(--grid);border-radius:8px;padding:10px}
canvas{width:100%;height:240px;display:block}
.stats{display:flex;gap:24px;margin:10px 0;flex-wrap:wrap;color:var(--mut)}
.stats b{display:block;font-size:18px;color:var(--fg)}
.ctl{display:flex;gap:10px;align-items:center;margin:10px 0}
input[type=range]{flex:1}
button{padding:4px 14px}
</style>
</head>
<body>
<h1>ladder: market maker replay</h1>
<div class="sub" id="note"></div>
<div class="ctl"><button id="play">play</button><input id="slider" type="range" min="0" value="0"><span id="label"></span><select id="speed"><option value="1">1x</option><option value="4" selected>4x</option><option value="16">16x</option></select></div>
<div class="stats"><div>step<b id="s_t">0</b></div><div>mid (ticks)<b id="s_mid"></b></div><div>inventory<b id="s_inv"></b></div><div>profit and loss (ticks)<b id="s_pnl"></b></div><div>fills so far<b id="s_fills"></b></div></div>
<div class="row">
<div class="card"><div class="sub">order book, top 8 levels (outlined row: our quote)</div><canvas id="book"></canvas></div>
<div class="card"><div class="sub">mid and our quotes (dots: our fills, green buy, red sell)</div><canvas id="price"></canvas></div>
<div class="card"><div class="sub">inventory</div><canvas id="inv"></canvas></div>
<div class="card"><div class="sub">profit and loss</div><canvas id="pnl"></canvas></div>
</div>
<script>
const D = __DATA__;
const F = D.frames;
const $ = id => document.getElementById(id);
const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const mid = F.map(f => f.mid), bq = F.map(f => f.bid_quote), aq = F.map(f => f.ask_quote);
const inv = F.map(f => f.q), pnl = F.map(f => f.pnl);
let t = 0, timer = null;
$("slider").max = F.length - 1;
$("note").textContent = D.note;

function setup(id) {
  const c = $(id), r = c.getBoundingClientRect(), d = window.devicePixelRatio || 1;
  c.width = r.width * d;
  c.height = r.height * d;
  const g = c.getContext("2d");
  g.setTransform(d, 0, 0, d, 0, 0);
  return [g, r.width, r.height];
}

function drawBook(f) {
  const [g, w, h] = setup("book");
  const rows = [];
  f.asks.slice().reverse().forEach(l => rows.push([l, "ask"]));
  f.bids.forEach(l => rows.push([l, "bid"]));
  const mx = Math.max(1, ...rows.map(r => r[0][1]));
  const rh = h / rows.length;
  g.font = "12px system-ui";
  g.textBaseline = "middle";
  rows.forEach((r, i) => {
    const p = r[0][0], q = r[0][1], y = i * rh;
    g.globalAlpha = 0.55;
    g.fillStyle = css(r[1] === "ask" ? "--ask" : "--bid");
    g.fillRect(60, y + 1, (w - 120) * q / mx, rh - 2);
    g.globalAlpha = 1;
    g.fillStyle = css("--fg");
    g.textAlign = "left";
    g.fillText(p, 4, y + rh / 2);
    g.textAlign = "right";
    g.fillText(q, w - 4, y + rh / 2);
    if ((r[1] === "bid" && p === f.bid_quote) || (r[1] === "ask" && p === f.ask_quote)) {
      g.strokeStyle = css("--fg");
      g.lineWidth = 2;
      g.strokeRect(58, y + 1, w - 62, rh - 2);
    }
  });
}

function lineChart(id, series, upto) {
  const [g, w, h] = setup(id);
  const all = series.flatMap(s => s.v);
  let lo = Math.min(...all), hi = Math.max(...all);
  if (hi === lo) { hi += 1; lo -= 1; }
  const pad = 40;
  const X = i => pad + (w - pad - 6) * i / (F.length - 1);
  const Y = v => h - 14 - (h - 24) * (v - lo) / (hi - lo);
  g.strokeStyle = css("--grid");
  g.lineWidth = 1;
  g.beginPath();
  g.moveTo(pad, 4);
  g.lineTo(pad, h - 14);
  g.lineTo(w - 4, h - 14);
  g.stroke();
  g.fillStyle = css("--mut");
  g.font = "11px system-ui";
  g.textAlign = "right";
  g.textBaseline = "middle";
  g.fillText(hi.toFixed(1), pad - 3, 8);
  g.fillText(lo.toFixed(1), pad - 3, h - 18);
  series.forEach(s => {
    g.strokeStyle = css(s.c);
    g.lineWidth = s.w;
    g.beginPath();
    for (let i = 0; i <= upto; i++) {
      const x = X(i), y = Y(s.v[i]);
      if (i) g.lineTo(x, y); else g.moveTo(x, y);
    }
    g.stroke();
  });
  return {g: g, X: X, Y: Y};
}

function render() {
  const f = F[t];
  $("slider").value = t;
  $("label").textContent = t + " / " + (F.length - 1);
  $("s_t").textContent = t;
  $("s_mid").textContent = f.mid.toFixed(1);
  $("s_inv").textContent = f.q;
  $("s_pnl").textContent = f.pnl.toFixed(1);
  $("s_fills").textContent = F.slice(0, t + 1).reduce((a, x) => a + x.fills.length, 0);
  drawBook(f);
  const c = lineChart("price", [{v: mid, c: "--fg", w: 1.5}, {v: bq, c: "--bid", w: 1}, {v: aq, c: "--ask", w: 1}], t);
  for (let i = 0; i <= t; i++) {
    F[i].fills.forEach(m => {
      c.g.fillStyle = css(m[0] === "buy" ? "--bid" : "--ask");
      c.g.beginPath();
      c.g.arc(c.X(i), c.Y(m[1]), 3, 0, 7);
      c.g.fill();
    });
  }
  lineChart("inv", [{v: inv, c: "--line", w: 1.5}], t);
  lineChart("pnl", [{v: pnl, c: "--line", w: 1.5}], t);
}

function stop() {
  clearInterval(timer);
  timer = null;
  $("play").textContent = "play";
}

$("slider").oninput = e => { t = +e.target.value; render(); };
$("play").onclick = () => {
  if (timer) { stop(); return; }
  if (t === F.length - 1) t = 0;
  $("play").textContent = "pause";
  timer = setInterval(() => {
    t = Math.min(F.length - 1, t + +$("speed").value);
    render();
    if (t === F.length - 1) stop();
  }, 100);
};
window.onresize = render;
render();
</script>
</body>
</html>
'''


class World:
    def __init__(self, seed):
        self.rng = np.random.default_rng(seed)
        self.book = OrderBook()
        self.live = []
        self.next_id = 0
        self.last_mid = 10000.5
        for p in range(9990, 10000):
            self.add("buy", p, int(self.rng.integers(1, 6)))
        for p in range(10001, 10011):
            self.add("sell", p, int(self.rng.integers(1, 6)))

    def add(self, side, price, qty):
        self.book.add_limit(self.next_id, side, price, qty)
        self.live.append(self.next_id)
        self.next_id += 1

    def mid(self):
        return (self.book.best_bid() + self.book.best_ask()) / 2

    def ensure(self):
        buys, sells = self.book.books["buy"], self.book.books["sell"]
        if not buys and not sells:
            c = int(self.last_mid)
            self.add("buy", c, 3)
            self.add("sell", c + 1, 3)
        elif not buys:
            self.add("buy", self.book.best_ask() - 2, 3)
        elif not sells:
            self.add("sell", self.book.best_bid() + 2, 3)
        self.last_mid = self.mid()

    def cancel_random(self):
        for _ in range(20):
            if not self.live:
                return
            j = int(self.rng.integers(len(self.live)))
            self.live[j], self.live[-1] = self.live[-1], self.live[j]
            if self.book.cancel(self.live.pop()):
                return

    def event(self):
        r = self.rng.random()
        qty = int(self.rng.integers(1, 6))
        bp, ap = self.book.best_bid(), self.book.best_ask()
        p_add = 0.30 if len(self.book.index) < TARGET else 0.20
        if r < p_add:
            self.add("buy", ap - 1 - int(self.rng.integers(0, 5)), qty)
        elif r < 2 * p_add:
            self.add("sell", bp + 1 + int(self.rng.integers(0, 5)), qty)
        elif r < 2 * p_add + 0.10:
            return "buy", (bp + ap) / 2, self.book.market_order("buy", qty)
        elif r < 2 * p_add + 0.20:
            return "sell", (bp + ap) / 2, self.book.market_order("sell", qty)
        else:
            self.cancel_random()
        return None


def spread(tau, gamma):
    return gamma * SIGMA ** 2 * tau + (2 / gamma) * np.log(1 + gamma / K)


def top(levels, reverse, n=8):
    return [[p, sum(q for _, q in levels[p])] for p in sorted(levels, reverse=reverse)[:n]]


def main():
    w = World(SEED)
    gamma = G / (SIGMA ** 2 * STEPS)
    q, cash, prev = 0, 0.0, None
    frames = []
    for t in range(STEPS):
        if prev:
            for oid in prev:
                w.book.cancel(oid)
        w.ensure()
        m = w.mid()
        tau = STEPS - t
        r = m - q * gamma * SIGMA ** 2 * tau
        half = spread(tau, gamma) / 2
        bp, ap = w.book.best_bid(), w.book.best_ask()
        bid = min(int(np.floor(r - half)), ap - 1)
        ask = max(int(np.ceil(r + half)), bp + 1)
        if ask <= bid:
            ask = bid + 1
        ids = (MM_BASE + 2 * t, MM_BASE + 2 * t + 1)
        w.book.add_limit(ids[0], "buy", bid, 1)
        w.book.add_limit(ids[1], "sell", ask, 1)
        prev = ids
        fills = []
        for _ in range(EVENTS):
            out = w.event()
            w.ensure()
            if out:
                side, _, hit = out
                for oid, price, qty in hit:
                    if oid >= MM_BASE:
                        if side == "buy":
                            q -= qty
                            cash += price * qty
                            fills.append(["sell", price])
                        else:
                            q += qty
                            cash -= price * qty
                            fills.append(["buy", price])
        mid = w.mid()
        frames.append({
            "mid": mid,
            "bid_quote": bid,
            "ask_quote": ask,
            "q": q,
            "pnl": cash + q * mid,
            "bids": top(w.book.books["buy"], True),
            "asks": top(w.book.books["sell"], False),
            "fills": fills,
        })
    note = f"Avellaneda-Stoikov inventory quotes, g = {G}, sigma {SIGMA}, k {K}, one unit per side, reposted every step, seed {SEED}. Synthetic book from Entry 26."
    page = PAGE.replace("__DATA__", json.dumps({"note": note, "frames": frames}, separators=(",", ":")))
    with open("docs/replay.html", "w") as f:
        f.write(page)
    total = sum(len(f["fills"]) for f in frames)
    print("frames:", len(frames), " fills:", total, " final inventory:", q,
          " max |q|:", max(abs(f["q"]) for f in frames),
          " final PnL:", round(frames[-1]["pnl"], 1), " file bytes:", len(page))


if __name__ == "__main__":
    main()