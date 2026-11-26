---
title: "Magnetic Heading Measurement: Mathematical Specification for Virtual Sensor Accuracy Experiments"
subtitle: "Handover to the Simulation Developer (T3) | heading-monitor project"
author: "Mathematics & Sensor Scientist (T2)"
date: "2026-11-26"
---

**Status:** v1.0. Every numeric expected value in this document comes from `reference_model.py` and is
asserted by `test_reference.py` (23 tests). Machine-readable vectors are in `test_cases.json`.
Tags used: **[ANALYTIC]** closed-form result; **[SOURCE]** taken from a cited publication;
**[DATASHEET]** taken from the T1 hardware fact sheet (`docs/hardware/FACTSHEET.md`), which cites PNI's user manual;
**[ASSUMED]** a typical value picked for simulation, *not* a measured or datasheet number.
All results are **[SIMULATED]**. Nothing here has been checked on hardware.

---

# 1. Frames and conventions

Implement these exactly. Most real compass bugs are sign or frame bugs.

| Item | Convention |
|---|---|
| Navigation frame | **NED**: $x_n$ = true North, $y_n$ = East, $z_n$ = Down (right-handed). |
| ENU (only if needed) | $[E,N,U]^T = [y_n,\;x_n,\;-z_n]^T$. Do not mix with NED inside the heading code. |
| Body frame | $x_b$ forward, $y_b$ right, $z_b$ down (matches `ARCHITECTURE.md`). |
| Attitude | ZYX Euler angles: yaw $\psi$, pitch $\theta$, roll $\phi$. Nose up means $\theta>0$. Right wing down means $\phi>0$. |
| Rotation NED→body | $\mathbf v_b = C_{nb}\,\mathbf v_n$, $\;C_{nb}=R_1(\phi)R_2(\theta)R_3(\psi)$ (frame rotations, below). |
| Heading $\psi$ | The angle from north to the projection of $x_b$ onto the horizontal plane, measured **clockwise seen from above**. Reported in $[0^\circ,360^\circ)$. |
| Angle differences | Signed shortest difference $\operatorname{wrap}_{180}(a-b)\in(-180^\circ,180^\circ]$. |
| Declination $D$ | **East positive**: $D>0$ when magnetic north lies east of true north. |
| Inclination $I$ | **Down positive**: $I>0$ in the northern magnetic hemisphere. |
| Units | Field in µT (SI in T for the physics formulas in §6). Angles in degrees at interfaces and radians inside the maths. Distance in m. |
| Accelerometer | **Specific force** $\mathbf f_b = C_{nb}[0,0,-g]^T$. A level unit at rest reads $[0,0,-g]$. If a driver reports $+g$ on $z$ when level (the "gravity" convention), negate the vector first. **Interface item:** T3 and T4 must state which convention they emit. |

Frame rotation matrices:
$$
R_1(\phi)=\begin{bmatrix}1&0&0\\0&\cos\phi&\sin\phi\\0&-\sin\phi&\cos\phi\end{bmatrix},\;
R_2(\theta)=\begin{bmatrix}\cos\theta&0&-\sin\theta\\0&1&0\\\sin\theta&0&\cos\theta\end{bmatrix},\;
R_3(\psi)=\begin{bmatrix}\cos\psi&\sin\psi&0\\-\sin\psi&\cos\psi&0\\0&0&1\end{bmatrix}.
$$

Wrapping functions:
$$\operatorname{wrap}_{360}(a)=a-360\lfloor a/360\rfloor,\qquad \operatorname{wrap}_{180}(a)=180-\operatorname{wrap}_{360}(180-a).$$
Edge cases (tested): $\operatorname{wrap}_{360}(360)=0$, $\operatorname{wrap}_{360}(-1)=359$, $\operatorname{wrap}_{180}(-180)=+180$.

# 2. Earth magnetic field model

## 2.1 Field elements

In true-north NED, the geomagnetic field vector is
$$
\mathbf b_n=\begin{bmatrix}X\\Y\\Z\end{bmatrix}=\begin{bmatrix}F\cos I\cos D\\F\cos I\sin D\\F\sin I\end{bmatrix},\qquad
H=\sqrt{X^2+Y^2}=F\cos I,\quad I=\operatorname{atan2}(Z,H),\quad D=\operatorname{atan2}(Y,X).
$$
At the Earth's surface, $F$ ranges from about 23 000 to 67 000 nT, $H$ from 0 to about 43 000 nT, and $I$ from −90° to +90°
**[SOURCE: WMM2025 Technical Report, Table 1]**. The project's default test field is $F=50\,\mu$T and $I=60^\circ$, which gives
$H=25\,\mu$T and $Z=43.301\,\mu$T **[ASSUMED, mid-latitude-like]**. Replace it with WMM values for the real test site.

## 2.2 The three norths

* **True (geographic) north:** the direction along the meridian to the geographic pole on the WGS84 ellipsoid.
* **Magnetic north:** the direction of the horizontal field $\mathbf H$. A compass measures heading relative to it.
* **Grid north:** the $+y$ ("northing") axis of a map projection such as UTM. It differs from true north by the grid convergence $\gamma$.

Conversions (all wrapped to $[0,360)$):
$$\psi_T=\psi_M+D,\qquad \psi_M=\psi_T-D,\qquad \psi_G=\psi_T-\gamma .$$
Here $\gamma>0$ when grid north lies east of true north. For a Transverse Mercator projection on the sphere,
$\tan\gamma=\tan(\lambda-\lambda_0)\sin\varphi$, which to first order is $\gamma\approx(\lambda-\lambda_0)\sin\varphi$.
The ellipsoidal correction terms are omitted. They are of order $10^{-2}$ degrees for the test case, but that is an estimate, not a tested number.
Grid variation ("grivation") is $D-\gamma$, so $\psi_G=\psi_M+D-\gamma$.

