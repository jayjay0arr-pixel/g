// Run once after `cap add android` (npm run android:add does it for you).
// Safe to run again: it only changes what is not already patched, and says what it did.
//
//   node scripts/patch-android.mjs [path/to/AndroidManifest.xml] [path/to/styles.xml]
//   node scripts/patch-android.mjs --check [same paths]     change nothing; exit 1 if anything is not patched (used by the workflow)
//
// What it sets up
//   1. Storage: lets the app write to the shared Documents folder (Batch 1).
//   2. Rotation: the main activity follows the phone's auto-rotate setting
//      (android:screenOrientation="user"). With auto-rotate off the phone stays in whatever
//      orientation the user locked it to (portrait on a normal phone). With auto-rotate on, the app turns
//      to landscape when you turn the phone. configChanges keeps the web view alive while it rotates.
//   3. Keyboard: android:windowSoftInputMode="adjustResize", so the page shrinks when the phone keyboard
//      opens instead of the keyboard covering the fields.
//   4. Edge-to-edge opt-out: apps built for Android 15 (targetSdk 35, which Capacitor 7 uses) are forced to draw
//      under the status/navigation bars, and in that mode adjustResize alone no longer shrinks the page for the
//      keyboard (Capacitor 7's own handler does not pass the keyboard inset on). Setting
//      windowOptOutEdgeToEdgeEnforcement in the app themes gives the classic behaviour back: solid system bars,
//      page sits between them, adjustResize works. Android ignores this opt-out only for apps that target
//      Android 16 (API 36) or higher, so step 6 pins targetSdkVersion to 35.
//   5. Look (Batch 3): app icon (adaptive + legacy + themed), splash, status/navigation bar colours matching the app.
//      The artwork is drawn by scripts/make-assets.mjs; this script wires it into the manifest and themes.
//   6. Pin targetSdkVersion = 35 in android/variables.gradle (keeps step 4 valid; compileSdk must be >= 35).
//   7. Sharing exports: makes sure the FileProvider paths cover Documents/ and the app cache (Share sheet needs it).
//   8. Fixed debug signing key (signing/debug.keystore) so every build can be installed over the previous one.
import { readFileSync, writeFileSync as realWrite, existsSync } from "node:fs";
import { generateAssets } from "./make-assets.mjs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const argv = process.argv.slice(2), CHECK = argv.includes("--check"), pos = argv.filter((a) => !a.startsWith("--"));
const pending = [];                                   // --check: what is not patched yet
const writeFileSync = (f, d) => { if (CHECK) pending.push("would change " + f); else realWrite(f, d); };
const manifestFile = pos[0] || join(root, "android", "app", "src", "main", "AndroidManifest.xml");
const stylesFile = pos[1] || join(dirname(manifestFile), "res", "values", "styles.xml");
if (!existsSync(manifestFile)) { console.error("AndroidManifest.xml not found: " + manifestFile + "\nRun `npx cap add android` first."); process.exit(1); }

const log = [];

/* ---------- small XML helpers (attribute-level edits, everything else is left alone) ---------- */
const esc = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
const getAttr = (tag, name) => { const m = tag.match(new RegExp("(?<![\\w:])" + esc(name) + '\\s*=\\s*"([^"]*)"')); return m ? m[1] : null; };
function setAttr(tag, name, value) {
  const re = new RegExp("((?<![\\w:])" + esc(name) + '\\s*=\\s*")[^"]*(")');
  if (re.test(tag)) return tag.replace(re, (_, a, b) => a + value + b);
  const ind = (tag.match(/\n([ \t]+)android:/) || [, "            "])[1];
  return tag.replace(/^<(activity|application)\b/, (m, n) => "<" + n + "\n" + ind + name + '="' + value + '"');
}

/* ---------- 1 + 2 + 3: manifest ---------- */
let x = readFileSync(manifestFile, "utf8");
const before = x;

// 1. storage permissions (Batch 1)
const perms = [
  '<uses-permission android:name="android.permission.READ_EXTERNAL_STORAGE" android:maxSdkVersion="32" />',
  '<uses-permission android:name="android.permission.WRITE_EXTERNAL_STORAGE" android:maxSdkVersion="29" />',
];
for (const p of perms) {
  const name = p.match(/android:name="([^"]+)"/)[1];
  if (!x.includes(name)) { x = x.replace("</manifest>", "    " + p + "\n</manifest>"); log.push("added permission " + name.split(".").pop()); }
}
if (!x.includes("requestLegacyExternalStorage")) {
  if (!/<application\b/.test(x)) { console.error("No <application> tag found."); process.exit(1); }
  x = x.replace(/<application\b/, '<application\n        android:requestLegacyExternalStorage="true"');
  log.push("set requestLegacyExternalStorage");
}

