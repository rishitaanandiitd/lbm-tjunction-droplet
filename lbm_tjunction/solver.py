"""
Two-phase lattice Boltzmann solver for droplet formation in a microfluidic
T-junction (CLL 770 term project).

Model
-----
* Hydrodynamics: D2Q9 single-relaxation-time (BGK) lattice Boltzmann method
  for the incompressible, low-Reynolds-number Navier-Stokes equations, with
  Guo et al. forcing.
* Interface: conservative phase-field (Cahn-Hilliard) description.  The order
  parameter ``phi`` is +1 in the dispersed phase and -1 in the continuous
  phase.  Its chemical potential supplies the surface-tension force
  ``F = mu * grad(phi)`` in the hydrodynamic LBM.
* Viscosity is interpolated linearly in ``phi`` between the two phases, so a
  viscosity ratio can be imposed.  Densities are matched (ratio 1) for
  numerical stability, as stated in the report.
* Walls: half-way bounce-back (no slip).  Wall nodes carry a prescribed
  ghost value ``phi + ghost_delta``, which imposes wettability.
* Inlets: equilibrium distributions with a fully developed parabolic
  (Poiseuille) velocity profile.  Outlet: zero-gradient (copy) outflow.

All hot loops are compiled with Numba.  Everything is scripted: every figure
in the report can be regenerated with ``python3 run_all.py``.

Units are lattice units throughout.  Physical interpretation uses
Ca = mu_c * U_c / sigma,  Qd/Qc,  lambda = mu_d / mu_c and L/w_c.
"""

from __future__ import annotations

import numpy as np

try:
    from numba import njit
except ImportError:  # pragma: no cover - fallback, much slower
    def njit(*args, **kwargs):
        def wrap(fn):
            return fn
        return wrap(args[0]) if args and callable(args[0]) else wrap

# ---------------------------------------------------------------- D2Q9 ----
CX = np.array([0, 1, 0, -1, 0, 1, -1, -1, 1], dtype=np.int64)
CY = np.array([0, 0, 1, 0, -1, 1, 1, -1, -1], dtype=np.int64)
WT = np.array([4/9, 1/9, 1/9, 1/9, 1/9, 1/36, 1/36, 1/36, 1/36])
OPP = np.array([0, 3, 4, 1, 2, 7, 8, 5, 6], dtype=np.int64)
CS2 = 1.0 / 3.0

# Phase-field constants.  With beta = kappa = 0.05 the diffuse-interface
# profile is phi = tanh(r / sqrt(2*kappa/beta)) and the emergent surface
# tension (verified by the Laplace test) is
# sigma = (2*sqrt(2)/3) * sqrt(kappa*beta) in lattice units; the
# value actually used for Ca is the one measured in the Laplace test.
BETA = 0.015
KAPPA = 0.015
SIGMA_THEORY = (2.0 * np.sqrt(2.0) / 3.0) * np.sqrt(KAPPA * BETA)  
MOBILITY = 0.10
INTERFACE_W = np.sqrt(2.0 * KAPPA / BETA)  # ~1.41 (profile scale)


@njit(cache=True, fastmath=True)
def _nb_phi(phi, solid, y, x, yy, xx, wetting):
    """Neighbour phi; solid neighbours use a ghost value from the wetting
    condition  d(phi)/dn = wetting * (1 - phi^2)  (n = into the wall).
    This is zero in either bulk phase (phi = +/-1, no spurious wall film)
    and is active only where an interface meets the wall.  wetting=0 is
    neutral (90 deg); its sign/magnitude set the contact angle (calibrated
    against the measured angle in the contact-angle test)."""
    if yy < 0 or yy >= phi.shape[0] or xx < 0 or xx >= phi.shape[1]:
        p = phi[y, x]
        return p + wetting * (1.0 - p * p)
    if solid[yy, xx]:
        p = phi[y, x]
        return p + wetting * (1.0 - p * p)
    return phi[yy, xx]


@njit(cache=True, fastmath=True)
def _nb_mu(mu, solid, y, x, yy, xx):
    if yy < 0 or yy >= mu.shape[0] or xx < 0 or xx >= mu.shape[1]:
        return mu[y, x]
    if solid[yy, xx]:
        return mu[y, x]
    return mu[yy, xx]


