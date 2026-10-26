// Draws the Recall Rush app icon and splash and writes them into an Android project's res/ folder.
// No dependencies: it renders the orange-ring logo (the `.dot` in index.html) itself and writes PNGs with node:zlib.
// Called by scripts/patch-android.mjs, so `npm run android:add` and the cloud build do it automatically.
//
//   node scripts/make-assets.mjs [path/to/res]               write the Android resources
//   node scripts/make-assets.mjs --preview assets/preview    also write preview PNGs (not used by the build)
//
// Logo = `.dot` in index.html: a ring, dark (#2a2c31) with an orange (#fb4a1c) top/right arc, turned -20 degrees.
// Ring proportions are the CSS ones (26px box, 5px border). Change the colours here if the app colours change.
import { writeFileSync, readFileSync, existsSync, mkdirSync } from "node:fs";
import { join, dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { deflateSync, inflateSync } from "node:zlib";

export const COLORS = {
  orange: "#fb4a1c", dark: "#2a2c31",
  iconBg: "#fcfbfd",    // launcher icon background (the app's card colour)
  splashBg: "#e4e4e6",  // splash + system bars (the app's page colour)
  bar: "#e4e4e6",
};
const hex = (h) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16));
const ORANGE = hex(COLORS.orange), DARK = hex(COLORS.dark);

/* ---------- tiny PNG encoder ---------- */
const CRC = (() => { const t = new Uint32Array(256); for (let n = 0; n < 256; n++) { let c = n; for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1; t[n] = c >>> 0; } return t; })();
const crc32 = (b) => { let c = 0xffffffff; for (let i = 0; i < b.length; i++) c = CRC[(c ^ b[i]) & 255] ^ (c >>> 8); return (c ^ 0xffffffff) >>> 0; };
function chunk(type, data) {
  const out = Buffer.alloc(12 + data.length);
  out.writeUInt32BE(data.length, 0); out.write(type, 4, "ascii"); data.copy(out, 8);
  out.writeUInt32BE(crc32(out.subarray(4, 8 + data.length)), 8 + data.length);
  return out;
}
export function encodePng(w, h, rgba) {
  const raw = Buffer.alloc((w * 4 + 1) * h);
  for (let y = 0; y < h; y++) { raw[y * (w * 4 + 1)] = 0; rgba.copy(raw, y * (w * 4 + 1) + 1, y * w * 4, (y + 1) * w * 4); }
  const ihdr = Buffer.alloc(13); ihdr.writeUInt32BE(w, 0); ihdr.writeUInt32BE(h, 4); ihdr[8] = 8; ihdr[9] = 6;
  return Buffer.concat([Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]), chunk("IHDR", ihdr), chunk("IDAT", deflateSync(raw, { level: 9 })), chunk("IEND", Buffer.alloc(0))]);
}

/* ---------- the logo ---------- */
// colour of the ring at (dx,dy) from its centre, or null if the point is not on the ring. D = outer diameter in px.
function ringAt(dx, dy, D, mode) {
  const R = D / 2, t = D * (5 / 26), d = Math.hypot(dx, dy);
  if (d > R || d < R - t) return null;
  // the CSS element is rotated -20deg, so look the point up in the un-rotated ring
  let a = (Math.atan2(dy, dx) * 180) / Math.PI + 20;
  if (a > 180) a -= 360;
  const orange = a > -135 && a < 45;          // border-top + border-right are orange
  if (mode === "mono") return [0, 0, 0, orange ? 1 : 0.55];
  const c = orange ? ORANGE : DARK;
  return [c[0], c[1], c[2], 1];
}

