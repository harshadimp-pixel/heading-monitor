import os,signal,subprocess,sys,tempfile,time,glob,shutil
NEW="/workspace/audit/d10/clone2_new"; V="/workspace/audit/venv_clean/bin/python"
def cnt(P):
    return sum(1 for f in os.listdir(P) if f.startswith(("hm-cdp-","scoped_dir",".com.google.Chrome","com.google.Chrome")))
def deep(P):
    return sum(len(fs)+len(ds) for _,ds,fs in os.walk(P))
for sig in (signal.SIGINT, signal.SIGTERM):
    P=tempfile.mkdtemp(prefix="t6d10s.",dir="/tmp")
    env={**os.environ,"TMPDIR":P}
    pr=subprocess.Popen([V,"-m","pytest","-q","-p","no:cacheprovider","app/tests/test_app_ui_headless.py"],cwd=NEW,env=env,
        stdout=open(f"/workspace/audit/d10/out2/sig_{sig.name}.log","w"),stderr=subprocess.STDOUT,
        preexec_fn=lambda: (signal.signal(signal.SIGINT,signal.SIG_DFL),signal.signal(signal.SIGTERM,signal.SIG_DFL)))
    t0=time.time()
    while time.time()-t0<30 and not glob.glob(P+"/hm-cdp-root-*/hm-cdp-*/profile/DevToolsActivePort"): time.sleep(0.05)
    time.sleep(0.5); chrome_during=len(glob.glob(P+"/hm-cdp-root-*/hm-cdp-*"))
    pr.send_signal(sig); rc=pr.wait(30); time.sleep(3)
    alive=subprocess.run(["pgrep","-f",P],capture_output=True,text=True).stdout.split()
    print(f"{sig.name}: launch dirs during={chrome_during}; rc={rc}; after 3 s: top-level entries={cnt(P)}, files+dirs total={deep(P)}, size={subprocess.run(['du','-sh',P],capture_output=True,text=True).stdout.split()[0]}, chrome procs alive={len(alive)}; log tail={open(f'/workspace/audit/d10/out2/sig_{sig.name}.log').read().strip().splitlines()[-1][:80]}")
    for p in alive:
        try: os.kill(int(p),signal.SIGKILL)
        except Exception: pass
    time.sleep(1); shutil.rmtree(P,ignore_errors=True)