@njit(cache=True, fastmath=True)
def _phi_nb(phi, solid, y, x, wetting):
    """Isotropic neighbour values (E,W,N,S,NE,NW,SE,SW) with wetting ghosts."""
    ny, nx = phi.shape
    pc = phi[y, x]
    ghost = pc + wetting * (1.0 - pc * pc)
    v0 = phi[y, x+1] if (x+1 < nx and not solid[y, x+1]) else ghost
    v1 = phi[y, x-1] if (x-1 >= 0 and not solid[y, x-1]) else ghost
    v2 = phi[y+1, x] if (y+1 < ny and not solid[y+1, x]) else ghost
    v3 = phi[y-1, x] if (y-1 >= 0 and not solid[y-1, x]) else ghost
    v4 = phi[y+1, x+1] if (y+1 < ny and x+1 < nx and not solid[y+1, x+1]) else ghost
    v5 = phi[y+1, x-1] if (y+1 < ny and x-1 >= 0 and not solid[y+1, x-1]) else ghost
    v6 = phi[y-1, x+1] if (y-1 >= 0 and x+1 < nx and not solid[y-1, x+1]) else ghost
    v7 = phi[y-1, x-1] if (y-1 >= 0 and x-1 >= 0 and not solid[y-1, x-1]) else ghost
    return (v0, v1, v2, v3, v4, v5, v6, v7)


@njit(cache=True, fastmath=True)
def _mu_nb(mu, solid, y, x):
    ny, nx = mu.shape
    pc = mu[y, x]
    v0 = mu[y, x+1] if (x+1 < nx and not solid[y, x+1]) else pc
    v1 = mu[y, x-1] if (x-1 >= 0 and not solid[y, x-1]) else pc
    v2 = mu[y+1, x] if (y+1 < ny and not solid[y+1, x]) else pc
    v3 = mu[y-1, x] if (y-1 >= 0 and not solid[y-1, x]) else pc
    v4 = mu[y+1, x+1] if (y+1 < ny and x+1 < nx and not solid[y+1, x+1]) else pc
    v5 = mu[y+1, x-1] if (y+1 < ny and x-1 >= 0 and not solid[y+1, x-1]) else pc
    v6 = mu[y-1, x+1] if (y-1 >= 0 and x+1 < nx and not solid[y-1, x+1]) else pc
    v7 = mu[y-1, x-1] if (y-1 >= 0 and x-1 >= 0 and not solid[y-1, x-1]) else pc
    return (v0, v1, v2, v3, v4, v5, v6, v7)


@njit(cache=True, fastmath=True)
def _iso_grad_lap(nb, pc):
    """D2Q9 isotropic gradient and Laplacian from neighbour values.
    nb order: E,W,N,S,NE,NW,SE,SW."""
    gx = (nb[0] - nb[1]) / 3.0 + ((nb[4] + nb[6]) - (nb[5] + nb[7])) / 12.0
    gy = (nb[2] - nb[3]) / 3.0 + ((nb[4] + nb[5]) - (nb[6] + nb[7])) / 12.0
    weighted = (nb[0] + nb[1] + nb[2] + nb[3]) * (1.0/9.0) \
        + (nb[4] + nb[5] + nb[6] + nb[7]) * (1.0/36.0)
    lap = 6.0 * (weighted - pc * (5.0/9.0))
    return gx, gy, lap


