import sys, json
import os; sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
import h
from h import *
from seed import data, BANK
s=serve()
res=[]
def ok(name,cond,extra=""):
    res.append(bool(cond)); print(("PASS " if cond else "FAIL ")+name+(("  -> "+str(extra)) if (extra and not cond) else ""))

FAKE = """
(()=>{
 const call=(op,o)=>window.__fsCall(op,JSON.stringify(o)).then(r=>{r=JSON.parse(r);if(r.err)throw new Error(r.err);return r.v});
 window.__backCbs=[];window.__exited=false;
 window.Capacitor={isNativePlatform:()=>true,Plugins:{
  Filesystem:{requestPermissions:async()=>({}),mkdir:o=>call('mkdir',o),readFile:o=>call('read',o),writeFile:o=>call('write',o)},
  App:{addListener:(n,cb)=>{if(n==='backButton')window.__backCbs.push(cb);return Promise.resolve({remove(){}})},exitApp:()=>{window.__exited=true}}}};
})();
"""
class FS:
    def __init__(s): s.f={}; s.d=set(); s.writes=0; s.docs_ok=True
    def call(s,op,a):
        a=json.loads(a); key=a["directory"]+"/"+a["path"]
        try:
            if a["directory"]=="DOCUMENTS" and not s.docs_ok: raise Exception("Documents not writable")
            if op=="mkdir": s.d.add(key); return json.dumps({"v":{}})
            if op=="write": s.f[key]=a["data"]; s.writes+=1; return json.dumps({"v":{"uri":key}})
            if op=="read":
                if key not in s.f: raise Exception("File does not exist")
                return json.dumps({"v":{"data":s.f[key]}})
        except Exception as e: return json.dumps({"err":str(e)})
def launch(p,fs,seed=None,native=True,w=390,hh=844,keep_ctx=None):
    b=p.chromium.launch(); ctx=b.new_context(viewport={"width":w,"height":hh},is_mobile=True,has_touch=True)
    pg=ctx.new_page(); errs=[]
    pg.on("pageerror",lambda e:errs.append(str(e)))
    pg.on("dialog",lambda d:d.accept())
    if native:
        ctx.expose_function("__fsCall",lambda op,a:fs.call(op,a)); pg.add_init_script(FAKE)
    pg.add_init_script("(()=>{let a=777;Math.random=()=>{a=(a*1664525+1013904223)>>>0;return a/4294967296}})()")
    if seed: pg.add_init_script("if(!localStorage.getItem('ff_topics_v2'))localStorage.setItem('ff_topics_v2',%s);"%json.dumps(json.dumps(seed)))
    pg.goto(f"http://127.0.0.1:{PORT}/index.html"); pg.wait_for_selector("#card .hub, #card .dev, #card [data-a]",timeout=9000)
    pg.wait_for_timeout(1200)
    return b,ctx,pg,errs

