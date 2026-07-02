"""
bridge/agents/stock_research.py - Your Company Stock Research Agent (v3.2)
============================================================================
5 sub-agents using yfinance (free, no API key).
Watchlist: NUE, STLD, CMC, CLF, RS + SPY.
Technical, Fundamental, Sentiment, Risk, Thesis Writer.
"""

from datetime import datetime, timezone

# Steel watchlist - companies Your Company can track for market intel
# BUG-9 fix: ticker "X" (U.S. Steel) removed - acquired by Nippon Steel
# June 2025, no longer trades publicly. yfinance returned a delisted warning
# on every diagnostic run. If U.S. Steel relists, add it back here.
DEFAULT_WATCHLIST = ["NUE", "STLD", "CMC", "CLF", "RS", "SPY"]


def _get_ticker(symbol: str):
    """Load yfinance ticker. Returns None if yfinance not installed."""
    try:
        import yfinance as yf
        return yf.Ticker(symbol)
    except ImportError:
        return None


def _safe_float(val, default=0.0) -> float:
    try:
        return float(val) if val is not None else default
    except (TypeError, ValueError):
        return default


# ── 1. Technical Analysis ──────────────────────────────────────────

def technical_analysis(symbol: str) -> dict:
    """MA20/50/200, RSI 14, 52-week range, volume vs avg, signal."""
    t = _get_ticker(symbol)
    if not t:
        return {"error": "yfinance not installed. Run: pip install yfinance"}

    try:
        hist = t.history(period="1y")
        if hist.empty:
            return {"error": f"No data for {symbol}"}

        close = hist["Close"]
        vol   = hist["Volume"]
        price = _safe_float(close.iloc[-1])
        ma20  = _safe_float(close.tail(20).mean())
        ma50  = _safe_float(close.tail(50).mean())
        ma200 = _safe_float(close.mean())

        # RSI 14
        delta    = close.diff()
        gain     = delta.clip(lower=0).tail(14).mean()
        loss     = (-delta.clip(upper=0)).tail(14).mean()
        rsi      = round(100 - 100 / (1 + gain / loss), 1) if loss != 0 else 50.0

        wk52_hi  = _safe_float(close.max())
        wk52_lo  = _safe_float(close.min())
        avg_vol  = _safe_float(vol.tail(20).mean())
        last_vol = _safe_float(vol.iloc[-1])

        # Signal
        if price > ma20 > ma50 > ma200 and rsi < 70:
            signal = "BULLISH"
        elif price < ma20 < ma50 and rsi > 70:
            signal = "OVERBOUGHT"
        elif price < ma20 < ma50:
            signal = "BEARISH"
        else:
            signal = "NEUTRAL"

        return {
            "symbol":     symbol,
            "price":      round(price, 2),
            "ma20":       round(ma20, 2),
            "ma50":       round(ma50, 2),
            "ma200":      round(ma200, 2),
            "rsi_14":     rsi,
            "52w_high":   round(wk52_hi, 2),
            "52w_low":    round(wk52_lo, 2),
            "vs_52w_high": f"{round((price/wk52_hi-1)*100, 1)}%",
            "volume_ratio":round(last_vol/avg_vol, 2) if avg_vol else 0,
            "signal":     signal,
        }
    except Exception as e:
        return {"error": str(e), "symbol": symbol}


# ── 2. Fundamental Analysis ────────────────────────────────────────

def fundamental_analysis(symbol: str) -> dict:
    """PE, EV/EBITDA, margins, revenue growth, debt-to-equity, analyst targets."""
    t = _get_ticker(symbol)
    if not t:
        return {"error": "yfinance not installed"}

    try:
        info = t.info
        return {
            "symbol":           symbol,
            "pe_trailing":      _safe_float(info.get("trailingPE")),
            "pe_forward":       _safe_float(info.get("forwardPE")),
            "ev_ebitda":        _safe_float(info.get("enterpriseToEbitda")),
            "revenue_growth":   _safe_float(info.get("revenueGrowth")),
            "gross_margin":     _safe_float(info.get("grossMargins")),
            "operating_margin": _safe_float(info.get("operatingMargins")),
            "net_margin":       _safe_float(info.get("profitMargins")),
            "debt_equity":      _safe_float(info.get("debtToEquity")),
            "analyst_target":   _safe_float(info.get("targetMeanPrice")),
            "current_price":    _safe_float(info.get("currentPrice")),
            "upside_pct":       round(
                (_safe_float(info.get("targetMeanPrice")) /
                 max(_safe_float(info.get("currentPrice")), 0.01) - 1) * 100, 1
            ),
            "market_cap_B":     round(_safe_float(info.get("marketCap")) / 1e9, 2),
        }
    except Exception as e:
        return {"error": str(e), "symbol": symbol}


# ── 3. Risk Analysis ───────────────────────────────────────────────

