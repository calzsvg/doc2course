// Small drawing helpers that every long video ended up copying into its own common.js.
// Import them instead of re-writing them:  import { A, head, box, mono, sideText, line } from '/engine/kit.js';
// Coordinates are 1920x1080 canvas pixels; every helper does nothing when its alpha is 0.
import { C, FONT, txt, rrect, arrow, eo, seg, lerp } from '/engine/core.js';
import { MONO } from '/engine/templates.js';

// Reveal of sentence k: 0 -> 1 over the first part [a, b] of that sentence's window.  const a1 = A(S, 1);
export const A = (S, k, a = 0, b = .2) => eo(seg(S.P(k), a, b));

// Slide heading at the top left with a green underline that grows with a; optional gray subheading.
export function head(ctx, s, a, sub = '') {
  if (a <= 0) return;
  txt(ctx, s, 100, 132, { size: 44, weight: 800, alpha: a, maxW: 1500 });
  rrect(ctx, 102, 150, 120 * a, 5, 2, C.green, null, 0, a);
  if (sub) txt(ctx, sub, 100, 194, { size: 26, color: C.gray, alpha: a, maxW: 1700 });
}

// Monospace text (code, bit strings, addresses, register names).
export function mono(ctx, s, x, y, { size = 28, color = C.white, alpha = 1, align = 'left', weight = 600 } = {}) {
  if (alpha <= 0) return;
  ctx.save(); ctx.globalAlpha = alpha; ctx.fillStyle = color; ctx.textAlign = align; ctx.font = `${weight} ${size}px ${MONO}`;
  ctx.fillText(s, x, y); ctx.restore();
}

// Rounded box with a centered label and an optional gray sub-label under it. ty overrides the label's baseline.
export function box(ctx, x, y, w, h, label, { alpha = 1, color = C.white, size = 26, fill = 'rgba(14,20,28,.92)', lw = 2.5, ty, weight = 800, sub = '', subSize } = {}) {
  if (alpha <= 0) return;
  rrect(ctx, x, y, w, h, 10, fill, color, lw, alpha);
  const ss = subSize || size * .7;
  if (label) txt(ctx, label, x + w / 2, ty ?? (y + h / 2 + size * .36 - (sub ? ss * .6 : 0)), { size, weight, align: 'center', color, alpha, maxW: w - 12 });
  if (sub) txt(ctx, sub, x + w / 2, y + h / 2 + ss * 1.1, { size: ss, weight: 600, align: 'center', color: C.gray, alpha, maxW: w - 12 });
}

// Column of paragraphs that wrap on spaces, each revealed on its sentence.
// items: [{ t, k (sentence; omit = always shown), size, color, weight, gap }]. Returns the y below the last line.
export function sideText(ctx, items, S, { x = 100, y = 190, w = 560, size = 30 } = {}) {
  let yy = y;
  items.forEach(it => {
    const a = it.k === undefined ? 1 : eo(seg(S.P(it.k), 0, .2)), sz = it.size || size;
    ctx.save(); ctx.font = `${it.weight || 700} ${sz}px ${FONT}`;
    const words = it.t.split(' '), lines = []; let cur = '';
    for (const wd of words) { const t = cur ? cur + ' ' + wd : wd; if (ctx.measureText(t).width > w && cur) { lines.push(cur); cur = wd; } else cur = t; }
    if (cur) lines.push(cur); ctx.restore();
    if (a > 0) lines.forEach((l, i) => txt(ctx, l, x, yy + sz + i * sz * 1.3, { size: sz, weight: it.weight || 700, color: it.color || C.white, alpha: a }));
    yy += lines.length * sz * 1.3 + (it.gap ?? 18);
  });
  return yy;
}

// Polyline drawn up to prog (0..1) with an arrowhead at the end (head = 0: none); dash e.g. [10, 8].
export function line(ctx, pts, { color = C.gray, lw = 3, alpha = 1, head = 14, dash = null, prog = 1 } = {}) {
  if (alpha <= 0 || prog <= 0) return;
  let L = 0; const seglen = [];
  for (let i = 1; i < pts.length; i++) { const d = Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]); seglen.push(d); L += d; }
  let rem = L * prog; const out = [pts[0]];
  for (let i = 1; i < pts.length && rem > 0; i++) { const d = seglen[i - 1], f = Math.min(1, rem / d); out.push([lerp(pts[i - 1][0], pts[i][0], f), lerp(pts[i - 1][1], pts[i][1], f)]); rem -= d; }
  ctx.save(); ctx.globalAlpha = alpha; ctx.strokeStyle = color; ctx.lineWidth = lw; ctx.lineJoin = 'round'; ctx.lineCap = 'round'; if (dash) ctx.setLineDash(dash);
  ctx.beginPath(); out.forEach((p, i) => (i ? ctx.lineTo(p[0], p[1]) : ctx.moveTo(p[0], p[1]))); ctx.stroke(); ctx.restore();
  if (head && out.length > 1) { const p = out[out.length - 1], q = out[out.length - 2]; arrow(ctx, lerp(q[0], p[0], .9), lerp(q[1], p[1], .9), p[0], p[1], color, lw, 1, alpha, head); }
}

