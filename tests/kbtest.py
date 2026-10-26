import sys
import os; sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from h import *
s=serve()
res=[]
def ok(name,cond,extra=""):
    res.append(cond); print(("PASS " if cond else "FAIL ")+name+(" "+str(extra) if extra and not cond else ""))
def st(pg): return pg.evaluate("""()=>({on:KB.on,touch:KB.touch,act:document.activeElement&&(document.activeElement.id||document.activeElement.tagName),
  im:document.getElementById('kb').getAttribute('inputmode'),ro:document.getElementById('kb').readOnly,
  pressed:document.getElementById('kbt').getAttribute('aria-pressed'),lcd:document.getElementById('lcd').textContent.replace(/\\s+/g,'')})""")
with sync_playwright() as p:
    # ---------- touch device ----------
    b,ctx,pg,errs=open_play(p,390,844)
    start_practice(pg)
    a=st(pg)
    ok("touch: detected + html class", a["touch"] and pg.evaluate("document.documentElement.classList.contains('rr-touch')"))
    ok("touch: #kb starts inputmode=none + readonly", a["im"]=="none" and a["ro"])
    ok("touch: #ty / unit style fields locked", pg.evaluate("[...document.querySelectorAll('#pg-play input')].every(e=>e.getAttribute('inputmode')==='none'&&e.readOnly)"))
    pg.click(".disp .ex")
    ok("touch: tapping the display does NOT focus the typing field (keyboard stays hidden)", st(pg)["act"]!="kb", st(pg))
    pg.click("[data-k='7']"); pg.click("[data-k='+']")
    ok("touch: on-screen keypad still types", "7+" in st(pg)["lcd"], st(pg))
    pg.click("#kbt")
    a=st(pg)
    ok("⌨ on: state, focus on #kb, inputmode=text, not readonly, aria-pressed", a["on"] and a["act"]=="kb" and a["im"]=="text" and not a["ro"] and a["pressed"]=="true", a)
    ok("⌨ click did not trigger the display's own click handler (cursor/lcd unchanged)", "7+" in a["lcd"], a)
    pg.keyboard.type("m")
    ok("⌨ on: phone-keyboard typing reaches the display", st(pg)["lcd"].endswith("m"), st(pg))
    pg.click("[data-k='3']")
    a=st(pg)
    ok("⌨ on: keypad tap keeps focus in #kb (keyboard stays open)", a["act"]=="kb" and a["lcd"].endswith("m3"), a)
    pg.click("#kbt")
    a=st(pg)
    ok("⌨ off: relocked, blurred, aria-pressed=false", (not a["on"]) and a["im"]=="none" and a["ro"] and a["act"]!="kb" and a["pressed"]=="false", a)
    # keyboard dismissed by the system while flag is on: simulate IME via viewport resize
    pg.click("#kbt")                                   # on
    pg.set_viewport_size({"width":390,"height":520})   # IME opened -> window shrinks
    pg.wait_for_timeout(150)
    ok("IME-visible detected after window shrink", pg.evaluate("kbVis()"))
    pg.click("#kbt")
    ok("tap with IME visible turns it off", not st(pg)["on"], st(pg))
    pg.set_viewport_size({"width":390,"height":844}); pg.wait_for_timeout(100)
    # system dismissed IME (window back to full size) but flag still on -> next tap re-shows rather than toggling off
    pg.click("#kbt"); pg.set_viewport_size({"width":390,"height":520}); pg.wait_for_timeout(100)
    pg.set_viewport_size({"width":390,"height":844}); pg.wait_for_timeout(100)
    pg.click("#kbt")
    a=st(pg)
    ok("after system dismissed IME, next ⌨ tap shows it again (stays on)", a["on"] and a["act"]=="kb", a)
    # stage 2 keeps keyboard flow
    pg.evaluate("ed.e=cur.t.slice();ed.pos=ed.e.length;lcd();check()"); pg.wait_for_timeout(300)
    a=pg.evaluate("({stage,act:document.activeElement.id||document.activeElement.dataset.pu||document.activeElement.tagName,ro:document.getElementById('u')?document.getElementById('u').readOnly:null,im:document.getElementById('u')&&document.getElementById('u').getAttribute('inputmode')})")
    ok("stage 2 with ⌨ on: unit field unlocked and focused", a["stage"]==2 and a["ro"]==False and a["im"]=="text" and a["act"] in ("u","0","1","2","3","4"), a)
    # bank / review / list fields untouched
    pg.click("[data-go=bank]"); pg.wait_for_timeout(200)
    r=pg.evaluate("[...document.querySelectorAll('#pg-bank input,#pg-bank textarea,#pg-folders input')].map(e=>(e.id||e.tagName)+':'+e.getAttribute('inputmode')+':'+e.readOnly)")
    ok("bank fields have no inputmode/readonly", all(x.endswith(":null:false") for x in r) and len(r)>=1, r)
    pg.click("[data-go=review]"); pg.wait_for_timeout(200)
    r=pg.evaluate("[...document.querySelectorAll('#pg-review input:not([type=checkbox]),#pg-review textarea')].map(e=>(e.id||e.tagName)+':'+e.getAttribute('inputmode')+':'+e.readOnly)")
    ok("review Find field untouched", all(x.endswith(":null:false") for x in r) and len(r)>=1, r)
    pg.click("[data-go=list]"); pg.wait_for_timeout(200)
    r=pg.evaluate("[...document.querySelectorAll('#pg-list input')].map(e=>(e.id||e.tagName)+':'+e.getAttribute('inputmode')+':'+e.readOnly)")
    ok("list Find field untouched", all(x.endswith(":null:false") for x in r) and len(r)>=1, r)
    ok("no JS errors (touch)", not errs, errs)
    b.close()
    # ---------- laptop / browser (no touch) ----------
    b,ctx,pg,errs=open_play(p,1280,800,mobile=False)
    start_practice(pg)
    a=st(pg)
    ok("laptop: not touch, no readonly, ⌨ button hidden", (not a["touch"]) and (not a["ro"]) and pg.evaluate("getComputedStyle(document.getElementById('kbt')).display")=="none", a)
    pg.keyboard.type("5+3")
    ok("laptop: physical keyboard still types without focusing anything", "5+3" in st(pg)["lcd"], st(pg))
    pg.click(".disp .ex")
    ok("laptop: clicking the display still focuses #kb", st(pg)["act"]=="kb", st(pg))
    ok("no JS errors (laptop)", not errs, errs)
    b.close()
print(f"\n{sum(res)}/{len(res)} passed")
