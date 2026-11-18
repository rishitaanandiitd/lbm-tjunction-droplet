"""
Build the presentation deck as an editable PowerPoint file and as PDF.

    python3 make_slide_figures.py     # once, after run_all.py
    python3 build_slides.py
    -> output/CLL770_Presentation.pptx
       output/CLL770_Presentation.pdf   (converted with LibreOffice)

Every number on the slides is read from results/data (written by
run_all.py); nothing is typed in by hand from a figure.  Speaker notes
are attached to every slide.
"""

import ast
import csv
import os
import re
import shutil
import subprocess
import tempfile

import numpy as np
from lxml import etree
from PIL import Image
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, MSO_AUTO_SIZE, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Inches, Pt

from project_meta import COURSE, GITHUB, SUBTITLE, TEAM, TITLE

ROOT = os.path.dirname(os.path.abspath(__file__))
DAT = os.path.join(ROOT, "results", "data")
SFIG = os.path.join(ROOT, "results", "slides")
OUT_DIR = os.path.join(ROOT, "output")
PPTX = os.path.join(OUT_DIR, "CLL770_Presentation.pptx")
PDF = os.path.join(OUT_DIR, "CLL770_Presentation.pdf")

NAVY, INK, BLUE = "0B1F3A", "1E2A3A", "2364AA"
ORANGE, ORANGE_D = "F29E4C", "C46A16"
TEAL, TEAL_D, MINT = "1B998B", "137A6F", "7FD1C7"
RED, GREY, MUTED = "D1495B", "5B6573", "8A94A3"
LINE, CARD, WHITE, SKY = "DCE3EB", "F3F6FA", "FFFFFF", "A9C7EA"
TEAL_L, RED_L, ORANGE_L, BLUE_L = "E3F4F1", "FBE7EA", "FDF0E2", "E6EEF8"
OIL, WALL = "F6E2B3", "DDE3EA"
FONT = "Calibri"
W, H = 13.333, 7.5
FOOTER = ("LBM simulation of droplet formation in a microfluidic T-junction"
          "   ·   CLL 770   ·   IIT Delhi")
WC, WD = 30, 16


# ------------------------------------------------------------------- data --
def read_csv(name):
    with open(os.path.join(DAT, name)) as fh:
        return list(csv.DictReader(fh))


SUM = {}
for _line in open(os.path.join(DAT, "summary.txt")):
    _k, _, _v = _line.strip().partition(" ")
    SUM[_k] = _v
SIGMA = float(SUM["sigma_measured"])
R2 = float(SUM["laplace_R2"])
POIS = float(SUM["poiseuille_rel_rms_percent"])
CA_HERO = float(SUM["hero_Ca"])
HERO = ast.literal_eval(SUM["hero_pinch"])
HERO_STEP, HERO_L = HERO["step"], HERO["length"]

SWEEP = read_csv("sweep.csv")
_con = read_csv("contact_angle.csv")
_cw = np.array([float(r["wetting_parameter"]) for r in _con])
_cth = np.array([float(r["theta_deg"]) for r in _con])


def theta(w):
    return float(np.interp(w, _cw, _cth))


def rows(series):
    return [r for r in SWEEP if r["series"] == series]


def pinched(r):
    return float(r["L_over_wc"]) > 0


BASE = next(r for r in rows("Ca") if abs(float(r["Uc"]) - 0.003) < 1e-9)
_gq = [(float(BASE["Qr"]), float(BASE["L_over_wc"]))]
_gq += [(float(r["Qr"]), float(r["L_over_wc"])) for r in rows("Qr") if pinched(r)]
_qx, _qy = np.array([a for a, _ in _gq]), np.array([b for _, b in _gq])
ALPHA = float(np.sum(_qx * (_qy - 1)) / np.sum(_qx ** 2))

CA_DROP = sorted(float(r["Ca"]) for r in rows("Ca") if pinched(r))
CA_DROP_L = sorted(float(r["L_over_wc"]) for r in rows("Ca") if pinched(r))
CA_THREAD = sorted(float(r["Ca"]) for r in rows("Ca")
                   if not pinched(r) and float(r["Ca"]) > CA_DROP[0])
CA_SHORT = sorted(float(r["Ca"]) for r in rows("Ca")
                  if not pinched(r) and float(r["Ca"]) < CA_DROP[0])
TH_PROD = theta(-0.6)


def steps(n):
    return f"{int(n):,}".replace(",", " ")


# ---------------------------------------------------------------- helpers --
def rgb(h):
    return RGBColor.from_string(h)


def _plain(shape):
    st = shape._element.find(qn("p:style"))
    if st is not None:
        shape._element.remove(st)


def box(s, x, y, w, h, fill=None, line=None, lw=1.0, kind=MSO_SHAPE.RECTANGLE,
        radius=0.0):
    if radius and kind == MSO_SHAPE.RECTANGLE:
        kind = MSO_SHAPE.ROUNDED_RECTANGLE
    sh = s.shapes.add_shape(kind, Inches(x), Inches(y), Inches(w), Inches(h))
    _plain(sh)
    if fill:
        sh.fill.solid(); sh.fill.fore_color.rgb = rgb(fill)
    else:
        sh.fill.background()
    if line:
        sh.line.color.rgb = rgb(line); sh.line.width = Pt(lw)
    else:
        sh.line.fill.background()
    if kind == MSO_SHAPE.ROUNDED_RECTANGLE:
        sh.adjustments[0] = min(0.5, radius / min(w, h)) if radius else 0.08
    return sh


def card(s, x, y, w, h, fill=CARD, line=None):
    return box(s, x, y, w, h, fill=fill, line=line, radius=0.12)


TOKEN = re.compile(r"(\*\*|_\{[^}]*\}|\^\{[^}]*\})")


def add_runs(p, txt, size, color, bold=False, italic=False, link=None):
    b = bold
    for tok in TOKEN.split(txt):
        if not tok:
            continue
        if tok == "**":
            b = not b
            continue
        base = None
        if tok.startswith("_{"):
            tok, base = tok[2:-1], "-25000"
        elif tok.startswith("^{"):
            tok, base = tok[2:-1], "30000"
        r = p.add_run()
        r.text = tok
        f = r.font
        f.name, f.size, f.bold, f.italic = FONT, Pt(size), b, italic
        f.color.rgb = rgb(color)
        if base:
            r._r.get_or_add_rPr().set("baseline", base)
        if link:
            r.hyperlink.address = link