with sync_playwright() as p:
    # 1. empty first launch + folders
    fs=FS(); b,ctx,pg,errs=launch(p,fs)
    ok("1 empty first launch: app starts, hub visible, 0 formulas", pg.evaluate("F.length")==0 and pg.evaluate("!!document.querySelector('#card .hub')"))
    ok("1 no JS errors", not errs, errs)
    ok("1 folders ESAS/MATH/EE created in Documents/RecallRush", all(f"DOCUMENTS/RecallRush/{c}" in fs.d for c in ["ESAS","MATH","EE"]), fs.d)
    ok("1 data file created on first launch", "DOCUMENTS/RecallRush/recall-rush-data.json" in fs.f)
    ok("1 status chip says Synced", pg.evaluate("document.getElementById('sv').dataset.st")=="ok" and "Synced" in pg.evaluate("document.getElementById('svt').textContent"))
    # 2. file sync after pasting formulas through the real UI
    pg.click("[data-go=bank]"); pg.wait_for_timeout(200)
    pg.click("[data-b=newt]"); pg.fill("#tn","Sample EE"); pg.click("[data-b=mkt]"); pg.wait_for_timeout(300)
    pg.fill("#bt", BANK); pg.click("[data-b=save]"); pg.wait_for_timeout(1800)
    j=json.loads(fs.f["DOCUMENTS/RecallRush/recall-rush-data.json"])
    ok("2 formulas pasted in Formula bank are mirrored to the data file", len(j["t"])>=1 and "Normal stress" in j["t"][0]["t"], str(j)[:150])
    # play a bit so progress is written too
    pg.click("[data-go=play]"); pg.wait_for_timeout(200); pg.click("[data-a=rprac]"); pg.wait_for_selector(".dev")
    pg.evaluate("ed.e=cur.t.slice();ed.pos=ed.e.length;lcd();check()"); pg.wait_for_timeout(1800)
    j2=json.loads(fs.f["DOCUMENTS/RecallRush/recall-rush-data.json"])
    ok("2 progress (XP) is mirrored to the data file", j2.get("p",{}).get("xp",0)>0, j2.get("p",{}).get("xp"))
    # 4. back button inside a run (portrait play with keyboard control present)
    pg.evaluate("document.querySelector('.mn').open=true"); pg.evaluate("__backCbs[0]()")
    ok("4 back closes the open ⋯ menu first", pg.evaluate("!document.querySelector('.mn').open"))
    pg.evaluate("__backCbs[0]()")   # in a run -> End this run? (dialog auto-accepted)
    pg.wait_for_timeout(400)
    ok("4 back during a run ends it (confirm) and returns to the runs screen", pg.evaluate("!!document.querySelector('#card .hub')"), pg.evaluate("document.querySelector('#card').innerText.slice(0,80)"))
    pg.evaluate("__backCbs[0]()"); pg.wait_for_timeout(200)
    ok("4 back on runs screen: first press just warns, does not exit", not pg.evaluate("__exited"))
    pg.evaluate("__backCbs[0]()")
    ok("4 back twice on runs screen exits", pg.evaluate("__exited"))
    pg.click("[data-go=bank]"); pg.wait_for_timeout(150); pg.evaluate("__backCbs[0]()"); pg.wait_for_timeout(200)
    ok("4 back from Formula bank returns to Play", pg.evaluate("!document.getElementById('pg-play').hidden"))
    ok("4 no JS errors after all of that", not errs, errs)
    saved=dict(fs.f); b.close()

    # 3. restore from file: fresh app storage, data file present
    fs2=FS(); fs2.f=dict(saved); b,ctx,pg,errs=launch(p,fs2)
    ok("3 restore: formulas come back from the data file", pg.evaluate("F.filter(f=>f.topic).length")>=5, pg.evaluate("F.length"))
    ok("3 restore: progress comes back (XP > 0)", pg.evaluate("P.xp")>0, pg.evaluate("P.xp"))
    ok("3 restore: file not overwritten with an empty copy", len(json.loads(fs2.f["DOCUMENTS/RecallRush/recall-rush-data.json"])["t"])>=1)
    ok("3 no JS errors", not errs, errs); b.close()

    # 3b. Documents not writable -> private storage fallback
    fs3=FS(); fs3.docs_ok=False; b,ctx,pg,errs=launch(p,fs3)
    ok("3b Documents blocked: falls back to app storage, chip says so", pg.evaluate("document.getElementById('sv').dataset.st")=="warn" and any(k.startswith("DATA/") for k in fs3.f), (pg.evaluate("document.getElementById('sv').dataset.st"), list(fs3.f)))
    b.close()

    # 5. browser mode (no Capacitor)
    b,ctx,pg,errs=launch(p,None,native=False)
    ok("5 browser mode: starts, chip 'Saved in this browser'", "browser" in pg.evaluate("document.getElementById('svt').textContent"))
    pg.click("[data-go=bank]"); pg.wait_for_timeout(150); pg.click("[data-b=newt]"); pg.fill("#tn","Sample EE"); pg.click("[data-b=mkt]"); pg.wait_for_timeout(300)
    pg.fill("#bt",BANK); pg.click("[data-b=save]"); pg.wait_for_timeout(300)
    pg.reload(); pg.wait_for_selector("#card .hub", state="attached"); pg.wait_for_timeout(900)
    ok("5 browser mode: formulas survive a reload (localStorage)", pg.evaluate("F.filter(f=>f.topic).length")>=5)
    pg.click("[data-go=play]"); pg.wait_for_timeout(200); pg.click("[data-a=rprac]"); pg.wait_for_selector(".dev")
    ok("5 browser mode (touch emulation): play screen + ⌨ button present", pg.evaluate("!!document.getElementById('kbt')"))
    ok("5 no JS errors", not errs, errs); b.close()
print(f"\n{sum(res)}/{len(res)} passed")
