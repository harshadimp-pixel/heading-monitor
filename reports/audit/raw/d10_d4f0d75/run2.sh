#!/bin/bash
# T6 D10 verification: fresh clones, private venv, private TMPDIR per run
R=/workspace/audit/d10/out2; rm -rf $R; mkdir -p $R; V=/workspace/audit/venv_clean/bin/python
mk(){ rm -rf $1; git clone -q --no-hardlinks /workspace/heading-monitor $1 && git -C $1 checkout -q $2; echo "clone $1 at $(git -C $1 rev-parse --short HEAD) dirty=$(git -C $1 status --porcelain|wc -l)" >> $R/status; }
cnt(){ # chrome-ish entries (any depth 1) in dir $1, excluding pytest-of-*
  ls -A $1 2>/dev/null | grep -E '^(scoped_dir|\.com\.google\.Chrome|com\.google\.Chrome|\.org\.chromium|hm-cdp-|t6-chrome-)' | wc -l; }
tmpc(){ ls -A /tmp | grep -E '^(scoped_dir|\.com\.google\.Chrome|com\.google\.Chrome|\.org\.chromium|hm-cdp-)' | sort; }
OLD=/workspace/audit/d10/clone2_old; NEW=/workspace/audit/d10/clone2_new
mk $OLD 4bcba22; mk $NEW d4f0d75; sleep 1
run(){ # tag clone target
  P=$(mktemp -d /tmp/t6d10.XXXX); tmpc > $R/tmp_before_$1
  (cd $2 && TMPDIR=$P timeout 900 $V -m pytest -q -p no:cacheprovider $3 > $R/$1.log 2>&1)
  tmpc > $R/tmp_after_$1
  echo "$1 $(date +%T): $(tail -n1 $R/$1.log) | private TMPDIR chrome/hm-cdp entries left: $(cnt $P) (size $(du -sh $P|cut -f1)); /tmp new chrome-ish names during run: $(comm -13 $R/tmp_before_$1 $R/tmp_after_$1 | wc -l)" >> $R/status
  ls -A $P > $R/$1.leftover; rm -rf $P; }
run old_headless_1 $OLD app/tests/test_app_ui_headless.py
for i in 1 2 3; do run new_headless_$i $NEW app/tests/test_app_ui_headless.py; done
for i in 1 2; do run new_apptests_$i $NEW app/tests; done
# interrupted runs
for sig in INT TERM; do
  P=$(mktemp -d /tmp/t6d10.XXXX)
  cd $NEW; TMPDIR=$P $V -m pytest -q -p no:cacheprovider app/tests/test_app_ui_headless.py > $R/kill_$sig.log 2>&1 &
  PID=$!; cd /workspace/audit
  for k in $(seq 1 100); do sleep 0.2; [ -n "$(ls -A $P 2>/dev/null | grep hm-cdp-)" ] && break; done
  sleep 1.5; during=$(cnt $P)
  kill -$sig $PID; wait $PID; sleep 3
  echo "kill_$sig $(date +%T): hm-cdp/chrome entries during=$during, after signal+3s=$(cnt $P) (size $(du -sh $P|cut -f1)); chrome procs with this TMPDIR still alive: $(pgrep -f "$P" | wc -l); log tail: $(tail -n1 $R/kill_$sig.log)" >> $R/status
  ls -AR $P | head -20 > $R/kill_$sig.leftover; pkill -f "$P"; sleep 1; rm -rf $P
done
# full repo suite on new clone
P=$(mktemp -d /tmp/t6d10.XXXX)
(cd $NEW && TMPDIR=$P $V -m pytest -q -rs -p no:cacheprovider --junitxml=$R/junit_d4f0d75.xml > $R/pytest_rs_d4f0d75.log 2>&1)
echo "FULL $(date +%T): $(tail -n1 $R/pytest_rs_d4f0d75.log) | leftover chrome entries: $(cnt $P)" >> $R/status; rm -rf $P
tmpc > $R/tmp_before_default
(cd $NEW && env -u TMPDIR $V -m pytest -q -p no:cacheprovider app/tests > $R/apptests_default_tmp.log 2>&1)
tmpc > $R/tmp_after_default
echo "apptests default /tmp $(date +%T): $(tail -n1 $R/apptests_default_tmp.log) | /tmp new chrome-ish names: $(comm -13 $R/tmp_before_default $R/tmp_after_default | wc -l) [$(comm -13 $R/tmp_before_default $R/tmp_after_default | head -5 | tr '\n' ' ')]" >> $R/status
echo ALLDONE >> $R/status
