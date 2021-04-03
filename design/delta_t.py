#!/usr/bin/env python3

"""
Choosing a source for ∆T
========================

1. `ftp://ftp.iers.org/products/eop/rapid/standard/`_
2. `ftp://ftp.iers.org/products/eop/rapid/standard/csv/`_

* The CSV files are slightly larger, both compressed and uncompressed.
* For the position of an object at the celestial equator,
  1 second of time = 15 arcseconds.
  1 millisecond of time = 15 mas.

"""
import sys
from time import time

import matplotlib.pyplot as plt
import numpy as np
from numpy import array, concatenate
from skyfield import timelib
from skyfield.api import load
from skyfield.curvelib import Splines
from skyfield.data import iers
from skyfield.data.earth_orientation import parse_S15_table
from skyfield.functions import load_bundled_npy
from skyfield.interpolation import build_spline_given_ends
from skyfield.timelib import Time

delta_t_parabola_stephenson_morrison_hohenkerk_2020_maybe = Splines(
    [1825.0, 1925.0, 0.0, 31.4, 0.0, -320.0])

class A(object):
    __getitem__ = array
A = A()

class E2(list):
    def __init__(self, value):
        self.value = value
    def __eq__(self, other):
        return np.array_equal(other, self.value)

class E():
    def __getitem__(self, i):
        return E2(i)
E = E()

x = A[1, 2, 3]  # No parens!
#print('=', x == E[1,2,3])

def cat(*args):
    return concatenate(args)

def _cat(*args):
    return concatenate(args, axis=1)

def main(argv):
    # work_on_delta_t_discontinuities()
    # compare_splines_to_finals2000_error_bars()
    compare_old_and_new_delta_t()
    # big_solution_vs_slopes()
    # try_solving_relation_between_lod_and_delta_t()

def work_on_delta_t_discontinuities():
    with load.open('finals2000A.all') as f:
        mjd_utc, dut1 = iers.parse_dut1_from_finals_all(f)
    delta_t_recent, leap_dates, leap_offsets = (
        iers._build_timescale_arrays(mjd_utc, dut1)
    )
    delta_t_function = build_new_delta_t(delta_t_recent)

    ts = load.timescale()
    t = ts.J(np.arange(-3000 * 12, 4000 * 12) / 12)

    fig, ax = plt.subplots(1, 1)
    fig.set(size_inches=(5, 5))
    ax.plot(t.J[:-1], np.diff(delta_t_function(t.tt)))
    ax.grid()
    ax.set(xlabel='Year', ylabel='∆T month-to-month change')
    fig.tight_layout()
    fig.savefig('tmp.png')

def do_plot(ax, t, delta_t_function):
    ax.plot(t.J, delta_t_function(t.tt))
    ax.plot(t.J, delta_t_function._long_term_function(t.J))
    ax.grid()

def compare_splines_to_finals2000_error_bars():
    #url = 'http://astro.ukho.gov.uk/nao/lvm/Table-S15-v18.txt'
    url = 'http://astro.ukho.gov.uk/nao/lvm/Table-S15.2020.txt'
    with load.open(url) as f:
        names, columns = parse_S15_table(f)

    i, start_year, end_year, a0, a1, a2, a3 = columns

    f = load.open('finals2000A.all')
    mjd_utc, dut1 = iers.parse_dut1_from_finals_all(f)
    delta_t_recent, leap_dates, leap_offsets = (
        iers._build_timescale_arrays(mjd_utc, dut1)
    )

    print('Size of IERS table:', delta_t_recent.shape)
    print('Number of splines:', i.shape)

    #year = [-720, 400, 700]
    #year = np.arange(-720, 2010)
    #year = np.arange(1800, 2010)
    #year = np.arange(1980, 2010)
    year = np.arange(1980, 2010, 0.1)
    interpolate = Splines(start_year, end_year, a3, a2, a1, a0)
    s15_curve = interpolate(year)

    finals_tt, finals_delta_t = delta_t_recent
    ts = load.timescale()
    t = ts.utc(year)
    tt = t.tt

    interpolate = Splines(
        finals_tt[:-1],
        finals_tt[1:],
        finals_delta_t[1:] - finals_delta_t[:-1],
        finals_delta_t[:-1],
    )

    T0 = time()
    finals_curve = interpolate(tt)
    print(time() - T0, 's for interpolate()')

    T0 = time()
    finals_curve2 = np.interp(tt, finals_tt, finals_delta_t)
    print(time() - T0, 's for interp()')

    assert (finals_curve == finals_curve2).all()

    diff = max(abs(s15_curve - finals_curve))
    print('Max difference (seconds, arcseconds):', diff, diff * 15)

def compare_old_and_new_delta_t():
    f = load.open('finals2000A.all')
    mjd_utc, dut1 = iers.parse_dut1_from_finals_all(f)
    delta_t_recent, leap_dates, leap_offsets = (
        iers._build_timescale_arrays(mjd_utc, dut1)
    )
    plot_delta_t_functions(
        build_legacy_delta_t(delta_t_recent),
        build_new_delta_t(delta_t_recent),
    )