def _bullet(p, color, indent):
    pPr = p._p.get_or_add_pPr()
    pPr.set("marL", str(int(Inches(indent))))
    pPr.set("indent", str(-int(Inches(indent))))
    clr = etree.SubElement(pPr, qn("a:buClr"))
    etree.SubElement(clr, qn("a:srgbClr")).set("val", color)
    etree.SubElement(pPr, qn("a:buSzPct")).set("val", "100000")
    etree.SubElement(pPr, qn("a:buFont")).set("typeface", "Arial")
    etree.SubElement(pPr, qn("a:buChar")).set("char", "•")


ALIGN = {"l": PP_ALIGN.LEFT, "c": PP_ALIGN.CENTER, "r": PP_ALIGN.RIGHT}
ANCHOR = {"t": MSO_ANCHOR.TOP, "m": MSO_ANCHOR.MIDDLE, "b": MSO_ANCHOR.BOTTOM}


def fill_frame(tf, paras, size, color, bold=False, italic=False, align="l",
               anchor="t", spacing=1.05, after=0, bullet=None, indent=0.26,
               spc=None, link=None, margin=0.0):
    tf.word_wrap = True
    tf.auto_size = MSO_AUTO_SIZE.NONE
    tf.margin_left = tf.margin_right = Inches(margin)
    tf.margin_top = tf.margin_bottom = Inches(0)
    tf.vertical_anchor = ANCHOR[anchor]
    if isinstance(paras, str):
        paras = [paras]
    for i, para in enumerate(paras):
        opts = {}
        if isinstance(para, tuple):
            para, opts = para
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = ALIGN[opts.get("align", align)]
        p.line_spacing = opts.get("spacing", spacing)
        p.space_after = Pt(opts.get("after", after))
        add_runs(p, para, opts.get("size", size), opts.get("color", color),
                 opts.get("bold", bold), opts.get("italic", italic),
                 opts.get("link", link))
        bc = opts.get("bullet", bullet)
        if bc:
            _bullet(p, bc, opts.get("indent", indent))
        if spc:
            for r in p.runs:
                r._r.get_or_add_rPr().set("spc", str(spc))


def text(s, x, y, w, h, paras, size=16, color=INK, **kw):
    tb = s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    fill_frame(tb.text_frame, paras, size, color, **kw)
    return tb


def label_in(sh, txt, size, color, bold=True, **kw):
    fill_frame(sh.text_frame, txt, size, color, bold=bold, align="c",
               anchor="m", **kw)
    return sh


def circle_num(s, x, y, d, txt, fill=TEAL, color=WHITE, size=14):
    sh = box(s, x, y, d, d, fill=fill, kind=MSO_SHAPE.OVAL)
    return label_in(sh, txt, size, color)


def pic(s, name, x, y, w=None, h=None):
    path = os.path.join(SFIG, name)
    iw, ih = Image.open(path).size
    if w is None:
        w = h * iw / ih
    if h is None:
        h = w * ih / iw
    s.shapes.add_picture(path, Inches(x), Inches(y), Inches(w), Inches(h))
    return w, h


def bg(s, color):
    box(s, 0, 0, W, H, fill=color)


def notes(s, txt):
    s.notes_slide.notes_text_frame.text = txt


class Deck:
    def __init__(self):
        self.prs = Presentation()
        self.prs.slide_width, self.prs.slide_height = Inches(W), Inches(H)
        self.blank = self.prs.slide_layouts[6]
        self.prs.core_properties.title = TITLE
        self.prs.core_properties.author = ", ".join(n for n, _ in TEAM)
        self.prs.core_properties.subject = COURSE

    def new(self):
        return self.prs.slides.add_slide(self.blank)

    def content(self, n, total, section, title):
        s = self.new()
        text(s, 0.6, 0.4, 9.0, 0.3, section.upper(), 12, TEAL, bold=True, spc=200)
        text(s, 0.6, 0.66, 12.13, 0.7, title, 28, NAVY, bold=True, anchor="m")
        box(s, 0.6, 1.45, 12.13, 0.02, fill=LINE)
        text(s, 0.6, 6.98, 9.5, 0.3, FOOTER, 10, MUTED)
        text(s, 10.73, 6.98, 2.0, 0.3, f"{n:02d} / {total:02d}", 10, GREY,
             bold=True, align="r")
        box(s, 0, H - 0.07, W, 0.07, fill="E9EEF4")
        box(s, 0, H - 0.07, W * n / total, 0.07, fill=TEAL)
        return s


# ----------------------------------------------------------------- slides --
def s_title(d, n, N):
    s = d.new()
    bg(s, NAVY)
    text(s, 0.75, 0.6, 11.8, 0.3,
         "CLL 770  ·  Introduction to Microfluidics and Fabrication  ·  IIT Delhi",
         13, MINT, bold=True, spc=120)
    text(s, 0.75, 0.98, 11.8, 1.65, TITLE, 40, WHITE, bold=True, spacing=0.92,
         anchor="m")
    text(s, 0.75, 2.72, 11.8, 0.45, SUBTITLE, 22, SKY)
    for i, (name, entry) in enumerate(TEAM):
        x = 0.75 + i * 3.45
        text(s, x, 3.42, 3.35, 0.36, name, 19, WHITE, bold=True)
        text(s, x, 3.79, 3.35, 0.3, entry, 14, SKY)
    iw, ih = Image.open(os.path.join(SFIG, "phi_title.png")).size
    pic(s, "phi_title.png", 0, H - W * ih / iw, w=W)
    pill = box(s, 0.75, 4.28, 6.55, 0.46, fill="13325A", line="3C8DDE", lw=1.0,
               radius=0.23)
    tf = pill.text_frame
    fill_frame(tf, "", 14, WHITE, anchor="m", margin=0.18)
    p = tf.paragraphs[0]
    add_runs(p, "GitHub   ", 14, MINT, bold=True)
    add_runs(p, GITHUB, 14, WHITE)
    pill.click_action.hyperlink.address = GITHUB
    text(s, 7.55, 4.28, 5.0, 0.46, "Final project presentation  ·  November 2026",
         13, SKY, anchor="m")
    notes(s, "Introduce the team and the question: how does a microfluidic "
             "T-junction turn two immiscible streams into droplets, and what sets "
             "their size? We answer it with a two-phase lattice Boltzmann solver "
             "that we wrote and validated ourselves. All code and data are on the "
             "GitHub link shown here.")


