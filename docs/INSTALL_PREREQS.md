# Installation and browser-test prerequisites

Owner: PM & CTO. This complements the UI-owned walkthrough in `INSTALL.md`. It records what the code actually requires and how optional tools are detected. It does not replace `INSTALL.md`.

**Scope:** the virtual (simulated and replayed) project. No physical flight hardware is required to install or to run the test suite.

## 1. Python and virtualenv

| Need | Requirement | Notes |
|---|---|---|
| Python | 3.10+ (`REQUIREMENTS.md` N1) | Verified in this project on **Python 3.13.5**. Python 3.10 itself has not been tested (`reports/audit/traceability.md` N1). |
| OS | Linux (N1) | The official suites were run on Linux. |
| git | any | For cloning. |
| venv | `python3 -m venv .venv` then `. .venv/bin/activate` | Same sequence as `INSTALL.md`. |

## 2. Python packages (`requirements.txt`)

From the repo root, with the venv active:

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

`requirements.txt` currently lists:

- **Required for the suites and the app stack:** `numpy`, `pytest`, `jsonschema`.
- **Optional:** `pyserial`, commented in that file as needed only for `firmware_bridge --port` on a real or virtual serial port.

The app package (`app/`) itself uses the Python standard library. `numpy` is required by `heading_core` and `sim`. `jsonschema` is used to validate the Sample contract (several tests `importorskip` it if it is missing).

### pyserial

- Not required to run the simulator, log replay, or ingest sources, or to run most of the test suite.
- Required for `python -m app --source serial:<port>` and `python -m firmware_bridge --port <port>` (including a virtual pty).
- Without it, `firmware_bridge` exits with a clear error that pyserial is not installed.
- The live-serial regression in `firmware_bridge/tests/test_bridge_modes.py` calls `pytest.importorskip("serial")` and is also skipped when the OS has no POSIX pty (`@pytest.mark.skipif(not hasattr(os, "openpty"), reason="needs a POSIX pty")`). On a normal Linux install with pyserial present, that test runs and is part of the official 513-passed count. Without pyserial the official skip count rises (historically 45 instead of 44).

## 3. Headless browser for the UI tests

The five tests in `app/tests/test_app_ui_headless.py` drive a real browser over the Chrome DevTools Protocol. **Playwright is not used** and is not a dependency. The driver is `app/tests/_cdp.py`, which uses only the Python standard library.

**Binary detection** (`app/tests/_cdp.py`):

```python
CHROME = next((shutil.which(c) for c in ("google-chrome", "chromium", "chromium-browser") if shutil.which(c)), None)
```

The first name found on `PATH` wins. If none is found, `CHROME` is `None` and the entire headless module is skipped:

```python
pytestmark = pytest.mark.skipif(CHROME is None, reason="no headless Chrome/Chromium available")
```

The browser is started as:

```text
<CHROME> --headless=new --no-sandbox --disable-gpu --no-first-run
         --user-data-dir=<temp> --remote-debugging-port=0 --window-size=...
```

The test then reads the DevTools port from `DevToolsActivePort` in that user-data directory and speaks the protocol over a stdlib WebSocket. There is no `--virtual-time-budget`; staleness checks use the real clock.

`INSTALL.md` was verified with `google-chrome`. Other Chromium builds work if they appear on `PATH` under one of the three names above. Firefox, Snap-only binaries that are not on `PATH` under those names, and Playwright browsers are not detected.

The demo video (`reports/demo/make_demo.py`) also needs Chrome (or Chromium) plus `ffmpeg` with libx264. That is optional and is not part of `pytest`.

## 4. Node.js (optional, front-end maths tests)

A small number of app and Auditor tests run `app/static/headingmath.js` under Node, to check display maths and badge mapping.

- `app/tests/test_app_heading_math.py::test_ui_display_math_in_js` is skipped when `shutil.which("node")` is `None`, reason: `node not installed`.
- `app/tests/test_app_d6_replay.py` has a Node-based `badgeInfo` check that skips with `node not available`.
- `tests/test_t6_app.py` likewise skips with `node not available` when Node is missing.

Node is not required to start the dashboard. `INSTALL.md` was verified with Node v24.

## 5. What a clean install is expected to do

With Python 3.10+ (3.13.5 verified), a fresh venv, `pip install -r requirements.txt`, and — on this team's machines — pyserial, `google-chrome` or Chromium, and Node present:

- `python -m pytest -q` at the repo root is the official combined run.
- At commit `1bef73e` / Auditor export of that commit, that run was **513 passed, 44 skipped, 0 failed**. The 44 skips are documented in `reports/audit/skipped_tests.md` (all are out-of-scope simulator cross-checks in `sim/tests/test_spec_cases.py`; none hide a required check).
- If Chrome/Chromium, Node, or pyserial is absent, further tests are skipped for the reasons in sections 2–4. Those environment skips are not part of the official 44.

No paid services or paid packages are required.