// 5a. launcher icon names (the artwork itself is written by make-assets.mjs below)
{
  const app = x.match(/<application\b[^>]*>/)[0];
  let app2 = app;
  for (const [attr, val] of [["android:icon", "@mipmap/ic_launcher"], ["android:roundIcon", "@mipmap/ic_launcher_round"]]) {
    if (getAttr(app2, attr) !== val) { log.push(attr + " -> " + val); app2 = setAttr(app2, attr, val); }
  }
  if (app2 !== app) x = x.replace(app, () => app2);
}

// find the main activity's opening tag
const tags = x.match(/<activity\b[^>]*>/g) || [];
const act = tags.find((t) => /android:name\s*=\s*"[^"]*MainActivity"/.test(t)) || tags[0];
if (!act) { console.error("No <activity> tag found in the manifest."); process.exit(1); }
let a2 = act;

// 2. rotation: follow the user's auto-rotate setting; never lock to one orientation
if (getAttr(a2, "android:screenOrientation") !== "user") {
  log.push("screenOrientation " + (getAttr(a2, "android:screenOrientation") || "(none)") + " -> user");
  a2 = setAttr(a2, "android:screenOrientation", "user");
}
// rotating must not restart the activity (a restart would reload the web view)
const needCC = ["orientation", "screenSize", "smallestScreenSize", "screenLayout", "keyboardHidden", "keyboard"];
const haveCC = (getAttr(a2, "android:configChanges") || "").split("|").map((s) => s.trim()).filter(Boolean);
const missCC = needCC.filter((t) => !haveCC.includes(t));
if (missCC.length) {
  log.push("configChanges += " + missCC.join("|"));
  a2 = setAttr(a2, "android:configChanges", haveCC.concat(missCC).join("|"));
}

// 3. keyboard: shrink the page instead of covering it (keeps any state flag such as stateHidden)
const wsm = (getAttr(a2, "android:windowSoftInputMode") || "").split("|").map((s) => s.trim()).filter(Boolean);
const wsmOk = wsm.includes("adjustResize") && !wsm.some((t) => /^adjust/.test(t) && t !== "adjustResize");
if (!wsmOk) {
  const next = wsm.filter((t) => !/^adjust/.test(t)).concat("adjustResize").join("|");
  log.push("windowSoftInputMode " + (wsm.join("|") || "(none)") + " -> " + next);
  a2 = setAttr(a2, "android:windowSoftInputMode", next);
}
if (a2 !== act) x = x.replace(act, () => a2);
if (x !== before) writeFileSync(manifestFile, x);

/* ---------- 4 + 5: themes: edge-to-edge opt-out, system bar colours, splash ---------- */
// <item> helpers: set an item's value (replace it if present, else append it)
const itemRe = (name) => new RegExp('<item\\s+name="' + esc(name) + '"[^>]*>[\\s\\S]*?</item>');
function upsertItem(body, name, value, onlyIfPresent) {
  const line = '<item name="' + name + '">' + value + "</item>";
  const m = body.match(itemRe(name));
  if (m) return m[0] === line ? body : body.replace(m[0], line);
  if (onlyIfPresent) return body;
  const ind = (body.match(/\n([ \t]+)<item/) || [, "        "])[1];
  return body.replace(/\s*$/, "") + "\n" + ind + line + "\n    ";
}
const BAR_ITEMS = [   // status + navigation bar: the app's own colour, dark icons
  ["android:windowOptOutEdgeToEdgeEnforcement", "true"],
  ["android:statusBarColor", "@color/rr_bar"],
  ["android:navigationBarColor", "@color/rr_bar"],
  ["android:windowLightStatusBar", "true"],
  ["android:windowLightNavigationBar", "true"],
];
if (existsSync(stylesFile)) {
  let st = readFileSync(stylesFile, "utf8");
  const st0 = st;
  let hit = 0;
  for (const theme of ["AppTheme", "AppTheme.NoActionBar", "AppTheme.NoActionBarLaunch"]) {
    const re = new RegExp('(<style\\s+name="' + esc(theme) + '"([^>]*)>)([\\s\\S]*?)(</style>)');
    const m = st.match(re);
    if (!m) continue;
    hit++;
    let body = m[3];
    const b0 = body;
    for (const [n, v] of BAR_ITEMS) body = upsertItem(body, n, v);
    // Capacitor's default indigo (colorPrimary / colorPrimaryDark / colorAccent), if the theme sets them
    body = upsertItem(body, "colorPrimary", "@color/rr_dark", true);
    body = upsertItem(body, "colorPrimaryDark", "@color/rr_bar", true);
    body = upsertItem(body, "colorAccent", "@color/rr_orange", true);
    if (theme === "AppTheme.NoActionBarLaunch") {
      body = upsertItem(body, "android:background", "@drawable/rr_splash");
      if (/SplashScreen/.test(m[2])) {           // Android 12+ system splash (androidx core-splashscreen attributes)
        body = upsertItem(body, "windowSplashScreenBackground", "@color/rr_splash_bg");
        body = upsertItem(body, "windowSplashScreenAnimatedIcon", "@drawable/rr_splash_icon");
      }
    }
    if (body !== b0) { st = st.replace(re, (_, o, _a, _b, c) => o + body + c); log.push("system bars / splash / edge-to-edge opt-out set in theme " + theme); }
  }
  if (!hit) console.warn("WARNING: none of the expected themes (AppTheme, AppTheme.NoActionBar) found in " + stylesFile + ". The keyboard may cover fields on Android 15+ and the bars keep their default colour.");
  if (st !== st0) writeFileSync(stylesFile, st);
} else {
  console.warn("WARNING: " + stylesFile + " not found, edge-to-edge opt-out and bar colours skipped.");
}