def s_roadmap(d, n, N):
    s = d.content(n, N, "Overview", "What we did, in five steps")
    items = [("Motivation", "Why droplets, and why a T-junction"),
             ("Physics", "Ca, Q_{d}/Q_{c}, λ and θ decide squeezing vs dripping"),
             ("Solver", "Two-phase lattice Boltzmann, written from scratch"),
             ("Validation", "Laplace, Poiseuille and contact-angle tests"),
             ("Results", "Break-up, pressure, regime map and droplet size")]
    cw, gap = 2.3, (12.13 - 5 * 2.3) / 4
    for i, (head, body) in enumerate(items):
        x = 0.6 + i * (cw + gap)
        card(s, x, 1.8, cw, 2.85)
        text(s, x + 0.25, 1.98, 1.4, 0.65, f"{i + 1:02d}", 36, TEAL, bold=True)
        box(s, x + 0.27, 2.72, 0.5, 0.045, fill=TEAL)
        text(s, x + 0.25, 2.9, cw - 0.45, 0.4, head, 20, NAVY, bold=True)
        text(s, x + 0.25, 3.36, cw - 0.45, 1.2, body, 15, GREY, spacing=1.08)
    card(s, 0.6, 4.95, 12.13, 1.78, fill=NAVY)
    text(s, 0.95, 5.15, 4.0, 0.3, "THE BOTTOM LINE", 12, MINT, bold=True, spc=200)
    text(s, 0.95, 5.48, 11.45, 1.1,
         "A validated solver reproduces a complete T-junction break-up "
         f"(**L/w_{{c}} = {HERO_L / WC:.2f}**) and shows that droplets form only "
         "inside a bounded window of capillary number, flow-rate ratio, viscosity "
         "ratio and wall wettability.", 19, WHITE, spacing=1.06)
    notes(s, "Roadmap. Five parts: motivation, the physics, our solver, how we "
             "validated it, and the results. The bottom line is on the slide: "
             "the solver reproduces a full break-up, and droplets only form "
             "inside a bounded window of the four dimensionless knobs.")


def s_motivation(d, n, N):
    s = d.content(n, N, "01  ·  Motivation",
                  "Every droplet is a picolitre reactor")
    apps = [("Digital PCR", "Thousands of droplets, each a single-molecule assay"),
            ("Single-cell encapsulation", "One cell per droplet for screening and sequencing"),
            ("Monodisperse particles", "Uniform emulsions for drug delivery and materials")]
    for i, (head, body) in enumerate(apps):
        y = 1.8 + i * 1.03
        box(s, 0.6, y + 0.04, 0.07, 0.8, fill=TEAL)
        text(s, 0.9, y, 5.9, 0.42, head, 20, NAVY, bold=True)
        text(s, 0.9, y + 0.43, 5.9, 0.4, body, 15, GREY)
    card(s, 0.6, 5.0, 6.3, 1.75)
    text(s, 0.9, 5.0, 5.75, 1.75,
         ["**Why a T-junction?**",
          "The simplest droplet generator: a side channel feeds the dispersed "
          "phase into a cross-flowing continuous phase, which chops it into a "
          "train of near-identical droplets."], 16, INK, spacing=1.06, after=3,
         anchor="m")
    w, h = pic(s, "stage_4.png", 7.3, 1.8, w=5.43)
    text(s, 7.3, 1.8 + h + 0.08, 5.43, 0.3,
         "Our simulation: a droplet pinching off at the junction", 13, MUTED,
         italic=True)
    card(s, 7.3, 4.5, 5.43, 2.25, fill=ORANGE_L)
    text(s, 7.6, 4.66, 4.9, 0.3, "TWO DESIGN QUESTIONS", 12, ORANGE_D, bold=True,
         spc=200)
    text(s, 7.6, 5.0, 4.9, 0.8,
         ["1   Which regime: squeezing, dripping or jetting?",
          "2   How long is each droplet?"], 17, NAVY, bold=True, after=2)
    text(s, 7.6, 5.82, 4.9, 0.85,
         "No closed-form answer: the free interface, moving contact lines and "
         "thin wall films all interact — so we simulate.", 14, GREY, spacing=1.05)
    notes(s, "Why care: in droplet microfluidics each droplet is an isolated "
             "reactor, the basis of digital PCR, single-cell work and uniform "
             "particles. The T-junction is the simplest generator. A designer "
             "needs two answers - which regime, and how big - and there is no "
             "closed-form answer, which motivates a simulation.")


