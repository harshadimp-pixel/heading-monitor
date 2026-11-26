"""Q1/Q2/Q3 claims audit.

Q1a  Evidence-tag rule (documented in reports/verification_report.md):
     A line containing the hardware tag ("[HARDWARE-VERIFIED]", "HARDWARE-VERIFIED", "hardware-verified", "hardware verified")
     is a MENTION (allowed) only if the same line also contains a rule/negation cue from MENTION_CUES (it explains the
     labelling rule or says nothing carries the tag). Every other occurrence is APPLIED, and an APPLIED hardware tag
     fails unless reports/hardware_logs/ contains at least one file. Every excluded MENTION is printed and was
     manually confirmed by T6 (list in verification_report.md).
Q1b  Positioning / distance / GPS-independent-navigation phrases: printed as an inventory; hard red flags fail unless the
     line is negated/limiting or the path was manually adjudicated (ADJUDICATED_OK).
Q3   LIMITATIONS section present in every role's area (TEAM_RULES 13).
"""
import os, re, pytest
from conftest import ROOT

SKIP_DIRS = {".git", "__pycache__", ".venv", "node_modules", "tests", "screenshots"}
SKIP_FILES = {"TEST_PLAN.md", "verification_report.md", "TEST_RESULTS.md"}  # T6's own reports quote the rules

HW_TAG = re.compile(r"(?i)\[?hardware[- ]verified\]?")
MENTION_CUES = re.compile(r"(?i)\b(no|not|nothing|none|never|nobody|cannot|can't|requires?|required|until|"
                          r"before any|must not|may not|only (if|when|after)|without a|isn't|is not|are not|carries)\b")
NAV = re.compile(r"(?i)gps[- ]?(free|independent|denied|less|replacement)|without gps|dead[- ]?reckon\w*|odometr\w*|"
                 r"\b(position|location|coordinates|distance travelled|distance traveled)\b")
NAV_RED = re.compile(r"(?i)gps[- ]?(free|independent|replacement)|dead[- ]?reckon|odometr")
NEGATION = re.compile(r"(?i)\b(no|not|cannot|can't|never|does not|isn't|unknown|unobservable|without evidence|reject\w*|removed|nothing)\b")
ADJUDICATED_OK = {
    "docs/math/sensor-spec/": "error-propagation analysis (heading bias -> DR cross-track error); SPEC.md s4.6 states position is "
                              "unobservable from heading alone; no capability claim. T6 recomputed TC12/TC18.",
    "docs/math/HEADING_MATH.md": "scope rule section; manually read by T6 (no capability claim).",
}

def files():
    for d, ds, fs in os.walk(ROOT):
        ds[:] = [x for x in ds if x not in SKIP_DIRS]
        for f in fs:
            if f in SKIP_FILES: continue
            if f.endswith((".md", ".html", ".js", ".py", ".txt", ".json", ".css")):
                yield os.path.join(d, f)

def lines():
    for p in files():
        rel = os.path.relpath(p, ROOT)
        for i, line in enumerate(open(p, errors="ignore"), 1):
            yield rel, i, line.strip()

def hw_logs_exist():
    d = os.path.join(ROOT, "reports", "hardware_logs")
    return os.path.isdir(d) and any(f for f in os.listdir(d) if not f.startswith("."))

def classify_hw_tags():
    mentions, applied = [], []
    for rel, i, l in lines():
        if HW_TAG.search(l):
            (mentions if MENTION_CUES.search(l) else applied).append(f"{rel}:{i}: {l[:220]}")
    return mentions, applied

def test_Q1a_hardware_tag_applied_only_with_logs():
    mentions, applied = classify_hw_tags()
    for m in mentions: print("MENTION (excluded, manually confirmed):", m)
    for a in applied: print("APPLIED:", a)
    if not hw_logs_exist():
        assert not applied, "Hardware tag applied without reports/hardware_logs/:\n" + "\n".join(applied)

def test_Q1a_rule_selfcheck():
    """The rule must still catch an applied tag and still exclude a rule explanation."""
    assert not MENTION_CUES.search("Heading RMSE 0.4 deg [HARDWARE-VERIFIED]")
    assert not MENTION_CUES.search("| H1 | 0.01 deg | HARDWARE-VERIFIED |")
    assert MENTION_CUES.search("Nothing here carries [HARDWARE-VERIFIED].")
    assert MENTION_CUES.search("[HARDWARE-VERIFIED] requires a raw log from the physical RM3100")

def test_Q1b_navigation_claims():
    inv, red = [], []
    for rel, i, l in lines():
        if NAV.search(l):
            h = f"{rel}:{i}: {l[:220]}"; inv.append(h)
            if NAV_RED.search(l) and not NEGATION.search(l) and not any(rel.startswith(k) for k in ADJUDICATED_OK):
                red.append(h)
    for h in inv: print("NAV?", h)
    assert not red, "Unsupported positioning/navigation claims:\n" + "\n".join(red)

def test_Q3_limitations_sections():
    areas = ["docs/hardware", "docs/math", "sim", "docs/firmware", "firmware_bridge", "app"]
    missing = []
    for d in areas:
        txt = ""
        for dd, _, fs in os.walk(os.path.join(ROOT, d)):
            for f in fs:
                if f.endswith(".md"): txt += open(os.path.join(dd, f), errors="ignore").read()
        if not re.search(r"(?im)^#+\s*(\d+\.?\s*)?(\w+\s+)?limitations", txt): missing.append(d)
    assert not missing, f"No LIMITATIONS section (TEAM_RULES 13) in: {missing}"