def plot_delta_t_functions(*functions):
    """Display one or more ∆T curves across timescales short to long."""
    ts = load.timescale()
    bounds = [(1990, 2025), (1650, 2025), (1000, 2500), (-2000, 5500)]
    fig, axes = plt.subplots(len(bounds), 1)
    fig.set(size_inches=(5, 10))
    for (lower, upper), ax in zip(bounds, axes):
        t = ts.utc(np.linspace(lower, upper, 1e3))
        for i, f in enumerate(functions):
            label = chr(ord('A') + i)
            linestyle = '-' if i % 2 else '--'
            ax.plot(t.J, f(t.tt), label=label, linestyle=linestyle)
        ax.set(ylabel='∆T (seconds)')
        ax.grid()
    axes[0].legend()
    axes[-1].set(xlabel='Year')
    fig.tight_layout()
    fig.savefig('tmp.png')

def build_new_delta_t(delta_t_recent):
    parabola = timelib.delta_t_parabola_stephenson_morrison_hohenkerk_2016
    tt_index, tt_values = delta_t_recent

    url = 'http://astro.ukho.gov.uk/nao/lvm/Table-S15.2020.txt'
    with load.open(url) as f:
        names, s15_table = parse_S15_table(f)
    s15_table = s15_table[[1,2,6,5,4,3]]

    p = parabola
    pd = parabola.derivative
    s = Splines(s15_table)
    sd = s.derivative

    long_term_parabola_width = p.upper[0] - p.lower[0]

    # How many years wide to make the splines we craft to connect the
    # ends of the tables to the long-term spline.  Tuned by hand until
    # the derivative graphed by `work_on_delta_t_discontinuities()`
    # doesn't look too terrible.
    patch_width = 800.0

    # To the left of the official splines, design a spline connecting
    # them to the long-term parabola.

    x1 = s.lower[0]  # For the current table, this is the year -720.0.
    x0 = x1 - patch_width
    left2 = build_spline_given_ends(x0, x1, p(x0), pd(x0), s(x1), sd(x1))

    # To the left of the connector, put the pure long-term parabola.

    x1 = x0
    x0 = x1 - long_term_parabola_width
    left1 = build_spline_given_ends(x0, x1, p(x0), pd(x0), p(x1), pd(x1))

    # To the right of the recent ∆T table, design a spline connecting
    # smoothly to the long-term parabola.

    x0 = (tt_index[-1] - 1721045.0) / 365.25
    x1 = (x0 + patch_width) // 100.0 * 100.0  # Choose multiple of 100 years
    y0 = tt_values[-1]
    slope0 = tt_values[-1] - tt_values[-366]  # Final year of recent ∆T
    right1 = build_spline_given_ends(x0, x1, y0, slope0, p(x1), pd(x1))

    # At the far right, finish with the pure long-term parabola.

    x0 = x1
    x1 = x0 + long_term_parabola_width
    right2 = build_spline_given_ends(x0, x1, p(x0), pd(x0), p(x1), pd(x1))

    curve = Splines(_cat(
        np.array([left1]).T,
        np.array([left2]).T,
        s15_table,
        np.array([right1]).T,
        np.array([right2]).T,
    ))

    return timelib.DeltaT(tt_index, tt_values, curve)

def build_legacy_delta_t(delta_t_recent):
    bundled = _cat(
        load_bundled_npy('morrison_stephenson_deltat.npy')[:,:22],
        load_bundled_npy('historic_deltat.npy'),
    )
    recent_start_time = delta_t_recent[0,0]
    i = np.searchsorted(bundled[0], recent_start_time)
    century = 36524.0
    start_tt = bundled[0,0] - century
    start_J = Time(None, start_tt).J
    end_tt = delta_t_recent[0,-1] + century
    end_J = Time(None, end_tt).J
    parabola = timelib.delta_t_parabola_morrison_stephenson_2004
    delta_t_table = _cat(
        [[start_tt], [parabola(start_J)]],
        bundled[:,:i],
        delta_t_recent,
        [[end_tt], [parabola(end_J)]],
    )
    return timelib.DeltaT(delta_t_table[0], delta_t_table[1], parabola)

def big_solution_vs_slopes():
    # Q: Do we really need the huge move_spline_endpoints() routine that
    #    SymPy figured out for us?  Or can we rebuild a spline over a
    #    different range using just its endpoints and their slopes?
    #
    # A: Wow, we can just use their slopes!
    #
    p = timelib.delta_t_parabola_stephenson_morrison_hohenkerk_2016
    row = p.table[:,0]
    print('Original row:')
    print(row)

    x = np.arange(1700, 2000)
    x0 = 1790
    x1 = 1800

    row2 = move_spline_endpoints(x0, x1, row)
    print('Move endpoints:')
    print(row2)

    row3 = build_spline_given_ends(
        x0, x1, p(x0), p(x1), p.derivative(x0), p.derivative(x1),
    )
    print('From y and slopes:')
    print(row3)

    p2 = Splines(row3)

    fig, ax = plt.subplots(1, 1)
    ax.plot(x, p(x))
    ax.plot(x, p2(x), linestyle='--')
    fig.savefig('tmp.png')