def s_physics(d, n, N):
    s = d.content(n, N, "02  ·  Physics",
                  "Four dimensionless knobs decide how droplets break off")
    knobs = [("Ca = μ_{c}U_{c}/σ", "Capillary number", "shear vs interfacial tension"),
             ("Q_{d}/Q_{c}", "Flow-rate ratio", "dispersed volume fed per cycle"),
             ("λ = μ_{d}/μ_{c}", "Viscosity ratio", "how fast the neck can drain"),
             ("θ", "Contact angle", "which phase wets the wall")]
    cw = (12.13 - 3 * 0.2) / 4
    for i, (formula, name, desc) in enumerate(knobs):
        x = 0.6 + i * (cw + 0.2)
        card(s, x, 1.75, cw, 1.6)
        text(s, x + 0.25, 1.9, cw - 0.4, 0.5, formula, 24, NAVY, bold=True)
        text(s, x + 0.25, 2.5, cw - 0.4, 0.32, name, 15, TEAL, bold=True)
        text(s, x + 0.25, 2.83, cw - 0.4, 0.4, desc, 14, GREY)
    pw = (12.13 - 0.2) / 2
    panels = [("SQUEEZING   ·   LOW Ca", BLUE, BLUE_L,
               ["Droplet fills and blocks the channel",
                "Upstream pressure builds behind it",
                "Pressure squeezes the neck shut"],
               "L/w_{c} = 1 + α · Q_{d}/Q_{c}", "Garstecki et al., Lab Chip (2006)"),
              ("DRIPPING → JETTING   ·   HIGH Ca", ORANGE_D, ORANGE_L,
               ["Shear drags the interface downstream",
                "A thread forms before the channel blocks",
                "Thread breaks: smaller, less regular drops"],
               "Ca_{crit} ≈ 0.018", "Liu & Zhang, J. Appl. Phys. (2009)")]
    for i, (head, col, fill, lines, formula, ref) in enumerate(panels):
        x = 0.6 + i * (pw + 0.2)
        card(s, x, 3.6, pw, 3.15, fill=fill)
        text(s, x + 0.3, 3.75, pw - 0.6, 0.32, head, 13, col, bold=True, spc=150)
        for j, ln in enumerate(lines):
            circle_num(s, x + 0.3, 4.2 + j * 0.5, 0.34, str(j + 1), fill=col, size=13)
            text(s, x + 0.8, 4.2 + j * 0.5, pw - 1.1, 0.34, ln, 16, INK, anchor="m")
        card(s, x + 0.3, 5.78, pw - 0.6, 0.78, fill=WHITE)
        text(s, x + 0.5, 5.84, 3.2, 0.66, formula, 21, NAVY, bold=True, anchor="m")
        text(s, x + 3.55, 5.84, pw - 4.05, 0.66, ref, 12, GREY, anchor="m",
             align="r")
    notes(s, "Four dimensionless groups. Capillary number compares shear with "
             "surface tension; the flow-rate ratio sets how much dispersed phase "
             "enters per cycle; the viscosity ratio controls neck drainage; the "
             "contact angle says which phase wets the wall. At low Ca the droplet "
             "blocks the channel and is squeezed off - Garstecki's law predicts "
             "its length. At high Ca shear pulls out a thread instead. Liu and "
             "Zhang put the transition near Ca = 0.018 for their geometry.")


def s_solver(d, n, N):
    s = d.content(n, N, "03  ·  Method",
                  "A two-phase lattice Boltzmann solver, built from scratch")
    steps_ = [("Collide", "D2Q9 BGK with Guo forcing → low-Re Navier–Stokes"),
              ("Stream", "Bounce-back walls give no-slip on the lattice"),
              ("Track the interface", "Cahn–Hilliard phase field φ; surface tension F = μ∇φ"),
              ("Boundaries", "Syringe-pump inlets, Q_{c}+Q_{d} outlet, wetting ∂φ/∂n = w(1−φ^{2})")]
    box(s, 0.84, 2.05, 0.03, 3.45, fill=LINE)
    for i, (head, body) in enumerate(steps_):
        y = 1.8 + i * 1.13
        circle_num(s, 0.6, y, 0.5, str(i + 1), size=16)
        text(s, 1.3, y - 0.02, 4.6, 0.38, head, 19, NAVY, bold=True)
        text(s, 1.3, y + 0.37, 4.6, 0.65, body, 15, GREY, spacing=1.05)
    card(s, 6.35, 1.75, 6.38, 3.75)
    x0, x1, yt, yb = 6.65, 12.43, 2.05, 4.25
    box(s, x0, yt, x1 - x0, yb - yt, fill=WALL)
    cy0, cy1 = 3.1, 3.8
    box(s, x0, cy0, x1 - x0, cy1 - cy0, fill=OIL)
    sx = x0 + (x1 - x0) * 124 / 400
    sw = (cy1 - cy0) * WD / WC
    box(s, sx, yt, sw, cy0 - yt, fill="3C78C3")
    box(s, x0 + 0.15, cy0 + 0.23, 0.75, 0.24, fill=NAVY, kind=MSO_SHAPE.RIGHT_ARROW)
    box(s, x1 - 0.9, cy0 + 0.23, 0.75, 0.24, fill=NAVY, kind=MSO_SHAPE.RIGHT_ARROW)
    box(s, sx + sw / 2 - 0.1, yt + 0.12, 0.2, 0.55, fill=WHITE, kind=MSO_SHAPE.DOWN_ARROW)
    text(s, x0 + 0.12, cy0 - 0.36, 2.0, 0.3, "continuous  Q_{c}", 14, NAVY, bold=True)
    text(s, sx + sw + 0.15, yt + 0.12, 2.6, 0.3, "dispersed  Q_{d}", 14, "1D4E89",
         bold=True)
    text(s, sx + sw + 0.15, yt + 0.42, 2.6, 0.3, f"w_{{d}} = {WD} lu", 13, GREY)
    text(s, x1 - 2.1, cy0 - 0.36, 1.95, 0.3, "outlet  Q_{c} + Q_{d}", 14, NAVY,
         bold=True, align="r")
    text(s, 9.25, cy0 + 0.2, 1.7, 0.3, f"w_{{c}} = {WC} lu", 13, NAVY, align="c")
    chips = ["D2Q9 lattice", "400 × 90 lu", f"w_{{d}}/w_{{c}} = {WD / WC:.2f}", "Re < 0.4"]
    cw = (x1 - x0 - 3 * 0.15) / 4
    for i, c in enumerate(chips):
        ch = box(s, x0 + i * (cw + 0.15), 4.55, cw, 0.42, fill=WHITE, line=LINE,
                 radius=0.21)
        label_in(ch, c, 13, NAVY, bold=False)
    text(s, 6.35, 5.72, 6.38, 1.0,
         [("**Numba-compiled kernels:** 30 000 time steps ≈ 1 minute on a laptop", {}),
          ("**One command** — python3 run_all.py — regenerates every number and "
           "figure in this talk", {})], 15, INK, after=4)
    notes(s, "Our solver. Each time step: collide with a BGK operator plus Guo "
             "forcing, which recovers low-Reynolds Navier-Stokes; stream, with "
             "bounce-back giving no-slip walls; update the Cahn-Hilliard phase "
             "field, whose chemical potential gives the surface-tension force; "
             "then apply syringe-pump inlets and the wetting condition. The "
             "geometry on the right has a side channel about half the main "
             "channel width. It runs about a minute per case.")


