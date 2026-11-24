"""Reproducible calculations for risk_return_ceiling.md
Run: python3 risk_return_ceiling_sim.py
Requires: numpy, scipy

All figures labelled [คำนวณเอง] in the notes come from this script.
Assumptions:
  - 1 month = 21 trading days, 63 trades (3/day)
  - Model A: fixed-fraction bet, payoff 1:1, per-trade sigma = 1R, no costs
  - Model B: fixed-notional margin position, equity = 1 + L*(S-1),
    liquidation at equity <= 0, GBM, no jumps (understates tail risk)
"""
import math
import numpy as np
from scipy.stats import norm

rng = np.random.default_rng(21)


# ---------- Model A: fixed-fraction betting ----------
def month_sim(edge, f, n_trades=63, b=1.0, trials=200_000):
    p = min(max((1.0 + edge) / (1.0 + b), 0.0), 1.0)
    wins = rng.binomial(n_trades, p, trials)
    return (1 + f * b) ** wins * (1 - f) ** (n_trades - wins)


def table_a():
    print("=== A. Fixed-fraction, 63 trades/month, 1:1 ===")
    hdr = ("edge", "risk", "p_win", "P(3x)", "P(2x)", "P(>1)", "median", "p05", "P(<=10%)")
    print("{:>5} {:>6} {:>6} {:>7} {:>7} {:>7} {:>7} {:>7} {:>9}".format(*hdr))
    for edge in (0.0, 0.01, 0.05, 0.10):
        for f in (0.005, 0.01, 0.02, 0.05, 0.10, 0.25, 0.50):
            m = month_sim(edge, f)
            print(
                f"{edge:5.0%} {f:6.1%} {(1+edge)/2:6.1%} {(m>=3).mean():7.2%} "
                f"{(m>=2).mean():7.2%} {(m>1).mean():7.1%} {np.median(m):7.2f} "
                f"{np.percentile(m,5):7.3f} {(m<=0.10).mean():9.2%}"
            )


def table_b():
    print("\n=== B. Kelly ceiling: f* = edge/sigma^2, g = edge^2/(2 sigma^2) ===")
    for edge in (0.01, 0.02, 0.04, 0.05, 0.10):
        g = edge ** 2 / 2 * 63
        print(
            f"edge={edge:4.0%}/trade  f*={edge:4.1%} of equity  "
            f"median month {math.exp(g)-1:+7.2%}  months to 3x {math.log(3)/g:7.1f}"
        )


def table_c():
    print("\n=== C. Per-trade Sharpe needed for 3x in one month (full Kelly) ===")
    g = math.log(3) / 63
    sr = math.sqrt(2 * g)
    print(f"g/trade={g:.4%}  per-trade Sharpe={sr:.3f}  "
          f"equivalent 1:1 win rate={(1+sr)/2:.1%}  monthly Sharpe={sr*math.sqrt(63):.2f}")


# ---------- Model B: leverage / liquidation ----------
def p_hit(a, sig_ann, years):
    """Probability a driftless GBM touches a downside barrier a within T years."""
    return 2 * norm.cdf(-a / (sig_ann * math.sqrt(years)))


def table_d():
    print("\n=== D. Barrier probability 2*Phi(-a/(sigma*sqrt(T))) ===")
    grid = [(1/365, "1d"), (7/365, "1w"), (21/252, "1m")]
    for name, sig in (("BTC 60%/yr", 0.60), ("EURUSD 8%/yr", 0.08)):
        print(f"-- {name} --")
        for L in (5, 10, 20, 30, 50):
            for a, tag in ((1.0 / L, "wipe"), (0.5 / L, "closeout50%")):
                cells = " ".join(f"{lab} {p_hit(a,sig,T):6.2%}" for T, lab in grid)
                print(f"  L={L:>2} {tag:>11} @{a:5.2%}: {cells}")


def run_lev(L, sig=0.60, days=21, steps=24, trials=200_000, drag_ann=0.0):
    n = days * steps
    dt = days / 365 / n          # total horizon = n*dt = days/365
    sd = sig * math.sqrt(dt)
    mu = (-drag_ann - 0.5 * sig ** 2) * dt
    S = np.ones(trials)
    alive = np.ones(trials, bool)
    hit3 = np.zeros(trials, bool)
    for _ in range(n):
        S = np.where(alive, S * np.exp(rng.normal(mu, sd, trials)), S)
        eq = np.where(alive, 1 + L * (S - 1), -1.0)
        hit3 |= alive & (eq >= 3)
        alive &= eq > 0
    eqf = np.where(alive, 1 + L * (S - 1), 0.0)
    return alive.mean(), (eqf >= 3).mean(), hit3.mean(), float(np.median(eqf))


def table_e():
    print("\n=== E. Monte Carlo: BTC 60%/yr, 1 month hold, no edge ===")
    print(f"{'L':>3} {'alive':>7} {'end>=3x':>8} {'touch3x':>8} {'median':>7}")
    for L in (5, 10, 20, 50):
        a, e3, h, m = run_lev(L)
        print(f"{L:>3} {a:7.2%} {e3:8.2%} {h:8.2%} {m:7.2f}")
    print("carry drag @20x (funding+fees on notional):")
    for drag in (0.0, 0.11, 0.25):
        a, e3, h, m = run_lev(20, drag_ann=drag)
        print(f"  {drag:4.0%}/yr -> {drag*20:5.0%} on equity: alive {a:6.2%} "
              f"touch3x {h:6.2%} median {m:5.3f}")


def table_f():
    print("\n=== F. Sample size to confirm an edge (two-sided 95%) ===")
    for p, delta in ((0.52, 0.02), (0.55, 0.05), (0.60, 0.05)):
        n = p * (1 - p) * (1.96 / delta) ** 2
        print(f"win {p:.0%} +/-{delta:.0%}: n={n:7.0f} trades, {n/3:6.0f} days at 3/day")

    print("\n=== G. Fee drag, 0.10% of notional per round trip, 63 trades ===")
    for L in (1, 3, 5, 10, 20):
        print(f"notional {L:>2}x: cost/trade {0.001*L:5.2%} of equity, "
              f"remaining {(1-0.001*L)**63:6.1%}")


if __name__ == "__main__":
    table_a()
    table_b()
    table_c()
    table_d()
    table_e()
    table_f()