// kind: "fg" ring only | "mono" | "square" | "round" (ring on the icon background)
// ringFrac: ring outer diameter as a fraction of the canvas
function render(S, W, H, ringFrac, kind) {
  const SS = S <= 600 ? 4 : 3, buf = Buffer.alloc(W * H * 4), bg = hex(COLORS.iconBg);
  const D = Math.min(W, H) * ringFrac, cx = W / 2, cy = H / 2, rad = Math.min(W, H) * 0.2;
  const inBg = (x, y) => {
    if (kind === "square") {          // rounded square, full bleed
      const qx = Math.abs(x - cx) - (W / 2 - rad), qy = Math.abs(y - cy) - (H / 2 - rad);
      return Math.hypot(Math.max(qx, 0), Math.max(qy, 0)) + Math.min(Math.max(qx, qy), 0) <= rad;
    }
    if (kind === "round") return Math.hypot(x - cx, y - cy) <= Math.min(W, H) / 2;
    return false;
  };
  for (let py = 0; py < H; py++) for (let px = 0; px < W; px++) {
    let r = 0, g = 0, b = 0, a = 0;
    for (let sy = 0; sy < SS; sy++) for (let sx = 0; sx < SS; sx++) {
      const x = px + (sx + 0.5) / SS, y = py + (sy + 0.5) / SS;
      let c = null;
      const ring = ringAt(x - cx, y - cy, D, kind);
      if (ring) c = ring;
      else if (inBg(x, y)) c = [bg[0], bg[1], bg[2], 1];
      if (c) { r += c[0] * c[3]; g += c[1] * c[3]; b += c[2] * c[3]; a += c[3]; }
    }
    const o = (py * W + px) * 4, n = SS * SS;
    if (a > 0) { buf[o] = Math.round(r / a); buf[o + 1] = Math.round(g / a); buf[o + 2] = Math.round(b / a); buf[o + 3] = Math.round((a / n) * 255); }
  }
  return encodePng(W, H, buf);
}

/* ---------- what goes where ---------- */
const DENS = { mdpi: 1, hdpi: 1.5, xhdpi: 2, xxhdpi: 3, xxxhdpi: 4 };
const XML_ICON = `<?xml version="1.0" encoding="utf-8"?>
<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android">
    <background android:drawable="@color/rr_icon_bg"/>
    <foreground android:drawable="@mipmap/rr_icon_fg"/>
    <monochrome android:drawable="@mipmap/rr_icon_mono"/>
</adaptive-icon>
`;
const XML_SPLASH = `<?xml version="1.0" encoding="utf-8"?>
<layer-list xmlns:android="http://schemas.android.com/apk/res/android">
    <item android:drawable="@color/rr_splash_bg"/>
    <item>
        <bitmap android:src="@drawable/rr_splash_icon" android:gravity="center"/>
    </item>
</layer-list>
`;
const XML_COLORS = `<?xml version="1.0" encoding="utf-8"?>
<resources>
    <color name="rr_icon_bg">${COLORS.iconBg}</color>
    <color name="rr_splash_bg">${COLORS.splashBg}</color>
    <color name="rr_bar">${COLORS.bar}</color>
    <color name="rr_orange">${COLORS.orange}</color>
    <color name="rr_dark">${COLORS.dark}</color>
</resources>
`;

export function generateAssets(res, opts = {}) {
  const log = [];
  const put = (rel, data) => {
    const f = join(res, rel);
    if (existsSync(f) && Buffer.compare(readFileSync(f), Buffer.isBuffer(data) ? data : Buffer.from(data)) === 0) return false;
    if (!opts.dry) { mkdirSync(dirname(f), { recursive: true }); writeFileSync(f, data); }
    return true;
  };
  let n = 0;
  for (const [d, m] of Object.entries(DENS)) {
    const legacy = Math.round(48 * m), adaptive = Math.round(108 * m), splash = Math.round(288 * m);
    n += put(`mipmap-${d}/ic_launcher.png`, render(legacy, legacy, legacy, 0.6, "square"));
    n += put(`mipmap-${d}/ic_launcher_round.png`, render(legacy, legacy, legacy, 0.58, "round"));
    n += put(`mipmap-${d}/rr_icon_fg.png`, render(adaptive, adaptive, adaptive, 0.5, "fg"));      // inside the 66dp safe zone of 108dp
    n += put(`mipmap-${d}/rr_icon_mono.png`, render(adaptive, adaptive, adaptive, 0.5, "mono"));
    n += put(`drawable-${d}/rr_splash_icon.png`, render(splash, splash, splash, 128 / 288, "fg")); // 128dp ring on a 288dp canvas
  }
  n += put("mipmap-anydpi-v26/ic_launcher.xml", XML_ICON);
  n += put("mipmap-anydpi-v26/ic_launcher_round.xml", XML_ICON);
  n += put("drawable/rr_splash.xml", XML_SPLASH);
  n += put("values/rr_colors.xml", XML_COLORS);
  log.push(n ? "icon, splash and colour resources written (" + n + " files changed)" : "icon and splash resources already up to date");
  return log;
}

