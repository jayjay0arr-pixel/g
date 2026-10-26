import sys, json
import os; sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from h import *
sizes=[(390,844),(412,915),(390,772),(412,843),(360,740),(360,640)]
if len(sys.argv)>1: sizes=[tuple(map(int,a.split('x'))) for a in sys.argv[1:]]
s=serve()
rows=[]
with sync_playwright() as p:
    for (w,hh) in sizes:
        b,ctx,pg,errs=open_play(p,w,hh)
        start_practice(pg)
        names=pg.evaluate("F.filter(f=>f.topic==='Sample EE').map(f=>f.n)")
        worst=None
        for n in names:
            pg.evaluate("n=>{deck=[F.find(f=>f.n===n)];i=0;round();ed.e=cur.t.slice();ed.pos=ed.e.length;lcd()}", n)
            pg.wait_for_timeout(60)
            m=pg.evaluate("""()=>{const d=document.querySelector('.disp'),ex=document.getElementById('lcd');
              const r=e=>Math.round(e.getBoundingClientRect().height);
              const kp=[...document.querySelectorAll('.dev>.kp')];
              return {n:cur.n, docH:Math.max(document.documentElement.scrollHeight,document.body.scrollHeight,Math.ceil(document.querySelector('.app').getBoundingClientRect().bottom),Math.ceil(document.querySelector('.dev').getBoundingClientRect().bottom)), innerH:innerHeight,
               dispH:r(d), dispClip:d.scrollHeight-d.clientHeight, exW:ex.scrollWidth-ex.clientWidth,
               sci:r(kp[1]), num:Math.round(r(kp[kp.length-1])/4), hscroll:document.documentElement.scrollWidth-innerWidth}}""")
            if worst is None or m["dispH"]>worst["dispH"]: worst=m
            rows.append((w,hh,m))
        ok=all(m["docH"]<=m["innerH"] and m["dispClip"]<=0 and m["hscroll"]<=0 for (_,_,m) in rows if True)
        b.close()
for w,hh,m in rows:
    flag = "" if (m["docH"]<=m["innerH"] and m["dispClip"]<=0 and m["hscroll"]<=0) else "  <-- PROBLEM"
    print(f"{w}x{hh} {m['n'][:22]:22} doc={m['docH']} disp={m['dispH']} clip={m['dispClip']} sci={m['sci']} num={m['num']} hx={m['hscroll']}{flag}")
