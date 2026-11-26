"""U1-U3 app smoke: start, HTTP 200, source badge. Detailed WebSocket checks in Phase 2."""
import os, subprocess, sys, time, urllib.request, pytest
from conftest import ROOT

def test_U1_app_starts_sim():
    if not os.path.isfile(os.path.join(ROOT, "app", "__main__.py")):
        pytest.skip("NOT RUN (missing deliverable): app/__main__.py")
    p = subprocess.Popen([sys.executable, "-m", "app", "--source", "sim"], cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    try:
        body = None
        for _ in range(40):
            time.sleep(0.25)
            try:
                body = urllib.request.urlopen("http://localhost:8080/", timeout=2).read().decode(errors="ignore"); break
            except Exception: pass
        assert body is not None, "app did not serve :8080 within 10 s"
        assert "SIMULATED" in body.upper() or "source" in body.lower()
    finally:
        p.terminate(); p.wait(5)
