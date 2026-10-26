/* Recall Rush native layer (Android via Capacitor).
   - first launch: creates Documents/RecallRush/{ESAS,MATH,EE}
   - keeps Documents/RecallRush/recall-rush-data.json in sync with the app
   - drives the sync status chip in the header
   - Android back button
   Also works in a plain browser: it just skips the native parts. */
(function () {
  "use strict";
  var TK = "ff_topics_v2", PK = "ff_progress_v1";
  var ROOT = "RecallRush", FILE = ROOT + "/recall-rush-data.json", CATS = ["ESAS", "MATH", "EE"];

  var cap = window.Capacitor || null, native = false;
  try { native = !!(cap && cap.isNativePlatform && cap.isNativePlatform()); } catch (e) {}
  var plug = (cap && cap.Plugins) || {};
  var FS = native ? plug.Filesystem : null;
  var APP = native ? plug.App : null;

  var rawSet = Storage.prototype.setItem, rawGet = Storage.prototype.getItem;
  var dir = null, timer = 0, busy = false, again = false, last = "";

  /* ---------- status chip ---------- */
  function status(st, short, path, title) {
    var b = document.getElementById("sv");
    if (!b) return;
    b.setAttribute("data-st", st);
    var t = document.getElementById("svt"), p = document.getElementById("svp");
    if (t) t.textContent = short;
    if (p) p.textContent = path || "";
    b.title = title || "";
  }
  function showOk() {
    if (dir === "DOCUMENTS") status("ok", "Synced", " to Documents/RecallRush", "Saved to Documents/RecallRush/recall-rush-data.json. Tap to sync now.");
    else status("warn", "Saved in app only", "", "The Documents folder wasn't available, so your data is in the app's private storage. Tap to retry.");
  }
  function showErr(e) {
    status("err", "Not synced", "", "Couldn't write the data file: " + String((e && e.message) || e) + ". Tap to retry.");
  }

  /* ---------- helpers ---------- */
  function readLS(k) { try { return JSON.parse(rawGet.call(window.localStorage, k) || "null"); } catch (e) { return null; } }

  function build() {
    var T = readLS(TK) || {}, Pr = readLS(PK);
    var o = { v: 1, t: T.t || [], f: T.f || [], c: T.c || {}, r: T.r || {}, l: T.l || "medium", s: T.s || 0 };
    if (Pr) o.p = Pr;
    o.ts = Math.max(T.ts || 0, (Pr && Pr.ts) || 0) || Date.now();
    return JSON.stringify(o);
  }

  async function ensure(d) {
    for (var i = 0; i < CATS.length; i++) {
      try { await FS.mkdir({ path: ROOT + "/" + CATS[i], directory: d, recursive: true }); }
      catch (e) { if (!/exist/i.test(String((e && e.message) || e))) throw e; }
    }
  }
  async function readFile(d) {
    try {
      var r = await FS.readFile({ path: FILE, directory: d, encoding: "utf8" });
      return typeof r.data === "string" ? r.data : null;
    } catch (e) { return null; }
  }
  function writeTo(d, str) {
    return FS.writeFile({ path: FILE, data: str, directory: d, encoding: "utf8", recursive: true });
  }

  /* ---------- sync ---------- */
  function hasData(str) {
    try { var j = JSON.parse(str); return !!((j.t && j.t.length) || (j.f && j.f.length) || (j.p && j.p.xp > 0)); }
    catch (e) { return false; }
  }
  var fileHasData = false;   // the data file on disk currently holds real content

  async function flush(force) {
    if (!FS || !dir) return;
    clearTimeout(timer);
    if (busy) { again = true; return; }
    /* Safety: if the app's own storage has been wiped (no topics key at all) but the file still
       holds your data, never overwrite the file with an empty copy. */
    if (!readLS(TK) && fileHasData) return;
    var str = build();
    if (!force && str === last) return;
    busy = true;
    try {
      try { await writeTo(dir, str); }
      catch (e) {
        if (dir !== "DOCUMENTS") throw e;
        dir = "DATA";                      // fall back to the app's private folder
        await ensure("DATA");
        await writeTo("DATA", str);
      }
      last = str;
      fileHasData = hasData(str);
      showOk();
    } catch (e) { showErr(e); }
    busy = false;
    if (again) { again = false; schedule(); }
  }
  function schedule() { clearTimeout(timer); timer = setTimeout(function () { flush(false); }, 700); }

  /* when the app saves, mirror it to the file */
  Storage.prototype.setItem = function (k, v) {
    rawSet.call(this, k, v);
    if (FS && this === window.localStorage && (k === TK || k === PK)) schedule();
  };

  function seed(txt) {
    var j;
    try { j = JSON.parse(txt); } catch (e) { return; }
    if (!j || !Array.isArray(j.t)) return;
    var T = readLS(TK);
    if (!T || (j.ts || 0) > (T.ts || 0)) {
      rawSet.call(window.localStorage, TK, JSON.stringify({ v: 1, t: j.t, f: j.f || [], c: j.c || {}, r: j.r || {}, l: j.l || "medium", s: j.s || 0, ts: j.ts || Date.now() }));
    }
    var Pl = readLS(PK);
    if (j.p && typeof j.p.xp === "number" && (!Pl || (j.p.ts || 0) > (Pl.ts || 0))) {
      rawSet.call(window.localStorage, PK, JSON.stringify(j.p));
    }
  }

  async function init() {
    if (!FS) {
      status("ok", "Saved in this browser", "", "Not running as the Android app, so data stays in this browser.");
      return;
    }
    status("idle", "Starting", "", "");
    try { if (FS.requestPermissions) await FS.requestPermissions(); } catch (e) {}
    dir = "DOCUMENTS";
    try { await ensure("DOCUMENTS"); }
    catch (e) {
      dir = "DATA";
      try { await ensure("DATA"); } catch (e2) { dir = null; }
    }
    if (!dir) { status("err", "Not saved", "", "Couldn't open any storage folder."); return; }
    var txt = await readFile(dir);
    if (txt === null && dir === "DOCUMENTS") txt = await readFile("DATA");
    if (txt) { seed(txt); fileHasData = hasData(txt); }
    await flush(true);                    // creates the data file on first launch
  }

  /* ---------- Android back button ---------- */
  function curPage() {
    var a = ["play", "bank", "review", "list", "progress"];
    for (var i = 0; i < a.length; i++) { var e = document.getElementById("pg-" + a[i]); if (e && !e.hidden) return a[i]; }
    return "play";
  }
  var lastBack = 0;
  function exitTap() {
    var now = Date.now();
    if (now - lastBack < 2000) { if (APP && APP.exitApp) APP.exitApp(); return; }
    lastBack = now;
    try { toast("Press back again to exit", "info"); } catch (e) {}
  }
  function onBack() {
    try {
      var pk = document.getElementById("pkp");
      if (pk && !pk.hidden) { document.body.click(); return; }            // close scope picker
      var mn = document.querySelector(".mn");
      if (mn && mn.open) { mn.open = false; return; }                     // close the ⋯ menu
      var pg = curPage();
      if (pg === "play") {
        var c = document.getElementById("card");
        if (c && c.querySelector(".end")) { hub(); return; }              // finished screen -> runs
        if (typeof run !== "undefined" && run) { endRun(); return; }      // in a run -> asks "End this run?"
        exitTap(); return;                                                // on the runs screen
      }
      if (pg === "bank") {
        var N = window.__nv;
        if (window.__fnw) { window.__fnw = false; fdraw(); return; }
        if (N && N.f) { N.f = fpar(N.f) || null; fdraw(); return; }       // up one folder
        if (N && N.c) { N.c = null; fdraw(); return; }                    // up to the categories
        go("play"); return;
      }
      if (pg === "review" && typeof rv !== "undefined" && rv.ed) { rv.ed = null; rvDraw(); return; }
      go("play");
    } catch (e) { exitTap(); }
  }

  /* ---------- exports: PDF / .txt files (Android's WebView cannot download or print) ----------
     RR.exportFile(name, data, mime, how) writes Documents/RecallRush/Exports/<name>, shows a toast with the
     saved path and opens Android's share sheet (Open with / Share / Print / Drive ...).
       data: string (written as UTF-8 text) or Uint8Array / ArrayBuffer (written as binary).
       how:  "print" only changes the toast wording. */
  var SH = native ? plug.Share : null, CB = native ? plug.Clipboard : null;
  var EXP = ROOT + "/Exports", askedPerm = false;

  function b64(data) {
    var u = data instanceof Uint8Array ? data : new Uint8Array(data), s = "";
    for (var i = 0; i < u.length; i += 0x8000) s += String.fromCharCode.apply(null, u.subarray(i, i + 0x8000));
    return btoa(s);
  }
  function say(t, kind, ms) { try { toast(t, kind || "info", ms); } catch (e) {} }

  async function writeExport(name, data) {
    var text = typeof data === "string";
    var body = text ? { data: data, encoding: "utf8" } : { data: b64(data) };
    var order = ["DOCUMENTS", "CACHE"], lastErr = null;
    for (var i = 0; i < order.length; i++) {
      for (var attempt = 0; attempt < 2; attempt++) {
        try {
          var r = await FS.writeFile({ path: EXP + "/" + name, directory: order[i], recursive: true, data: body.data, encoding: body.encoding });
          return { dir: order[i], uri: r && r.uri };
        } catch (e) {
          lastErr = e;
          if (order[i] === "DOCUMENTS" && attempt === 0 && !askedPerm && /perm|denied|access/i.test(String((e && e.message) || e))) {
            askedPerm = true;
            try { if (FS.requestPermissions) await FS.requestPermissions(); } catch (e2) {}
            continue;                       // retry once after asking
          }
          break;
        }
      }
    }
    throw lastErr || new Error("could not write the file");
  }

  async function exportFile(name, data, mime, how) {
    if (!FS) throw new Error("not running as the Android app");
    var r;
    try { r = await writeExport(name, data); }
    catch (e) { say("Couldn't save " + name + ": " + String((e && e.message) || e), "err", 6000); return null; }
    var where = r.dir === "DOCUMENTS" ? "Documents/" + EXP + "/" + name : "app cache (Documents not available): " + name;
    say("Saved to " + where + (how === "print" ? ". Pick Print or a PDF app next." : ""), "info", 7000);
    if (SH && SH.share && r.uri) {
      try { await SH.share({ title: name, text: name, url: r.uri, dialogTitle: "Open or share " + name }); }
      catch (e) {
        if (!/cancel/i.test(String((e && e.message) || e))) say("Saved, but the share sheet didn't open. Find it in Files > Documents > RecallRush > Exports.", "info", 7000);
      }
    }
    return { path: where, uri: r.uri };
  }

  /* copy text with the native clipboard when available (WebView clipboard can be blocked) */
  async function copyText(t) {
    if (CB && CB.write) { try { await CB.write({ string: t }); return true; } catch (e) {} }
    return false;
  }

  window.RR = {
    native: native,
    exportFile: native && FS ? exportFile : null,
    copyText: native ? copyText : null,
    afterStart: function () {
      if (APP && APP.addListener) APP.addListener("backButton", onBack);
      if (native) {   // the buttons make a PDF + open the share sheet here, not a print dialog / browser download
        var t = { prb: "Makes a PDF and opens Android's share sheet (choose Print there)", pdfb: "Saves a PDF to Documents/RecallRush/Exports",
                  lpr: "Makes a PDF and opens Android's share sheet (choose Print there)", lsv: "Saves a PDF to Documents/RecallRush/Exports", lst: "Saves a .txt to Documents/RecallRush/Exports" };
        for (var id in t) { var el = document.getElementById(id); if (el) el.title = t[id]; }
      }
    },
    _onBack: onBack
  };

  /* ---------- lifecycle + start ---------- */
  document.addEventListener("visibilitychange", function () { if (document.hidden) flush(false); });
  if (APP && APP.addListener) { try { APP.addListener("pause", function () { flush(false); }); } catch (e) {} }
  var chip = document.getElementById("sv");
  if (chip) chip.addEventListener("click", function () { if (FS) flush(true); });

  init().catch(function (e) { showErr(e); }).then(function () { if (window.__rrStart) window.__rrStart(); });
})();