## 2.3 Source of $D$ and $I$: WMM and IGRF

* **WMM2025** (NOAA NCEI and BGS) is valid for 2025.0 to 2030.0. It is a degree-12 spherical-harmonic main-field model with a
  linear secular-variation (SV) model. **IGRF-14** is the IAGA equivalent (degree 13), with a predictive SV term for 2025 to 2030.
  Neither model contains crustal anomalies, ionospheric or magnetospheric fields, or magnetic storms.
* **Stated accuracy, WMM2025 error model (1σ) [SOURCE: NCEI "WMM Accuracy, Limitations, and Error Model"]:**
  X 137 nT, Y 89 nT, Z 141 nT, H 133 nT, F 138 nT, I 0.20°, and
  $$\sigma_D=\sqrt{0.26^2+\left(\frac{5417}{H\,[\mathrm{nT}]}\right)^2}\;\text{degrees}.$$
  For $H=25\,000$ nT this gives $\sigma_D=0.338^\circ$. For $H=2\,000$ nT (near a magnetic pole) it gives $\sigma_D=2.72^\circ$ (TC13).
  NCEI also notes that local declination anomalies of 3–4° are "not uncommon" and some exceed 10°.
* **Secular variation:** $D(t)\approx D(t_0)+\dot D\,(t-t_0)$. $\dot D$ is typically some arc-minutes per year, and the
  local value comes from the model. Always evaluate the model at the *experiment date*. An out-of-date declination is a
  pure bias in true heading (§5.7).
* **The simulator does not embed WMM.** $D$, $I$ and $F$ are scenario inputs, and should come from the NCEI calculator or
  the official WMM coefficient file for the chosen site and date.

# 3. Heading computation

## 3.1 Level case

When level ($\phi=\theta=0$), $C_{nb}=R_3(\psi)$. In magnetic-north NED, $\mathbf b=[H,0,Z]^T$, so
$$\mathbf m_b=[H\cos\psi,\;-H\sin\psi,\;Z]^T\quad\Rightarrow\quad \boxed{\psi_M=\operatorname{atan2}(-m_y,\;m_x)}$$
This holds in the body NED frame (x forward, y right, z down). The minus sign is needed because $y_b$ points right while $\psi$
increases clockwise. In an ENU or y-left body frame the formula changes sign, so check it against TC01.

## 3.2 Roll and pitch from the accelerometer

With the unit static and unaccelerated, $\mathbf f_b=[g\sin\theta,\;-g\sin\phi\cos\theta,\;-g\cos\phi\cos\theta]^T$, so
$$\phi=\operatorname{atan2}(-f_y,\,-f_z),\qquad \theta=\operatorname{atan2}\!\left(f_x,\sqrt{f_y^2+f_z^2}\right)\in[-90^\circ,90^\circ].$$
Linear acceleration $\mathbf a$ adds directly to $\mathbf f_b$ and corrupts $\phi$ and $\theta$. A tilt error of $\delta$ produced this way
causes a heading error of about $\tan I\cdot\delta$ (§3.4). This is why the estimator should gate on
$\big|\,\|\mathbf f\|-g\big|$ or fuse a gyro.

## 3.3 Tilt-compensated case

Undo roll, then pitch: $\mathbf m_h=R_2(\theta)^TR_1(\phi)^T\mathbf m_b$, which gives
$$
\begin{aligned}
X_h&=m_x\cos\theta+m_y\sin\phi\sin\theta+m_z\cos\phi\sin\theta\\
Y_h&=m_y\cos\phi-m_z\sin\phi\\
Z_h&=-m_x\sin\theta+m_y\sin\phi\cos\theta+m_z\cos\phi\cos\theta
\end{aligned}
\qquad
\boxed{\psi_M=\operatorname{atan2}(-Y_h,\;X_h)},\quad \psi_T=\operatorname{wrap}_{360}(\psi_M+D).
$$
$Z_h$ gives the measured dip $\hat I=\operatorname{atan2}(Z_h,\sqrt{X_h^2+Y_h^2})$, which is used for interference checks (§6.3).

**Why it matters (TC04):** at yaw 45°, pitch 30° and $I=60^\circ$, applying the level formula to tilted data gives
109.73° instead of 45° (an error of 64.7°). The tilt-compensated formula gives exactly 45°.

## 3.4 Singularities and ill-conditioning

1. **Pitch → ±90°.** Roll is undefined, because $f_y,f_z\to0$ and $\operatorname{atan2}(0,0)$ has no value. Heading is defined by the
   projection of $x_b$, which becomes vertical (gimbal lock). Do not use Euler heading for $|\theta|>\theta_{\max}$.
   The default $\theta_{\max}=60^\circ$ **[ASSUMED]**. Use quaternions with a different heading definition if
   operation beyond that is needed.
2. **Tilt-error coupling.** For a vehicle that is actually level but has roll and pitch estimate errors $\delta\phi,\delta\theta$:
   $$\delta\psi\approx\tan I\,(\delta\phi\cos\psi-\delta\theta\sin\psi)\quad[\text{rad, first order}].$$
   At $I=60^\circ$, a 1° roll error at $\psi=0$ gives 1.7314° exactly (first order: $\tan 60^\circ=1.7321^\circ$) (TC14).
   The heading error from a tilt error therefore grows like $\tan I$ toward the magnetic poles.
3. **Near the magnetic poles, $H\to0$.** Heading is $\operatorname{atan2}$ of a vector of length $H$, so every additive error
   $\varepsilon$ produces $\delta\psi\sim\varepsilon/H$ (§5). When $H$ approaches the sensor noise and residual-calibration level,
   heading carries no information. Flag the case $H_{\text{expected}}<H_{\min}$; a starting value of $H_{\min}\approx5\,\mu$T is **[ASSUMED]**.

