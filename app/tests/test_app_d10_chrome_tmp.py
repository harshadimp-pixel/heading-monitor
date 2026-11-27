"""D10: headless Chrome must not leak temp dirs into the system /tmp.

Chrome 156 headless writes .com.google.Chrome.*, com.google.Chrome.* and scoped_dir* into $TMPDIR on every launch
and never removes them (~36 MB per launch observed on 27 Nov; the box's / reached 100%). HeadlessPage (app/tests/
_cdp.py) gives each launch one private dir (profile + Chrome's TMPDIR) and removes it on close / atexit.
Each test uses its own private parent dir, so concurrent runs by other agents cannot disturb the counts."""
import os
import subprocess
import tempfile
import time

import pytest

from . import _cdp
from ._cdp import CHROME, HeadlessPage

pytestmark = pytest.mark.skipif(CHROME is None, reason="no headless Chrome/Chromium available")


def _alive(pid):
    try:
        os.killpg(pid, 0)
        return True
    except ProcessLookupError:
        return False


@pytest.fixture
def parent():
    d = tempfile.mkdtemp(prefix="hm-d10-test-")
    yield d
    left = os.listdir(d)
    os.rmdir(d) if not left else None
    assert left == [], f"leftovers in private parent: {left}"


def test_chrome_temp_files_go_to_private_tmpdir_and_are_removed(parent):
    with HeadlessPage("about:blank", parent=parent) as page:
        assert page.eval("1+1") == 2
        assert os.path.dirname(page.box) == parent and os.path.basename(page.box).startswith(_cdp.LAUNCH_PREFIX)
        pid, box = page.proc.pid, page.box
        t0 = time.time()                                    # Chrome honours TMPDIR: its temp files appear here
        while not os.listdir(page.chrome_tmp) and time.time() - t0 < 10:
            time.sleep(0.1)
        assert os.listdir(page.chrome_tmp), "Chrome wrote nothing to its private TMPDIR (env not honoured?)"
        assert os.path.isdir(page.tmp)                     # --user-data-dir lives in the same private dir
    assert not os.path.exists(box), "launch dir not removed on close"
    assert not _alive(pid), "Chrome process group still running after close"
    assert os.listdir(parent) == []                         # 0 leftovers


def test_cleanup_runs_when_the_test_body_raises(parent):
    box = None
    with pytest.raises(ZeroDivisionError):
        with HeadlessPage("about:blank", parent=parent) as page:
            box, pid = page.box, page.proc.pid
            1 / 0
    assert box and not os.path.exists(box) and not _alive(pid)
    assert os.listdir(parent) == []


def test_atexit_backup_cleans_pages_never_closed(parent):
    page = HeadlessPage("about:blank", parent=parent)       # deliberately not closed
    box, pid = page.box, page.proc.pid
    assert page in _cdp._LIVE
    _cdp._cleanup_live()                                    # what the atexit hook runs
    assert page not in _cdp._LIVE
    assert not os.path.exists(box) and not _alive(pid)
    page.close()                                            # idempotent
    assert os.listdir(parent) == []


def test_atexit_hook_cleans_up_in_a_real_interpreter_exit(parent):
    """A process that opens a page and exits without closing it leaves nothing behind (atexit backup)."""
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    code = ("import sys; sys.path.insert(0, %r); from app.tests._cdp import HeadlessPage;"
            "p = HeadlessPage('about:blank', parent=%r); print(p.proc.pid, flush=True)") % (root, parent)
    out = subprocess.run([os.sys.executable, "-c", code], capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    pid = int(out.stdout.split()[0])
    assert not _alive(pid)
    assert os.listdir(parent) == []