def risk_analysis(symbol: str, benchmark: str = "SPY") -> dict:
    """Beta vs SPY, annualized volatility, max drawdown, Sharpe ratio."""
    t   = _get_ticker(symbol)
    spy = _get_ticker(benchmark)
    if not t:
        return {"error": "yfinance not installed"}

    try:
        import numpy as np
        hist = t.history(period="1y")["Close"].pct_change().dropna()
        spy_h= spy.history(period="1y")["Close"].pct_change().dropna() if spy else None

        ann_vol    = round(float(hist.std()) * (252 ** 0.5) * 100, 1)
        max_dd     = round(float(((hist.cumsum() + 1).cummin() - (hist.cumsum() + 1)).min()) * 100, 1)
        sharpe     = round(float(hist.mean() / hist.std()) * (252 ** 0.5), 2) if hist.std() else 0

        beta = None
        if spy_h is not None:
            aligned = hist.align(spy_h, join='inner')
            if len(aligned[0]) > 20:
                cov = float(np.cov(aligned[0], aligned[1])[0][1])
                var = float(aligned[1].var())
                beta = round(cov / var, 2) if var else None

        return {
            "symbol":          symbol,
            "beta_vs_spy":     beta,
            "ann_volatility":  f"{ann_vol}%",
            "max_drawdown_1y": f"{max_dd}%",
            "sharpe_ratio":    sharpe,
            "risk_level":      "HIGH" if ann_vol > 35 else "MEDIUM" if ann_vol > 20 else "LOW",
        }
    except Exception as e:
        return {"error": str(e), "symbol": symbol}


# ── 4. Sentiment Analysis ──────────────────────────────────────────

def sentiment_analysis(symbol: str) -> dict:
    """Short float, insider ownership, institutional ownership, analyst consensus."""
    t = _get_ticker(symbol)
    if not t:
        return {"error": "yfinance not installed"}

    try:
        info = t.info
        rec  = info.get("recommendationKey", "").upper()
        return {
            "symbol":             symbol,
            "analyst_consensus":  rec or "N/A",
            "analyst_count":      info.get("numberOfAnalystOpinions", 0),
            "short_float_pct":    round(_safe_float(info.get("shortPercentOfFloat")) * 100, 1),
            "insider_pct":        round(_safe_float(info.get("heldPercentInsiders")) * 100, 1),
            "institutional_pct":  round(_safe_float(info.get("heldPercentInstitutions")) * 100, 1),
            "52w_change_pct":     round(_safe_float(info.get("52WeekChange")) * 100, 1),
        }
    except Exception as e:
        return {"error": str(e), "symbol": symbol}


# ── 5. Investment Thesis (composite) ──────────────────────────────

def investment_thesis(symbol: str) -> dict:
    """Composite score 0-100 + verdict from STRONG BUY to STRONG SELL."""
    tech  = technical_analysis(symbol)
    fund  = fundamental_analysis(symbol)
    risk  = risk_analysis(symbol)
    sent  = sentiment_analysis(symbol)

    if "error" in tech:
        return tech

    score = 50  # baseline neutral

    # Technical signals
    sig = tech.get("signal", "NEUTRAL")
    if sig == "BULLISH":   score += 15
    elif sig == "BEARISH": score -= 15
    elif sig == "OVERBOUGHT": score -= 5

    # Valuation
    pe = fund.get("pe_forward", 0)
    if 0 < pe < 12:   score += 10
    elif pe > 25:     score -= 10
    upside = fund.get("upside_pct", 0)
    if upside > 20:   score += 10
    elif upside < 0:  score -= 10

    # Risk
    rl = risk.get("risk_level", "MEDIUM")
    if rl == "HIGH":   score -= 8
    elif rl == "LOW":  score += 5
    sharpe = risk.get("sharpe_ratio", 0)
    if sharpe > 1.0:   score += 8
    elif sharpe < 0:   score -= 8

    # Sentiment
    consensus = sent.get("analyst_consensus", "")
    if "BUY" in consensus:   score += 10
    elif "SELL" in consensus: score -= 10
    if sent.get("insider_pct", 0) > 10: score += 5

    score = max(0, min(100, score))

    if score >= 75:   verdict = "STRONG BUY"
    elif score >= 60: verdict = "BUY"
    elif score >= 40: verdict = "HOLD"
    elif score >= 25: verdict = "SELL"
    else:             verdict = "STRONG SELL"

    return {
        "symbol":        symbol,
        "composite_score": score,
        "verdict":       verdict,
        "price":         tech.get("price"),
        "analyst_target":fund.get("analyst_target"),
        "upside_pct":    fund.get("upside_pct"),
        "rsi":           tech.get("rsi_14"),
        "signal":        sig,
        "risk_level":    rl,
        "consensus":     sent.get("analyst_consensus"),
        "generated_at":  datetime.now(timezone.utc).isoformat(),
    }


def portfolio_brief(symbols: list[str] = None) -> list[dict]:
    """Run investment thesis on the full watchlist or provided symbols."""
    tickers = symbols or DEFAULT_WATCHLIST
    results = []
    for sym in tickers:
        thesis = investment_thesis(sym)
        results.append(thesis)
    # Sort by composite score descending
    results.sort(key=lambda x: x.get("composite_score", 0), reverse=True)
    return results