// ---------------------------------------------------------------- computer architecture
// ALU trapezoid with the input notch, centered at (cx, cy).
export function aluShape(ctx, cx, cy, w, h, { alpha = 1, color = C.white, label = 'ALU', size = 26, fill = 'rgba(14,20,28,.92)' } = {}) {
  if (alpha <= 0) return;
  const x0 = cx - w / 2, y0 = cy - h / 2;
  ctx.save(); ctx.globalAlpha = alpha; ctx.strokeStyle = color; ctx.fillStyle = fill; ctx.lineWidth = 3; ctx.lineJoin = 'round';
  ctx.beginPath(); ctx.moveTo(x0, y0); ctx.lineTo(cx - w * .08, y0); ctx.lineTo(cx, y0 + h * .28); ctx.lineTo(cx + w * .08, y0); ctx.lineTo(x0 + w, y0);
  ctx.lineTo(x0 + w * .78, y0 + h); ctx.lineTo(x0 + w * .22, y0 + h); ctx.closePath(); ctx.fill(); ctx.stroke(); ctx.restore();
  if (label) txt(ctx, label, cx, cy + h * .26, { size, weight: 800, align: 'center', color, alpha });
}

// Instruction format / bit fields. fields: [{ name, w (bits), val, color }]; cell: px per bit.
// show: 0..1 or one value per field (reveals the values); hiField: index drawn green; idx: bit numbers under the fields
// (those digits are on-screen numbers: cover them in claims or allow_numbers).
// Returns [[x, width], ...] per field.
export function bitRow(ctx, x, y, cell, fields, { show = 1, h = 70, size = 30, nameSize = 22, idx = true, alpha = 1, hiField = -1, valColor } = {}) {
  let cx = x; const out = [];
  let bit = fields.reduce((s, f) => s + f.w, 0) - 1;
  fields.forEach((f, i) => {
    const w = f.w * cell, a = alpha * (Array.isArray(show) ? show[i] ?? 0 : show), col = f.color || C.white, hiOn = i === hiField;
    out.push([cx, w]);
    rrect(ctx, cx, y, w, h, 6, hiOn ? 'rgba(118,185,0,.22)' : 'rgba(14,20,28,.92)', hiOn ? C.green : 'rgba(255,255,255,.55)', hiOn ? 3 : 2, alpha);
    if (f.name) txt(ctx, f.name, cx + w / 2, y - 14, { size: nameSize, weight: 700, align: 'center', color: hiOn ? C.green : col === C.white ? C.gray : col, alpha, maxW: w + 30 });
    if (f.val !== undefined && a > 0) mono(ctx, String(f.val), cx + w / 2, y + h / 2 + size * .36, { size, align: 'center', color: valColor || col, alpha: a, weight: 700 });
    if (idx) {
      const hiB = bit, loB = bit - f.w + 1;
      txt(ctx, String(hiB), cx + 8, y + h + 24, { size: 17, color: C.gray, alpha: alpha * .9 });
      if (f.w > 1) txt(ctx, String(loB), cx + w - 8, y + h + 24, { size: 17, color: C.gray, alpha: alpha * .9, align: 'right' });
    }
    bit -= f.w; cx += w;
  });
  return out;
}

// Memory / register column. rows: [{ addr, data, color, fill }]; hi: row indexes drawn green; head: [address title, data title].
// Returns each row's center y.
export function memCol(ctx, x, y, w, rh, rows, { alpha = 1, addrW = 180, size = 26, hi = [], hiColor = C.green, addrColor = C.gray, dataSize, head = ['', ''] } = {}) {
  if (alpha <= 0) return rows.map((_, i) => y + i * rh + rh / 2);
  if (head[0]) txt(ctx, head[0], x - 20, y - 16, { size: 22, weight: 700, align: 'right', color: C.gray, alpha });
  if (head[1]) txt(ctx, head[1], x + w / 2, y - 16, { size: 22, weight: 700, align: 'center', color: C.gray, alpha });
  return rows.map((r, i) => {
    const yy = y + i * rh, on = hi.includes(i);
    rrect(ctx, x, yy, w, rh, 0, on ? 'rgba(118,185,0,.22)' : r.fill || 'rgba(14,20,28,.92)', on ? hiColor : 'rgba(255,255,255,.5)', on ? 3 : 1.5, alpha);
    if (r.addr !== undefined) mono(ctx, r.addr, x - 20, yy + rh / 2 + size * .36, { size, align: 'right', color: on ? hiColor : addrColor, alpha });
    if (r.data !== undefined) mono(ctx, r.data, x + w / 2, yy + rh / 2 + (dataSize || size) * .36, { size: dataSize || size, align: 'center', color: r.color || C.white, alpha });
    return yy + rh / 2;
  });
}
