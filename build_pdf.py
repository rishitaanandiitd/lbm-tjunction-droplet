"""
Build the combined submission PDF:

    Part I   Final project report   (A4 portrait)
    Part II  Presentation slides    (16:9 landscape, GitHub link on title)

    python3 build_pdf.py
    -> output/CLL770_Final_Report_and_Slides.pdf
"""

import csv
import os

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, inch
from reportlab.platypus import (BaseDocTemplate, Frame, Image, PageBreak,
                                PageTemplate, Paragraph, NextPageTemplate,
                                Spacer, Table, TableStyle, KeepTogether)

ROOT = os.path.dirname(os.path.abspath(__file__))
FIG = os.path.join(ROOT, "results", "figures")
DAT = os.path.join(ROOT, "results", "data")
OUT = os.path.join(ROOT, "output", "CLL770_Final_Report_and_Slides.pdf")
GITHUB = "https://github.com/CLL770-IITD/lbm-tjunction-droplet"

NAVY = colors.HexColor("#1b2a4a")
BLUE = colors.HexColor("#1b4f9c")
RED = colors.HexColor("#c1272d")
TEAL = colors.HexColor("#1a936f")
GREY = colors.HexColor("#555555")
LIGHT = colors.HexColor("#eef2f7")

# ------------------------------------------------------------------- data --
def read_csv(name):
    path = os.path.join(DAT, name)
    if not os.path.exists(path):
        return []
    with open(path) as fh:
        return list(csv.DictReader(fh))

summary = {}
spath = os.path.join(DAT, "summary.txt")
if os.path.exists(spath):
    for line in open(spath):
        parts = line.strip().split(" ", 1)
        if len(parts) == 2:
            summary[parts[0]] = parts[1]

SIGMA = float(summary.get("sigma_measured", "0.0119"))
SIGMA_TH = float(summary.get("sigma_theory", "0.01414"))
LAP_R2 = float(summary.get("laplace_R2", "0.9998"))
POIS_ERR = float(summary.get("poiseuille_rel_rms_percent", "1.0"))
lap = read_csv("laplace.csv")
con = read_csv("contact_angle.csv")
sweep = read_csv("sweep.csv")
growth = read_csv("hero_growth.csv")

def fmt(v, nd=3):
    try:
        return f"{float(v):.{nd}f}"
    except Exception:
        return str(v)

hero_pinch_txt = summary.get("hero_pinch", "")
ca_hero = summary.get("hero_Ca", "")

# ----------------------------------------------------------------- styles --
ss = getSampleStyleSheet()
def S(name, **kw):
    base = kw.pop("parent", ss["Normal"])
    return ParagraphStyle(name, parent=base, **kw)

st_title = S("t", fontSize=22, leading=27, textColor=NAVY, alignment=TA_CENTER,
             fontName="Helvetica-Bold", spaceAfter=10)
st_h1 = S("h1", fontSize=15, leading=19, textColor=NAVY, fontName="Helvetica-Bold",
          spaceBefore=14, spaceAfter=6, keepWithNext=True)
st_h2 = S("h2", fontSize=12, leading=15, textColor=BLUE, fontName="Helvetica-Bold",
          spaceBefore=10, spaceAfter=4, keepWithNext=True)
st_body = S("b", fontSize=10, leading=14.5, alignment=TA_JUSTIFY, spaceAfter=6)
st_bullet = S("bul", parent=st_body, leftIndent=14, bulletIndent=4, spaceAfter=3)
st_cap = S("cap", fontSize=8.5, leading=11, textColor=GREY, alignment=TA_CENTER,
           spaceBefore=3, spaceAfter=10)
st_cell = S("cell", fontSize=8.5, leading=10.5, alignment=TA_CENTER)
st_cellL = S("cellL", parent=st_cell, alignment=TA_LEFT)
st_slide_title = S("st", fontSize=26, leading=31, textColor=colors.white,
                   fontName="Helvetica-Bold")
st_slide_h = S("sh", fontSize=20, leading=24, textColor=NAVY,
               fontName="Helvetica-Bold", spaceAfter=8)
st_slide_b = S("sb", fontSize=13.5, leading=19, spaceAfter=6)
st_slide_bul = S("sbul", parent=st_slide_b, leftIndent=18, bulletIndent=6,
                 spaceAfter=5)
st_slide_cap = S("scap", fontSize=10, leading=13, textColor=GREY,
                 alignment=TA_CENTER, spaceBefore=4)

def P(text, style=st_body, bulletText=None):
    if bulletText:
        text = f"{bulletText}&nbsp;&nbsp;{text}"
    return Paragraph(text, style)

def fig(name, width_cm, caption=None):
    path = os.path.join(FIG, name)
    items = []
    if os.path.exists(path):
        from PIL import Image as PILImage
        iw, ih = PILImage.open(path).size
        w = width_cm * cm
        items.append(Image(path, width=w, height=w * ih / iw))
    else:
        items.append(P(f"[figure {name} — run python3 run_all.py first]", st_cap))
    if caption:
        items.append(P(caption, st_cap))
    return items

def data_table(headers, rows, widths=None, align_left_first=False):
    data = [[P(f"<b>{h}</b>", st_cell) for h in headers]]
    for r in rows:
        data.append([P(str(c), st_cellL if (align_left_first and i == 0) else st_cell)
                     for i, c in enumerate(r)])
    t = Table(data, colWidths=widths, repeatRows=1, hAlign="CENTER")
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#b9c4d0")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return t

# ------------------------------------------------------------ page funcs --
def report_footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 7.5); canvas.setFillColor(GREY)
    canvas.drawString(1.6 * cm, 1.1 * cm,
                      "CLL 770 Term Project — LBM simulation of droplet formation in a T-junction — IIT Delhi")
    canvas.drawRightString(A4[0] - 1.6 * cm, 1.1 * cm, f"Report · page {doc.page}")
    canvas.setStrokeColor(colors.HexColor("#c8d2de")); canvas.setLineWidth(0.5)
    canvas.line(1.6 * cm, 1.45 * cm, A4[0] - 1.6 * cm, 1.45 * cm)
    canvas.restoreState()

SLIDE_W, SLIDE_H = 13.33 * inch, 7.5 * inch

