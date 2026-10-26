"""Export checks: Print / Save PDF / .txt / Copy as text on the Review and List pages.
Fake Android (Filesystem + Share + Clipboard) for the native paths, plain Chromium for the browser paths.
jsPDF / html2canvas are not in the sandbox, so the Review page uses small stand-ins that return a real PDF;
that proves the plumbing (arraybuffer -> base64 -> file -> share), not jsPDF itself.
The List page PDF is made by the app's own PDF writer, so that one is validated for real (pypdf + pdftoppm)."""
import sys, json, base64, os, io, subprocess, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import h
from h import *
from seed import data
STUB = os.environ.get("STUB_PDF", os.path.join(os.path.dirname(os.path.abspath(__file__)), "stub.pdf"))
stub_b64 = base64.b64encode(open(STUB, "rb").read()).decode()
OUT = os.environ.get("OUT", tempfile.mkdtemp(prefix="rr-export-"))
s = serve(); res = []
def ok(name, cond, extra=""):
    res.append(bool(cond)); print(("PASS " if cond else "FAIL ") + name + (("  -> " + str(extra)[:300]) if (extra and not cond) else ""))

FAKE = """
(()=>{
 const call=(op,o)=>window.__fsCall(op,JSON.stringify(o)).then(r=>{r=JSON.parse(r);if(r.err)throw new Error(r.err);return r.v});
 window.__printed=0; window.print=()=>{window.__printed++};
 window.Capacitor={isNativePlatform:()=>true,Plugins:{
  Filesystem:{requestPermissions:async()=>{await call('perm',{});return {}},mkdir:o=>call('mkdir',o),readFile:o=>call('read',o),writeFile:o=>call('write',o)},
  Share:{share:o=>window.__shareCall(JSON.stringify(o)).then(r=>{r=JSON.parse(r);if(r.err)throw new Error(r.err);return {}})},
  Clipboard:{write:o=>window.__clipCall(JSON.stringify(o)).then(()=>({}))},
  App:{addListener:()=>Promise.resolve({remove(){}}),exitApp:()=>{}}}};
})();
"""
JSPDF = """window.jspdf={jsPDF:function(){this.addPage=function(){};this.addImage=function(){};this.save=function(){window.__saved=1};
 this.output=function(t){const b=atob('%s'),u=new Uint8Array(b.length);for(let i=0;i<b.length;i++)u[i]=b.charCodeAt(i);return u.buffer}}};""" % stub_b64
H2C = "window.html2canvas=async function(){const c=document.createElement('canvas');c.width=10;c.height=10;return c};"

class FS:
    def __init__(s): s.f = {}; s.enc = {}; s.d = set(); s.docs_ok = True; s.need_perm = False; s.perm_calls = 0; s.shares = []; s.share_err = None; s.clips = []
    def call(s, op, a):
        a = json.loads(a)
        try:
            if op == "perm": s.perm_calls += 1; s.need_perm = False; return json.dumps({"v": {}})
            key = a["directory"] + "/" + a["path"]
            if op == "mkdir": s.d.add(key); return json.dumps({"v": {}})
            if op == "write":
                if a["directory"] == "DOCUMENTS" and (not s.docs_ok or s.need_perm): raise Exception("Permission denied" if s.need_perm else "Documents not writable")
                s.f[key] = a["data"]; s.enc[key] = a.get("encoding")
                root = "file:///storage/emulated/0/Documents/" if a["directory"] == "DOCUMENTS" else "file:///data/user/0/com.recallrush.app/cache/"
                return json.dumps({"v": {"uri": root + a["path"]}})
            if op == "read":
                if key not in s.f: raise Exception("File does not exist")
                return json.dumps({"v": {"data": s.f[key]}})
        except Exception as e: return json.dumps({"err": str(e)})
    def share(s, a):
        s.shares.append(json.loads(a)); return json.dumps({"err": s.share_err} if s.share_err else {})
    def raw(s, key):   # bytes as they would land on disk
        return s.f[key].encode("utf8") if s.enc.get(key) == "utf8" else base64.b64decode(s.f[key])

def launch(p, fs, native=True):
    b = p.chromium.launch(); ctx = b.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True, accept_downloads=True)
    pg = ctx.new_page(); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e))); pg.on("dialog", lambda d: d.accept())
    ctx.route("**/lib/jspdf.umd.min.js", lambda r: r.fulfill(body=JSPDF, content_type="application/javascript"))
    ctx.route("**/lib/html2canvas.min.js", lambda r: r.fulfill(body=H2C, content_type="application/javascript"))
    if native:
        ctx.expose_function("__fsCall", lambda op, a: fs.call(op, a)); ctx.expose_function("__shareCall", lambda a: fs.share(a))
        ctx.expose_function("__clipCall", lambda a: fs.clips.append(json.loads(a)) or "{}")
        pg.add_init_script(FAKE)
    else:
        pg.add_init_script("window.__printed=0;window.print=()=>{window.__printed++};")
    pg.add_init_script("if(!localStorage.getItem('ff_topics_v2'))localStorage.setItem('ff_topics_v2',%s);" % json.dumps(json.dumps(data())))
    pg.goto(f"http://127.0.0.1:{PORT}/index.html"); pg.wait_for_selector("#card .hub, #card .dev, #card [data-a]", timeout=9000); pg.wait_for_timeout(1200)
    return b, ctx, pg, errs