# 4. Heading vs movement vs distance vs position

These are four different mathematical objects. A compass measures **only the first**.

| Quantity | Definition | Type | Sensor that observes it |
|---|---|---|---|
| **Heading** $\psi$ | Direction of the body axis $x_b$ projected on the horizontal plane | Angle of an *orientation* (attitude) | Magnetometer + tilt (or gyro-compass) |
| **Course / track over ground** $\chi$ | $\chi=\operatorname{atan2}(v_E,v_N)$, the direction of the *velocity* vector | Angle of a *motion* | GNSS velocity, or DR with known flow |
| **Crab / drift angle** $\beta$ | $\beta=\operatorname{wrap}_{180}(\chi-\psi)$, caused by wind, current, sideslip or lateral motion | Difference of the two | Needs both |
| **Speed** | $\lVert\mathbf v\rVert$ (ground speed $\neq$ airspeed or water speed) | Scalar rate | GNSS, odometry, pitot, log |
| **Distance travelled** | $s=\int_{t_0}^{t_1}\lVert\mathbf v(t)\rVert\,dt$, the path length | Scalar, monotone | Integrates speed |
| **Displacement** | $\Delta\mathbf p=\mathbf p(t_1)-\mathbf p(t_0)=\int\mathbf v\,dt$, with $\lVert\Delta\mathbf p\rVert\le s$ | Vector | Integrates velocity |
| **Geographic position** | $(\varphi,\lambda,h)$ on the WGS84 ellipsoid | Point on a manifold | GNSS; DR needs $\mathbf p_0$ |

## 4.1 Heading vs track (crab)
$$\mathbf v_g=V_a\begin{bmatrix}\cos(\psi+\beta_s)\\\sin(\psi+\beta_s)\end{bmatrix}+\mathbf w,\qquad
\chi=\operatorname{atan2}(v_{g,E},v_{g,N}),\qquad \beta=\chi-\psi .$$
Here $\beta_s$ is the aerodynamic or hydrodynamic sideslip and $\mathbf w$ is the wind or current vector (the direction it blows *toward*).
TC09: $\psi=0^\circ$, $V_a=50$ m/s and a wind of 10 m/s toward 090° give $\chi=11.3099^\circ$, GS $=50.9902$ m/s and $\beta=+11.31^\circ$.
The compass reads 0° throughout.

## 4.2 Distance vs displacement
TC10: the path N 100 m, E 100 m, S 100 m has $s=300$ m and $\lVert\Delta\mathbf p\rVert=100$ m at bearing 090°.
A semicircle of radius 100 m has $s=\pi R=314.159$ m and $\lVert\Delta\mathbf p\rVert=200$ m.

## 4.3 Dead reckoning (DR)

**Flat-earth local NED** (short ranges, a few km):
$$N_{k+1}=N_k+v_k\cos\chi_k\,\Delta t,\qquad E_{k+1}=E_k+v_k\sin\chi_k\,\Delta t .$$

**WGS84** ($a=6\,378\,137$ m, $f=1/298.257223563$, $e^2=f(2-f)$):
$$M(\varphi)=\frac{a(1-e^2)}{(1-e^2\sin^2\varphi)^{3/2}}\;(\text{meridian}),\qquad N(\varphi)=\frac{a}{\sqrt{1-e^2\sin^2\varphi}}\;(\text{prime vertical}),$$
$$\dot\varphi=\frac{v_N}{M+h},\qquad \dot\lambda=\frac{v_E}{(N+h)\cos\varphi},\qquad \dot h=-v_D .$$
TC17: $M(0)=6\,335\,439.327$ m, $N(0)=6\,378\,137$ m, $M(45^\circ)=6\,367\,381.816$ m and $N(45^\circ)=6\,388\,838.290$ m.
1 km north at the equator is $\Delta\varphi=0.00904369^\circ$. 1 km east at 45°N is $\Delta\lambda=0.01268282^\circ$.
$\dot\lambda$ is singular at the geographic poles.

## 4.4 Great circle and rhumb line (spherical Earth, radius $R$)
$$a=\sin^2\tfrac{\Delta\varphi}{2}+\cos\varphi_1\cos\varphi_2\sin^2\tfrac{\Delta\lambda}{2},\qquad c=2\arcsin\sqrt a,\qquad d=Rc,$$
$$\chi_0=\operatorname{atan2}\big(\sin\Delta\lambda\cos\varphi_2,\;\cos\varphi_1\sin\varphi_2-\sin\varphi_1\cos\varphi_2\cos\Delta\lambda\big).$$
Rhumb line (constant true course): $\Delta\Psi=\ln\frac{\tan(\pi/4+\varphi_2/2)}{\tan(\pi/4+\varphi_1/2)}$, $q=\Delta\varphi/\Delta\Psi$
($q=\cos\varphi$ if $\Delta\Psi=0$), $\chi=\operatorname{atan2}(\Delta\lambda,\Delta\Psi)$, $d=R\sqrt{\Delta\varphi^2+q^2\Delta\lambda^2}$.

TC11 **[SOURCE: Ed Williams, *Aviation Formulary*, LAX→JFK example]:** LAX (33°57′N, 118°24′W) to JFK (40°38′N, 73°47′W):
$c=0.623585$ rad, which is 2143.7 nm (with $R$ in nm so that 1′ = 1 nm); initial course 65.892°; rhumb line 79.32° over 2164.6 nm.
With $R=6\,371\,008.8$ m the great-circle distance is 3972.863 km. A spherical model differs from the ellipsoidal (Vincenty or
Karney) geodesic by up to about 0.5%, so use an ellipsoidal geodesic where position truth needs better than that.

