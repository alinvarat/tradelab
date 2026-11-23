"""Technical indicators on plain lists. None marks warm-up bars."""
import math


def sma(x, n):
    out, s = [None] * len(x), 0.0
    for i, v in enumerate(x):
        s += v
        if i >= n:
            s -= x[i - n]
        if i >= n - 1:
            out[i] = s / n
    return out


def ema(x, n):
    out, k, prev = [None] * len(x), 2 / (n + 1), None
    for i, v in enumerate(x):
        if i == n - 1:
            prev = sum(x[:n]) / n
        elif i >= n:
            prev = v * k + prev * (1 - k)
        out[i] = prev
    return out


def rsi(x, n=14):
    out, ag, al = [None] * len(x), 0.0, 0.0
    for i in range(1, len(x)):
        d = x[i] - x[i - 1]
        g, ls = max(d, 0), max(-d, 0)
        if i <= n:
            ag += g / n
            al += ls / n
        else:
            ag = (ag * (n - 1) + g) / n
            al = (al * (n - 1) + ls) / n
        if i >= n:
            out[i] = 100.0 if al == 0 else 100 - 100 / (1 + ag / al)
    return out


def macd(x, fast=12, slow=26, sig=9):
    ef, es = ema(x, fast), ema(x, slow)
    line = [a - b if a is not None and b is not None else None for a, b in zip(ef, es)]
    start = next((i for i, v in enumerate(line) if v is not None), len(x))
    sl = [None] * len(x)
    if len(x) - start >= sig:
        e = ema(line[start:], sig)
        sl[start:] = e
    hist = [a - b if a is not None and b is not None else None for a, b in zip(line, sl)]
    return line, sl, hist


def bollinger(x, n=20, k=2.0):
    mid, up, lo = [None] * len(x), [None] * len(x), [None] * len(x)
    for i in range(n - 1, len(x)):
        w = x[i - n + 1:i + 1]
        m = sum(w) / n
        sd = math.sqrt(sum((v - m) ** 2 for v in w) / n)
        mid[i], up[i], lo[i] = m, m + k * sd, m - k * sd
    return mid, up, lo


def true_range(h, l, c):
    return [h[0] - l[0]] + [max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1])) for i in range(1, len(c))]


def atr(h, l, c, n=14):
    tr, out, prev = true_range(h, l, c), [None] * len(c), None
    for i in range(len(c)):
        if i < n:
            prev = tr[i] if prev is None else prev + tr[i]
            if i == n - 1:
                prev /= n
                out[i] = prev
        else:
            prev = (prev * (n - 1) + tr[i]) / n
            out[i] = prev
    return out


def stochastic(h, l, c, n=14, d=3):
    k = [None] * len(c)
    for i in range(n - 1, len(c)):
        hh, ll = max(h[i - n + 1:i + 1]), min(l[i - n + 1:i + 1])
        k[i] = 50.0 if hh == ll else (c[i] - ll) / (hh - ll) * 100
    start = n - 1
    dl = [None] * len(c)
    for i in range(start + d - 1, len(c)):
        dl[i] = sum(k[i - d + 1:i + 1]) / d
    return k, dl


def adx(h, l, c, n=14):
    """Wilder ADX with +DI / -DI."""
    L = len(c)
    out, pdi, mdi = [None] * L, [None] * L, [None] * L
    if L < 2 * n + 1:
        return out, pdi, mdi
    tr = true_range(h, l, c)
    pdm = [0.0] + [max(h[i] - h[i - 1], 0) if h[i] - h[i - 1] > l[i - 1] - l[i] else 0.0 for i in range(1, L)]
    mdm = [0.0] + [max(l[i - 1] - l[i], 0) if l[i - 1] - l[i] > h[i] - h[i - 1] else 0.0 for i in range(1, L)]
    atr_s, p_s, m_s = sum(tr[1:n + 1]), sum(pdm[1:n + 1]), sum(mdm[1:n + 1])
    dxs = []
    for i in range(n, L):
        if i > n:
            atr_s = atr_s - atr_s / n + tr[i]
            p_s = p_s - p_s / n + pdm[i]
            m_s = m_s - m_s / n + mdm[i]
        pd_ = 100 * p_s / atr_s if atr_s else 0
        md_ = 100 * m_s / atr_s if atr_s else 0
        pdi[i], mdi[i] = pd_, md_
        dx = 100 * abs(pd_ - md_) / (pd_ + md_) if pd_ + md_ else 0
        dxs.append(dx)
        if len(dxs) == n:
            out[i] = sum(dxs) / n
        elif len(dxs) > n:
            out[i] = (out[i - 1] * (n - 1) + dx) / n
    return out, pdi, mdi


def obv(c, v):
    out = [0.0]
    for i in range(1, len(c)):
        out.append(out[-1] + (v[i] if c[i] > c[i - 1] else -v[i] if c[i] < c[i - 1] else 0))
    return out


def donchian(h, l, n=20):
    up = [None if i < n - 1 else max(h[i - n + 1:i + 1]) for i in range(len(h))]
    lo = [None if i < n - 1 else min(l[i - n + 1:i + 1]) for i in range(len(l))]
    return up, lo


def returns(c):
    return [c[i] / c[i - 1] - 1 for i in range(1, len(c)) if c[i - 1]]


def hist_vol(c, periods_per_year=252):
    r = returns(c)
    if len(r) < 2:
        return None
    m = sum(r) / len(r)
    return math.sqrt(sum((x - m) ** 2 for x in r) / (len(r) - 1)) * math.sqrt(periods_per_year) * 100
