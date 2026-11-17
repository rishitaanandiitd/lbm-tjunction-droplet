"""
Regenerate every result in the CLL 770 term-project report.

    python3 run_all.py

Outputs
-------
results/data/*.csv, results/data/hero_snaps.npz
results/figures/*.png   (300 dpi-equivalent, colourblind-safe palette)

Lattice -> dimensionless groups (sigma is the Laplace-measured value):
    Ca    = mu_c * Uc / sigma,     mu = rho * nu  (rho = 1)
    Qr    = Qd / Qc = (Ud * w_d) / (Uc * w_c)
    lambda = mu_d / mu_c
    L/wc  = droplet length (phi = 0 extent) / main-channel width
"""

import os
import sys
import time

import numpy as np
from scipy import ndimage

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from lbm_tjunction.solver import (TJunction, _step, _moments, equilibrium,
                                  INTERFACE_W, SIGMA_THEORY)

ROOT = os.path.dirname(os.path.abspath(__file__))
FIG = os.path.join(ROOT, "results", "figures")
DAT = os.path.join(ROOT, "results", "data")
os.makedirs(FIG, exist_ok=True)
os.makedirs(DAT, exist_ok=True)

plt.rcParams.update({
    "font.size": 10, "axes.labelsize": 11, "axes.titlesize": 11,
    "legend.fontsize": 9, "figure.dpi": 150, "savefig.dpi": 150,
    "axes.grid": True, "grid.alpha": 0.3,
})
BLUE, RED, TEAL, ORANGE = "#1b4f9c", "#c1272d", "#1a936f", "#e08214"

NU_REF = 0.05                     # reference continuous-phase viscosity
SIGMA_GUESS = 0.0126               # replaced by Laplace measurement below


# ------------------------------------------------------------------ utils --
def save_csv(name, header, rows):
    path = os.path.join(DAT, name)
    with open(path, "w") as fh:
        fh.write(",".join(header) + "\n")
        for r in rows:
            fh.write(",".join(str(x) for x in r) + "\n")
    print("wrote", path, flush=True)


def droplet_components(t, phi, min_area=80):
    """Detached (not inlet-connected) phi>0 components in the main channel."""
    mask = np.zeros_like(phi, dtype=bool)
    mask[t.y0:t.y0 + t.h, :] = True
    mask &= (phi > 0)
    lab, n = ndimage.label(mask)
    if n == 0:
        return []
    top = lab[t.y0 + t.h - 1, t.x0:t.x0 + t.w]
    inlet = set(int(v) for v in top if v > 0)
    out = []
    for i in range(1, n + 1):
        if i in inlet:
            continue
        ys, xs = np.where(lab == i)
        if len(xs) < min_area:
            continue
        out.append(dict(length=int(xs.max() - xs.min() + 1),
                        area=int(len(xs)), xmin=int(xs.min()),
                        xmax=int(xs.max()), xcent=float(xs.mean())))
    return sorted(out, key=lambda d: -d["area"])


def run_until_pinch(t, uc, qr, max_steps=30000, chunk=500, snap_steps=()):
    """Run in chunks; stop at the first junction pinch-off.

    A pinch is a detached component of area >= 80 lu^2 whose left edge is
    still within 90 lu of the junction (xmin criterion), which rejects
    tip-breakup of a thread far downstream and outlet artefacts.
    Returns (result_dict, snapshots_dict)."""
    snaps = {}
    done = 0
    pinch = None
    pressure_all = []
    while done < max_steps:
        want = tuple(s for s in snap_steps if done < s <= done + chunk)
        out = t.run(uc_mean=uc, q_ratio=qr, steps=chunk, snap_at=())
        done += chunk
        for s in want:
            snaps[s] = out["phi"].copy()
        if done in snap_steps:
            snaps[done] = out["phi"].copy()
        pressure_all.append(out["pressure"])
        for d in droplet_components(t, out["phi"]):
            if d["xmin"] < t.x0 + t.w + 90:
                pinch = dict(step=done, **d)
                break
        if pinch:
            break
    return pinch, snaps, out


