"""
Presentation-styled figures for the slide deck (large type, clean axes,
one palette shared with build_slides.py).

    python3 make_slide_figures.py
    -> results/slides/*.png

Plots are drawn from the CSVs written by run_all.py.  The phase-field
frames need the phi fields themselves, so the reference case and the
sessile-droplet tests are re-run once and cached in
results/data/slide_fields.npz (delete it to force a re-run).
"""

import csv
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.colors import LinearSegmentedColormap

from lbm_tjunction.solver import TJunction, _step, equilibrium, INTERFACE_W

ROOT = os.path.dirname(os.path.abspath(__file__))
DAT = os.path.join(ROOT, "results", "data")
OUT = os.path.join(ROOT, "results", "slides")
CACHE = os.path.join(DAT, "slide_fields.npz")
os.makedirs(OUT, exist_ok=True)

NAVY = "#0B1F3A"
BLUE = "#2364AA"
ORANGE = "#F29E4C"
TEAL = "#1B998B"
RED = "#D1495B"
GREY = "#5B6573"
LINE = "#C9D3DE"
OIL = "#F6E2B3"
WALL = "#DDE3EA"

for path in ["/Applications/LibreOffice.app/Contents/Resources/fonts/truetype"]:
    if os.path.isdir(path):
        for fn in os.listdir(path):
            if fn.startswith("Carlito"):
                font_manager.fontManager.addfont(os.path.join(path, fn))
FAMILY = ("Carlito" if any(f.name == "Carlito" for f in font_manager.fontManager.ttflist)
          else "DejaVu Sans")

plt.rcParams.update({
    "font.family": FAMILY, "mathtext.fontset": "custom",
    "mathtext.rm": FAMILY, "mathtext.it": f"{FAMILY}:italic",
    "mathtext.bf": f"{FAMILY}:bold",
    "font.size": 15, "axes.labelsize": 17, "xtick.labelsize": 14,
    "ytick.labelsize": 14, "legend.fontsize": 14, "legend.frameon": False,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.edgecolor": GREY, "axes.labelcolor": NAVY, "xtick.color": GREY,
    "ytick.color": GREY, "axes.linewidth": 1.1, "axes.grid": True,
    "grid.color": "#E6EBF1", "grid.linewidth": 0.9, "axes.axisbelow": True,
    "figure.dpi": 100, "savefig.dpi": 220, "savefig.bbox": "tight",
    "savefig.pad_inches": 0.06,
})

PHI_CMAP = LinearSegmentedColormap.from_list("oil_water", [OIL, "#9DB8D9", "#1D4E89"])
PHI_CMAP_DARK = LinearSegmentedColormap.from_list("oil_water_dark",
                                                  [OIL, "#A9CBEF", "#3C8DDE"])


def read_csv(name):
    with open(os.path.join(DAT, name)) as fh:
        return list(csv.DictReader(fh))


def summary():
    out = {}
    for line in open(os.path.join(DAT, "summary.txt")):
        k, _, v = line.strip().partition(" ")
        out[k] = v
    return out


# ------------------------------------------------------------ phi fields --
HERO_STEPS = (3000, 15000, 23500, 24500, 27000)
CONTACT_W = (-0.8, -0.5, -0.2, 0.0, 0.3, 0.6)