## 4.5 Heading error → position error
A straight leg of length $d$ flown with a constant heading (and hence track) error $\delta\psi$ gives:
$$e_{\perp}=d\sin\delta\psi\approx d\,\delta\psi,\qquad e_{\parallel}=d(1-\cos\delta\psi),\qquad \lVert\mathbf e\rVert=2d\sin(\delta\psi/2).$$
TC12: $d=1$ km and $\delta\psi=2^\circ$ give a cross-track error of 34.899 m (small-angle value 34.907 m), an along-track
distance of 999.391 m and a total error of 34.905 m. Error growth over $n$ steps of $v\Delta t$:

* constant bias: $e_\perp(t)=v t\sin\delta\psi$, which grows **linearly** with distance;
* independent per-step heading noise with std $\sigma_\psi$: $\mathrm{RMS}(e_\perp)\approx v\Delta t\,\sigma_\psi\sqrt n$, a **random walk**
  (TC18: 100 steps of 10 m with $\sigma_\psi=2^\circ$ give 3.49 m, compared with 17.45 m from a 1° bias);
* correlated (Gauss-Markov) heading error falls between these two cases;
* speed scale error $\varepsilon$: $e_\parallel=\varepsilon s$.

## 4.6 Why a perfect compass alone cannot give position
$$\mathbf p(t)=\mathbf p_0+\int_0^t\lVert\mathbf v\rVert\begin{bmatrix}\cos\chi\\\sin\chi\end{bmatrix}d\tau,\qquad \chi=\psi+\beta .$$
A compass supplies $\psi(t)$ only. The integral also needs (i) the initial position $\mathbf p_0$ (a constant of integration),
(ii) the speed $\lVert\mathbf v(t)\rVert$, and (iii) the crab angle $\beta(t)$. Every speed profile, and every wind or current field, is
consistent with the same heading history, so position is unobservable from heading alone. Test `test_heading_needs_no_speed_position_nullspace`:
an identical 0° compass history over 60 s with and without a 10 m/s crosswind ends 600 m apart.

# 5. Sensor error model

## 5.1 Measurement equation
$$
\boxed{\mathbf m_k=Q\!\left[(1+k_T\Delta T)\,S\,M\big(C_{nb}\,\mathbf b_n+\mathbf b_{\text{int}}(t)\big)+\mathbf h+\mathbf k_{\text{off}}\Delta T+\mathbf b_{\text{rw}}(t)+\mathbf n_k\right]}
$$

| Term | Meaning | Simulation model |
|---|---|---|
| $S$ (3×3) | Soft iron plus per-axis scale factor. Symmetric positive-definite part = scale and soft iron | $S=I+E_s$ |
| $M$ (3×3) | Non-orthogonality of the axes and mounting misalignment (≈ small rotation plus shear) | $M\approx I+[\boldsymbol\epsilon]_\times+$ shear |
| $\mathbf h$ | Hard-iron offset: magnetised material fixed to the body, plus the sensor's own offset | constant per scenario |
| $\mathbf b_{\text{int}}(t)$ | External or variable interference (motors, currents, nearby steel) | §6 |
| $\mathbf n_k$ | White Gaussian noise, $\mathcal N(0,\sigma_m^2I)$ per axis | seeded RNG |
| $\mathbf b_{\text{rw}}$ | Bias random walk $\mathbf b_k=\mathbf b_{k-1}+\sigma_{rw}\sqrt{\Delta t}\,\mathbf w_k$, or first-order Gauss-Markov bias instability $\mathbf b_k=e^{-\Delta t/\tau}\mathbf b_{k-1}+\sigma_{ss}\sqrt{1-e^{-2\Delta t/\tau}}\,\mathbf w_k$ | `bias_random_walk`, `gauss_markov_bias` |
| $Q[\cdot]$ | Quantisation to the LSB $q$: $\sigma_q=q/\sqrt{12}$ (uniform-error model, valid when noise ≥ about 1 LSB) | `round(m/q)*q` |
| $k_T, \mathbf k_{\text{off}}$ | Temperature coefficients of scale and offset | linear in $\Delta T$ |

## 5.2 White noise → heading noise
The heading error is the noise component perpendicular to $\mathbf H$, divided by $H$:
$$\boxed{\sigma_\psi\approx\frac{\sigma_m}{H}\;\text{rad}}$$
This is the level case, for isotropic per-axis noise. Tilt compensation mixes $m_z$ noise in, but the magnitude stays similar for moderate tilt.
TC07: $\sigma_m=0.1\,\mu$T and $H=25\,\mu$T give a predicted $0.2292^\circ$ and a Monte Carlo value (N = 20 000, seed 0) of $0.2278^\circ$ (within 3%).
For an RM3100 at CC = 200 the noise is 15 nT **[DATASHEET, per T1]**, so $\sigma_\psi=0.0344^\circ$ at $H=25\,\mu$T (TC19).
Sensor noise is therefore rarely the dominant term for that part. Calibration residuals and interference dominate.

## 5.3 Hard iron → one-cycle (1ψ) error
Take a level unit with horizontal offset $(b_x,b_y)$ in body axes and $\varphi_b=\operatorname{atan2}(b_y,b_x)$:
$$\delta\psi=\operatorname{atan2}\!\big(-(b_x\sin\psi+b_y\cos\psi),\;H+b_x\cos\psi-b_y\sin\psi\big)\;\approx\;-\frac{|\mathbf b|}{H}\sin(\psi+\varphi_b).$$
The maximum over all headings is $\arcsin(|\mathbf b|/H)$ for $|\mathbf b|<H$. If $|\mathbf b|\ge H$, the reading can point anywhere.
TC05: $b_x=5\,\mu$T and $H=25\,\mu$T give $-11.310^\circ$ exactly at $\psi=90^\circ$ (first order $-11.459^\circ$), with a maximum of $11.537^\circ$.

