"""Always-valid sequential test (betting e-process) so a forward test can be checked every day and stopped as soon as
the evidence is clear, without the false-positive inflation of peeking at a fixed-sample test.

H0 "edge": mean <= 0 is rejected when the wealth of a bettor who bets on a positive mean reaches 1/alpha (Ville's
inequality). The mirror bettor rejects "mean >= 0" for a futility stop ("no edge").
`lo` must be a HARD lower bound of one observation (1.0 for an unlevered return or an option premium; the stake share for
a portfolio day), because clipping the loss side would favour the strategy. Wins are clipped at `hi`, which can only lower
the mean, so that side stays valid. Values are scaled by `lo` into [-1, hi/lo]; a paired difference by lo+hi into [-1, 1].

Feed ONE value per independent unit (for example the mean return of all trades entered on a day), not every trade,
because trades on the same day share market moves. Reference: Waudby-Smith & Ramdas (2023), aGRAPA betting.
"""
import math

ALPHA = 0.05
LAMBDA_MAX = 0.5
FORWARD_START_TS = 1795564800  # 2026-11-25 00:00 UTC, first eligible day for daily-v1


class EProcess:
    def __init__(self, alpha: float = ALPHA, lo: float = 1.0, hi: float = 3.0, paired: bool = False):
        self.alpha, self.lo, self.hi, self.paired = alpha, lo, hi, paired
        self.n, self.sum, self.sumsq = 0, 0.0, 0.0
        self.log_up, self.log_down = 0.0, 0.0          # log wealth of the "mean > 0" and "mean < 0" bettors
        self.decision, self.decided_at = "continue", None

    def _scale(self, x: float) -> float:
        if self.paired:
            return max(-1.0, min(1.0, x / (self.lo + self.hi)))
        return max(-1.0, min(self.hi, x) / self.lo)

    def _top(self) -> float:
        return 1.0 if self.paired else self.hi / self.lo

    def _lambda(self, sign: int) -> float:
        """aGRAPA: predictable bet size from past data only (0 before the first observation's evidence)."""
        if self.n == 0:
            return 0.0
        m = self.sum / self.n
        v = max(self.sumsq / self.n - m * m, 1e-12)
        lam = sign * m / (v + m * m)
        cap = LAMBDA_MAX if sign > 0 else LAMBDA_MAX / max(1.0, self._top())   # keeps 1 + lam*y > 0 for every y
        return max(0.0, min(cap, lam))

    def update(self, x: float) -> str:
        y = self._scale(x)
        lu, ld = self._lambda(+1), self._lambda(-1)
        self.log_up += math.log(max(1e-300, 1.0 + lu * y))
        self.log_down += math.log(max(1e-300, 1.0 - ld * y))
        self.n += 1
        self.sum += y
        self.sumsq += y * y
        if self.decision == "continue":
            if self.log_up >= math.log(1 / self.alpha):
                self.decision, self.decided_at = "edge", self.n
            elif self.log_down >= math.log(1 / self.alpha):
                self.decision, self.decided_at = "no edge (negative)", self.n
        return self.decision

    def view(self) -> dict:
        return {"n_units": self.n, "e_value_edge": round(math.exp(min(self.log_up, 700)), 4),
                "e_value_negative": round(math.exp(min(self.log_down, 700)), 4), "threshold": round(1 / self.alpha, 2),
                "decision": self.decision, "decided_at_unit": self.decided_at,
                "mean_scaled": round(self.sum / self.n, 6) if self.n else None}


def run(values: list, **kw) -> dict:
    e = EProcess(**kw)
    for v in values:
        e.update(v)
    return e.view()


def daily_means(rows: list, key_ts: str = "ts", value: str = "ret") -> list:
    """[{ts, ret}] -> mean value per UTC day, in time order (one independent unit per day)."""
    import time
    by: dict = {}
    for r in rows:
        if r.get(value) is None or r.get(key_ts) is None:
            continue
        by.setdefault(time.strftime("%Y-%m-%d", time.gmtime(r[key_ts])), []).append(r[value])
    return [sum(v) / len(v) for _, v in sorted(by.items())]


def paired_daily(rows: list, *, start: float, before: float) -> dict:
    """Report evidence on daily means of bounded model/control returns in [start, before)."""
    low, high = -2.0, 3.0
    metrics = {"model": [], "paired": []}
    for row in rows:
        ts, model, control = row.get("ts"), row.get("model"), row.get("control")
        if ts is None or not start <= ts < before or model is None or not math.isfinite(model):
            continue
        bounded_model = min(high, max(low, model))
        metrics["model"].append({"ts": ts, "ret": bounded_model})
        if control is not None and math.isfinite(control):
            bounded_control = min(high, max(low, control))
            metrics["paired"].append({"ts": ts, "ret": bounded_model - bounded_control})
    return {
        "protocol": "daily-v1",
        "model": run(daily_means(metrics["model"]), lo=-low, hi=high),
        "paired": run(daily_means(metrics["paired"]), lo=-low, hi=high, paired=True),
    }