def move_spline_endpoints(new_left, new_right, table_row):
    old_left, old_right, a3, a2, a1, a0 = table_row

    k0, k1 = old_left, old_right
    j0, j1 = new_left, new_right

    u0 = a1/(-k0 + k1)
    u1 = j0*u0
    u2 = k0**2
    u3 = k1**2
    u4 = 2*k0
    u5 = a2/(-k1*u4 + u2 + u3)
    u6 = k0**3
    u7 = 3*k0
    u8 = 3*u2
    u9 = a3/(k1**3 + k1*u8 - u3*u7 - u6)
    u10 = j0**3*u9
    u11 = u4*u5
    u12 = j0*u11
    u13 = u8*u9
    u14 = j0*u13
    u15 = j0**2
    u16 = u15*u5
    u17 = u15*u9
    u18 = u16 - u17*u7
    u19 = j0*j1
    u20 = 2*u19*u5
    u21 = 3*u10
    u22 = 6*k0
    u23 = u19*u22*u9
    u24 = j1*u17
    u25 = 3*u24
    u26 = j1**2
    u27 = u26*u9
    u28 = 3*j0*u27

    b0 = a0 - k0*u0 + u1 + u10 - u12 + u14 + u18 + u2*u5 - u6*u9
    b1 = j1*u0 - j1*u11 + j1*u13 - u1 + u12 - u14 - 2*u16 + u17*u22 + u20 - u21 - u23 + u25
    b2 = u18 - u20 + u21 + u23 - 6*u24 + u26*u5 - u27*u7 + u28
    b3 = j1**3*u9 - u10 + u25 - u28
    return new_left, new_right, b3, b2, b1, b0

def try_solving_moving_endpoints_of_spline():
    import sympy as sy
    sy.init_printing()

    a0, a1, a2, a3, k0, k1, j0, j1, new_t = sy.symbols(
        'a0, a1, a2, a3, k0, k1, j0, j1, new_t')

    # Q: How much simpler is it if we only move one end?
    #j0 = k0  # A: Wow, much simpler!  30+ ops instead of 80+
    #j1 = k1  # A: GADS, not much simpler at all, still 80+ operations.

    years = new_t * (j1 - j0) + j0
    old_t = (years - k0) / (k1 - k0)
    d = (((a3 * old_t + a2) * old_t) + a1) * old_t + a0

    #d = sy.factor(d)
    #d = sy.expand(d)
    #d = sy.simplify(d)
    d = sy.expand(d)

    d = sy.collect(d, new_t)
    b0 = d.coeff(new_t, 0)
    b1 = d.coeff(new_t, 1)
    b2 = d.coeff(new_t, 2)
    b3 = d.coeff(new_t, 3)

    commons, outputs = sy.cse(
        [b0, b1, b2, b3],
        sy.numbered_symbols('u'),
        #optimizations='basic',
    )
    n = 0
    for symbol, expr in commons:
        n += sy.count_ops(expr)
        print(symbol, '=', expr)
    print()
    for i, expr in enumerate(outputs):
        n += sy.count_ops(expr)
        print('b{} = {}'.format(i, expr))
    print('Total operations: {}'.format(n))

def try_solving_relation_between_lod_and_delta_t():
    # From 2016 paper:
    #
    # "The following parabola is a good fit overall to the values of ΔT
    # discussed in §3 and plotted in figures 9, 11–14 (it lies outside
    # the box in figure 10). ΔT= −320.0+(32.5±0.6)((year−1825)/100)^2 s.
    # (4.1)"
    #
    # "The long-term average rate of change in lod derived from the time
    # derivative of equation (4.1) is +1.78±0.03 ms cy−1"
    #
    lod_rate_ms_per_century = +1.78
    lod_rate_s_per_century = lod_rate_ms_per_century / 1000.0
    #
    # ΔT falls further behind by the "lod" amount every single day.
    # There are this many days in a century:
    #
    lod_affect_on_delta_t_per_century = lod_rate_s_per_century * 36525.0
    #
    # Integrate: coefficient * t -> (coefficient/2) t^2.
    #
    delta_t_square_coefficient = 0.5 * lod_affect_on_delta_t_per_century
    #
    # The result is happily close to 32.5!
    #
    print(delta_t_square_coefficient)  # prints: 32.50725

    # But their new Supplement claims to integrate "lod = +1.72 t" but
    # without ever offering the corresponding parabola.  Thus, let's
    # repeat the above calculation for this new "lod" value:
    #
    lod_rate_ms_per_century = +1.72
    lod_rate_s_per_century = lod_rate_ms_per_century / 1000.0
    lod_affect_on_delta_t_per_century = lod_rate_s_per_century * 36525.0
    delta_t_square_coefficient = 0.5 * lod_affect_on_delta_t_per_century
    print(delta_t_square_coefficient)  # prints: 31.4115

if __name__ == '__main__':
    main(sys.argv[1:])