## 5.4 Soft iron → two-cycle (2ψ) error
For a horizontal $2\times2$ block $(I+E)$ with small $E$:
$$\delta\psi\approx\underbrace{\tfrac{e_{12}-e_{21}}{2}}_{\text{constant (rotation)}}+\tfrac{e_{22}-e_{11}}{2}\sin2\psi-\tfrac{e_{12}+e_{21}}{2}\cos2\psi\quad[\text{rad}].$$
TC06: $S=\operatorname{diag}(1.05,0.95)$ gives $-2.8624^\circ$ at 45° (first order $-2.8648^\circ$), $+2.8624^\circ$ at 135°, and 0 at the cardinal points.
The antisymmetric part of $E$ (and of $M$) is a pure rotation. It gives a constant heading offset that **no magnitude-based calibration can see** (§7.3).

## 5.5 Tilt error couples through dip
$\delta\psi\approx\tan I(\delta\phi\cos\psi-\delta\theta\sin\psi)$ (§3.4, TC14).

## 5.6 Temperature and bias drift
Offset drift $\mathbf k_{\text{off}}\Delta T$ acts as a slowly varying hard iron, so it gives a 1ψ error $\sim|\mathbf k_{\text{off}}\Delta T|/H$.
A common scale drift $k_T$ does **not** change heading, since atan2 is scale-invariant, but differential scale drift between axes acts like soft iron.

## 5.7 Declination error passes straight through
$\psi_T=\psi_M+D$, so $\delta\psi_T=\delta\psi_M+\delta D$ with unit gain (TC02: $\delta D=0.5^\circ$ gives $0.5^\circ$).
Calibration cannot remove it. Its budget is the WMM $\sigma_D$ plus local anomalies (§2.3).

## 5.8 Error budget (independent terms, small-angle)
$$\sigma_{\psi_T}^2\approx\Big(\tfrac{\sigma_m}{H}\Big)^2+\tfrac12\Big(\tfrac{|\mathbf b_{\text{res}}|}{H}\Big)^2+\tfrac12\Big(\tfrac{e_{\text{res}}}{1}\Big)^2+\epsilon_{\text{align}}^2+\tan^2I\,\sigma_{\text{tilt}}^2+\sigma_D^2+\sigma_{\text{int}}^2 .$$
The factor ½ is the mean of $\sin^2$ over uniformly distributed heading. $e_{\text{res}}$ is the amplitude of the residual 2ψ term.
This is a planning formula. The Monte Carlo of §8 is the reference.

# 6. Magnetic interference

## 6.1 Dipole
$$\mathbf B(\mathbf r)=\frac{\mu_0}{4\pi r^3}\big[3(\mathbf m\cdot\hat{\mathbf r})\hat{\mathbf r}-\mathbf m\big],\qquad \mu_0=4\pi\times10^{-7}\ \mathrm{T\,m/A}.$$
On the axis $|\mathbf B|=\mu_0 m/(2\pi r^3)$. On the equator it is half that, with the opposite sign. The field falls off as $r^{-3}$, so doubling the
distance divides it by 8. TC08: $m=1\ \mathrm{A\,m^2}$ gives $7.407\,\mu$T on the axis at 0.3 m, $-3.704\,\mu$T on the equator, and $0.926\,\mu$T at 0.6 m.
The dipole moment of a small permanent magnet, steel tool or loudspeaker magnet varies widely with the object, so it is **[ASSUMED]** per scenario.
The simulator should sweep $m\in[0.01,10]\ \mathrm{A\,m^2}$ and $r\in[0.05,2]$ m.

## 6.2 Currents
For an infinite straight wire, $|\mathbf B|=\mu_0 I/(2\pi r)$, which falls off as $r^{-1}$. TC08: 10 A gives 20 µT at 0.1 m and 2 µT at 1 m.
A battery lead carrying motor current can therefore exceed the Earth's horizontal field. Twisted supply/return pairs cancel to first order.
Motor and ESC interference is approximately $\mathbf b_{\text{int}}=\mathbf k_I\,I_{\text{motor}}(t)$ (the linear "compass-mot" model; the coefficient vector is [ASSUMED] per scenario).

## 6.3 Static vs transient disturbance, and detection
* **Static, body-fixed** (attached steel, magnets): the field rotates with the body, so it is part of $\mathbf h$ and $S$. Calibration absorbs it.
* **Static, world-fixed** (rebar, a parked car, a desk): its body-frame value changes with position and attitude. It cannot be calibrated, so detect it and reject the readings.
* **Transient** (current pulses, passing vehicles): time-varying. Detect it, then hold heading on the gyro.

Consistency checks:
$$\text{Magnitude: } \big|\lVert\mathbf m\rVert-F_{\text{ref}}\big|<\tau_F F_{\text{ref}},\qquad \text{Dip: } |\hat I-I_{\text{ref}}|<\tau_I .$$
Here $F_{\text{ref}}$ and $I_{\text{ref}}$ come from WMM or a post-calibration average.
**Key result (TC08):** a 7.41 µT disturbance perpendicular to $\mathbf H$ moves heading by 16.50° (343.50°), yet $\lVert\mathbf m\rVert$ changes by
only 1.09% (50.546 µT), which **passes** a 5% magnitude gate. The dip changes by 1.05° and is caught by a 1° dip gate.
Use both checks, and remember that a disturbance which preserves both $F$ and $I$ cannot be detected from the magnetometer alone.
Suggested starting gates are $\tau_F=5\%$ and $\tau_I=2^\circ$ **[ASSUMED; tune on simulation ROC curves]**.

# 7. Calibration