/* ---------- 5: icon + splash artwork ---------- */
const resDir = join(dirname(manifestFile), "res");
for (const l of generateAssets(resDir, { dry: CHECK })) { if (!/already up to date/.test(l)) log.push(l); }

/* ---------- 6: targetSdkVersion = 35 ---------- */
const androidDir = join(dirname(manifestFile), "..", "..", "..");
const vars = join(androidDir, "variables.gradle");
if (existsSync(vars)) {
  let t = readFileSync(vars, "utf8");
  const tm = t.match(/targetSdkVersion\s*=\s*(\d+)/), cm = t.match(/compileSdkVersion\s*=\s*(\d+)/);
  if (!tm) console.warn("WARNING: no targetSdkVersion in variables.gradle; add `targetSdkVersion = 35` to the ext block.");
  else if (+tm[1] !== 35) {
    log.push("targetSdkVersion " + tm[1] + " -> 35 (the edge-to-edge opt-out stops working at 36)");
    t = t.replace(/(targetSdkVersion\s*=\s*)\d+/, "$135"); writeFileSync(vars, t);
  }
  if (cm && +cm[1] < 35) console.warn("WARNING: compileSdkVersion is " + cm[1] + "; it must be at least 35.");
} else console.warn("WARNING: " + vars + " not found; could not pin targetSdkVersion.");

/* ---------- 7: FileProvider paths (Share sheet needs Documents/ and the cache) ---------- */
const fpFile = join(dirname(manifestFile), "res", "xml", "file_paths.xml");
if (existsSync(fpFile)) {
  let fp = readFileSync(fpFile, "utf8"); const fp0 = fp;
  const add = [];
  if (!/<external-path\b/.test(fp)) add.push('<external-path name="rr_external" path="." />');
  if (!/<cache-path\b/.test(fp)) add.push('<cache-path name="rr_cache" path="." />');
  if (add.length) { fp = fp.replace("</paths>", "    " + add.join("\n    ") + "\n</paths>"); log.push("file_paths.xml += " + add.length + " path(s)"); }
  if (fp !== fp0) writeFileSync(fpFile, fp);
} else console.warn("WARNING: " + fpFile + " not found; the Share sheet may not be able to open exported files.");

/* ---------- 8: fixed debug signing key ---------- */
// A fresh CI runner makes a new random debug key each time, and Android refuses to install an APK over one
// signed with a different key. signing/debug.keystore (standard debug credentials, not a secret) fixes that.
const gradleFile = join(androidDir, "app", "build.gradle");
const keystore = join(root, "signing", "debug.keystore");
const MARK = "// recall-rush: fixed debug keystore";
if (existsSync(gradleFile)) {
  let g = readFileSync(gradleFile, "utf8");
  if (!g.includes(MARK)) {
    if (!existsSync(keystore)) console.warn("WARNING: signing/debug.keystore is missing, so builds will use a random debug key (updates will need an uninstall first).");
    else if (!/buildTypes\s*\{/.test(g)) console.warn("WARNING: no buildTypes block in app/build.gradle; fixed debug key not set.");
    else {
      const ind = (g.match(/\n([ \t]+)buildTypes\s*\{/) || [, "    "])[1];
      const blk = [MARK, "signingConfigs {", "    debug {", '        storeFile rootProject.file("../signing/debug.keystore")', '        storePassword "android"', '        keyAlias "androiddebugkey"', '        keyPassword "android"', "    }", "}", ""].map((l) => (l ? ind + l : "")).join("\n");
      g = g.replace(/([ \t]*)buildTypes\s*\{/, (m) => blk + m); writeFileSync(gradleFile, g); log.push("app/build.gradle: fixed debug keystore");
    }
  }
} else console.warn("WARNING: " + gradleFile + " not found; fixed debug key not set.");

/* ---------- result ---------- */
if (CHECK) {
  if (pending.length || log.length) { console.error("NOT PATCHED:\n - " + log.concat(pending).join("\n - ")); process.exit(1); }
  console.log("OK: the Android project has every patch (rotation, keyboard, edge-to-edge opt-out, bar colours, icon, splash, targetSdk 35, share paths, debug key).");
} else console.log(log.length ? "Android project patched:\n - " + log.join("\n - ") : "Android project already patched. Nothing to do.");
