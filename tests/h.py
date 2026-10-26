import json, subprocess, time, os, sys, threading, http.server, socketserver, functools
from playwright.sync_api import sync_playwright
from seed import data

WWW = os.environ.get("WWW", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "www"))
PORT = 8765

def serve(www=WWW, port=PORT):
    H = functools.partial(http.server.SimpleHTTPRequestHandler, directory=www)
    H.log_message = lambda *a, **k: None
    class S(socketserver.TCPServer): allow_reuse_address = True
    s = S(("127.0.0.1", port), H)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    return s

def seed_script(d=None):
    d = d or data()
    return "if(!localStorage.getItem('ff_topics_v2'))localStorage.setItem('ff_topics_v2',%s);" % json.dumps(json.dumps(d))

def open_play(p, w, h, landscape=False, mobile=True, seed=True, level="medium", capacitor=False):
    b = p.chromium.launch()
    ctx = b.new_context(viewport={"width": w, "height": h}, device_scale_factor=2,
                        is_mobile=mobile, has_touch=mobile)
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.on("console", lambda m: errs.append("console:"+m.text) if m.type=="error" and "404" not in m.text else None)
    pg.add_init_script("(()=>{let a=12345;Math.random=()=>{a=(a*1664525+1013904223)>>>0;return a/4294967296}})()")
    if seed: pg.add_init_script(seed_script())
    pg.goto(f"http://127.0.0.1:{PORT}/index.html")
    pg.wait_for_selector("[data-a=rprac]", timeout=8000)
    pg.evaluate("document.getElementById('splash')&&document.getElementById('splash').remove()")
    return b, ctx, pg, errs

def start_practice(pg):
    pg.click("[data-a=rprac]")
    pg.wait_for_selector(".dev", timeout=5000)
    pg.wait_for_timeout(300)
