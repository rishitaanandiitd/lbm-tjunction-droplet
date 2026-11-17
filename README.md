# Lattice Boltzmann Simulation of Droplet Formation in a Microfluidic T-Junction

**CLL 770 – Introduction to Microfluidics and Fabrication | Term Project**
IIT Delhi

| # | Name | Entry Number |
|---|------|--------------|
| 1 | Ananyaa Agrawal | 2022CH71487 |
| 2 | Yash Balram Sakhare | 2022CH71496 |
| 3 | Rishita Anand | 2022CH71042 |

**GitHub repository:** https://github.com/rishitaanandiitd/lbm-tjunction-droplet

> Note: if this link does not resolve yet, the repository has not been
> pushed from the authors' machine — the complete, self-contained code
> is in this folder and runs without the remote.

## What this is

A two-phase lattice Boltzmann (LBM) solver, written from scratch in
Python/NumPy and accelerated with Numba, that simulates droplet
formation at a microfluidic T-junction:

- **Hydrodynamics** — D2Q9 BGK lattice Boltzmann for the low-Re
  Navier–Stokes equations, Guo forcing.
- **Interface** — Cahn–Hilliard phase field (`phi = +1` dispersed,
  `phi = -1` continuous); surface tension enters as `F = mu · grad(phi)`
  with `mu` the chemical potential. D2Q9-isotropic gradients/Laplacian,
  upwind advection of `phi`.
- **Walls** — bounce-back (no slip); wetting through
  `d(phi)/dn = wetting · (1 - phi²)`, calibrated in the contact-angle test.
- **Inlets/outlets** — syringe-pump (imposed-flow-rate) forcing zones with
  parabolic profiles and local density; fully developed velocity outlet
  carrying `Qc + Qd`.

## Run it

```bash
pip install -r requirements.txt
python3 run_all.py        # regenerates every figure + CSV (~10 min)
python3 build_pdf.py      # builds output/CLL770_Final_Report_and_Slides.pdf
```

Quick single case:

```python
from lbm_tjunction.solver import TJunction
t = TJunction(nu_c=0.05)                       # w_c=30, w_d=16 lu
out = t.run(uc_mean=0.003, q_ratio=0.5, steps=20000,
            snap_at=(0, 5000, 10000, 20000))
print(out["phi"].shape, out["pressure"][:3])
```

## Layout

```
lbm_tjunction/solver.py   # the solver (all physics, Numba kernels)
run_all.py                # validations + T-junction sweeps -> figures/CSVs
build_pdf.py              # report + slides -> one combined PDF
results/figures/          # generated figures (used in the PDF)
results/data/             # generated CSVs, summary.txt, hero snapshots
output/                   # the final combined PDF
```

## Dimensionless groups

`Ca = mu_c Uc / sigma`, `Qr = Qd/Qc`, `lambda = mu_d/mu_c`, `L/wc`.
`sigma = 0.0126 lu` is **measured** in the Laplace test
(`results/data/laplace.csv`), not assumed.

## Limitations (also in the report)

2-D, matched densities, moderate viscosity ratios, diffuse interface
~3–4 lu wide. Results are therefore quantitative for trends, regime
boundaries and scaling exponents, and qualitative for absolute droplet
volumes in a real 3-D PDMS device.

## References

1. H. Liu, Y. Zhang, *Droplet formation in a T-shaped microfluidic
   junction*, J. Appl. Phys. **106**, 034906 (2009). DOI: 10.1063/1.3187831
2. P. Garstecki, M. J. Fuerstman, H. A. Stone, G. M. Whitesides,
   *Formation of droplets and bubbles in a microfluidic T-junction —
   scaling and mechanism of break-up*, Lab Chip **6**, 437–446 (2006).