@njit(cache=True, fastmath=True)
def _step(f, f_new, phi, phi_new, mu, solid, nu_c, nu_d, wetting):
    ny, nx = phi.shape
    # --- chemical potential -------------------------------------------------
    for y in range(ny):
        for x in range(nx):
            if solid[y, x]:
                continue
            nb = _phi_nb(phi, solid, y, x, wetting)
            gx, gy, lap = _iso_grad_lap(nb, phi[y, x])
            p = phi[y, x]
            mu[y, x] = BETA * p * (p * p - 1.0) - KAPPA * lap
    # --- hydrodynamics -------------------------------------------------------
    for y in range(ny):
        for x in range(nx):
            if solid[y, x]:
                continue
            nb = _phi_nb(phi, solid, y, x, wetting)
            gx, gy, lap = _iso_grad_lap(nb, phi[y, x])
            fx_s = mu[y, x] * gx
            fy_s = mu[y, x] * gy
            rho = 0.0; mx = 0.0; my = 0.0
            for i in range(9):
                rho += f[i, y, x]; mx += CX[i] * f[i, y, x]; my += CY[i] * f[i, y, x]
            if rho < 1e-12:
                rho = 1.0
            ux = mx / rho + 0.5 * fx_s / rho
            uy = my / rho + 0.5 * fy_s / rho
            frac_d = 0.5 * (phi[y, x] + 1.0)
            if frac_d < 0.0: frac_d = 0.0
            if frac_d > 1.0: frac_d = 1.0
            nu = nu_c * (1.0 - frac_d) + nu_d * frac_d
            tau = 3.0 * nu + 0.5
            inv_tau = 1.0 / tau
            u2 = ux * ux + uy * uy
            for i in range(9):
                cu = CX[i] * ux + CY[i] * uy
                feq = WT[i] * rho * (1.0 + cu / CS2 + cu * cu / (2.0 * CS2 * CS2) - u2 / (2.0 * CS2))
                fterm = WT[i] * (1.0 - 0.5 * inv_tau) * (
                    ((CX[i] - ux) / CS2 + cu * CX[i] / (CS2 * CS2)) * fx_s
                    + ((CY[i] - uy) / CS2 + cu * CY[i] / (CS2 * CS2)) * fy_s)
                fpost = f[i, y, x] - (f[i, y, x] - feq) * inv_tau + fterm
                dx_ = x + CX[i]; dy_ = y + CY[i]
                if dx_ < 0 or dx_ >= nx or dy_ < 0 or dy_ >= ny:
                    pass
                elif solid[dy_, dx_]:
                    f_new[OPP[i], y, x] = fpost
                else:
                    f_new[i, dy_, dx_] = fpost
    # --- Cahn-Hilliard -------------------------------------------------------
    for y in range(ny):
        for x in range(nx):
            if solid[y, x]:
                phi_new[y, x] = -1.0
                continue
            nb_mu = _mu_nb(mu, solid, y, x)
            gmx, gmy, lap_mu = _iso_grad_lap(nb_mu, mu[y, x])
            nb_phi = _phi_nb(phi, solid, y, x, wetting)
            rho = 0.0; mx = 0.0; my = 0.0
            for i in range(9):
                rho += f[i, y, x]; mx += CX[i] * f[i, y, x]; my += CY[i] * f[i, y, x]
            if rho < 1e-12:
                rho = 1.0
            ux = mx / rho; uy = my / rho
            # first-order upwind gradient for advection (robust under shear;
            # the Cahn-Hilliard term re-sharpens the profile)
            pc = phi[y, x]
            gpx = (pc - nb_phi[1]) if ux >= 0.0 else (nb_phi[0] - pc)
            gpy = (pc - nb_phi[3]) if uy >= 0.0 else (nb_phi[2] - pc)
            val = phi[y, x] - (ux * gpx + uy * gpy) + MOBILITY * lap_mu
            if val > 1.0: val = 1.0
            if val < -1.0: val = -1.0
            phi_new[y, x] = val
    return


@njit(cache=True, fastmath=True)
def _set_nebb(f, y, x, rho, ux, uy, kind):
    """Non-equilibrium bounce-back for the unknown populations at a
    boundary node.  kind: 0 = left inlet (unknowns move east),
    1 = top inlet (unknowns move south), 2 = right outlet (unknowns
    move west).  Known populations keep their non-equilibrium part."""
    for i in range(9):
        unknown = False
        if kind == 0 and CX[i] > 0:
            unknown = True
        if kind == 1 and CY[i] < 0:
            unknown = True
        if kind == 2 and CX[i] < 0:
            unknown = True
        if unknown:
            o = OPP[i]
            cu_i = CX[i] * ux + CY[i] * uy
            cu_o = CX[o] * ux + CY[o] * uy
            u2 = ux * ux + uy * uy
            feq_i = WT[i] * rho * (1.0 + cu_i / CS2 + cu_i * cu_i / (2.0 * CS2 * CS2) - u2 / (2.0 * CS2))
            feq_o = WT[o] * rho * (1.0 + cu_o / CS2 + cu_o * cu_o / (2.0 * CS2 * CS2) - u2 / (2.0 * CS2))
            f[i, y, x] = feq_i + (f[o, y, x] - feq_o)