# -------------------------------------------------------------- validation --
def laplace():
    print("== Laplace test ==", flush=True)
    rows, fields = [], {}
    for R in [15, 20, 25, 30, 35]:
        N = 110
        y, x = np.mgrid[0:N, 0:N]
        phi = np.tanh((R - np.sqrt((x - N / 2) ** 2 + (y - N / 2) ** 2))
                      / INTERFACE_W)
        solid = np.zeros((N, N), dtype=bool)
        f = equilibrium(np.ones((N, N)), np.zeros((N, N)), np.zeros((N, N)))
        fn, pn, mu = f.copy(), phi.copy(), np.zeros((N, N))
        for _ in range(3000):
            _step(f, fn, phi, pn, mu, solid, NU_REF, NU_REF, 0.0)
            f, fn, phi, pn = fn, f, pn, phi
        rho = np.ones((N, N)); ux = np.zeros((N, N)); uy = np.zeros((N, N))
        _moments(f, rho, ux, uy, solid)
        pin = rho[N // 2 - 4:N // 2 + 5, N // 2 - 4:N // 2 + 5].mean() / 3
        pout = rho[0:8, 0:8].mean() / 3
        dp = pin - pout
        rows.append([R, dp, dp * R])
        fields[R] = phi
        print(R, dp, flush=True)
    arr = np.array(rows, dtype=float)
    # Young-Laplace in 2D: dp = sigma / R  ->  fit dp vs 1/R through origin
    slope = np.sum(arr[:, 1] / arr[:, 0] * (1 / arr[:, 0]))  # placeholder
    A = 1.0 / arr[:, 0]
    sigma_fit, *_ = np.linalg.lstsq(A.reshape(-1, 1), arr[:, 1], rcond=None)
    sigma_fit = float(sigma_fit[0])
    pred = sigma_fit * A
    ss_res = float(np.sum((arr[:, 1] - pred) ** 2))
    ss_tot = float(np.sum((arr[:, 1] - arr[:, 1].mean()) ** 2))
    r2 = 1 - ss_res / ss_tot
    save_csv("laplace.csv", ["R_lu", "dp_lu", "sigma_est_lu"], rows)

    fig, axes = plt.subplots(1, 2, figsize=(9, 3.6))
    axes[0].plot(A, arr[:, 1], "o", color=BLUE, ms=7, label="LBM")
    xx = np.linspace(0, A.max() * 1.05, 50)
    axes[0].plot(xx, sigma_fit * xx, "-", color=RED,
                 label=f"fit: $\\sigma$={sigma_fit:.4f}, $R^2$={r2:.4f}")
    axes[0].set_xlabel(r"$1/R\ \mathrm{[lu^{-1}]}$")
    axes[0].set_ylabel(r"$\Delta p\ \mathrm{[lu]}$")
    axes[0].set_title("(a) Young–Laplace test (2D)")
    axes[0].legend()
    axes[1].imshow(fields[25], origin="lower", cmap="RdBu", vmin=-1, vmax=1)
    axes[1].contour(fields[25], levels=[0], colors="k", linewidths=1)
    axes[1].set_title("(b) Equilibrated droplet, $R=25$ lu")
    axes[1].set_xlabel("x [lu]"); axes[1].set_ylabel("y [lu]")
    fig.tight_layout(); fig.savefig(os.path.join(FIG, "fig_laplace.png"))
    plt.close(fig)
    return sigma_fit, r2


def poiseuille(sigma):
    print("== Poiseuille test ==", flush=True)
    t = TJunction(nu_c=NU_REF)
    uc = 0.010
    out = t.run(uc_mean=uc, q_ratio=0.0, steps=6000)
    xsec = 60
    y = np.arange(t.y0, t.y0 + t.h)
    u_num = out["ux"][t.y0:t.y0 + t.h, xsec]
    s = (y - (t.y0 + t.h / 2 - 0.5)) / (t.h / 2)
    u_ana = 1.5 * uc * (1 - s ** 2)
    err = float(np.sqrt(np.mean((u_num - u_ana) ** 2)) / (1.5 * uc) * 100)
    save_csv("poiseuille.csv", ["y_lu", "u_lbm", "u_analytical"],
             [[int(yy), float(a), float(b)] for yy, a, b in zip(y, u_num, u_ana)])
    fig, ax = plt.subplots(figsize=(5.2, 3.8))
    ax.plot(u_ana, y, "-", color=RED, lw=2, label="analytical parabola")
    ax.plot(u_num, y, "o", color=BLUE, ms=5, label=f"LBM (rel. RMS err. {err:.2f}%)")
    ax.set_xlabel(r"$u_x\ \mathrm{[lu\,step^{-1}]}$"); ax.set_ylabel("y [lu]")
    ax.set_title("Single-phase Poiseuille profile, $x=60$ lu")
    ax.legend(); fig.tight_layout()
    fig.savefig(os.path.join(FIG, "fig_poiseuille.png")); plt.close(fig)
    return err


def contact_angle():
    print("== Contact-angle test ==", flush=True)
    rows, fields = [], {}
    for wet in [-0.8, -0.5, -0.2, 0.0, 0.3, 0.6]:
        W, N, wall = 80, 120, 10
        solid = np.ones((W, N), dtype=bool); solid[wall:, :] = False
        y, x = np.mgrid[0:W, 0:N]
        d = np.sqrt((x - 60) ** 2 + (y - wall) ** 2)
        phi = np.where(y >= wall, np.tanh((22 - d) / INTERFACE_W), -1.0)
        phi = np.where(solid, -1.0, phi)
        f = equilibrium(np.ones((W, N)), np.zeros((W, N)), np.zeros((W, N)))
        fn, pn, mu = f.copy(), phi.copy(), np.zeros((W, N))
        for _ in range(3500):
            _step(f, fn, phi, pn, mu, solid, NU_REF, NU_REF, wet)
            f, fn, phi, pn = fn, f, pn, phi
        # phi=0 crossing points (droplet contour), circle fit
        pts = []
        for yy in range(wall + 1, W - 1):
            row = phi[yy]
            for xx in range(1, N - 1):
                if row[xx - 1] < 0 <= row[xx] or row[xx - 1] > 0 >= row[xx]:
                    pts.append((xx, yy))
        pts = np.array(pts, dtype=float)
        theta = np.nan
        if len(pts) > 20:
            A = np.c_[2 * pts[:, 0], 2 * pts[:, 1], np.ones(len(pts))]
            b = pts[:, 0] ** 2 + pts[:, 1] ** 2
            sol, *_ = np.linalg.lstsq(A, b, rcond=None)
            cx, cy = sol[0], sol[1]
            R = np.sqrt(max(sol[2] + cx ** 2 + cy ** 2, 1.0))
            cos_t = np.clip((wall - cy) / R, -1, 1)
            theta = float(np.degrees(np.arccos(cos_t)))
        rows.append([wet, theta, int((phi > 0).sum())])
        fields[wet] = (phi, solid)
        print(wet, theta, flush=True)
    save_csv("contact_angle.csv", ["wetting_parameter", "theta_deg", "area_lu2"], rows)
    fig, axes = plt.subplots(2, 3, figsize=(10, 5.2))
    for ax, (wet, _) in zip(axes.ravel(), [(r[0], r[1]) for r in rows]):
        phi, solid = fields[wet]
        ax.imshow(np.ma.masked_where(solid, phi), origin="lower",
                  cmap="RdBu", vmin=-1, vmax=1)
        ax.contour(phi, levels=[0], colors="k", linewidths=0.8)
        th = [r[1] for r in rows if r[0] == wet][0]
        ax.set_title(f"wetting={wet:+.1f}, $\\theta$={th:.0f}°")
        ax.set_xticks([]); ax.set_yticks([])
    fig.suptitle("Sessile droplet on a wall: imposed wetting → measured contact angle")
    fig.tight_layout(); fig.savefig(os.path.join(FIG, "fig_contact.png"))
    plt.close(fig)
    return rows


# ------------------------------------------------------------- T-junction --
def plot_field(ax, t, phi, title, xmax=None):
    xmax = xmax or t.nx
    disp = np.ma.masked_where(t.solid[:, :xmax], phi[:, :xmax])
    ax.imshow(disp, origin="lower", cmap="RdBu", vmin=-1, vmax=1,
              extent=[0, xmax, 0, t.ny], aspect="auto")
    ax.contour(phi[:, :xmax], levels=[0], colors="k", linewidths=0.7,
               extent=[0, xmax, 0, t.ny])
    ax.set_title(title); ax.set_xlabel("x [lu]"); ax.set_ylabel("y [lu]")


def hero(sigma):
    print("== Hero squeezing case ==", flush=True)
    uc, qr = 0.003, 0.5
    Ca = NU_REF * uc / sigma
    t = TJunction(nu_c=NU_REF)
    snap_steps = (0, 3000, 6000, 9000, 12000, 15000, 18000, 21000, 24000,
                  27000, 30000)
    pinch, snaps, out = run_until_pinch(t, uc, qr, max_steps=30000,
                                        chunk=500, snap_steps=snap_steps)
    print("hero pinch:", pinch, "Ca=", Ca, flush=True)
    np.savez_compressed(os.path.join(DAT, "hero_snaps.npz"),
                        steps=np.array(sorted(snaps.keys())),
                        **{f"phi_{k}": v for k, v in snaps.items()},
                        pinch_step=(pinch["step"] if pinch else -1),
                        pinch_length=(pinch["length"] if pinch else -1))
    # neck width + slug length from snapshots
    rows = []
    for s in sorted(snaps):
        phi = snaps[s]
        neck = int((phi[t.y0 + t.h + 2, t.x0:t.x0 + t.w] > 0).sum())
        main = phi[t.y0:t.y0 + t.h, :]
        xs = np.where((main > 0).any(axis=0))[0]
        slug = int(xs.max() - xs.min() + 1) if len(xs) else 0
        rows.append([s, neck, slug])
    save_csv("hero_growth.csv", ["step", "neck_width_lu", "slug_length_lu"], rows)
    # pressure trace from the final chunk is not the full trace; re-read:
    # (pressure is returned per chunk in run_until_pinch; for the figure we
    #  use the saved growth data + a dedicated pressure run below)
    fig, axes = plt.subplots(2, 3, figsize=(12, 5.4))
    chosen = sorted(snaps.keys())
    chosen = [chosen[i] for i in np.linspace(0, len(chosen) - 1, 6).astype(int)]
    for ax, s in zip(axes.ravel(), chosen):
        plot_field(ax, t, snaps[s], f"step {s}", xmax=300)
    fig.suptitle(f"Droplet formation at the T-junction "
                 f"(Ca={Ca:.3f}, $Q_d/Q_c$={qr}, $\\lambda$=1)")
    fig.tight_layout(); fig.savefig(os.path.join(FIG, "fig_hero_sequence.png"))
    plt.close(fig)

    # dedicated pressure run (single call so the trace is continuous)
    t2 = TJunction(nu_c=NU_REF)
    out2 = t2.run(uc_mean=uc, q_ratio=qr, steps=30000, probe_every=25)
    save_csv("hero_pressure.csv", ["step", "p_upstream_lu"],
             [[int(a), float(b)] for a, b in out2["pressure"]])
    fig, ax = plt.subplots(figsize=(7.5, 3.6))
    ax.plot(out2["pressure"][:, 0], out2["pressure"][:, 1], color=BLUE, lw=1)
    if pinch:
        ax.axvline(pinch["step"], color=RED, ls="--",
                   label=f"pinch-off (step {pinch['step']})")
        ax.legend()
    ax.set_xlabel("step"); ax.set_ylabel(r"upstream $p=\rho/3$ [lu]")
    ax.set_title("Upstream pressure during filling and break-up")
    fig.tight_layout(); fig.savefig(os.path.join(FIG, "fig_pressure.png"))
    plt.close(fig)
    return pinch, Ca


def pinch_sequence(sigma):
    """Zoomed waist-collapse sequence for the reference case (Fig. 6)."""
    print("== Pinch sequence ==", flush=True)
    t = TJunction(nu_c=NU_REF)
    want = {20000, 22000, 23500, 24500, 25500, 27000}
    snaps = {}
    out = None
    for chunk in range(54):
        out = t.run(uc_mean=0.003, q_ratio=0.5, steps=500)
        step = (chunk + 1) * 500
        if step in want:
            snaps[step] = out["phi"].copy()
    fig, axes = plt.subplots(2, 3, figsize=(13, 6))
    for ax, (k, v) in zip(axes.ravel(), sorted(snaps.items())):
        disp = np.ma.masked_where(t.solid, v)
        ax.imshow(disp[:, 90:280], origin="lower", cmap="RdBu", vmin=-1,
                  vmax=1, extent=[90, 280, 0, t.ny])
        ax.contour(v[:, 90:280], levels=[0], colors="k", linewidths=0.7,
                   extent=[90, 280, 0, t.ny])
        ax.set_title(f"step {k}"); ax.set_xlabel("x [lu]")
    fig.suptitle("Waist formation and droplet detachment (reference case, zoomed)")
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "fig_pinch_sequence.png")); plt.close(fig)