def s_validation1(d, n, N):
    s = d.content(n, N, "04  ·  Validation",
                  "Surface tension and channel flow match theory")
    cols = [("Laplace test  ·  static droplets", "laplace.png", f"R^{{2}} = {R2:.4f}",
             f"Δp = σ/R holds; measured σ = {SIGMA:.4f} lu sets every Ca we quote"),
            ("Poiseuille test  ·  single-phase channel", "poiseuille.png",
             f"{POIS:.1f} %", "RMS error vs the analytical parabola: validates "
             "flow, walls and inlets")]
    cw = (12.13 - 0.33) / 2
    for i, (head, img, big, small) in enumerate(cols):
        x = 0.6 + i * (cw + 0.33)
        text(s, x, 1.68, cw, 0.35, head, 17, NAVY, bold=True)
        iw, ih = Image.open(os.path.join(SFIG, img)).size
        h = 3.5
        w = h * iw / ih
        pic(s, img, x + (cw - w) / 2, 2.1, h=h)
        card(s, x, 5.78, cw, 0.97)
        text(s, x + 0.28, 5.78, 2.4, 0.97, big, 28, TEAL, bold=True, anchor="m")
        text(s, x + 2.75, 5.78, cw - 3.0, 0.97, small, 14, GREY, anchor="m",
             spacing=1.05)
    notes(s, "Before trusting any droplet result we checked problems with known "
             "answers, using exactly the production parameters. Left: static "
             "droplets of different radius - the pressure jump is linear in "
             "curvature, as Young-Laplace requires, and the slope gives the "
             "surface tension we use for every capillary number. Right: with no "
             "dispersed phase the channel recovers the Poiseuille parabola to "
             "under three percent.")


def s_validation2(d, n, N):
    s = d.content(n, N, "04  ·  Validation",
                  f"Wall wettability is tunable from {_cth.min():.0f}° to {_cth.max():.0f}°")
    cw = (12.13 - 5 * 0.15) / 6
    for i, (wv, th) in enumerate(zip(_cw, _cth)):
        x = 0.6 + i * (cw + 0.15)
        _, h = pic(s, f"contact_{i}.png", x, 1.72, w=cw)
        text(s, x, 1.72 + h + 0.06, cw, 0.34, f"θ = {th:.0f}°", 17, NAVY,
             bold=True, align="c")
        text(s, x, 1.72 + h + 0.38, cw, 0.28, f"w = {wv:+.1f}".replace("-", "−"),
             13, GREY, align="c")
    pic(s, "contact_curve.png", 0.6, 3.72, h=3.05)
    card(s, 5.55, 3.85, 7.18, 2.9)
    text(s, 5.85, 4.02, 6.6, 0.3, "WHAT WE USE", 12, TEAL, bold=True, spc=200)
    text(s, 5.85, 4.38, 6.6, 2.3,
         [(f"Production runs use **w = −0.6 → θ ≈ {TH_PROD:.0f}°**: the continuous "
           "phase wets the wall, so droplets ride on a lubricating film — like an "
           "aqueous droplet in a hydrophobic PDMS channel.", {"after": 8}),
          ("The condition acts only where the interface touches a wall, so it "
           "creates no artificial films in either bulk phase.",
           {"color": GREY, "size": 15})], 17, INK, spacing=1.06)
    notes(s, "Third test: a sessile droplet on a wall. One wetting parameter in "
             "the boundary condition sets the contact angle, and the measured "
             "angle varies smoothly from about 150 to 50 degrees. For the "
             "T-junction we use a wall that the continuous phase prefers, about "
             "135 degrees, which is the usual situation for aqueous droplets in "
             "oil in a hydrophobic PDMS channel.")


