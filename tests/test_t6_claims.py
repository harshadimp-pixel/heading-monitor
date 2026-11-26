"""Q1/Q2 claims audit: scan every doc/UI string for unsupported positioning, distance, navigation, hardware claims."""
import os, re, pytest
from conftest import ROOT

SKIP_DIRS = {".git", "__pycache__", ".venv", "node_modules", "tests"}
SKIP_FILES = {"TEST_PLAN.md", "verification_report.md", "TEAM_RULES.md"}
PAT = re.compile(r"(?i)\b(gps[- ]?(free|independent|denied|less|replacement)|without gps|dead[- ]?reckon\w*|position(ing)?\b|locat(e|ion|ing)\b|geolocat\w*|"
                 r"distance|odometr\w*|displacement|navigat\w*|coordinates?|lat(itude)?/lon|hardware[- ]verified|tested on (real )?hardware|flight[- ]proven|accura(te|cy) of)")

def files():
    for d, ds, fs in os.walk(ROOT):
        ds[:] = [x for x in ds if x not in SKIP_DIRS]
        for f in fs:
            if f in SKIP_FILES: continue
            if f.endswith((".md", ".html", ".js", ".py", ".txt", ".json")):
                yield os.path.join(d, f)

def scan():
    hits = []
    for p in files():
        for i, line in enumerate(open(p, errors="ignore"), 1):
            if PAT.search(line): hits.append(f"{os.path.relpath(p, ROOT)}:{i}: {line.strip()[:200]}")
    return hits

# Manually adjudicated by T6 (see reports/verification_report.md, Claims audit). Path prefix -> reason.
ADJUDICATED_OK = {
    "docs/math/sensor-spec/": "error-propagation analysis (heading bias -> DR cross-track error); SPEC.md s4.6 states position is "
                              "unobservable from heading alone; no capability claim. T6 recomputed TC12/TC18.",
}

def test_Q1_claims_inventory(capsys):
    """Inventory only (manual adjudication in verification_report.md). Fails on hard red flags."""
    hits = scan()
    for h in hits: print("CLAIM?", h)
    red = [h for h in hits if re.search(r"(?i)gps[- ]?(free|independent|replacement)|dead[- ]?reckon|\[HARDWARE-VERIFIED\]", h)
           and not re.search(r"(?i)\b(not|no|cannot|can't|never|does not|isn't|without evidence|nobody|reject|requires|nothing|no claim|may|unknown|before any|must be)\b", h)]
    red = [h for h in red if not any(h.startswith(k) for k in ADJUDICATED_OK)]
    hw_logs = os.path.isdir(os.path.join(ROOT, "reports", "hardware_logs")) and os.listdir(os.path.join(ROOT, "reports", "hardware_logs"))
    if hw_logs: red = [h for h in red if "HARDWARE-VERIFIED" not in h]
    assert not red, "Unsupported claims:\n" + "\n".join(red)

def test_Q3_limitations_sections():
    expected = {"docs/hardware": "HW", "docs/math": "math", "sim": "sim", "docs/firmware": "fw", "app": "ui"}
    missing = []
    for d in expected:
        txt = ""
        for dd, _, fs in os.walk(os.path.join(ROOT, d)):
            for f in fs:
                if f.endswith(".md"): txt += open(os.path.join(dd, f), errors="ignore").read()
        if not re.search(r"(?im)^#+\s*(\d+\.?\s*)?limitations", txt): missing.append(d)
    assert not missing, f"No LIMITATIONS section (TEAM_RULES 13) in: {missing}"