def sweep(sigma):
    print("== Sweeps ==", flush=True)
    rows = []
    cases = []
    # Ca sweep at fixed Qr
    for uc in [0.002, 0.003, 0.005, 0.008, 0.012, 0.020]:
        cases.append(dict(series="Ca", uc=uc, qr=0.5, lam=1.0, wet=-0.6))
    # Qr sweep at fixed Uc
    for qr in [0.25, 1.0, 2.0]:
        cases.append(dict(series="Qr", uc=0.003, qr=qr, lam=1.0, wet=-0.6))
    # viscosity-ratio sweep
    for lam in [0.2, 5.0]:
        cases.append(dict(series="lambda", uc=0.003, qr=0.5, lam=lam, wet=-0.6))
    # wetting sweep
    for wet in [-0.2, 0.2]:
        cases.append(dict(series="wetting", uc=0.003, qr=0.5, lam=1.0, wet=wet))

    for c in cases:
        t = TJunction(nu_c=NU_REF, viscosity_ratio=c["lam"], wetting=c["wet"])
        pinch, _, out = run_until_pinch(t, c["uc"], c["qr"], max_steps=26000,
                                        chunk=500)
        Ca = NU_REF * c["uc"] / sigma
        L = pinch["length"] if pinch else -1
        rows.append([c["series"], c["uc"], Ca, c["qr"], c["lam"], c["wet"],
                     pinch["step"] if pinch else -1, L,
                     (L / t.h if pinch else -1),
                     pinch["area"] if pinch else -1,
                     "droplet" if pinch else "no pinch (thread/jet)"])
        print(c, "->", pinch, flush=True)
    save_csv("sweep.csv",
             ["series", "Uc", "Ca", "Qr", "lambda", "wetting", "pinch_step",
              "L_lu", "L_over_wc", "area_lu2", "regime"], rows)
    return rows