@njit(cache=True, fastmath=True)
def _apply_inlet_outlet(f, phi, y0, y1, x0, x1, uc_max, ud_max, ny, nx):
    """Velocity inlets (parabolic profile, non-equilibrium bounce-back)
    at x=0 and at the top of the side arm; fixed-pressure (rho=1)
    outlet at x=nx-1 with velocity extrapolated from the interior."""
    yc = 0.5 * (y0 + y1 - 1)
    hh = 0.5 * (y1 - y0)
    # velocity-inlet forcing zones (3 columns / rows): populations are set
    # to equilibrium at the target velocity with the *local* density, so
    # the inlet pressure is free to build up as it does in an experiment
    # driven by syringe pumps (imposed flow rate).
    for xx in range(0, 3):
        for y in range(y0, y1):
            s = (y - yc) / hh
            u = uc_max * (1.0 - s * s)
            if u < 0.0:
                u = 0.0
            rho = 0.0
            for i in range(9):
                rho += f[i, y, xx]
            if rho < 1e-12:
                rho = 1.0
            for i in range(9):
                cu = CX[i] * u
                f[i, y, xx] = WT[i] * rho * (1.0 + cu / CS2 + cu * cu / (2.0 * CS2 * CS2) - (u * u) / (2.0 * CS2))
            phi[y, xx] = -1.0
    xc = 0.5 * (x0 + x1 - 1)
    hw = 0.5 * (x1 - x0)
    for yy in range(ny - 3, ny):
        for x in range(x0, x1):
            s = (x - xc) / hw
            v = -ud_max * (1.0 - s * s)
            if v > 0.0:
                v = 0.0
            rho = 0.0
            for i in range(9):
                rho += f[i, yy, x]
            if rho < 1e-12:
                rho = 1.0
            for i in range(9):
                cu = CY[i] * v
                f[i, yy, x] = WT[i] * rho * (1.0 + cu / CS2 + cu * cu / (2.0 * CS2 * CS2) - (v * v) / (2.0 * CS2))
            phi[yy, x] = 1.0
    # velocity outlet over the last 3 columns: fully developed parabolic
    # profile whose flow rate equals Qc + Qd (mass conservation), with the
    # local density retained so the interior pressure is unconstrained.
    uc_mean = uc_max / 1.5
    ud_mean = ud_max / 1.5
    uout_max = 1.5 * (uc_mean * (y1 - y0) + ud_mean * (x1 - x0)) / (y1 - y0)
    for xx in range(nx - 3, nx):
        for y in range(y0, y1):
            s = (y - yc) / hh
            u = uout_max * (1.0 - s * s)
            if u < 0.0:
                u = 0.0
            rho = 0.0
            for i in range(9):
                rho += f[i, y, xx]
            if rho < 1e-12:
                rho = 1.0
            for i in range(9):
                cu = CX[i] * u
                f[i, y, xx] = WT[i] * rho * (1.0 + cu / CS2 + cu * cu / (2.0 * CS2 * CS2) - (u * u) / (2.0 * CS2))
            phi[y, xx] = phi[y, nx - 4]


@njit(cache=True, fastmath=True)
def _moments(f, rho_out, ux_out, uy_out, solid):
    ny, nx = rho_out.shape
    for y in range(ny):
        for x in range(nx):
            if solid[y, x]:
                rho_out[y, x] = 1.0
                ux_out[y, x] = 0.0
                uy_out[y, x] = 0.0
                continue
            rho = 0.0
            mx = 0.0
            my = 0.0
            for i in range(9):
                rho += f[i, y, x]
                mx += CX[i] * f[i, y, x]
                my += CY[i] * f[i, y, x]
            if rho < 1e-12:
                rho = 1.0
            rho_out[y, x] = rho
            ux_out[y, x] = mx / rho
            uy_out[y, x] = my / rho