toast_txt = lambda pg: pg.evaluate("[...document.querySelectorAll('#toasts .toast')].map(e=>e.textContent).join(' | ')")
def validate_pdf(raw, tag):
    from pypdf import PdfReader
    path = os.path.join(OUT, tag + ".pdf"); open(path, "wb").write(raw)
    n = len(PdfReader(io.BytesIO(raw)).pages)
    subprocess.run(["pdftoppm", "-r", "50", "-png", "-f", "1", "-l", "1", path, os.path.join(OUT, tag)], check=True)
    return n

with sync_playwright() as p:
    D = "DOCUMENTS/RecallRush/Exports/"
    # ---------- List page, native ----------
    fs = FS(); b, ctx, pg, errs = launch(p, fs)
    pg.click("[data-go=list]"); pg.wait_for_timeout(300)
    expect_txt = pg.evaluate("lsText()"); name_txt = pg.evaluate("lsName('txt')"); name_pdf = pg.evaluate("lsName('pdf')")
    pg.click("#lst"); pg.wait_for_timeout(500)
    ok("L1 Save as .txt writes Documents/RecallRush/Exports/<name>.txt", D + name_txt in fs.f, list(fs.f))
    ok("L1 .txt is UTF-8 text identical to the list text (· √ ² ω kept)", fs.enc.get(D + name_txt) == "utf8" and fs.raw(D + name_txt).decode("utf8") == expect_txt and "√" in expect_txt)
    ok("L1 share sheet opened with the saved file:// uri", fs.shares and fs.shares[-1]["url"].endswith("Exports/" + name_txt) and fs.shares[-1]["url"].startswith("file://"), fs.shares)
    ok("L1 toast shows the saved path", "Saved to Documents/RecallRush/Exports/" + name_txt in toast_txt(pg), toast_txt(pg))
    ok("L1 no extra 'List saved.' browser-style toast", "List saved." not in toast_txt(pg))
    pg.click("#lsv"); pg.wait_for_timeout(1500)
    k = D + name_pdf
    ok("L2 Save as PDF writes a .pdf, base64/binary (no encoding)", k in fs.f and fs.enc.get(k) is None, list(fs.f))
    raw = fs.raw(k); n = validate_pdf(raw, "list-save")
    ok("L2 the file is a valid PDF (%PDF header, %%EOF, pypdf opens it, >=1 page, renders)", raw[:5] == b"%PDF-" and raw.rstrip().endswith(b"%%EOF") and n >= 1, (raw[:8], n))
    ok("L2 share sheet opened for the PDF", fs.shares[-1]["url"].endswith(name_pdf))
    nshare = len(fs.shares); pg.evaluate("document.getElementById('lsv').click()")
    pg.click("#lpr"); pg.wait_for_timeout(1500)
    ok("L3 Print list: window.print() not called, PDF made + share sheet opened instead", pg.evaluate("__printed") == 0 and len(fs.shares) >= nshare + 1 and fs.shares[-1]["url"].endswith(name_pdf), (pg.evaluate("__printed"), len(fs.shares)))
    ok("L3 print toast tells you to pick Print / a PDF app", "Print" in toast_txt(pg), toast_txt(pg))
    pg.click("#lcp"); pg.wait_for_timeout(300)
    ok("L4 Copy as text goes through the native clipboard with the list text", fs.clips and fs.clips[-1]["string"] == expect_txt, fs.clips)
    ok("L4 'List copied.' toast is visible", "List copied." in toast_txt(pg), toast_txt(pg))
    ok("no JS errors (list, native)", not errs, errs); b.close()

    # ---------- Review page, native ----------
    fs = FS(); b, ctx, pg, errs = launch(p, fs)
    pg.click("[data-go=review]"); pg.wait_for_timeout(400)
    pg.click("#pdfb"); pg.wait_for_timeout(1500)
    keys = [x for x in fs.f if x.startswith(D) and x.endswith(".pdf")]
    ok("R1 Review > Save PDF writes Exports/Recall-Rush-Cards-<date>.pdf", len(keys) == 1 and "Recall-Rush-Cards-" in keys[0], list(fs.f))
    raw = fs.raw(keys[0]); n = validate_pdf(raw, "review-save")
    ok("R1 bytes written == bytes jsPDF produced; valid PDF (stand-in jsPDF)", raw == open(STUB, "rb").read() and n == 2, n)
    ok("R1 jsPDF.save() (browser download) was not used", not pg.evaluate("window.__saved"))
    ok("R1 share sheet opened, button label restored", fs.shares and pg.evaluate("document.getElementById('pdfb').textContent").strip().endswith("Save PDF") and not pg.evaluate("document.getElementById('pdfb').disabled"), fs.shares)
    ok("R1 toast shows the saved path", "Documents/RecallRush/Exports/Recall-Rush-Cards-" in toast_txt(pg), toast_txt(pg))
    nshare = len(fs.shares); pg.click("#prb"); pg.wait_for_timeout(1500)
    ok("R2 Review > Print: no window.print(), PDF made and share sheet opened", pg.evaluate("__printed") == 0 and len(fs.shares) == nshare + 1, (pg.evaluate("__printed"), len(fs.shares)))
    ok("R2 print button label restored", pg.evaluate("document.getElementById('prb').textContent").strip().endswith("Print") and not pg.evaluate("document.getElementById('prb').disabled"))
    ok("no JS errors (review, native)", not errs, errs); b.close()

    # ---------- failure paths ----------
    fs = FS(); fs.docs_ok = False; b, ctx, pg, errs = launch(p, fs)
    pg.click("[data-go=list]"); pg.wait_for_timeout(300); pg.click("#lst"); pg.wait_for_timeout(500)
    ok("F1 Documents blocked: saved to the app cache, toast says so, share sheet still opens", any(x.startswith("CACHE/RecallRush/Exports/") for x in fs.f) and "cache" in toast_txt(pg) and fs.shares and "cache" in fs.shares[-1]["url"], (list(fs.f), toast_txt(pg)))
    b.close()
    fs = FS(); fs.need_perm = True; b, ctx, pg, errs = launch(p, fs)
    pg.click("[data-go=list]"); pg.wait_for_timeout(300); pg.click("#lst"); pg.wait_for_timeout(600)
    ok("F2 permission denied once: asks for permission, retries, saves in Documents", fs.perm_calls >= 1 and any(x.startswith(D) for x in fs.f), (fs.perm_calls, list(fs.f)))
    b.close()
    fs = FS(); fs.share_err = "Share canceled"; b, ctx, pg, errs = launch(p, fs)
    pg.click("[data-go=list]"); pg.wait_for_timeout(300); pg.click("#lst"); pg.wait_for_timeout(500)
    ok("F3 closing the share sheet is not an error toast", "didn't open" not in toast_txt(pg) and "Saved to" in toast_txt(pg), toast_txt(pg))
    b.close()
    fs = FS(); fs.share_err = "Share unavailable"; b, ctx, pg, errs = launch(p, fs)
    pg.click("[data-go=list]"); pg.wait_for_timeout(300); pg.click("#lst"); pg.wait_for_timeout(500)
    ok("F4 share sheet failing still leaves the file saved and explains where it is", any(x.startswith(D) for x in fs.f) and "share sheet didn't open" in toast_txt(pg), toast_txt(pg))
    ok("no JS errors (failure paths)", not errs, errs); b.close()

    # ---------- browser / laptop: unchanged ----------
    b, ctx, pg, errs = launch(p, None, native=False)
    pg.click("[data-go=list]"); pg.wait_for_timeout(300)
    exp = pg.evaluate("lsText()"); nm = pg.evaluate("lsName('txt')")
    with pg.expect_download() as dl: pg.click("#lst")
    path = dl.value.path()
    ok("B1 browser: Save as .txt still downloads the file with the same text", dl.value.suggested_filename == nm and open(path, encoding="utf8").read() == exp)
    ok("B1 browser: 'List saved.' toast as before", "List saved." in toast_txt(pg), toast_txt(pg))
    with pg.expect_download() as dl: pg.click("#lsv")
    raw = open(dl.value.path(), "rb").read(); n = validate_pdf(raw, "list-browser")
    ok("B2 browser: Save as PDF still downloads a valid PDF", dl.value.suggested_filename.endswith(".pdf") and raw[:5] == b"%PDF-" and n >= 1, n)
    pg.click("#lpr"); pg.wait_for_timeout(300)
    ok("B3 browser: Print list still calls window.print()", pg.evaluate("__printed") == 1)
    pg.click("[data-go=review]"); pg.wait_for_timeout(300); pg.click("#prb"); pg.wait_for_timeout(300)
    ok("B4 browser: Review Print still calls window.print()", pg.evaluate("__printed") == 2)
    pg.click("#pdfb"); pg.wait_for_timeout(1200)
    ok("B5 browser: Review Save PDF still uses jsPDF.save()", pg.evaluate("window.__saved") == 1)
    pg.click("[data-go=list]"); pg.wait_for_timeout(300)
    pg.evaluate("Object.defineProperty(navigator,'clipboard',{value:{writeText:t=>{window.__clip=t;return Promise.resolve()}},configurable:true})")
    pg.click("#lcp"); pg.wait_for_timeout(300)
    ok("B6 browser: Copy as text uses navigator.clipboard", pg.evaluate("window.__clip") == exp)
    ok("no JS errors (browser)", not errs, errs); b.close()
print(f"\n{sum(res)}/{len(res)} passed   (PDF outputs for eyeballing: {OUT})")
sys.exit(0 if all(res) else 1)