def regime_figure(sigma, rows):
    ca_rows = [r for r in rows if r[0] == "Ca"]
    qr_rows = [r for r in rows if r[0] in ("Qr",)]
    fig, axes = plt.subplots(1, 3, figsize=(12, 3.8))
    # (a) L/wc vs Ca
    xs = [r[2] for r in ca_rows if float(r[8]) > 0]
    ys = [float(r[8]) for r in ca_rows if float(r[8]) > 0]
    xn = [r[2] for r in ca_rows if float(r[8]) <= 0]
    axes[0].plot(xs, ys, "o-", color=BLUE, label="pinched droplet")
    axes[0].plot(xn, [max(ys) * 1.08 if ys else 2] * len(xn), "x",
                 color=RED, ms=9, label="no pinch")
    axes[0].set_xlabel("Ca"); axes[0].set_ylabel(r"$L/w_c$")
    axes[0].set_title("(a) Droplet length vs Ca ($Q_r$=0.5)")
    axes[0].legend()
    # (b) Garstecki plot: L/wc vs Qr (Ca series point Qr=0.5 added from hero/Ca)
    all_q = []
    for r in rows:
        if float(r[8]) > 0 and r[0] in ("Qr", "Ca") and abs(float(r[3]) - 0.5) < 1e-9 and r[0] == "Ca":
            all_q.append((0.5, float(r[8])))
    for r in qr_rows:
        if float(r[8]) > 0:
            all_q.append((float(r[3]), float(r[8])))
    all_q = sorted(set(all_q))
    if len(all_q) >= 2:
        qx = np.array([a for a, _ in all_q]); qy = np.array([b for _, b in all_q])
        # Garstecki form with the intercept fixed at 1: L/wc - 1 = alpha * Qr
        alpha = float(np.sum(qx * (qy - 1.0)) / np.sum(qx * qx))
        axes[1].plot(qx, qy, "o", color=BLUE, ms=7, label="LBM (pinched cases)")
        xx = np.linspace(0, qx.max() * 1.1, 20)
        axes[1].plot(xx, 1.0 + alpha * xx, "-", color=RED,
                     label=f"Garstecki form, $\\alpha$={alpha:.2f}")
        axes[1].plot(xx, 1.0 + 1.0 * xx, "--", color="grey",
                     label="Garstecki, $\\alpha$=1")
        axes[1].legend()
    axes[1].set_xlabel(r"$Q_r=Q_d/Q_c$"); axes[1].set_ylabel(r"$L/w_c$")
    axes[1].set_title("(b) Garstecki scaling (Ca≈0.012)")
    # (c) regime map Ca vs Qr
    for r in rows:
        if r[0] not in ("Ca", "Qr"):
            continue
        droplet = float(r[8]) > 0
        axes[2].plot(r[2], float(r[3]), "o" if droplet else "x",
                     color=TEAL if droplet else RED, ms=9)
    axes[2].plot([], [], "o", color=TEAL, label="droplet (pinch)")
    axes[2].plot([], [], "x", color=RED, label="thread / no pinch")
    axes[2].set_xlabel("Ca"); axes[2].set_ylabel(r"$Q_r$")
    axes[2].set_title("(c) Regime map"); axes[2].legend()
    fig.tight_layout(); fig.savefig(os.path.join(FIG, "fig_sweeps.png"))
    plt.close(fig)


def main():
    t0 = time.time()
    sigma, r2 = laplace()
    print(f"sigma_measured={sigma:.5f} theory={SIGMA_THEORY:.5f} R2={r2:.4f}")
    with open(os.path.join(DAT, "summary.txt"), "w") as fh:
        fh.write(f"sigma_measured {sigma}\n")
        fh.write(f"sigma_theory {SIGMA_THEORY}\n")
        fh.write(f"laplace_R2 {r2}\n")
    err = poiseuille(sigma)
    with open(os.path.join(DAT, "summary.txt"), "a") as fh:
        fh.write(f"poiseuille_rel_rms_percent {err}\n")
    contact_angle()
    pinch, Ca = hero(sigma)
    with open(os.path.join(DAT, "summary.txt"), "a") as fh:
        fh.write(f"hero_Ca {Ca}\nhero_pinch {pinch}\n")
    pinch_sequence(sigma)
    rows = sweep(sigma)
    regime_figure(sigma, rows)
    print(f"ALL DONE in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