export function writePreviews(dir) {
  mkdirSync(dir, { recursive: true });
  // composite helper: adaptive icon = bg + fg masked (circle / rounded square), on a mid-grey home screen
  const out = (name, w, h, fn) => { const b = Buffer.alloc(w * h * 4); fn(b, w, h); writeFileSync(join(dir, name), encodePng(w, h, b)); };
  writeFileSync(join(dir, "icon-adaptive-foreground-432.png"), render(432, 432, 432, 0.5, "fg"));
  writeFileSync(join(dir, "icon-legacy-192.png"), render(192, 192, 192, 0.6, "square"));
  writeFileSync(join(dir, "icon-round-192.png"), render(192, 192, 192, 0.58, "round"));
  writeFileSync(join(dir, "icon-512.png"), render(512, 512, 512, 0.6, "square"));
  // splash as the phone shows it (1080 x 1920, ring centred, 128dp @ 3x = 384px)
  out("splash-portrait-1080x1920.png", 1080, 1920, (b, w, h) => {
    const bg = hex(COLORS.splashBg); for (let i = 0; i < w * h; i++) { b[i * 4] = bg[0]; b[i * 4 + 1] = bg[1]; b[i * 4 + 2] = bg[2]; b[i * 4 + 3] = 255; }
    const ic = 864, png = render(ic, ic, ic, 128 / 288, "fg");
    const raw = decodeSimple(png); const ox = (w - ic) / 2, oy = (h - ic) / 2;
    for (let y = 0; y < ic; y++) for (let x = 0; x < ic; x++) { const s = (y * ic + x) * 4, o = ((oy + y) * w + ox + x) * 4, a = raw[s + 3] / 255; for (let k = 0; k < 3; k++) b[o + k] = Math.round(raw[s + k] * a + b[o + k] * (1 - a)); }
  });
}
// minimal decoder for the PNGs this file writes (filter 0, RGBA8) - used only for the preview composite
function decodeSimple(png) {
  let p = 8, idat = [], w = 0, h = 0;
  while (p < png.length) { const len = png.readUInt32BE(p), type = png.toString("ascii", p + 4, p + 8); if (type === "IHDR") { w = png.readUInt32BE(p + 8); h = png.readUInt32BE(p + 12); } if (type === "IDAT") idat.push(png.subarray(p + 8, p + 8 + len)); p += 12 + len; }
  const raw = inflateSync(Buffer.concat(idat)), out = Buffer.alloc(w * h * 4);
  for (let y = 0; y < h; y++) raw.copy(out, y * w * 4, y * (w * 4 + 1) + 1, (y + 1) * (w * 4 + 1));
  return out;
}

// run directly
if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const args = process.argv.slice(2), pi = args.indexOf("--preview");
  if (pi >= 0) { writePreviews(args[pi + 1] || "assets/preview"); console.log("previews written to " + (args[pi + 1] || "assets/preview")); args.splice(pi, 2); }
  const res = args[0] || join(dirname(fileURLToPath(import.meta.url)), "..", "android", "app", "src", "main", "res");
  if (args[0] || pi < 0) console.log(generateAssets(res).join("\n"));
}
