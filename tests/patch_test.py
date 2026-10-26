"""Runs scripts/patch-android.mjs on a hand-made Capacitor-7-style android/ folder (see fixtures/make_fixture.py):
patch, patch again (must change nothing), --check, and a project that targets SDK 36. Needs node."""
import os, sys, re, subprocess, tempfile, hashlib, shutil
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, "fixtures"))
from make_fixture import make
SCRIPT = os.path.join(HERE, "..", "scripts", "patch-android.mjs"); res = []
def ok(n, c, e=""): res.append(bool(c)); print(("PASS " if c else "FAIL ") + n + (("  -> " + str(e)[:400]) if (e and not c) else ""))
def run(*a): r = subprocess.run(["node", SCRIPT, *a], capture_output=True, text=True); return r.returncode, r.stdout + r.stderr
def tree(d):
    h = hashlib.sha256()
    for r, _, fs in sorted(os.walk(d)):
        for f in sorted(fs): h.update(os.path.join(r, f).encode()); h.update(open(os.path.join(r, f), "rb").read())
    return h.hexdigest()
for sdk in (35, 36):
    d = tempfile.mkdtemp(prefix="rr-fixture-"); make(d, sdk); an = os.path.join(d, "android"); mf = os.path.join(an, "app/src/main/AndroidManifest.xml")
    rd = lambda rel: open(os.path.join(an, rel)).read()
    c, o = run("--check", mf); ok(f"[sdk {sdk}] --check on an unpatched project fails", c == 1 and "NOT PATCHED" in o, o)
    c, o = run(mf); ok(f"[sdk {sdk}] patch runs without error", c == 0, o); print(o)
    ok(f"[sdk {sdk}] no warnings", "WARNING" not in o, o)
    m = rd("app/src/main/AndroidManifest.xml"); st = rd("app/src/main/res/values/styles.xml")
    ok("manifest: screenOrientation=user, adjustResize, requestLegacyExternalStorage, storage permissions", 'android:screenOrientation="user"' in m and 'android:windowSoftInputMode="adjustResize"' in m and "requestLegacyExternalStorage" in m and "READ_EXTERNAL_STORAGE" in m)
    ok("manifest: icon + roundIcon point at @mipmap/ic_launcher(_round), no duplicate attributes", m.count("android:icon=") == 1 and m.count("android:roundIcon=") == 1 and 'android:roundIcon="@mipmap/ic_launcher_round"' in m)
    ok("styles: opt-out + bar colours in all three themes", all(st.count(f'name="{n}"') == 3 for n in ["android:windowOptOutEdgeToEdgeEnforcement", "android:statusBarColor", "android:navigationBarColor", "android:windowLightStatusBar", "android:windowLightNavigationBar"]), st)
    ok("styles: indigo replaced (colorPrimary / PrimaryDark / Accent)", "@color/rr_dark" in st and "colorPrimaryDark\">@color/rr_bar" in st and "@color/colorPrimaryDark" not in st and "@color/colorAccent" not in st)
    ok("styles: launch theme uses rr_splash + Android 12 splash attributes", "android:background\">@drawable/rr_splash<" in st and "windowSplashScreenAnimatedIcon" in st and "@drawable/splash<" not in st)
    ok("styles: AppTheme.NoActionBar keeps its own background=@null", 'name="android:background">@null' in st)
    import xml.dom.minidom as X
    for f in ["app/src/main/AndroidManifest.xml", "app/src/main/res/values/styles.xml", "app/src/main/res/values/rr_colors.xml", "app/src/main/res/mipmap-anydpi-v26/ic_launcher.xml", "app/src/main/res/drawable/rr_splash.xml", "app/src/main/res/xml/file_paths.xml"]:
        try: X.parseString(rd(f)); good = True
        except Exception as e: good = False; print(e)
        ok("well-formed XML: " + f.split("/")[-1], good)
    ok("variables.gradle: targetSdkVersion = 35", re.search(r"targetSdkVersion\s*=\s*35\b", rd("variables.gradle")), rd("variables.gradle"))
    ok("file_paths.xml still covers external + cache paths", "<external-path" in rd("app/src/main/res/xml/file_paths.xml") and "<cache-path" in rd("app/src/main/res/xml/file_paths.xml"))
    g = rd("app/build.gradle")
    ok("build.gradle: fixed debug keystore block sits inside android{} before buildTypes", g.index("signingConfigs") < g.index("buildTypes") and "debug.keystore" in g and g.count("signingConfigs") == 1, g)
    ok("icons: 5 densities x (launcher, round, fg, mono) + splash icons", all(os.path.exists(os.path.join(an, f"app/src/main/res/mipmap-{q}/{n}.png")) for q in ["mdpi", "hdpi", "xhdpi", "xxhdpi", "xxxhdpi"] for n in ["ic_launcher", "ic_launcher_round", "rr_icon_fg", "rr_icon_mono"]) and all(os.path.exists(os.path.join(an, f"app/src/main/res/drawable-{q}/rr_splash_icon.png")) for q in ["mdpi", "xxxhdpi"]))
    t1 = tree(an); c, o = run(mf); ok("second run: reports nothing to do", c == 0 and "already patched" in o, o)
    ok("second run: every file byte-identical (idempotent)", tree(an) == t1)
    c, o = run("--check", mf); ok("--check passes after patching", c == 0 and o.startswith("OK"), o)
    shutil.rmtree(d)
print(f"\n{sum(res)}/{len(res)} passed"); sys.exit(0 if all(res) else 1)
