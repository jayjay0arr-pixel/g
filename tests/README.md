# Tests (optional, not part of the app)

Headless-Chromium checks that need Python + Playwright (`pip install playwright pypdf && playwright install chromium`; `pdftoppm` from poppler is used to render PDFs) and Node for the patch test.
Run from this folder. Run `npm run prepare-web` first so the real fonts and PDF libraries exist (layout numbers depend on the fonts).

| Command | What it checks |
|---|---|
| `python3 fit.py 390x844 412x915` | Portrait play screen fits with no page scroll, for every sample formula (extra sizes: `390x772 360x740`) |
| `python3 kbtest.py` | ⌨ button, inputmode="none"/readonly locks, typing, Formula bank fields untouched, laptop mode unchanged |
| `python3 regress.py` | Fake Android (in-memory Documents): empty first launch, folders, file sync, restore, back button, browser mode |
| `python3 export.py` | Print / Save PDF / Save .txt / Copy as text on Review and List, with a fake Filesystem + Share + Clipboard: files land in `Documents/RecallRush/Exports/`, the .txt matches the list text, the list PDF is a valid PDF (pypdf + render), share sheet opens, cache fallback, permission retry, and the browser paths unchanged. Review's jsPDF/html2canvas are stand-ins when `www/lib/` is missing (set `STUB_PDF` to any PDF) |
| `python3 patch_test.py` | Runs `scripts/patch-android.mjs` on a hand-made Capacitor 7 style `android/` folder (`fixtures/`): patches, second run changes nothing, `--check`, a project that targets SDK 36 |

`seed.py` holds the sample formulas used by the tests (the app itself ships empty). Nothing here touches your real data.
`fixtures/make_fixture.py` is written from memory of the Capacitor 7 template, not copied from a generated project.
