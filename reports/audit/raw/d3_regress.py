import sys; sys.path.insert(0,'/workspace/heading-monitor/tests'); sys.path.insert(0,'.')
import numpy as np, heading_core as hc
from refmodel import body_vectors
ST={"SENSOR_STALE","MAG_STALE"}
def run(name, gen, n=200):
    est=hc.HeadingEstimator(calibration=hc.Calibration()); first=None; last=None
    for i in range(n):
        o=est.update(gen(i)); o=o if isinstance(o,dict) else o.to_dict()
        w=ST&set(o.get("warnings") or [])
        if w and first is None: first=(i/20, sorted(w))
        last=o
    print(f"{name}: first stale flag at {first}; final warnings {last.get('warnings')} quality {last['quality']:.3f}")
rng=np.random.default_rng(1); m,a=body_vectors(37,3,-2)
mq=(np.round(m/0.1)*0.1).tolist(); mf=[round(float(x)+0.0123457,7) for x in m]
acc=lambda: (np.round((a+rng.normal(0,0.002,3))*512)/512).tolist()
run("F1 mag-only frozen, quant meta", lambda i: {"t":i/20,"source":"replay","mag_uT":mq,"meta":{"mag_quant_uT":0.1}})
run("F2 mag-only frozen, no meta, off-grid float", lambda i: {"t":i/20,"source":"replay","mag_uT":mf})
run("F3 mag-only frozen, no meta, on 0.1 grid (inference)", lambda i: {"t":i/20,"source":"replay","mag_uT":mq})
run("F4 mag+accel all frozen, quant meta", lambda i: {"t":i/20,"source":"replay","mag_uT":mq,"accel_g":list(map(float,a)),"meta":{"mag_quant_uT":0.1}})
run("F5 frozen mag, live accel noise, no gyro, no meta off-grid", lambda i: {"t":i/20,"source":"replay","mag_uT":mf,"accel_g":acc()})
run("F6 frozen mag, live accel noise, no gyro, quant meta (stationary)", lambda i: {"t":i/20,"source":"replay","mag_uT":mq,"accel_g":acc(),"meta":{"mag_quant_uT":0.1}}, 1200)
def tilt(i):
    _,aa=body_vectors(37, 3+ (10*i/100 if i<100 else 10), -2)
    return {"t":i/20,"source":"replay","mag_uT":mq,"accel_g":(np.round((aa+rng.normal(0,0.002,3))*512)/512).tolist(),"meta":{"mag_quant_uT":0.1}}
run("F7 frozen mag, accel pitch +10 deg over 5 s, no gyro, quant meta", tilt)
run("F8 frozen mag, live accel, gyro 20 dps yaw, quant meta", lambda i: {"t":i/20,"source":"replay","mag_uT":mq,"accel_g":acc(),"gyro_dps":[0,0,20.0+float(rng.normal(0,.05))],"meta":{"mag_quant_uT":0.1}})
run("F9 frozen mag, live accel, gyro 0.5 dps (below deadband), quant meta", lambda i: {"t":i/20,"source":"replay","mag_uT":mq,"accel_g":acc(),"gyro_dps":[0,0,0.5],"meta":{"mag_quant_uT":0.1}},1200)
def yaw_nogyro(i):
    return {"t":i/20,"source":"replay","mag_uT":mq,"accel_g":acc(),"meta":{"mag_quant_uT":0.1}}
run("F10 frozen mag during a level 20 dps yaw turn, NO gyro, quant meta (accel unchanged by yaw)", yaw_nogyro, 600)
