# T5 demo video and screenshots

All of this is **[SIMULATED]**: every frame comes from the real running app (`python -m app`) fed by the T3
simulator or by a replay of a recording the app made of it. Nothing is hardware-verified. The app shows compass
heading only, with no position or navigation.

| File | What |
|---|---|
| `demo.mp4` | 71.5 s, 1440×900, H.264 (libx264, yuv420p, 25 fps), about 2.5 MB |
| `01_startup_uncalibrated.png` | start-up on `sim:calibration_dance`, uncalibrated |
| `02_calibration_fit.png` | calibration wizard after `heading_core.Calibration.fit` (ellipsoid) |
| `03_after_calibration.png` | calibration applied; caption shows before/after heading error vs sim truth |
| `04_tilted_spin.png` | `sim:tilted_spin` with reference heading 90° |
| `05_motor_interference.png` | `sim:motor_interference`: FIELD_MAGNITUDE_OUT_OF_RANGE warning, status DEGRADED |
| `06_replay.png` | `--source replay:reports/demo/demo_tilted_spin_recording.jsonl` |
| `demo_tilted_spin_recording.jsonl` | JSONL recorded by the app in scene 4 (contract Samples, `source:"sim"`), replayed in scene 6 |
| `demo_metrics.json` | numbers quoted in the captions, measured during the run |
| `make_demo.py` | the script that produced all of the above |

Scenes, in order. The DATA SOURCE badge is visible in every frame (sticky header), and every frame carries the overlay
*"Simulated data — not hardware-verified. Compass heading only; no position or navigation."* plus a scene caption.
1. Start-up on `sim:calibration_dance` (8 s).
2. Calibration wizard: collect (34 s real time shown 4× faster), Fit, Apply.
3. Heading after calibration. Mean |heading error| vs sim truth in the recorded run: **21.4° before → 0.42° after**
   (161 / 120 samples, fit residual 0.016 µT rms) [SIMULATED].
4. `sim:tilted_spin` (roll 20°, pitch −15°, yaw spin) while recording JSONL.
5. `sim:motor_interference` (`--sim-duration 40`, so the idle → 8 A → 20 A → pulsing profile plays within the scene;
   shown 1.5× faster): FIELD_MAGNITUDE_OUT_OF_RANGE + HIGH_NOISE, status DEGRADED.
6. Replay of the scene-4 recording. The badge stays **SIMULATED** because each replayed sample still says
   `source:"sim"` (PM decision, 2026-11-27). The transport line in the header shows `replay:…`.

## Reproduce
Requirements: the repo venv (`INSTALL.md`), Google Chrome/Chromium and ffmpeg with libx264. No Playwright needed.
```bash
cd /workspace/heading-monitor
python3 reports/demo/make_demo.py          # about 2 minutes; overwrites the files listed above
```
How it works: each scene runs `python -m app --port 0 --source …` (an OS-assigned port, so the 8080 instance is
untouched; started with `app/tests/_helpers.run_app`). Headless Chrome is driven over the DevTools protocol
(`app/tests/_cdp.py`, stdlib only) on the real clock. The caption overlay is injected into the page, and buttons
are clicked through the page's own handlers. JPEG viewport frames are captured at 5 fps (2 fps during the
time-lapse) and joined with the ffmpeg concat demuxer, using per-frame durations:
`ffmpeg -f concat -safe 0 -i list.txt -vf fps=25,scale=1440:900,format=yuv420p -c:v libx264 -crf 26 -movflags +faststart demo.mp4`.
Numbers differ slightly between runs (real-time capture), but the seeds are fixed (`--seed 1/2/3`).

## Verification
Frames extracted from the final `demo.mp4` at 4, 14, 22, 28, 36, 47, 57, 64 and 70 s were inspected. Each shows the
SIMULATED badge and the disclaimer overlay, with the expected scene: start-up, wizard collecting, fit result,
after calibration, tilted spin, motor interference, replay.

## Limitations
* The video is a sequence of headless screenshots, so it shows no mouse pointer. Button presses go through the
  page's own click handlers.
* Time-lapse segments (scene 2 at 4×, scene 5 at 1.5×) are labelled in the captions.
* The stale/NO DATA behaviour is not in the video, so that the badge stays SIMULATED/REPLAY throughout. It is
  covered by `reports/screenshots/t5_no_current_data_unknown.png` and by the app tests.