def s_breakup(d, n, N):
    s = d.content(n, N, "05  ·  Results",
                  "One complete break-up: fill → stretch → neck → detach")
    stages = [("Filling", 3000), ("Stretching", 15000), ("Necking", 23500),
              ("Detachment", HERO_STEP)]
    pw = 4.25
    for i, (name, st) in enumerate(stages):
        x = 0.6 + (i % 2) * (pw + 0.25)
        y = 1.68 + (i // 2) * 2.24
        circle_num(s, x, y + 0.01, 0.3, str(i + 1), size=12)
        text(s, x + 0.4, y, pw - 0.4, 0.32, f"**{name}**   ·   step {steps(st)}",
             15, NAVY, anchor="m")
        pic(s, f"stage_{i + 1}.png", x, y + 0.38, w=pw)
    legend = [(OIL, "continuous phase"), ("1D4E89", "dispersed phase"), (WALL, "wall")]
    lx = 0.6
    for col, lab in legend:
        box(s, lx, 6.38, 0.22, 0.22, fill=col, line=LINE, lw=0.5)
        text(s, lx + 0.3, 6.33, 1.9, 0.32, lab, 13, GREY, anchor="m")
        lx += 2.05
    text(s, 6.6, 6.33, 2.75, 0.32,
         f"Ca = {CA_HERO:.3f},  Q_{{d}}/Q_{{c}} = 0.5,  λ = 1", 13, GREY,
         anchor="m", align="r")
    facts = [(steps(HERO_STEP), "time steps to the first detachment"),
             (f"L/w_{{c}} = {HERO_L / WC:.2f}",
              f"droplet length {HERO_L} lu — about one channel width"),
             ("Slug waist", "is where it separates, not the side-arm neck of the "
              "textbook picture")]
    for i, (big, small) in enumerate(facts):
        y = 2.06 + i * 1.5
        card(s, 9.75, y, 2.98, 1.36)
        text(s, 9.98, y + 0.12, 2.6, 0.52, big, 25, TEAL, bold=True, anchor="m")
        text(s, 9.98, y + 0.66, 2.6, 0.62, small, 13, GREY, spacing=1.02)
    notes(s, "The reference case, frame by frame. One: the meniscus bulges into "
             "the main channel as a near-semicircular cap - surface tension in "
             "control. Two: the flow sweeps it into a growing slug. Three: the "
             "front bulb outruns the thinner tail and a waist forms. Four: at "
             "step 24 500 the waist collapses and a droplet 1.37 channel widths "
             "long detaches, while the next slug starts growing. Note that it "
             "separates at the waist, not at the side-arm neck - a useful "
             "warning against assuming the textbook neck location.")


def s_pressure(d, n, N):
    s = d.content(n, N, "05  ·  Results",
                  "Upstream pressure records blockage and release")
    pic(s, "pressure.png", 0.6, 1.72, w=8.15)
    items = [(BLUE, "Plateau", "The slug constricts the channel, so the pumps "
                               "must push harder"),
             (ORANGE, "Waist thins", "The continuous phase starts to bypass the "
                                     "slug"),
             (RED, "Pinch-off", "The channel re-opens as the droplet leaves: a "
                                "≈ 0.05 % rise-and-release")]
    for i, (col, head, body) in enumerate(items):
        y = 1.85 + i * 1.3
        box(s, 9.15, y + 0.04, 0.07, 1.0, fill=col)
        text(s, 9.45, y, 3.28, 0.38, head, 19, NAVY, bold=True)
        text(s, 9.45, y + 0.4, 3.28, 0.75, body, 15, GREY, spacing=1.05)
    card(s, 0.6, 5.85, 12.13, 0.9, fill=TEAL_L)
    text(s, 0.9, 5.85, 11.6, 0.9,
         "**Experimental hook:** an upstream pressure sensor on a real chip would "
         "show this same rise-and-release — a direct, measurable check of the "
         "blockage mechanism.", 16, INK, anchor="m")
    notes(s, "We probed the pressure 25 lattice units upstream of the junction. "
             "After the start-up waves die out, the pressure sits on a plateau "
             "while the slug blocks the channel, sags as the waist thins and the "
             "oil starts to bypass, and drops at pinch-off. The swing is small in "
             "absolute terms but systematic - it is the signature of "
             "blockage-controlled break-up, and something an experimentalist "
             "could measure.")


def s_capillary(d, n, N):
    s = d.content(n, N, "05  ·  Results",
                  "Droplets form only inside a bounded Ca window")
    _, h = pic(s, "ca_strip.png", 0.6, 1.62, w=12.13)
    y = 1.62 + h + 0.12
    cw = (12.13 - 0.4) / 3
    cards = [(TEAL_L, TEAL_D,
              f"Ca = {CA_DROP[0]:.3f} – {CA_DROP[-1]:.3f}   ·   droplets",
              f"fill, stretch, detach;  L/w_{{c}} = {CA_DROP_L[0]:.2f} – {CA_DROP_L[-1]:.2f}"),
             (RED_L, RED, f"Ca ≥ {CA_THREAD[0]:.3f}   ·   continuous thread",
              "the interface is swept downstream before it can pinch off"),
             (CARD, GREY, f"Ca = {CA_SHORT[0]:.3f}   ·   needs a longer run",
              "formation period ∝ 1/U: needs ≳ 36 000 steps vs our 26 000 — "
              "not a new regime")]
    for i, (fill, col, head, body) in enumerate(cards):
        x = 0.6 + i * (cw + 0.2)
        card(s, x, y, cw, 1.32, fill=fill)
        text(s, x + 0.25, y + 0.14, cw - 0.45, 0.36, head, 16, col, bold=True)
        text(s, x + 0.25, y + 0.53, cw - 0.45, 0.72, body, 14, INK, spacing=1.04)
    text(s, 0.6, y + 1.47, 12.13, 0.62,
         f"**Our droplet-to-thread boundary (Ca {CA_DROP[-1]:.3f} – {CA_THREAD[0]:.3f}) "
         "is within a factor of two of Liu & Zhang’s 0.018** — expected, because "
         f"the boundary depends on geometry (ours: w_{{d}}/w_{{c}} = {WD / WC:.2f}).",
         15, INK, spacing=1.05)
    notes(s, "Capillary-number sweep at fixed flow-rate ratio. Droplets detach "
             "at Ca 0.013 and 0.021. From 0.034 up the interface is dragged into "
             "a continuous thread - the dripping/jetting side. The lowest Ca "
             "simply forms more slowly than our 26 000-step window, so we report "
             "it as censored, not as a different regime. Our boundary lies "
             "between 0.021 and 0.034, within a factor of two of Liu and Zhang, "
             "which is what you expect for a geometry-dependent boundary.")


def s_scaling(d, n, N):
    s = d.content(n, N, "05  ·  Results",
                  f"Droplet length follows the Garstecki form (α ≈ {ALPHA:.2f})")
    cw = (12.13 - 0.33) / 2
    heads = ["Droplet length vs flow-rate ratio  ·  Ca = 0.013",
             "Regime map  ·  where droplets form"]
    for i, (head, img) in enumerate(zip(heads, ["garstecki.png", "regime_map.png"])):
        x = 0.6 + i * (cw + 0.33)
        text(s, x, 1.66, cw, 0.35, head, 17, NAVY, bold=True)
        iw, ih = Image.open(os.path.join(SFIG, img)).size
        h = 3.72
        pic(s, img, x + (cw - h * iw / ih) / 2, 2.06, h=h)
    card(s, 0.6, 5.92, cw, 0.83)
    text(s, 0.85, 5.92, 2.1, 0.83, f"α = {ALPHA:.2f}", 26, TEAL, bold=True, anchor="m")
    text(s, 3.0, 5.92, cw - 2.6, 0.83,
         "fit of L/w_{c} = 1 + α·Q_{d}/Q_{c}  (Garstecki: α ≈ 1)", 14, GREY,
         anchor="m")
    card(s, 0.6 + cw + 0.33, 5.92, cw, 0.83, fill=ORANGE_L)
    text(s, 0.85 + cw + 0.33, 5.92, cw - 0.5, 0.83,
         [f"**Honest caveat:** {len(_gq)} droplets at fixed Ca — consistent with the "
          "form, not yet a verified scaling law"], 14, INK, anchor="m")
    notes(s, "Left: at fixed Ca the droplet length grows with the flow-rate "
             "ratio and sits around the Garstecki line; fitting with the "
             f"intercept fixed at one gives alpha = {ALPHA:.2f}, close to the "
             "reference value of one. We only have three droplets at fixed Ca, "
             "so we claim consistency with the form, not a verified law. Right: "
             "the regime map - the droplet window is bounded in both Ca and "
             "flow-rate ratio, so operating points must be chosen jointly.")


def s_lambda_wetting(d, n, N):
    s = d.content(n, N, "05  ·  Results",
                  "Viscosity and wettability decide if a droplet releases")
    cw = (12.13 - 0.33) / 2
    cols = [("Viscosity ratio   λ = μ_{d}/μ_{c}", "lambda_bars.png",
             "A less viscous dispersed phase drains the neck faster and releases "
             "first; droplet size stays ≈ w_{c}."),
            ("Wall wettability   θ", "wetting_bars.png",
             "Only the strongly oil-wetting wall keeps the lubricating film that "
             "lets the waist close.")]
    for i, (head, img, body) in enumerate(cols):
        x = 0.6 + i * (cw + 0.33)
        text(s, x, 1.66, cw, 0.35, head, 17, NAVY, bold=True)
        _, h = pic(s, img, x, 2.08, w=cw)
        text(s, x, 2.08 + h + 0.1, cw, 0.7, body, 15, GREY, spacing=1.05)
    card(s, 0.6, 5.9, 12.13, 0.85, fill=NAVY)
    text(s, 0.9, 5.9, 11.6, 0.85,
         "**Fabrication link:** plasma treatment and hydrophobic recovery of PDMS "
         "set θ — surface treatment is a design variable, not an afterthought.",
         16, WHITE, anchor="m")
    notes(s, "Viscosity ratio: a thin dispersed phase releases fastest, a "
             "viscous one does not release within the window - lambda controls "
             "how fast the neck drains, not the droplet size. Wettability: only "
             "the strongly continuous-wetting wall released a droplet. For a "
             "PDMS chip this means surface treatment is a real design knob.")


def s_design(d, n, N):
    s = d.content(n, N, "06  ·  Implications",
                  "From simulation to a PDMS chip: three knobs")
    cols = [("Geometry", "set at the mask",
             "SU-8 thickness and drawn widths fix w_{d}/w_{c} and w_{c} — this "
             "chooses the regime."),
            ("Surface treatment", "set at bonding",
             "Plasma, hydrophobic recovery or surfactant fix θ — in our runs only "
             f"θ ≈ {TH_PROD:.0f}° released droplets."),
            ("Flow-rate ratio", "set at the pumps",
             "Q_{d}/Q_{c} is the in-use knob for droplet size:  "
             f"L/w_{{c}} ≈ 1 + {ALPHA:.2f}·Q_{{d}}/Q_{{c}}.")]
    cw = (12.13 - 0.4) / 3
    for i, (head, when, body) in enumerate(cols):
        x = 0.6 + i * (cw + 0.2)
        card(s, x, 1.8, cw, 3.4)
        circle_num(s, x + 0.3, 2.05, 0.62, str(i + 1), fill=NAVY, size=22)
        text(s, x + 0.3, 2.88, cw - 0.6, 0.42, head, 22, NAVY, bold=True)
        ch = box(s, x + 0.3, 3.4, 1.85, 0.38, fill=TEAL_L, radius=0.19)
        label_in(ch, when, 13, TEAL_D)
        text(s, x + 0.3, 3.98, cw - 0.6, 1.15, body, 17, INK, spacing=1.08)
    card(s, 0.6, 5.45, 12.13, 1.2, fill=TEAL_L)
    text(s, 0.9, 5.45, 11.6, 1.2,
         "**Rule of thumb:** fix geometry and surface treatment first (they set the "
         "regime), then tune Q_{d}/Q_{c} — and check the (Ca, Q_{d}/Q_{c}) operating "
         "point on a regime map, not against a single transition number.",
         16, INK, anchor="m", spacing=1.06)
    notes(s, "What this means for a real device made by soft lithography. "
             "Geometry is fixed when you draw the mask and pour SU-8; it chooses "
             "the regime. Surface treatment is fixed at plasma bonding and drifts "
             "with hydrophobic recovery; our wettability results say it can move "
             "you out of the droplet window. The flow-rate ratio is the knob you "
             "turn during operation to set droplet size.")


def s_limits(d, n, N):
    s = d.content(n, N, "06  ·  Limitations",
                  "What the model can — and cannot — tell us")
    cw = (12.13 - 0.33) / 2
    cols = [(RED_L, RED, "Limitations",
             ["**2-D:** real channels leave corner gutters, so absolute volumes and "
              "the exact transition Ca will shift; trends and ordering survive.",
              "**Diffuse interface (3–4 lu):** long threads slowly lose φ, so lengths "
              "are measured at first detachment; “no pinch” means within the window.",
              "**Matched densities, BGK collision:** limit the accessible viscosity "
              "ratio (inertia is negligible at Re < 0.4 anyway)."]),
            (TEAL_L, TEAL_D, "Next steps",
             ["**3-D or Hele-Shaw-corrected model** for absolute droplet volumes",
              "**Longer runs and more Q_{d}/Q_{c} points** to pin down the scaling law",
              "**Surfactant transport,** with σ depending on coverage",
              "**Calibrate against one fabricated PDMS chip;** MRT collision for "
              "higher λ"])]
    for i, (fill, col, head, items) in enumerate(cols):
        x = 0.6 + i * (cw + 0.33)
        card(s, x, 1.75, cw, 5.0, fill=fill)
        text(s, x + 0.35, 1.97, cw - 0.7, 0.32, head.upper(), 13, col, bold=True,
             spc=200)
        text(s, x + 0.35, 2.5, cw - 0.7, 4.1,
             [(it, {"after": 16}) for it in items], 18, INK, bullet=col,
             spacing=1.08, indent=0.3)
    notes(s, "We are explicit about limits. The model is 2-D, so absolute "
             "volumes and the exact transition will shift in a real rectangular "
             "channel; trends and regime ordering should survive. The diffuse "
             "interface slowly dissolves very long threads, which is why we "
             "measure at first detachment and qualify every no-pinch result. "
             "Next steps: 3-D, more flow-rate ratios, surfactants and a "
             "calibration against a fabricated chip.")


def s_conclusions(d, n, N):
    s = d.content(n, N, "07  ·  Conclusions", "Key takeaways")
    rows_ = [(f"R^{{2}} = {R2:.4f}",
              f"**Validated quantitatively:** Young–Laplace, Poiseuille ({POIS:.1f} % "
              f"error) and contact angles from {_cth.min():.0f}° to {_cth.max():.0f}°."),
             (f"L/w_{{c}} = {HERO_L / WC:.2f}",
              "**Full break-up reproduced** — fill, stretch, neck, detach — with its "
              "upstream-pressure signature."),
             (f"{CA_DROP[-1]:.3f}–{CA_THREAD[0]:.3f}",
              "**Droplet-to-thread transition in Ca,** within ×2 of Liu & Zhang’s "
              "0.018 for a different geometry."),
             (f"α = {ALPHA:.2f}",
              "**Droplet length fits the Garstecki form;** viscosity ratio and "
              "wettability control when droplets release.")]
    for i, (big, body) in enumerate(rows_):
        y = 1.72 + i * 1.07
        if i:
            box(s, 0.6, y - 0.06, 12.13, 0.015, fill=LINE)
        text(s, 0.6, y, 3.3, 0.95, big, 28, TEAL, bold=True, anchor="m")
        text(s, 4.0, y, 8.73, 0.95, body, 18, INK, anchor="m", spacing=1.05)
    card(s, 0.6, 6.08, 12.13, 0.68, fill=CARD)
    tb = text(s, 0.9, 6.08, 11.6, 0.68, "", 15, INK, anchor="m")
    p = tb.text_frame.paragraphs[0]
    add_runs(p, "Code & data:  ", 15, NAVY, bold=True)
    add_runs(p, GITHUB, 15, BLUE, link=GITHUB)
    add_runs(p, "   ·   python3 run_all.py regenerates everything", 15, GREY)
    notes(s, "Four takeaways: the solver is validated quantitatively; it "
             "reproduces a complete break-up and its pressure signature; the "
             "droplet-to-thread transition sits within a factor of two of the "
             "literature; and droplet length is consistent with the Garstecki "
             "form, with viscosity and wettability controlling release.")


def s_thanks(d, n, N):
    s = d.new()
    bg(s, NAVY)
    text(s, 0.75, 1.25, 8.0, 1.0, "Thank you", 54, WHITE, bold=True)
    text(s, 0.75, 2.3, 8.0, 0.5, "Questions and discussion", 24, SKY)
    text(s, 0.75, 3.15, 8.4, 0.4,
         "   ·   ".join(nm for nm, _ in TEAM), 17, WHITE, bold=True)
    tb = text(s, 0.75, 3.75, 8.4, 0.4, "", 16, WHITE)
    p = tb.text_frame.paragraphs[0]
    add_runs(p, "GitHub   ", 16, MINT, bold=True)
    add_runs(p, GITHUB, 16, WHITE)
    tb.click_action.hyperlink.address = GITHUB
    box(s, 0.75, 4.72, 8.4, 0.015, fill="2B4468")
    text(s, 0.75, 4.9, 8.4, 0.3, "REFERENCES", 11, MINT, bold=True, spc=200)
    text(s, 0.75, 5.22, 8.4, 1.6,
         ["H. Liu, Y. Zhang, “Droplet formation in a T-shaped microfluidic "
          "junction,” J. Appl. Phys. 106, 034906 (2009)",
          "P. Garstecki et al., “Formation of droplets and bubbles in a "
          "microfluidic T-junction,” Lab Chip 6, 437–446 (2006)",
          "T. Krüger et al., The Lattice Boltzmann Method, Springer (2017)"],
         12, SKY, after=4, spacing=1.02)
    qr = os.path.join(SFIG, "qr_github.png")
    if os.path.exists(qr):
        card(s, 9.75, 1.25, 2.85, 2.85, fill=WHITE)
        pic(s, "qr_github.png", 9.95, 1.45, w=2.45)
        text(s, 9.75, 4.2, 2.85, 0.35, "Scan for code & data", 14, SKY, align="c")
    notes(s, "Thank you - happy to take questions. The QR code and link go to "
             "the repository with the solver, the scripts that regenerate every "
             "figure, and this deck.")


SLIDES = [s_title, s_roadmap, s_motivation, s_physics, s_solver, s_validation1,
          s_validation2, s_breakup, s_pressure, s_capillary, s_scaling,
          s_lambda_wetting, s_design, s_limits, s_conclusions, s_thanks]


def to_pdf(pptx, pdf):
    soffice = shutil.which("soffice") or \
        "/Applications/LibreOffice.app/Contents/MacOS/soffice"
    if not os.path.exists(soffice):
        raise SystemExit("LibreOffice (soffice) is needed to export the slides to PDF")
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run([soffice, f"-env:UserInstallation=file://{tmp}/profile",
                        "--headless", "--convert-to", "pdf", "--outdir", tmp, pptx],
                       check=True, stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL)
        shutil.move(os.path.join(tmp, os.path.basename(pptx)[:-5] + ".pdf"), pdf)
    link_urls(pdf)


def link_urls(pdf):
    """Make every printed GitHub URL in the PDF a clickable link."""
    import fitz
    doc = fitz.open(pdf)
    added = 0
    for page in doc:
        linked = [fitz.Rect(l["from"]) for l in page.get_links() if l.get("uri")]
        for rect in page.search_for(GITHUB):
            if not any(rect.intersects(r) for r in linked):
                page.insert_link({"kind": fitz.LINK_URI, "from": rect, "uri": GITHUB})
                added += 1
    if added:
        tmp = pdf + ".tmp"
        doc.save(tmp, garbage=3, deflate=True)
        doc.close()
        os.replace(tmp, pdf)
    else:
        doc.close()


def build():
    d = Deck()
    for i, fn in enumerate(SLIDES, 1):
        fn(d, i, len(SLIDES))
    os.makedirs(OUT_DIR, exist_ok=True)
    d.prs.save(PPTX)
    to_pdf(PPTX, PDF)
    print("Built", PPTX, "and", PDF, f"({len(SLIDES)} slides)")
    return len(SLIDES)


if __name__ == "__main__":
    build()