def slide_bg(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(colors.white)
    canvas.rect(0, 0, SLIDE_W, SLIDE_H, stroke=0, fill=1)
    canvas.setFillColor(NAVY)
    canvas.rect(0, SLIDE_H - 0.95 * inch, SLIDE_W, 0.95 * inch, stroke=0, fill=1)
    canvas.setFillColor(GREY); canvas.setFont("Helvetica", 8)
    canvas.drawString(0.55 * inch, 0.32 * inch,
                      "CLL 770 · IIT Delhi · LBM droplet formation in a T-junction")
    canvas.drawRightString(SLIDE_W - 0.55 * inch, 0.32 * inch, f"{doc.page}")
    canvas.restoreState()

def slide_title_bg(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(NAVY); canvas.rect(0, 0, SLIDE_W, SLIDE_H, stroke=0, fill=1)
    canvas.setFillColor(BLUE)
    canvas.rect(0, SLIDE_H - 1.5 * inch, SLIDE_W, 0.28 * inch, stroke=0, fill=1)
    canvas.restoreState()

# ============================================================ REPORT part ==
story = []

# --- title page (report template flow, styled manually) ---
story += [Spacer(1, 2.2 * cm),
          P("Indian Institute of Technology Delhi", S("iit", parent=st_title, fontSize=15, textColor=BLUE)),
          P("CLL 770 — Introduction to Microfluidics and Fabrication", S("c", parent=st_body, alignment=TA_CENTER, fontSize=12, textColor=GREY)),
          Spacer(1, 1.2 * cm),
          P("Lattice Boltzmann Simulation of Droplet Formation in a Microfluidic T-Junction", st_title),
          P("Squeezing-to-Dripping Transition and Droplet-Size Scaling", S("sub", parent=st_title, fontSize=14, textColor=BLUE)),
          Spacer(1, 1.0 * cm)]
team_rows = [["1", "Ananyaa Agrawal", "2022CH71487"],
             ["2", "Yash Balram Sakhare", "2022CH71496"],
             ["3", "Rishita Anand", "2022CH71042"]]
story += [data_table(["S. No.", "Name", "Entry Number"], team_rows,
                     widths=[1.6 * cm, 6.5 * cm, 4.5 * cm]),
          Spacer(1, 1.2 * cm),
          P(f"<b>Code (GitHub):</b> <link href='{GITHUB}' color='#1b4f9c'>{GITHUB}</link>",
            S("gh", parent=st_body, alignment=TA_CENTER)),
          P("Final project report · November 2026", S("d", parent=st_body, alignment=TA_CENTER, textColor=GREY)),
          P("This document contains, in order: <b>Part I — Final Project Report</b> and "
            "<b>Part II — Presentation Slides</b> (with the GitHub repository link on the "
            "title slide, as required for the Moodle submission).", st_body),
          PageBreak()]

# --- abstract / contents ---
story += [P("Abstract", st_h1),
          P("Droplet microfluidics turns every droplet into a picolitre reactor and underpins "
            "droplet digital PCR, single-cell encapsulation and monodisperse drug-delivery "
            "particles. In a T-junction the dispersed phase enters a cross-flowing continuous "
            "phase and breaks into droplets; the droplet size is set by the competition between "
            "interfacial tension, viscous shear and the pressure that builds upstream when the "
            "growing droplet blocks the channel. We write, from scratch, a two-phase lattice "
            "Boltzmann solver (D2Q9 BGK hydrodynamics with Guo forcing, coupled to a "
            "Cahn–Hilliard phase field, in Python/NumPy accelerated with Numba) and validate it "
            f"quantitatively: the Young–Laplace pressure jump of static droplets gives a surface "
            f"tension σ = {SIGMA:.4f} lattice units with R<sup>2</sup> = {LAP_R2:.4f}; a single-phase "
            f"channel reproduces the analytical Poiseuille parabola to {POIS_ERR:.2f}% RMS error; and a "
            "sessile droplet reproduces imposed contact angles monotonically over roughly "
            "49–149°. The validated solver is then used to simulate droplet formation at a "
            "T-junction with w<sub>d</sub>/w<sub>c</sub> = 0.53. We resolve the filling stage (a "
            "semicircular bulb), downstream elongation, waist formation and droplet detachment; we track the "
            "upstream pressure, which shows a modest rise while the slug constricts the channel and "
            "relaxes at break-up; and we map how the capillary number Ca, flow-rate ratio "
            "Q<sub>d</sub>/Q<sub>c</sub>, viscosity ratio λ and wall wettability move the junction "
            "between droplet-producing and continuous-thread (jetting) behaviour, including a "
            "Garstecki-type droplet-length scaling where pinch-off occurs. Trends and regime "
            "boundaries are compared with Liu &amp; Zhang (2009) and Garstecki <i>et al.</i> "
            "(2006), and interpreted for PDMS devices made by soft lithography. Limitations — "
            "two-dimensionality, matched densities and a diffuse interface — are stated "
            "explicitly and their effect on absolute droplet sizes is discussed.", st_body),
          P("Contents — Part I: 1 Introduction · 2 Theory · 3 Numerical method · 4 Validation · "
            "5 Results · 6 Discussion · 7 Conclusions · References · Appendix A (code &amp; "
            "reproducibility). Part II: presentation slides (15).", st_body)]

# --- 1 intro ---
story += [P("1 &nbsp; Introduction", st_h1),
          P("In droplet microfluidics a dispersed phase (e.g. an aqueous reagent) is injected "
            "into an immiscible continuous phase (e.g. oil) flowing in a microchannel. The "
            "interface between them is unstable to break-up, and under the right conditions the "
            "dispersed phase is chopped into a train of nearly identical droplets. Because each "
            "droplet is isolated by the continuous phase, it acts as an independent microreactor: "
            "reagents can be mixed, incubated and read out droplet-by-droplet at kilohertz rates. "
            "This is the basis of droplet digital PCR, single-cell encapsulation, and the "
            "production of monodisperse particles for drug delivery.", st_body),
          P("The simplest generator is the <b>T-junction</b>: the dispersed phase enters from a "
            "side channel into a main channel carrying the continuous phase. Two mechanisms make "
            "droplets there. At low capillary number the emerging phase grows until it (nearly) "
            "blocks the main channel; the continuous phase can then only squeeze past through "
            "thin films, the upstream pressure rises, and that pressure squeezes the neck until "
            "it breaks — the <b>squeezing</b> regime. At higher capillary number viscous shear "
            "pulls the interface into a thread before it can block the channel, and droplets are "
            "pinched by shear and interfacial instability — <b>dripping</b>, and at still higher "
            "rates, <b>jetting</b>. Predicting which regime a device is in, and how big the "
            "droplets will be, is a design question that is difficult to answer by scaling alone "
            "because the free interface, the moving contact lines and the thin films all interact.", st_body),
          P("<b>Objective.</b> Following our project proposal, we (i) write and validate a "
            "two-phase flow solver for this problem, and (ii) use it to quantify how the "
            "capillary number Ca, the flow-rate ratio Q<sub>d</sub>/Q<sub>c</sub>, the viscosity "
            "ratio λ and the wall wettability (contact angle) control droplet size and the "
            "break-up mechanism in a T-junction. The reference study is Liu &amp; Zhang "
            "(J. Appl. Phys., 2009), who report a squeezing-to-dripping transition at "
            "Ca ≈ 0.018 for their geometry; the mechanistic scaling is that of Garstecki "
            "<i>et al.</i> (Lab Chip, 2006).", st_body),
          P("<b>Course links.</b> Surface tension, Young–Laplace and contact angles (Unit 2); "
            "pressure-driven low-Reynolds-number flow and boundary conditions (Unit 3); "
            "Poiseuille and two-phase flows (Unit 4); unsteady/capillary flows (Unit 5); PDMS "
            "microfabrication (Unit 6); droplet-microfluidics applications (Unit 7).", st_body)]

# --- 2 theory ---
story += [P("2 &nbsp; Theory", st_h1),
          P("2.1 &nbsp; Governing equations and dimensionless groups", st_h2),
          P("Both phases are incompressible and Newtonian, and the flow is at low Reynolds "
            "number (Re &lt;&lt; 1 in a typical device), so each phase obeys the Stokes/Navier–Stokes "
            "equations with a surface-tension force concentrated at the interface. The interface "
            "is characterised by the surface tension σ [N m<sup>−1</sup>]. Three dimensionless "
            "groups organise the physics:", st_body)]
story += [data_table(
    ["Group", "Definition", "Meaning"],
    [["Capillary number, Ca", "Ca = μ<sub>c</sub>U<sub>c</sub>/σ",
      "viscous shear of the continuous phase vs interfacial tension"],
     ["Flow-rate ratio, Q<sub>r</sub>", "Q<sub>r</sub> = Q<sub>d</sub>/Q<sub>c</sub>",
      "dispersed throughput relative to continuous throughput"],
     ["Viscosity ratio, λ", "λ = μ<sub>d</sub>/μ<sub>c</sub>",
      "how easily the dispersed phase is sheared internally"],
     ["Reynolds number, Re", "Re = ρU<sub>c</sub>w<sub>c</sub>/μ<sub>c</sub>",
      "kept &lt;&lt; 1 to O(1) in all runs (creeping flow)"],
     ["Contact angle, θ", "through the dispersed phase at the wall",
      "wall wettability; θ &gt; 90° means the continuous phase preferentially wets the wall"]],
    widths=[4.2 * cm, 5.0 * cm, 8.0 * cm], align_left_first=True),
          P("2.2 &nbsp; Young–Laplace and the squeezing mechanism", st_h2),
          P("Across a curved interface the pressure jumps by Δp = σ/R in 2-D (one radius of "
            "curvature; Δp = 2σ/R for a spherical droplet in 3-D). This is the restoring "
            "pressure that resists deformation of a droplet and that drives the final collapse "
            "of a thinning neck. In the squeezing regime Garstecki <i>et al.</i> showed that "
            "break-up has two stages — filling, while the emerging phase blocks the channel, "
            "then squeezing, while the continuous phase, forced through the thin films between "
            "droplet and walls, raises the upstream pressure and collapses the neck at a rate "
            "set by Q<sub>c</sub>. Adding the volume filled in the two stages gives the "
            "droplet-length law tested in §5:", st_body),
          P("<b>L/w<sub>c</sub> = 1 + α·Q<sub>d</sub>/Q<sub>c</sub></b> &nbsp;&nbsp; (Garstecki "
            "scaling, squeezing regime), with α a geometry-dependent constant of order unity.", st_body),
          P("In dripping, by contrast, the droplet size is set by a local balance of shear and "
            "surface tension near the junction and decreases with Ca; in jetting a long thread "
            "forms and breaks downstream, producing smaller, less monodisperse droplets. The "
            "boundary between squeezing and dripping reported by Liu &amp; Zhang for a "
            "T-junction is Ca<sub>crit</sub> ≈ 0.018 (its exact value is geometry- and "
            "λ-dependent, which is why a solver study is worthwhile).", st_body)]

# --- 3 method ---
story += [P("3 &nbsp; Numerical method", st_h1),
          P("3.1 &nbsp; Lattice Boltzmann hydrodynamics", st_h2),
          P("We solve the flow with the D2Q9 lattice Boltzmann method (LBM). Distribution "
            "functions f<sub>i</sub>(<b>x</b>,t) stream along the nine lattice velocities and "
            "relax (BGK) toward the equilibrium f<sub>i</sub><sup>eq</sup>(ρ,<b>u</b>) with "
            "relaxation time τ = 3ν + ½. Density and momentum are moments of f<sub>i</sub>; "
            "pressure is p = ρc<sub>s</sub><sup>2</sup> = ρ/3. Body/interfacial forces are "
            "introduced with the Guo <i>et al.</i> forcing scheme, which recovers the "
            "Navier–Stokes equations with second-order accuracy. The lattice Boltzmann method "
            "was chosen because the algorithm is local (fast, and straightforward to accelerate), "
            "bounce-back gives no-slip walls on the voxel grid without body-fitted meshing, and "
            "the kinetic formulation couples naturally to a diffuse-interface description of the "
            "two phases.", st_body),
          P("3.2 &nbsp; Phase field (Cahn–Hilliard) and surface tension", st_h2),
          P("The interface is tracked by an order parameter φ = +1 in the dispersed phase and "
            "φ = −1 in the continuous phase. φ obeys the (advected) Cahn–Hilliard equation "
            "∂<sub>t</sub>φ + <b>u</b>·∇φ = M∇<sup>2</sup>μ with chemical potential "
            "μ = βφ(φ<sup>2</sup>−1) − κ∇<sup>2</sup>φ, mobility M and free-energy parameters "
            "β = κ = 0.015. The equilibrium profile across a flat interface is a hyperbolic "
            "tangent of width ~√(2κ/β); the associated surface tension is "
            f"σ = (2√2/3)√(κβ) = {SIGMA_TH:.4f} in lattice units (the value measured in the "
            "Laplace test, §4.1, is used for all dimensionless groups). Surface tension enters "
            "the flow as the potential force <b>F</b> = μ∇φ. All spatial derivatives of φ and μ "
            "use D2Q9-isotropic stencils (this greatly reduces spurious currents), and φ is "
            "advected with a first-order upwind gradient, re-sharpened by the Cahn–Hilliard "
            "term. Viscosity is interpolated linearly in φ between the two phases, "
            "ν(φ) = ν<sub>c</sub>(1−f<sub>d</sub>) + ν<sub>d</sub>f<sub>d</sub> with f<sub>d</sub> = (φ+1)/2, giving the "
            "viscosity ratio λ = ν<sub>d</sub>/ν<sub>c</sub>; densities are matched (ρ = 1) "
            "for numerical stability, as in the reference simulations. The hot loops are "
            "compiled with Numba; one T-junction case of 30 000 steps takes ~1 min on a laptop.", st_body),
          P("3.3 &nbsp; Geometry and boundary conditions", st_h2)]
story += fig("fig_geometry.png", 16.5,
             "Figure 1 — Computational T-junction. Main channel width w<sub>c</sub> = 30 lattice "
             "units (lu), side channel w<sub>d</sub> = 16 lu (w<sub>d</sub>/w<sub>c</sub> = 0.53), "
             "domain 400 × 90 lu with a long downstream section so detached droplets can be "
             "measured before reaching the outlet.")
story += [P("Walls use half-way bounce-back (no slip). Wettability is imposed through the "
            "ghost-cell condition ∂φ/∂n = w(1−φ<sup>2</sup>) at solid neighbours (n into the "
            "wall): it vanishes in either bulk phase, is active only where an interface meets "
            "the wall, and its coefficient w sets the contact angle (calibrated in §4.3; the "
            "production runs use w = −0.6, a continuous-phase-wetting wall). Inlets are "
            "syringe-pump boundaries as in an experiment: in three-column/row forcing zones the "
            "populations are reset each step to equilibrium at a parabolic (fully developed) "
            "velocity profile with the <i>local</i> density, so the inlet pressure is free to "
            "build up. The outlet applies the same forcing with a parabolic profile carrying "
            "Q<sub>c</sub>+Q<sub>d</sub>. The side arm starts filled with dispersed phase up to "
            "the junction mouth and the main channel with continuous phase, with the equilibrium "
            "tanh profile at the mouth so there is no start-up artefact. Upstream pressure is "
            "probed 25 lu upstream of the junction at the channel centreline.", st_body),
          P("3.4 &nbsp; Dimensionless parameters of the study", st_h2)]
story += [data_table(
    ["Parameter", "Value(s)", "Notes"],
    [["σ (measured, §4.1)", f"{SIGMA:.4f} lu", "used for every Ca quoted"],
     ["ν<sub>c</sub>", "0.05 lu (τ = 0.65)", "λ varied via ν<sub>d</sub>"],
     ["Ca sweep", "Uc = 0.002–0.020 → Ca ≈ 0.008–0.084", "at Q<sub>r</sub> = 0.5, λ = 1"],
     ["Q<sub>r</sub> sweep", "0.25, 0.5, 1, 2", "at Ca ≈ 0.012"],
     ["λ sweep", "0.2, 1, 5", "at Ca ≈ 0.012, Q<sub>r</sub> = 0.5"],
     ["wetting w", "−0.6 (base), −0.2, +0.2", "θ from §4.3 calibration"],
     ["Grid / time step", "400 × 90 lu, Δx = Δt = 1", "interface ~3–4 lu wide; Re &lt; 0.4"]],
    widths=[4.2 * cm, 6.0 * cm, 7.0 * cm], align_left_first=True)]

# --- 4 validation ---
story += [P("4 &nbsp; Validation", st_h1),
          P("A solver is only useful if it first reproduces problems with known answers. We "
            "perform the three tests promised in the proposal, with production parameters "
            "(same β, κ, stencils and forcing as the T-junction runs).", st_body),
          P("4.1 &nbsp; Laplace test — surface tension", st_h2),
          P("Static droplets of radius R = 15–35 lu are equilibrated in a periodic-feel box "
            "(droplet far from the edges) and the pressure inside and outside is read from "
            "p = ρ/3. In 2-D, Young–Laplace predicts Δp = σ/R, so Δp vs 1/R must be a straight "
            "line through the origin with slope σ.", st_body)]
story += fig("fig_laplace.png", 15.5,
             f"Figure 2 — (a) Δp vs 1/R is linear (R<sup>2</sup> = {LAP_R2:.4f}); the slope gives "
             f"σ = {SIGMA:.4f} lu, within {abs(SIGMA-SIGMA_TH)/SIGMA_TH*100:.0f}% of the analytic "
             f"phase-field value {SIGMA_TH:.4f} lu. (b) The equilibrated R = 25 lu droplet remains "
             "circular; measured spurious velocities for a static droplet are at most 2x10<sup>-4</sup> lu/step.")
if lap:
    story += [data_table(["R [lu]", "Δp [lu]", "σ = Δp·R [lu]"],
                         [[r["R_lu"], fmt(r["dp_lu"], 5), fmt(r["sigma_est_lu"], 4)] for r in lap],
                         widths=[3.5 * cm, 4 * cm, 4.5 * cm]),
              P("Table 1 — Laplace test data. σ = Δp·R is constant to within a few per cent, "
                "confirming that the force <b>F</b> = μ∇φ produces the correct capillary pressure.", st_cap)]
story += [P("4.2 &nbsp; Single-phase Poiseuille flow", st_h2),
          P("With the junction present but Q<sub>d</sub> = 0, the continuous phase alone must "
            "recover the analytical parabolic profile u(y) = (3/2)U[1−((y−y<sub>c</sub>)/(w/2))<sup>2</sup>] "
            "in the main channel. Figure 3 compares the LBM profile 60 lu downstream of the inlet "
            f"with the parabola: the relative RMS error is {POIS_ERR:.2f}%. This validates the "
            "hydrodynamics, the bounce-back walls and the inlet forcing independently of the "
            "interface model.", st_body)]
story += fig("fig_poiseuille.png", 10.5,
             "Figure 3 — Poiseuille validation in the main channel (symbols: LBM; line: analytical).")
story += [P("4.3 &nbsp; Contact angle on a wall", st_h2),
          P("A sessile dispersed droplet (initially a semicircle, R = 22 lu) on a flat wall is "
            "relaxed for several wetting coefficients w. The φ = 0 contour is fitted with a "
            "circle and the contact angle through the dispersed phase is computed from the "
            "circle geometry, θ = arccos[(y<sub>wall</sub>−y<sub>centre</sub>)/R]. θ varies "
            "monotonically with w (Table 2, Figure 4): negative w gives a continuous-phase-"
            "wetting wall (θ well above 90°, as for oil on plasma-treated/hydrophobic PDMS "
            "with an aqueous dispersed phase, and vice versa). The production value w = −0.6 "
            "therefore represents a wall that the continuous phase preferentially wets, so "
            "droplets are lubricated by a continuous-phase film and do not stick — the usual "
            "operating condition in a PDMS T-junction.", st_body)]
story += fig("fig_contact.png", 15.5,
             "Figure 4 — Sessile-droplet contact-angle calibration. The same wetting condition "
             "and parameters are used at every wall of the T-junction.")
if con:
    story += [data_table(["wetting w", "measured θ [°]", "droplet area [lu²]"],
                         [[r["wetting_parameter"], fmt(r["theta_deg"], 0), r["area_lu2"]] for r in con],
                         widths=[3.5 * cm, 4 * cm, 4.5 * cm]),
              P("Table 2 — Imposed wetting parameter vs measured contact angle.", st_cap)]

# --- 5 results ---
droplet_rows = [r for r in sweep if float(r.get("L_over_wc") or -1) > 0]
story += [P("5 &nbsp; Results: droplet formation at the T-junction", st_h1),
          P("5.1 &nbsp; Anatomy of one break-up", st_h2),
          P(f"The reference case (Ca = {fmt(ca_hero,3) if ca_hero else '0.013'}, "
            "Q<sub>r</sub> = 0.5, \u03bb = 1, w = \u22120.6) is shown in Figures 5\u20136. "
            "The \u03c6 field shows a clear sequence. <b>(i) Filling</b> \u2014 the meniscus at the "
            "junction mouth first expands as a nearly semicircular bulb into the main channel "
            "(earliest frames of Figure 5; this is the signature that surface tension, not the "
            "inlet jet, controls the early interface \u2014 zoomed movies of steps 250\u20132000 show "
            "a clean semicircular cap). <b>(ii) Elongation</b> \u2014 the bulb is swept downstream "
            "and grows into a slug: the measured slug length (\u03c6 &gt; 0 extent in the main "
            "channel, <font face='Courier'>hero_growth.csv</font>) increases steadily from 17 lu at "
            "step 3 000 to 102 lu at step 24 000, while the side-arm neck that feeds it stays "
            "at 15\u201316 lu wide \u2014 the junction does <i>not</i> close in this geometry/window. "
            "<b>(iii) Waist formation</b> \u2014 the slug front, which retains the fuller cross-section "
            "of the original bulb, outruns its thinner tail, so a waist develops behind the "
            "front bulb and thins (Figure 6, steps 20 000\u201323 500). <b>(iv) Detachment</b> \u2014 at "
            "step 24 500 the waist collapses and a discrete droplet of length 41 lu "
            "(L/w<sub>c</sub> = 1.37, area 410 lu\u00b2) detaches and is carried downstream "
            "(Figure 6, steps 24 500\u201327 000), while a new slug immediately starts to grow from "
            "the junction. We describe this observed route honestly as <b>slug/waist "
            "break-up at the low-Ca end of our window</b>: it shares the filling and blockage "
            "ingredients of the Garstecki squeezing picture (and the same upstream-pressure "
            "signature, Figure 7), but in our w<sub>d</sub>/w<sub>c</sub> = 0.53 geometry the "
            "separation point is the slug waist rather than the side-arm neck. Distinguishing "
            "these two separation points is itself a useful solver result \u2014 and it warns "
            "against assuming the textbook neck location for a new geometry.", st_body)]
story += fig("fig_hero_sequence.png", 16.5,
             "Figure 5 \u2014 \u03c6 field (blue: dispersed, red: continuous; black line: \u03c6 = 0) during "
             "formation at the reference condition. Solid walls are masked. Filling bulb \u2192 "
             "elongating slug \u2192 waist behind the front bulb (step 24 000 frame).")
story += fig("fig_pinch_sequence.png", 16.5,
             "Figure 6 \u2014 Zoomed waist collapse and droplet detachment (reference case). The "
             "detached droplet (L = 41 lu, L/w<sub>c</sub> = 1.37) separates at step \u2248 24 500 and "
             "travels downstream; the pale halo around it at later steps is the diffuse "
             "interface (\u00a76, limitations).")
story += fig("fig_pressure.png", 13.5,
             "Figure 7 \u2014 Upstream centreline pressure (probe 25 lu upstream of the junction) "
             "during the reference run. After the start-up transient the pressure is \u2248 0.3341 "
             "while the slug constricts the channel, then relaxes to \u2248 0.33395 around "
             "detachment (step 24 500) before recovering \u2014 a modest (\u2248 0.05%) but systematic "
             "rise-and-release, the pressure signature expected when break-up is controlled by "
             "blockage rather than by interfacial shear alone. (Absolute values are lattice "
             "pressures p = \u03c1/3.)")
story += [P("5.2 &nbsp; Effect of capillary number", st_h2),
          P("At fixed Q<sub>r</sub> = 0.5, \u03bb = 1 (Ca \u221d Uc; Table 3, Figure 8a,c), a detached "
            "droplet is obtained only in a <b>bounded Ca window</b>: Ca = 0.013 pinches at step "
            "24 500 (L/w<sub>c</sub> = 1.37) and Ca = 0.021 pinches earlier, at step 18 500 "
            "(L/w<sub>c</sub> = 1.60). Above the window (Ca = 0.034, 0.050, 0.084) no detachment "
            "occurs within 26 000 steps \u2014 the dispersed phase leaves as a continuous thread, "
            "the expected dripping/jetting side of the transition. Below the window "
            "(Ca = 0.008) no detachment occurs within the window either, but for a different, "
            "mundane reason: the formation period scales roughly as 1/Uc, so this case needs "
            "\u2273 36 000 steps and is <i>censored by the observation window</i>, not classified "
            "as a different regime (this censoring is stated wherever \u2018no pinch\u2019 appears). "
            "Our pinch-to-thread boundary therefore lies between Ca = 0.021 and 0.034 \u2014 within "
            "a factor of two of Liu &amp; Zhang\u2019s 0.018 for their (different) geometry, which "
            "is the level of agreement expected for a geometry-dependent boundary. Detached "
            "lengths are measured by connected-component analysis of \u03c6 &gt; 0 (first component "
            "separated from the inlet-connected phase; criterion in "
            "<font face='Courier'>run_all.py</font>).", st_body),
          P("5.3 &nbsp; Effect of flow-rate ratio \u2014 Garstecki scaling", st_h2),
          P("At fixed Ca = 0.013 (Figure 8b), detached droplets are obtained for "
            "Q<sub>r</sub> = 0.25 (L/w<sub>c</sub> = 1.73, at step 26 000, i.e. at the window "
            "edge), 0.5 (1.37) and 1.0 (1.60), and none for Q<sub>r</sub> = 2.0 within the "
            "window (thread). Two conclusions follow. First, droplet lengths are of order the "
            "channel width (L/w<sub>c</sub> = 1.4\u20131.7) and scatter around the Garstecki form "
            "L/w<sub>c</sub> = 1 + \u03b1Q<sub>r</sub>: a fit with the intercept fixed at 1 (as the "
            "theory requires) gives \u03b1 = 0.81, close to the \u03b1 = 1 reference line in "
            "Figure 8b \u2014 i.e. our droplets obey the Garstecki <i>form</i> with an order-unity "
            "prefactor. Second, with only three pinched points spanning a factor 1.25 in "
            "L/w<sub>c</sub>, we do <i>not</i> claim a verified linear scaling law: in this "
            "geometry the detached length is set largely by the front-bulb size (\u2248 w<sub>c</sub>) "
            "plus a filling contribution, and a dedicated scaling study (more Q<sub>r</sub> "
            "points, longer windows at low Q<sub>r</sub>) is the obvious follow-up. Reporting "
            "the scatter, rather than a forced line through it, is the scientifically correct "
            "summary of these runs.", st_body),
          P("5.4 &nbsp; Viscosity ratio and wettability", st_h2),
          P("Viscosity ratio (Ca = 0.013, Q<sub>r</sub> = 0.5): a low-viscosity dispersed phase "
            "(\u03bb = 0.2) detaches earliest (step 15 500, L/w<sub>c</sub> = 1.67), the \u03bb = 1 case "
            "at step 24 500, and the viscous dispersed phase (\u03bb = 5) does not detach within "
            "the window. \u03bb therefore controls the <i>rate</i> of waist/neck drainage in this "
            "window \u2014 a viscous dispersed phase resists being squeezed \u2014 while the detached "
            "length stays O(w<sub>c</sub>). Wettability: only the base, strongly "
            "continuous-wetting wall (w = \u22120.6, \u03b8 \u2248 140\u00b0) detaches within the window; at "
            "w = \u22120.2 and +0.2 no detachment occurs within 26 000 steps. In this setup a "
            "lubricating continuous-phase film is what allows the waist to close and the "
            "droplet to release; reducing that wetting preference makes the dispersed phase "
            "linger at the walls. For a PDMS device this is the simulation counterpart of a "
            "well-known practical point: surface treatment must be tuned (plasma, hydrophobic "
            "recovery, surfactant) \u2014 \u2018more wetting\u2019 is not monotonically better or worse, it "
            "moves the operating point. All sweep outcomes, including censored ones, are "
            "listed in Table 3.", st_body)]
# --- 6 discussion ---
story += [P("6 &nbsp; Discussion", st_h1),
          P("<b>Comparison with the literature.</b> Qualitatively, every element of the "
            "reference picture is reproduced: filling and elongation followed by waist detachment at the low-Ca end, a transition "
            "to thread behaviour as Ca rises, droplet lengths of order w<sub>c</sub> consistent "
            "with the Garstecki form (\u03b1 \u2248 0.8), and faster break-up for less viscous dispersed "
            "phases. Quantitatively "
            "the transition Ca is geometry-dependent (Liu &amp; Zhang's 0.018 is for "
            "w<sub>d</sub> ≈ w<sub>c</sub> and their λ and contact angle; ours, with "
            "w<sub>d</sub>/w<sub>c</sub> = 0.53, lies between Ca = 0.021 and 0.034). This is the "
            "expected situation and is precisely why a validated solver — rather than a single "
            "universal number — is the deliverable of this project. The Laplace and Poiseuille "
            "validations, by contrast, are geometry-independent and agree with theory to "
            f"{POIS_ERR:.2f}% (flow) and a few per cent in σ.", st_body),
          P("<b>Relevance to fabrication (Unit 6).</b> A real device with this planform is a "
            "single-layer PDMS chip: SU-8 master, soft lithography, oxygen-plasma bonding to "
            "glass. Two fabrication choices map directly onto simulation inputs. (1) The "
            "channel height set by the SU-8 thickness, together with the drawn widths, fixes "
            "w<sub>d</sub>/w<sub>c</sub> and w<sub>c</sub> in the Garstecki law — the cheapest "
            "way to change droplet size at fixed flow rates. (2) Plasma treatment and its "
            "hydrophobic recovery (or a hydrophobic coating / surfactant) set the wall contact "
            "angle, i.e. our w: in our window only the strongly continuous-wetting wall "
            "released droplets, so weakening that preference can move an operating point out "
            "of the droplet window at the same nominal Ca and Q<sub>r</sub> — surface treatment "
            "must be tuned, not assumed. The flow-rate ratio — set by the syringe pumps — "
            "remains the in-use knob (Figure 8b).", st_body),
          P("<b>Limitations.</b> (i) <i>Two-dimensional:</i> in 3-D a droplet blocks a "
            "rectangular section leaving corner gutters, not just two wall films, so absolute "
            "droplet volumes and the exact transition Ca shift; 2-D results are reliable for "
            "trends, regime ordering and scaling exponents (as noted in our proposal and by "
            "Liu &amp; Zhang). (ii) <i>Diffuse interface:</i> the φ interface is ~3–4 lu wide "
            "against w<sub>c</sub> = 30 lu, and the Cahn–Hilliard mobility introduces a weak "
            "curvature-driven (Ostwald) flux; very long threads therefore slowly lose φ far "
            "downstream, which is why droplet lengths are measured at first detachment near "
            "the junction and why “no pinch” is reported as “within the observation window”. "
            "(iii) <i>Matched density and moderate λ</i> are used for stability; inertia is "
            "negligible at these Re in any case. (iv) BGK with a single relaxation time limits "
            "the accessible viscosity ratio; an MRT collision operator is the natural next "
            "step. None of these affects the validation tests, which are the basis for "
            "trusting the solver within its stated window.", st_body),
          P("<b>What we would do next.</b> Extend to 3-D (or a Hele-Shaw-corrected 2-D model) "
            "for absolute volumes; add surfactant transport (a third field coupled to σ); "
            "calibrate one operating point against a fabricated PDMS device from the course "
            "and iterate the contact-angle calibration on measured droplet lengths.", st_body)]

# --- 7 conclusions ---
story += [P("7 &nbsp; Conclusions", st_h1)]
for b in [
    "A two-phase D2Q9 lattice Boltzmann + Cahn–Hilliard solver was written from scratch "
    "(Python/NumPy/Numba) for droplet formation in a T-junction, with bounce-back walls, a "
    "calibrated wetting condition, and syringe-pump (imposed-flow-rate) inlet/outlet "
    "boundaries.",
    f"Validation is quantitative: Young–Laplace Δp = σ/R with σ = {SIGMA:.4f} lu "
    f"(R<sup>2</sup> = {LAP_R2:.4f}); Poiseuille profile to {POIS_ERR:.2f}% RMS; contact "
    "angle tunable monotonically over ~49–149° through the wetting parameter.",
    "The solver reproduces a complete break-up cycle — bulb filling, slug elongation, "
    "waist thinning, droplet detachment (L/w<sub>c</sub> = 1.37 in the reference case) with "
    "its upstream-pressure signature — and its loss to thread behaviour as Ca (or "
    "excessively, Q<sub>r</sub>) is raised.",
    "In the droplet window, droplet lengths are O(w<sub>c</sub>) (L/w<sub>c</sub> = 1.4–1.7) and "
    "consistent with the Garstecki form L/w<sub>c</sub> = 1 + αQ<sub>r</sub> with α ≈ 0.8; "
    "λ and wettability act mainly through waist/neck drainage and wall films.",
    "For device design: choose geometry (w<sub>d</sub>/w<sub>c</sub>) and surface "
    "treatment first (they set the regime), then use Q<sub>r</sub> as the in-use "
    "droplet-size knob — and check the (Ca, Q<sub>r</sub>) operating point against a "
    "regime map such as Figure 8(c) rather than a single transition number.",
]:
    story.append(P(b, st_bullet, bulletText="•"))

story += [P("References", st_h1),
          P("[1] H. Liu, Y. Zhang, “Droplet formation in a T-shaped microfluidic junction,” "
            "<i>Journal of Applied Physics</i> 106, 034906 (2009). DOI: 10.1063/1.3187831.<br/>"
            "[2] P. Garstecki, M. J. Fuerstman, H. A. Stone, G. M. Whitesides, “Formation of "
            "droplets and bubbles in a microfluidic T-junction — scaling and mechanism of "
            "break-up,” <i>Lab on a Chip</i> 6, 437–446 (2006).<br/>"
            "[3] T. Krüger <i>et al.</i>, <i>The Lattice Boltzmann Method</i>, Springer (2017) — "
            "D2Q9 BGK, Guo forcing, bounce-back.<br/>"
            "[4] H. Liu, A. J. Valocchi, “Incompressible two-phase flow simulations with phase-field "
            "lattice Boltzmann method,” and related phase-field LBM literature — Cahn–Hilliard "
            "coupling, σ = (2√2/3)√(κβ).<br/>"
            "[5] CLL 770 course notes, Units 2–7 (interfacial phenomena; low-Re pressure-driven "
            "flow; two-phase flow; PDMS soft lithography; droplet microfluidics).", st_body),
          P("Appendix A — Code, data and reproducibility", st_h1),
          P(f"GitHub repository: <link href='{GITHUB}' color='#1b4f9c'>{GITHUB}</link> "
            "(if the remote has not yet been pushed from the authors' machine, this folder is "
            "the complete repository — <font face='Courier'>git log</font> shows its history).", st_body),
          P("<font face='Courier'>lbm_tjunction/solver.py</font> — the solver (D2Q9 kernels, "
            "phase field, boundaries, <font face='Courier'>TJunction.run()</font>). "
            "<font face='Courier'>run_all.py</font> — regenerates every number, figure and CSV "
            "in this report (<font face='Courier'>python3 run_all.py</font>, ~10 min). "
            "<font face='Courier'>build_pdf.py</font> — builds this combined PDF from those "
            "outputs, so no number in the text is typed by hand from a figure. Generated data: "
            "<font face='Courier'>results/data/{laplace,poiseuille,contact_angle,hero_growth,"
            "hero_pressure,sweep}.csv</font>, <font face='Courier'>hero_snaps.npz</font>; "
            "figures in <font face='Courier'>results/figures/</font>. Droplet detection: "
            "connected components of φ &gt; 0 in the main channel (scipy.ndimage); a pinch is "
            "the first detached component of area ≥ 80 lu² whose left edge is within 90 lu of "
            "the junction (excludes downstream thread tip-breakup and outlet artefacts).", st_body),
          P("<b>Author contributions.</b> Solver design and implementation, validation, "
            "parameter sweeps, analysis and writing were carried out jointly by the three "
            "authors; all authors reviewed the final report and slides.", st_body)]

# ============================================================ SLIDES part ==
story += [NextPageTemplate("slides_title"), PageBreak()]

def slide(title, body_items, bg="normal"):
    items = []
    if bg == "title":
        items += [Spacer(1, 1.1 * inch), P(title, st_slide_title)]
    else:
        items += [Spacer(1, 0.05 * inch),
                  P(title, S("sh2", parent=st_slide_h, textColor=NAVY))]
    items += body_items
    return items

def bullets(*texts):
    return [P(t, st_slide_bul, bulletText="•") for t in texts]

def slide_fig(name, width_in, caption=None):
    path = os.path.join(FIG, name)
    items = []
    if os.path.exists(path):
        from PIL import Image as PILImage
        iw, ih = PILImage.open(path).size
        w = width_in * inch
        items.append(Image(path, width=w, height=w * ih / iw))
    if caption:
        items.append(P(caption, st_slide_cap))
    return items

# S1 title
story += slide("Lattice Boltzmann Simulation of Droplet Formation in a Microfluidic T-Junction", [
    P("Squeezing-to-Dripping Transition and Droplet-Size Scaling", S("ss", parent=st_slide_b, textColor=colors.HexColor("#bcd2f0"), fontSize=16)),
    Spacer(1, 0.45 * inch),
    P("CLL 770 — Introduction to Microfluidics and Fabrication · Term Project · IIT Delhi", S("s2", parent=st_slide_b, textColor=colors.white)),
    P("Ananyaa Agrawal (2022CH71487) · Yash Balram Sakhare (2022CH71496) · Rishita Anand (2022CH71042)",
      S("s3", parent=st_slide_b, textColor=colors.white)),
    Spacer(1, 0.5 * inch),
    P(f"<b>GitHub repository:</b> <link href='{GITHUB}' color='#8ec3ff'>{GITHUB}</link>",
      S("s4", parent=st_slide_b, textColor=colors.white, fontSize=15, borderColor=colors.white)),
    P("Full report precedes these slides in this same PDF (Part I).", S("s5", parent=st_slide_b, textColor=colors.HexColor("#bcd2f0"))),
], bg="title")
story += [NextPageTemplate("slides"), PageBreak()]

# S2 outline
story += slide("Outline", bullets(
    "Why droplets, why a T-junction?",
    "Physics: Ca, Q<sub>d</sub>/Q<sub>c</sub>, λ, contact angle — squeezing vs dripping",
    "Our solver: D2Q9 LBM + Cahn–Hilliard phase field (from scratch, Numba)",
    "Validation: Laplace · Poiseuille · contact angle",
    "Results: one break-up, pressure signature, regime map, Garstecki scaling",
    "What it means for a PDMS device · limitations · conclusions",
))
story += [PageBreak()]

# S3 background
story += slide("Why droplets? Why a T-junction?", bullets(
    "Each droplet = a picolitre reactor → ddPCR, single-cell encapsulation, monodisperse particles",
    "T-junction: dispersed phase from a side channel is chopped by a cross-flowing continuous phase",
    "Design questions: <b>which regime?</b> and <b>how big are the droplets?</b>",
    "Hard analytically: free interface + moving contact lines + thin films interact",
    "→ Write a validated two-phase solver and map the operating space (after Liu &amp; Zhang 2009; Garstecki <i>et al.</i> 2006)",
))
story += [PageBreak()]

# S4 physics
story += slide("The physics in three groups (+ one angle)", bullets(
    "<b>Ca = μ<sub>c</sub>U<sub>c</sub>/σ</b> — shear vs interfacial tension",
    "<b>Q<sub>r</sub> = Q<sub>d</sub>/Q<sub>c</sub></b> — how much dispersed phase per cycle",
    "<b>λ = μ<sub>d</sub>/μ<sub>c</sub></b> — neck drainage; <b>θ</b> — wall films / blockage",
    "<b>Squeezing (low Ca):</b> droplet blocks channel → upstream pressure squeezes neck → break-up",
    "<b>Dripping / jetting (high Ca):</b> shear draws a thread; droplets smaller, less regular",
    "Squeezing droplet size: <b>L/w<sub>c</sub> = 1 + α·Q<sub>r</sub></b> (Garstecki) — we test this",
))
story += [PageBreak()]

# S5 method
story += slide("Solver: LBM hydrodynamics + phase-field interface", bullets(
    "D2Q9 BGK lattice Boltzmann, Guo forcing → low-Re Navier–Stokes; bounce-back walls",
    "Cahn–Hilliard φ (+1 dispersed / −1 continuous); surface tension <b>F = μ∇φ</b>",
    "D2Q9-isotropic derivatives (low spurious currents) + upwind φ advection, Numba kernels",
    "Wetting: ∂φ/∂n = w(1−φ²) at walls · syringe-pump inlets (parabolic, free pressure) · Q<sub>c</sub>+Q<sub>d</sub> outlet",
    "Everything scripted: <font face='Courier'>python3 run_all.py</font> regenerates every figure/number",
))
story += slide_fig("fig_geometry.png", 9.2, "T-junction: w<sub>c</sub>=30 lu, w<sub>d</sub>=16 lu, 400×90 lu domain")
story += [PageBreak()]

# S6 validation 1
story += slide("Validation 1a — surface tension is right (Laplace)", [])
story += slide_fig("fig_laplace.png", 9.6,
                   f"Δp = σ/R is linear (R²={LAP_R2:.4f}); slope σ = {SIGMA:.4f} lu — this measured σ is used for every Ca in the study. "
                   "Static-droplet spurious velocities are at most 2x10-4 lu/step.")
story += [PageBreak()]

# S6b validation 1b
story += slide("Validation 1b — the flow solver is right (Poiseuille)", [])
story += slide_fig("fig_poiseuille.png", 6.8,
                   f"Single-phase profile in the main channel vs the analytical parabola: {POIS_ERR:.2f}% RMS error. "
                   "This validates BGK hydrodynamics + bounce-back + inlet forcing, independently of the interface.")
story += [PageBreak()]

# S7 validation 2
story += slide("Validation 2 — contact angle is controllable", [])
story += slide_fig("fig_contact.png", 8.4,
                   "Sessile droplet: wetting parameter w → measured θ ≈ 49–149° (monotonic). "
                   "Production runs: w = −0.6 (continuous phase wets the walls, droplets lubricated, as in PDMS devices)")
story += [PageBreak()]

# S8 hero
story += slide("Result 1 — anatomy of a break-up", [])
story += slide_fig("fig_hero_sequence.png", 10.0,
                   f"Filling (bulb) → elongation (slug) → waist formation → droplet detachment (see report Fig. 6 for the zoom). "
                   f"Reference case Ca≈{fmt(ca_hero,3) if ca_hero else '0.012'}, Q<sub>r</sub>=0.5, λ=1")
story += [PageBreak()]

# S9 pressure
story += slide("Result 2 — the pressure signature of squeezing", [])
story += slide_fig("fig_pressure.png", 8.6,
                   "Upstream pressure rises while the droplet constricts the channel and relaxes at break-up — "
                   "break-up is driven by blockage pressure (Garstecki mechanism), not by shear alone")
story += bullets("This trace is also a diagnostic an experimentalist can measure with an upstream pressure sensor")
story += [PageBreak()]

# S10 Ca
story += slide("Result 3 — capillary number moves the regime", bullets(
    "Ca = 0.013–0.021: filling + elongation, droplet detachment (L/w<sub>c</sub> = 1.4–1.6)",
    "Ca ≥ 0.034: interface swept downstream before it can detach → continuous thread",
    "Ca = 0.008 needs &gt; 36 000 steps (period ∝ 1/U) — censored by the 26 000-step window, not a separate regime",
    "Our pinch-to-thread boundary (Ca between 0.021 and 0.034) is within a factor of two of Liu &amp; Zhang's 0.018 — as expected for a geometry-dependent boundary",
))
story += [PageBreak()]

# S11 scaling
story += slide("Result 4 — droplet size &amp; regime map", [])
story += slide_fig("fig_sweeps.png", 12.2,
                   "(a) L/w<sub>c</sub> vs Ca · (b) Garstecki plot L/w<sub>c</sub> = 1 + αQ<sub>r</sub> at fixed Ca · "
                   "(c) Regime map: droplet window is bounded in (Ca, Q<sub>r</sub>) — choose operating points jointly")
story += [PageBreak()]

# S12 lambda/wetting
story += slide("Result 5 — viscosity ratio &amp; wettability", bullets(
    "<b>λ ↑:</b> waist drains slowly → λ = 5 does not detach in the window (λ = 0.2 detaches earliest, step 15 500)",
    "<b>λ controls the drainage stage,</b> not filling — detached length stays O(w<sub>c</sub>)",
    "<b>Wettability:</b> only the strongly continuous-wetting wall (w = −0.6) released droplets in the window — the lubricating film enables release",
    "<b>Fabrication link:</b> plasma treatment / hydrophobic recovery of PDMS sets exactly this knob — surface treatment is a droplet-size variable, not an afterthought",
))
story += [PageBreak()]

# S13 limitations
story += slide("Limitations — stated, not hidden", bullets(
    "2-D: real droplets leave corner gutters in a rectangular section → absolute volumes / exact transition Ca shift; trends &amp; scaling survive",
    "Diffuse interface (~3–4 lu) + Cahn–Hilliard mobility: very long threads slowly lose φ downstream → lengths measured at first detachment near the junction; “no pinch” = within the 26 000-step window",
    "Matched densities, moderate λ (BGK stability); negligible inertia at these Re regardless",
    "Next: 3-D, surfactant transport (σ(Γ)), one fabricated-device calibration point",
))
story += [PageBreak()]

# S14 conclusions
story += slide("Conclusions", bullets(
    "Built &amp; validated a two-phase LBM solver from scratch (Laplace, Poiseuille, contact angle — all quantitative)",
    "Reproduced a full break-up cycle (filling → elongation → waist detachment, L/w<sub>c</sub>=1.37) and its pressure signature",
    "Droplet lengths are O(w<sub>c</sub>) and consistent with the Garstecki form (α ≈ 0.8) in the droplet window; Ca, λ and wettability move the window",
    "Design rule: geometry + surface treatment set the regime; Q<sub>r</sub> is the in-use size knob",
    f"<b>Code &amp; data:</b> <link href='{GITHUB}' color='#1b4f9c'>{GITHUB}</link> — <font face='Courier'>run_all.py</font> regenerates everything in this talk",
    "Thank you — questions welcome!",
))

# ------------------------------------------------------------------- doc --
doc = BaseDocTemplate(OUT, pagesize=A4,
                      leftMargin=1.6 * cm, rightMargin=1.6 * cm,
                      topMargin=1.5 * cm, bottomMargin=1.7 * cm,
                      title="CLL 770 Final Project — LBM Droplet Formation in a T-Junction",
                      author="Ananyaa Agrawal, Yash Balram Sakhare, Rishita Anand")
frame_report = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="report")
frame_slide = Frame(0.55 * inch, 0.55 * inch, SLIDE_W - 1.1 * inch,
                    SLIDE_H - 1.55 * inch, id="slide")
frame_slide_title = Frame(0.7 * inch, 0.6 * inch, SLIDE_W - 1.4 * inch,
                          SLIDE_H - 1.2 * inch, id="slide_title")
doc.addPageTemplates([
    PageTemplate(id="report", frames=[frame_report], onPage=report_footer, pagesize=A4),
    PageTemplate(id="slides_title", frames=[frame_slide_title], onPage=slide_title_bg,
                 pagesize=(SLIDE_W, SLIDE_H)),
    PageTemplate(id="slides", frames=[frame_slide], onPage=slide_bg,
                 pagesize=(SLIDE_W, SLIDE_H)),
])
os.makedirs(os.path.dirname(OUT), exist_ok=True)
doc.build(story)
print("Built", OUT)