## 7.1 Ellipsoid fit (hard and soft iron)
Without noise and interference, $\mathbf m=A\mathbf u+\mathbf h$ with $\lVert\mathbf u\rVert=F$, so the samples lie on the ellipsoid
$(\mathbf m-\mathbf h)^TQ(\mathbf m-\mathbf h)=1$ with $Q=(AA^T)^{-1}/F^2$. The algebraic least-squares fit is
$$\min_{\mathbf v}\lVert D\mathbf v-\mathbf 1\rVert^2,\quad D_i=[x^2,y^2,z^2,2yz,2xz,2xy,2x,2y,2z]_i .$$
Build $A_q$ (3×3) from $v_{1..6}$ and $\mathbf g=v_{7..9}$. Then $\mathbf h=-A_q^{-1}\mathbf g$, $Q=A_q/(1+\mathbf h^TA_q\mathbf h)$,
and $W=r\,Q^{1/2}$ (the symmetric square root, with $r$ the geometric-mean radius). The calibrated field is $\mathbf m_c=W(\mathbf m-\mathbf h)$.

* **Requires full 3-D attitude coverage.** If the data come from a planar (yaw-only) rotation, $Q$ is rank-deficient in $z$
  and the fit fails or is badly conditioned. The reference code raises an error if $Q$ is not positive-definite.
* TC15 (500 random attitudes, $\mathbf h=[12,-7,4]$ µT, symmetric $S$): without noise, $\mathbf h$ is recovered to $10^{-14}$ µT and the heading
  error falls from 34.68° (maximum) to $<10^{-13}$°. With $\sigma_m=0.1$ µT, the offset error is 0.009 µT and the maximum heading error is 0.019°.
* $W$ recovers $S^{-1}$ only up to scale and an **unknown rotation**. The symmetric choice is exact only if the true $S$ is symmetric.

## 7.2 Compass swing / deviation curve
Swing the vehicle through known headings $\psi_j$ and fit, by linear least squares,
$$\delta(\psi)=A+B\sin\psi+C\cos\psi+D\sin2\psi+E\cos2\psi .$$
In this spec $\delta=\psi_{\text{meas}}-\psi_{\text{true}}$. Note that the marine "deviation" sign is often the opposite,
(magnetic − compass), so convert explicitly. To first order: $B=-b_x/H$, $C=-b_y/H$ (hard iron);
$A=(e_{12}-e_{21})/2$ (misalignment); $D=(e_{22}-e_{11})/2$; $E=-(e_{12}+e_{21})/2$ (soft iron).
TC16 confirms $B=-2.2918^\circ$ and $C=-1.1459^\circ$ for $\mathbf b=[1,0.5]$ µT. For the soft-iron case the fitted $A$, $D$ and $E$ agree with
first-order theory to within 0.03°, and the post-fit residual RMS is 0.025° (higher harmonics). At least 8 headings are needed, and 36 are recommended.
The curve is valid only at the swing's tilt, latitude ($H$, $I$) and load state.