def equilibrium(rho, ux, uy):
    f = np.zeros((9,) + rho.shape)
    u2 = ux ** 2 + uy ** 2
    for i in range(9):
        cu = CX[i] * ux + CY[i] * uy
        f[i] = WT[i] * rho * (1 + cu / CS2 + cu ** 2 / (2 * CS2 ** 2) - u2 / (2 * CS2))
    return f


class TJunction:
    """T-junction geometry: main channel along x, side channel from the top.

    Lattice geometry (default): domain 400 x 90, main channel height
    w_c = 30 (y = 30..59), side channel width w_d = 16 (x = 124..139),
    i.e. w_d / w_c = 0.53.  The long downstream section (260 lu) lets a
    detached droplet leave the junction before it reaches the outlet.
    """

    def __init__(self, nx=400, ny=90, y0=30, h=30, x0=124, w=16,
                 nu_c=0.15, viscosity_ratio=1.0, wetting=-0.6):
        self.nx, self.ny, self.y0, self.h, self.x0, self.w = nx, ny, y0, h, x0, w
        self.nu_c = nu_c
        self.nu_d = nu_c * viscosity_ratio
        self.wetting = wetting
        solid = np.ones((ny, nx), dtype=bool)
        solid[y0:y0 + h, :] = False                    # main channel
        solid[y0 + h:, x0:x0 + w] = False              # side channel (top)
        self.solid = solid
        self.phi = -np.ones((ny, nx))
        # Side arm is filled with dispersed phase up to the junction mouth,
        # as in an experiment before start-up; the main channel is filled
        # with continuous phase.  The interface at the mouth is initialised
        # as the equilibrium tanh profile so no spurious force is generated
        # at start-up.
        mouth = y0 + h - 1
        for yy in range(ny):
            prof = np.tanh((yy - mouth) / INTERFACE_W)
            for xx in range(x0, x0 + w):
                if not solid[yy, xx]:
                    self.phi[yy, xx] = prof
        self.phi[solid] = -1.0
        self.f = equilibrium(np.ones((ny, nx)), np.zeros((ny, nx)),
                             np.zeros((ny, nx)))
        self.f_new = self.f.copy()
        self.phi_new = self.phi.copy()
        self.mu = np.zeros((ny, nx))

    def run(self, uc_mean, q_ratio, steps, snap_at=(), probe_every=50):
        """uc_mean: mean continuous-phase inlet velocity.
        q_ratio = Qd/Qc, so Ud_mean = q_ratio * uc_mean * h / w."""
        ud_mean = q_ratio * uc_mean * self.h / self.w
        uc_max, ud_max = 1.5 * uc_mean, 1.5 * ud_mean
        snaps = {}
        pressure = []
        probe_x, probe_y = self.x0 - 25, self.y0 + self.h // 2
        rho = np.ones((self.ny, self.nx))
        ux = np.zeros_like(rho); uy = np.zeros_like(rho)
        for step in range(steps + 1):
            if step in snap_at:
                snaps[step] = self.phi.copy()
            if step % probe_every == 0:
                _moments(self.f, rho, ux, uy, self.solid)
                pressure.append((step, rho[probe_y, probe_x] / 3.0))
            _step(self.f, self.f_new, self.phi, self.phi_new, self.mu,
                  self.solid, self.nu_c, self.nu_d, self.wetting)
            self.f, self.f_new = self.f_new, self.f
            self.phi, self.phi_new = self.phi_new, self.phi
            _apply_inlet_outlet(self.f, self.phi, self.y0, self.y0 + self.h,
                                self.x0, self.x0 + self.w, uc_max, ud_max,
                                self.ny, self.nx)
        _moments(self.f, rho, ux, uy, self.solid)
        return {"snaps": snaps, "pressure": np.array(pressure),
                "phi": self.phi.copy(), "rho": rho, "ux": ux, "uy": uy,
                "ud_mean": ud_mean}