def compute_fields():
    print("re-running reference case for slide frames (~1 min) ...", flush=True)
    t = TJunction(nu_c=0.05)
    fields = {}
    for chunk in range(max(HERO_STEPS) // 500):
        out = t.run(uc_mean=0.003, q_ratio=0.5, steps=500)
        step = (chunk + 1) * 500
        if step in HERO_STEPS:
            fields[f"hero_{step}"] = out["phi"].copy()
    fields["solid"] = t.solid.copy()
    for wet in CONTACT_W:
        W, N, wall = 80, 120, 10
        solid = np.ones((W, N), dtype=bool); solid[wall:, :] = False
        y, x = np.mgrid[0:W, 0:N]
        d = np.sqrt((x - 60) ** 2 + (y - wall) ** 2)
        phi = np.where(y >= wall, np.tanh((22 - d) / INTERFACE_W), -1.0)
        phi = np.where(solid, -1.0, phi)
        f = equilibrium(np.ones((W, N)), np.zeros((W, N)), np.zeros((W, N)))
        fn, pn, mu = f.copy(), phi.copy(), np.zeros((W, N))
        for _ in range(3500):
            _step(f, fn, phi, pn, mu, solid, 0.05, 0.05, wet)
            f, fn, phi, pn = fn, f, pn, phi
        fields[f"contact_{wet:+.1f}"] = phi.copy()
    np.savez_compressed(CACHE, **fields)
    return dict(np.load(CACHE))


def load_fields():
    if os.path.exists(CACHE):
        d = dict(np.load(CACHE))
        if all(f"hero_{s}" in d for s in HERO_STEPS):
            return d
    return compute_fields()


def phi_rgba(phi, solid, wall_rgba, cmap=PHI_CMAP):
    rgba = cmap((np.clip(phi, -1, 1) + 1) / 2)
    rgba[solid] = wall_rgba
    return rgba


def field_panel(phi, solid, x0, x1, y0, y1, name, width_in, transparent=False,
                line=NAVY, cmap=PHI_CMAP):
    wall = (0, 0, 0, 0) if transparent else matplotlib.colors.to_rgba(WALL)
    img = phi_rgba(phi, solid, wall, cmap)[y0:y1, x0:x1]
    h_in = width_in * (y1 - y0) / (x1 - x0)
    fig = plt.figure(figsize=(width_in, h_in))
    ax = fig.add_axes([0, 0, 1, 1]); ax.set_axis_off()
    ax.imshow(img, origin="lower", interpolation="bicubic",
              extent=[x0, x1, y0, y1], aspect="auto")
    yy, xx = np.mgrid[y0:y1, x0:x1]
    sub = np.where(solid[y0:y1, x0:x1], -1.0, phi[y0:y1, x0:x1])
    ax.contour(xx + 0.5, yy + 0.5, sub, levels=[0], colors=line, linewidths=1.3)
    ax.set_xlim(x0, x1); ax.set_ylim(y0, y1)
    fig.savefig(os.path.join(OUT, name), transparent=transparent,
                bbox_inches=None, pad_inches=0)
    plt.close(fig)


def field_figures(fields):
    solid = fields["solid"].astype(bool)
    field_panel(fields["hero_24500"], solid, 40, 330, 30, 80, "phi_title.png",
                10.0, transparent=True, line="#FFFFFF", cmap=PHI_CMAP_DARK)
    for i, s in enumerate((3000, 15000, 23500, 24500), 1):
        field_panel(fields[f"hero_{s}"], solid, 100, 262, 26, 90,
                    f"stage_{i}.png", 4.0)
    field_panel(fields["hero_27000"], solid, 100, 300, 26, 90, "released.png", 5.0)
    for i, wet in enumerate(CONTACT_W):
        phi = fields[f"contact_{wet:+.1f}"]
        W, N = phi.shape
        cs = np.ones((W, N), dtype=bool); cs[10:, :] = False
        field_panel(phi, cs, 22, 98, 4, 50, f"contact_{i}.png", 2.6)


# ------------------------------------------------------------------ plots --
def save(fig, name):
    fig.savefig(os.path.join(OUT, name))
    plt.close(fig)


def laplace(sm):
    rows = read_csv("laplace.csv")
    R = np.array([float(r["R_lu"]) for r in rows])
    dp = np.array([float(r["dp_lu"]) for r in rows])
    sigma, r2 = float(sm["sigma_measured"]), float(sm["laplace_R2"])
    fig, ax = plt.subplots(figsize=(6.0, 4.1))
    xx = np.linspace(0, (1 / R).max() * 1.08, 50)
    ax.plot(xx, sigma * xx * 1e4, color=ORANGE, lw=2.6, zorder=2,
            label=fr"fit  $\Delta p=\sigma/R$,  $R^2={r2:.4f}$")
    ax.plot(1 / R, dp * 1e4, "o", color=BLUE, ms=11, mec="white", mew=1.5,
            zorder=3, label="LBM, static droplets R = 15–35")
    ax.set_xlabel(r"curvature  $1/R$  [lu$^{-1}$]")
    ax.set_ylabel(r"$\Delta p$  [$10^{-4}$ lu]")
    ax.set_xlim(0, None); ax.set_ylim(0, None)
    ax.legend(loc="upper left")
    save(fig, "laplace.png")


def poiseuille(sm):
    rows = read_csv("poiseuille.csv")
    y = np.array([float(r["y_lu"]) for r in rows]) - 30 + 0.5
    u = np.array([float(r["u_lbm"]) for r in rows])
    ua = np.array([float(r["u_analytical"]) for r in rows])
    fig, ax = plt.subplots(figsize=(6.0, 4.1))
    ax.plot(ua * 1e3, y, color=ORANGE, lw=2.6, label="analytical parabola")
    ax.plot(u * 1e3, y, "o", color=BLUE, ms=7.5, mec="white", mew=1.0,
            label="LBM")
    ax.set_xlabel(r"velocity  $u_x$  [$10^{-3}$ lu/step]")
    ax.set_ylabel(r"height across channel  [lu]")
    ax.set_xlim(0, None)
    ax.legend(loc="center left")
    save(fig, "poiseuille.png")


def contact_curve():
    rows = read_csv("contact_angle.csv")
    w = np.array([float(r["wetting_parameter"]) for r in rows])
    th = np.array([float(r["theta_deg"]) for r in rows])
    th_prod = float(np.interp(-0.6, w, th))
    fig, ax = plt.subplots(figsize=(5.4, 3.7))
    ax.axhline(90, color=LINE, lw=1.4, ls="--", zorder=1)
    ax.plot(w, th, "-", color=BLUE, lw=2.2, zorder=2)
    ax.plot(w, th, "o", color=BLUE, ms=10, mec="white", mew=1.4, zorder=3)
    ax.plot([-0.6], [th_prod], "D", color=ORANGE, ms=12, mec="white", mew=1.4,
            zorder=4)
    ax.annotate(f"production wall\nw = −0.6, θ ≈ {th_prod:.0f}°", (-0.6, th_prod),
                xytext=(-0.35, 150), color=NAVY, fontsize=14,
                arrowprops=dict(arrowstyle="-", color=GREY, lw=1.2))
    ax.text(0.62, 93, "neutral 90°", color=GREY, fontsize=12, ha="right",
            va="bottom")
    ax.set_xlabel("wetting parameter  w")
    ax.set_ylabel("contact angle  θ  [°]")
    ax.set_ylim(40, 165)
    save(fig, "contact_curve.png")
    return th_prod


def pressure(sm):
    rows = read_csv("hero_pressure.csv")
    s = np.array([float(r["step"]) for r in rows])
    p = np.array([float(r["p_upstream_lu"]) for r in rows])
    m = s >= 3000
    s, p = s[m], p[m]
    k = 9
    ps = np.convolve(p, np.ones(k) / k, mode="same")
    ps[:k] = p[:k]; ps[-k:] = p[-k:]
    pinch = 24500
    fig, ax = plt.subplots(figsize=(8.4, 4.0))
    ax.axvspan(3, 20, color="#E4ECF6", zorder=0)
    ax.axvspan(20, pinch / 1000, color="#FBE1C6", zorder=0)
    ax.plot(s / 1000, (ps - 1 / 3) * 1e4, color=BLUE, lw=2.4, zorder=3)
    ax.axvline(pinch / 1000, color=RED, lw=2.0, ls="--", zorder=4)
    top = ((ps - 1 / 3) * 1e4).max()
    ax.text(pinch / 1000 + 0.3, top * 0.97, "pinch-off\nstep 24 500", color=RED,
            fontsize=14, va="top")
    ax.text(11.5, top * 1.06, "slug fills & blocks the channel", color=GREY,
            fontsize=13, ha="center")
    ax.text(22.25, top * 1.06, "waist\nthins", color="#B86A1E", fontsize=13,
            ha="center", va="bottom", linespacing=0.95)
    ax.set_ylim(None, top * 1.2)
    ax.set_xlabel("time  [thousand steps]")
    ax.set_ylabel(r"$p - p_0$  [$10^{-4}$ lu]")
    ax.set_xlim(3, 30)
    ax.grid(axis="x")
    save(fig, "pressure.png")


def sweeps():
    rows = read_csv("sweep.csv")
    pts = []
    for r in rows:
        L = float(r["L_over_wc"])
        if L > 0 and ((r["series"] == "Ca" and abs(float(r["Qr"]) - 0.5) < 1e-9
                       and abs(float(r["Uc"]) - 0.003) < 1e-9) or r["series"] == "Qr"):
            pts.append((float(r["Qr"]), L))
    pts = sorted(set(pts))
    qx = np.array([a for a, _ in pts]); qy = np.array([b for _, b in pts])
    alpha = float(np.sum(qx * (qy - 1.0)) / np.sum(qx * qx))

    fig, ax = plt.subplots(figsize=(6.0, 4.3))
    xx = np.linspace(0, 1.15, 20)
    ax.plot(xx, 1 + xx, "--", color=GREY, lw=1.8, label=r"Garstecki,  $\alpha = 1$")
    ax.plot(xx, 1 + alpha * xx, "-", color=ORANGE, lw=2.8,
            label=fr"best fit,  $\alpha = {alpha:.2f}$")
    ax.plot(qx, qy, "o", color=BLUE, ms=13, mec="white", mew=1.6, zorder=3,
            label="LBM droplets")
    ax.set_xlabel(r"flow-rate ratio  $Q_d/Q_c$")
    ax.set_ylabel(r"droplet length  $L/w_c$")
    ax.set_xlim(0, 1.15); ax.set_ylim(0.9, 2.25)
    ax.legend(loc="upper left")
    save(fig, "garstecki.png")

    fig, ax = plt.subplots(figsize=(6.0, 4.3))
    ax.add_patch(matplotlib.patches.FancyBboxPatch(
        (0.0105, 0.12), 0.017, 1.03, boxstyle="round,pad=0,rounding_size=0.004",
        fc="#DDF1ED", ec="none", zorder=0, mutation_aspect=25))
    ax.text(0.019, 1.22, "droplet window", color=TEAL, fontsize=14,
            ha="center", va="bottom", fontweight="bold")
    for r in rows:
        if r["series"] not in ("Ca", "Qr"):
            continue
        ca, q, L = float(r["Ca"]), float(r["Qr"]), float(r["L_over_wc"])
        if L > 0:
            ax.plot(ca, q, "o", color=TEAL, ms=14, mec="white", mew=1.6, zorder=3)
        elif ca < 0.01:
            ax.plot(ca, q, "o", mfc="white", mec=GREY, mew=2.0, ms=13, zorder=3)
        else:
            ax.plot(ca, q, "X", color=RED, ms=14, mec="white", mew=1.2, zorder=3)
    ax.plot([], [], "o", color=TEAL, ms=12, label="droplet released")
    ax.plot([], [], "X", color=RED, ms=12, label="continuous thread")
    ax.plot([], [], "o", mfc="white", mec=GREY, mew=2.0, ms=11,
            label="needs longer run")
    ax.set_xlabel("capillary number  Ca")
    ax.set_ylabel(r"flow-rate ratio  $Q_d/Q_c$")
    ax.set_xlim(0, 0.09); ax.set_ylim(0, 2.3)
    ax.legend(loc="center right", borderaxespad=0.2, handletextpad=0.3)
    save(fig, "regime_map.png")
    return alpha


def ca_strip():
    rows = [r for r in read_csv("sweep.csv") if r["series"] == "Ca"]
    fig, ax = plt.subplots(figsize=(12.0, 2.15))
    ax.axvspan(0.0105, 0.0275, color="#DDF1ED", zorder=0)
    ax.text(0.019, -0.72, "droplet window", color=TEAL, fontsize=15,
            fontweight="bold", ha="center", va="center")
    ax.plot([0.018, 0.018], [-0.4, 1.05], ls=(0, (4, 3)), color=ORANGE, lw=2.2,
            zorder=1)
    ax.text(0.0186, 1.08, "Liu & Zhang (2009):  Ca ≈ 0.018", color="#C46A16",
            fontsize=14, va="bottom")
    pinched = [float(r["Ca"]) for r in rows if float(r["L_over_wc"]) > 0]
    for r in rows:
        ca, L = float(r["Ca"]), float(r["L_over_wc"])
        if L > 0:
            ax.plot(ca, 0, "o", color=TEAL, ms=22, mec="white", mew=2, zorder=3)
            left = ca == min(pinched) and len(pinched) > 1
            ax.text(ca + (-0.0006 if left else 0.0006), 0.42,
                    f"L/w$_c$ = {L:.2f}", color=TEAL, fontsize=15,
                    ha="right" if left else "left", fontweight="bold")
        elif ca < 0.01:
            ax.plot(ca, 0, "o", mfc="white", mec=GREY, mew=2.4, ms=20, zorder=3)
        else:
            ax.plot(ca, 0, "X", color=RED, ms=22, mec="white", mew=1.5, zorder=3)
    ax.set_ylim(-1.0, 1.5); ax.set_xlim(0, 0.09)
    ax.set_yticks([]); ax.spines["left"].set_visible(False)
    ax.grid(False)
    ax.set_xlabel("capillary number  Ca  (Q$_d$/Q$_c$ = 0.5, λ = 1)")
    save(fig, "ca_strip.png")


def release_bars(name, labels, steps, lengths, window=26000):
    fig, ax = plt.subplots(figsize=(6.0, 2.7))
    ypos = np.arange(len(labels))[::-1]
    for y, s, L in zip(ypos, steps, lengths):
        if s > 0:
            ax.barh(y, s / 1000, height=0.58, color=TEAL, zorder=2)
            ax.text(s / 1000 + 0.5, y, f"{s / 1000:.1f} k   ·   L/w$_c$ = {L:.2f}",
                    va="center", fontsize=14, color=NAVY)
        else:
            ax.barh(y, window / 1000, height=0.58, color="#EEF1F5", ec=LINE,
                    hatch="///", lw=0, zorder=2)
            ax.text(1.0, y, "no release within the 26 k-step window", va="center",
                    fontsize=14, color=GREY)
    ax.set_yticks(ypos); ax.set_yticklabels(labels, fontsize=15, color=NAVY)
    ax.tick_params(axis="y", length=0)
    ax.set_xlim(0, 40); ax.set_xticks([0, 10, 20, 26])
    ax.set_xlabel("release time  [thousand steps]")
    ax.spines["left"].set_visible(False)
    ax.grid(axis="y", visible=False)
    save(fig, name)


def release_figures():
    rows = read_csv("sweep.csv")
    contact = read_csv("contact_angle.csv")
    w = np.array([float(r["wetting_parameter"]) for r in contact])
    th = np.array([float(r["theta_deg"]) for r in contact])

    def get(series, key, val):
        if series == "base":
            r = next(r for r in rows if r["series"] == "Ca"
                     and abs(float(r["Uc"]) - 0.003) < 1e-9)
        else:
            r = next(r for r in rows if r["series"] == series
                     and abs(float(r[key]) - val) < 1e-9)
        return int(r["pinch_step"]), float(r["L_over_wc"])

    lam = [get("lambda", "lambda", 0.2), get("base", "", 0), get("lambda", "lambda", 5.0)]
    release_bars("lambda_bars.png", ["λ = 0.2", "λ = 1", "λ = 5"],
                 [a for a, _ in lam], [b for _, b in lam])
    wet = [get("base", "", 0), get("wetting", "wetting", -0.2),
           get("wetting", "wetting", 0.2)]
    labels = [f"θ ≈ {np.interp(v, w, th):.0f}°" for v in (-0.6, -0.2, 0.2)]
    release_bars("wetting_bars.png", labels, [a for a, _ in wet],
                 [b for _, b in wet])


def qr_code():
    try:
        import qrcode
    except ImportError:
        print("qrcode not installed; skipping QR code")
        return
    from project_meta import GITHUB
    q = qrcode.QRCode(border=1, box_size=12,
                      error_correction=qrcode.constants.ERROR_CORRECT_M)
    q.add_data(GITHUB); q.make(fit=True)
    q.make_image(fill_color=NAVY, back_color="white").save(
        os.path.join(OUT, "qr_github.png"))


def main():
    sm = summary()
    field_figures(load_fields())
    laplace(sm)
    poiseuille(sm)
    th = contact_curve()
    pressure(sm)
    alpha = sweeps()
    ca_strip()
    release_figures()
    qr_code()
    print(f"slide figures written to {OUT}  (theta(-0.6) = {th:.1f} deg, "
          f"alpha = {alpha:.2f})")


if __name__ == "__main__":
    main()