## 7.3 What calibration cannot fix
1. **Rotation (misalignment) between the magnetometer and the body or IMU frame.** Magnitude-only fits cannot see it. It needs a reference heading
   (swing, GNSS track while moving straight in still air, or alignment against the accelerometer's gravity direction for the tilt part).
2. **Declination and WMM error**, and local crustal anomalies.
3. **World-fixed and transient interference** (§6.3).
4. **Changes after calibration:** new payload, battery, re-magnetisation after a large field exposure, or temperature.
5. **Tilt estimation error under acceleration.**
6. **Noise** (calibration can only average it), and gains near the poles where $H$ is small.

# 8. Virtual sensor accuracy experiments

## 8.1 Monte Carlo framework (per scenario)
```
for run r = 1..N_runs (seed = base_seed + r):
    draw parameters θ_r ~ priors (Table 8.2)
    generate truth trajectory: ψ(t), θ(t), φ(t), position, velocity, wind
    b_n from scenario (F, I, D)            # from WMM at site/date
    m_k = sensor_model(...)                 # §5.1, + interference §6
    f_k = C_nb [0,0,-g] + a_lin + accel noise
    [optional] calibration phase -> (h_hat, W_hat) -> apply to the test phase
    ψ_hat_k = estimator(m_k, f_k, gyro_k)
    e_k = wrap180(ψ_hat_k - ψ_true_k)
collect metrics over k and r
```
Report the number of runs and the seed with every result. Monte Carlo standard error: $\mathrm{SE}(\text{RMS})\approx\mathrm{RMS}/\sqrt{2N_{\text{eff}}}$.

## 8.2 Parameter priors
All rows are **[ASSUMED]** unless tagged otherwise. They are typical ranges for consumer and hobby MEMS, AMR, Hall and magneto-inductive
magnetometer classes as general public datasheet classes describe them, not vendor numbers. Replace with T1 values where available.

| Parameter | Symbol | Nominal | Sweep range | Notes |
|---|---|---|---|---|
| Total field | $F$ | 50 µT | 23–67 µT | [SOURCE WMM range] |
| Inclination | $I$ | 60° | −85…85° | site |
| White noise (consumer MEMS) | $\sigma_m$ | 0.3 µT | 0.05–1 µT | [ASSUMED] |
| White noise (RM3100, CC 50/100/200) | $\sigma_m$ | 0.015 µT | 0.030/0.020/0.015 µT | [DATASHEET per T1] |
| Resolution / LSB | $q$ | 0.013 µT (RM3100 CC200) | 0.013–0.3 µT | RM3100 [DATASHEET per T1]; others [ASSUMED] |
| Hard iron (vehicle installed) | $\lvert\mathbf h\rvert$ | 10 µT | 0–100 µT | [ASSUMED]; can exceed $H$ |
| Soft iron / scale mismatch | $\lVert E_s\rVert$ | 3% | 0–10% | [ASSUMED] |
| Axis non-orthogonality | — | 0.5° | 0–2° | [ASSUMED] |
| Mounting misalignment | $\epsilon$ | 1° | 0–5° | [ASSUMED] |
| Bias instability (GM) | $\sigma_{ss},\tau$ | 0.05 µT, 100 s | 0–0.5 µT, 10–1000 s | [ASSUMED] |
| Offset tempco | $k_{\text{off}}$ | 0.01 µT/°C | 0–0.1 µT/°C | [ASSUMED] |
| Accel noise | $\sigma_a$ | 2 mg | 0.5–10 mg | [ASSUMED] |
| Motor interference coeff. | $\lvert\mathbf k_I\rvert$ | 0.5 µT/A | 0–5 µT/A | [ASSUMED] |
| Declination error | $\delta D$ | $\sigma_D$ (WMM) | + local anomaly 0–4° | [SOURCE WMM] |

## 8.3 Metrics (always on wrapped errors $e=\operatorname{wrap}_{180}(\hat\psi-\psi)$)
* Mean $\bar e$, RMS $\sqrt{\overline{e^2}}$, $\max|e|$, the 95th percentile of $|e|$.
* Circular statistics on raw angles: $\bar\psi=\operatorname{atan2}(\overline{\sin\psi},\overline{\cos\psi})$, $R=\sqrt{\overline{\sin}^2+\overline{\cos}^2}$,
  $\sigma_{\text{circ}}=\sqrt{-2\ln R}$. Never take the arithmetic mean of headings: the mean of 359° and 1° is 180° arithmetically but 0° circularly (TC03).
* Error as a function of heading (to expose 1ψ and 2ψ signatures, using the §7.2 fit), tilt and $H$.
* DR: cross-track and along-track error vs distance; final radial error CEP50 and CEP95.
* Interference detector: true-positive and false-positive rates vs gate (ROC).

## 8.4 Recommended experiments
E1 noise only (validate §5.2). E2 hard-iron sweep (1ψ). E3 soft-iron sweep (2ψ). E4 tilt sweep with and without compensation.
E5 accel-induced tilt error (§3.2). E6 calibration quality vs attitude coverage (full sphere, hemisphere, yaw-only).
E7 dipole distance sweep and detection ROC. E8 motor-current transient. E9 latitude sweep ($H$ from 40 to 2 µT).
E10 DR error growth with bias and noise (§4.5).

# 9. Assumptions
1. Rigid body. The sensor is at a point, so lever arms are irrelevant for a uniform field.
2. Earth field uniform over the experiment area and constant over its duration (no storms, no diurnal variation).
3. Errors are small for every first-order formula. Exact formulas are given and tested where they differ.
4. White noise is Gaussian, independent across axes and samples, and isotropic.
5. Quasi-static attitude for accelerometer tilt, so linear acceleration is zero unless a scenario injects it.
6. Spherical Earth for haversine and rhumb line; WGS84 for DR radii. Flat-earth DR only over short ranges.
7. Interference sources are modelled as point dipoles or infinite wires (far-field idealisations).
8. Euler ZYX, NED, body x-fwd/y-right/z-down; accelerometer specific-force convention (§1).

# 10. LIMITATIONS

Unresolved items, recorded per TEAM_RULES rule 13:

1. **No WMM/IGRF evaluation in the code.** $D$, $I$ and $F$ are inputs. Real values must come from the official NCEI calculator or coefficient file. The WMM error formula is implemented only as a planning aid.
2. **Hardware numbers:** apart from the RM3100 noise and resolution numbers tagged [DATASHEET per T1], every sensor parameter in §8.2 is an assumed typical range. None is measured. There is no hardware validation (all results are [SIMULATED]).
3. **Matek CAN RM3100 path:** per T1, the FC receives DroneCAN field values that are already scaled and possibly rotated by AP_Periph. The frame orientation and units at the FC/MSP boundary must be confirmed by T4 before these formulas are applied to logged data.
4. **Accelerometer sign convention:** `heading_core` uses the same specific-force default, and a read-only cross-check of `heading_core.tilt_compensated_heading` against TC04 and TC02 matched. What T3 and T4 actually emit is not confirmed here. Both conventions are supported (§1).
5. Euler heading is undefined near $|\theta|=90^\circ$. No quaternion-based heading is specified here.
6. The ellipsoid fit is algebraic, not geometric or maximum-likelihood. It is biased at low SNR or with partial coverage, it cannot determine rotation, and the output scale is the ellipsoid's geometric-mean radius, not $F$.
7. The spherical-Earth haversine and rhumb formulas carry an error of up to about 0.5%. Vincenty or Karney geodesics are not implemented. The TM convergence formula is spherical first-order.
8. Dipole and wire interference models are far-field idealisations. Near-field shapes, eddy currents, and the frequency content of PWM motor fields are not modelled.
9. Temperature effects are modelled as linear coefficients only. Hysteresis and re-magnetisation after strong fields are not modelled.
10. The error-budget formula (§5.8) assumes independent errors, and is approximate when the terms are correlated.
11. The Monte Carlo tolerances in TC07 and TC18 are statistical (3–4%). A different RNG implementation or seed may need a re-check.

# 11. Reference test cases

Inputs, expected values and absolute tolerances are listed in full in `test_cases.json`, which is generated by `python test_reference.py --dump`.
The default field is $F=50$ µT, $I=60^\circ$ ($H=25$ µT) and $D=0$ unless stated.

| ID | Case | Key inputs | Expected | Tol. |
|---|---|---|---|---|
| TC01 | Level cardinal | yaw 0/90/180/270/30, level | ψ = 0/90/180/270/30°; $\mathbf m_b(30^\circ)=[21.6506,-12.5,43.3013]$ µT | 1e-9° |
| TC02 | Mag→true | (10, −1.5), (359, +2), (0.5, −1), (180, 180) | 8.5°, 1.0°, 359.5°, 0.0°; δD 0.5° → 0.5° | 1e-9° |
| TC03 | Wrap, circular stats | {359, 1}; diffs; {350, 10, 0} | arithmetic mean 180°, circular mean 0°; diffs 2, −2, 180, 180; circ std 8.1754° | 1e-5° |
| TC04 | Tilt compensation | (ψ,θ,φ) = (135,20,−30), (45,30,0), (300,−15,25) | 135, 45, 300° (level formula: 133.918, 109.734, 302.941°); dip 60° | 1e-9° |
| TC05 | Hard iron | $b_x=5$ µT, ψ = 90° | −11.3099° exact, −11.4592° first order, max 11.5370° | 1e-5° |
| TC06 | Soft iron | S = diag(1.05, 0.95, 1) | −2.8624° @45°, +2.8624° @135°, 0 @0 and 90° | 1e-5° |
| TC07 | Noise MC | σ_m 0.1 µT, N 20 000, seed 0 | σ_ψ 0.2292° (MC 0.2278°), mean ≈ 0 | 3%, 0.01° |
| TC08 | Interference | 1 A·m² @0.3 m; 10 A wire; 7.407 µT on $y_b$ | 7.4074 / −3.7037 / 0.9259 µT; 20 / 2 µT; ψ 343.4956°, ‖m‖ 50.5457 µT (5% gate passes), dip 58.945° (1° gate flags) | 1e-5 |
| TC09 | Crab | ψ 0°, 50 m/s, wind 10 m/s → 090° | track 11.3099°, GS 50.9902 m/s, crab 11.3099° | 1e-5 |
| TC10 | Distance vs displacement | U path; semicircle R 100 m | 300 vs 100 m @090°; 314.159 vs 200 m | 1e-3 m |
| TC11 | Great circle | LAX→JFK | 0.623585 rad, 2143.7 nm, 65.892°; rhumb 79.32°, 2164.6 nm; 3972.863 km | per key |
| TC12 | DR cross-track | 1 km, 2° bias | 34.8995 m cross-track, 999.3908 m along-track, 34.9048 m total | 1e-5 m |
| TC13 | Near pole | σ_m 0.1 µT; H 25 vs 2 µT | 0.2292° vs 2.8648° (×12.5); WMM σ_D 0.3385° vs 2.7210° | 1e-5° |
| TC14 | Tilt-dip coupling | δφ = 1°, I = 60°, ψ = 0 | 1.7314° (first order 1.7321°) | 1e-5° |
| TC15 | Ellipsoid fit | h = [12, −7, 4], S symmetric, 500 attitudes | noise-free: exact; σ 0.1 µT: ‖δh‖ ≤ 0.05 µT, max heading error ≤ 0.1°; before calibration 34.679° | per key |
| TC16 | Deviation curve | b = [1, 0.5] µT; E = [[.04,.02],[−.01,−.03]] | B −2.2918°, C −1.1459°; A 0.859°, D −2.005°, E −0.286° | 1e-6 / 0.01–0.03° |
| TC17 | WGS84 radii, DR | φ = 0, 45° | M, N as in §4.3; Δφ 0.00904369°, Δλ 0.01268282° | 1e-8° |
| TC18 | DR growth MC | 100 × 10 m, bias 1° / σ 2° | 17.4524 m (bias); 3.4907 m RMS (MC 3.476 m) | 1e-5 / 4% |
| TC19 | Quantisation, RM3100 | q = 0.013, 0.15 µT; 15 nT | σ_q 0.003753, 0.043301 µT; σ_ψ 0.034377° | 1e-6 |
| TC20 | Grid convergence | φ 19°, λ 73°, λ₀ 75°, ψ_T 10° | γ −0.6514°, ψ_G 10.6514° | 1e-5° |

Extra pytest checks: wrap edge cases, accelerometer convention equivalence, and position non-observability from heading (§4.6).

**How to use with the simulator:** feed `inputs` into your implementation and compare against `expected` per key using
$|x-x_{\text{exp}}|\le\text{tol}$ (elementwise for lists; booleans must match). Angles compared this way are already wrapped.
For your own angle outputs, compare with $\operatorname{wrap}_{180}$ differences.

# References
1. Chulliat, A. et al. (2025). *The US/UK World Magnetic Model for 2025–2030: Technical Report*. NOAA NCEI. doi:10.25923/prbc-s316.
2. NOAA NCEI. *World Magnetic Model Accuracy, Limitations, and Error Model*. https://www.ncei.noaa.gov/products/world-magnetic-model/accuracy-limitations-error-model
3. Alken, P. et al. (2021). International Geomagnetic Reference Field: the thirteenth generation. *Earth, Planets and Space* 73:49. (IGRF-14 released by IAGA in late 2024.)
4. Williams, E. *Aviation Formulary* (great-circle and rhumb-line formulas, LAX–JFK worked example). https://edwilliams.org/avform147.htm
5. NIMA TR8350.2, *Department of Defense World Geodetic System 1984* (WGS84 constants, radii of curvature).
6. Gebre-Egziabher, D., Elkaim, G. H., Powell, J. D., Parkinson, B. W. (2006). Calibration of strapdown magnetometers in magnetic field domain. *J. Aerospace Engineering* 19(2).
7. Bowditch, N. *The American Practical Navigator* (NGA Pub. 9): compass deviation coefficients A–E.
8. T1 hardware fact sheet, `docs/hardware/FACTSHEET.md` (RM3100 gain, noise and resolution from the PNI user manual).
