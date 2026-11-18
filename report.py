"""Informe de resultados (win rate, R medio, factor de beneficio, por moneda) para Telegram."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from html import escape as esc
from typing import Optional


def _parse(ts: str) -> Optional[datetime]:
    try:
        return datetime.fromisoformat(ts)
    except (ValueError, TypeError):
        return None


def select(history: list[dict], days: int, now: Optional[datetime] = None) -> list[dict]:
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=days)
    out = []
    for t in history:
        ts = _parse(t.get("closed_at", ""))
        if ts and ts >= cutoff:
            out.append(t)
    return out


def stats(trades: list[dict]) -> dict:
    rs = [t["result_r"] for t in trades if "result_r" in t]
    wins = [r for r in rs if r > 0.05]
    losses = [r for r in rs if r < -0.05]
    by_symbol: dict[str, list[float]] = {}
    by_exit: dict[str, int] = {}
    for t in trades:
        if "result_r" in t:
            by_symbol.setdefault(t["symbol"], []).append(t["result_r"])
            by_exit[t.get("closed_status", "?")] = by_exit.get(t.get("closed_status", "?"), 0) + 1
    gross_loss = abs(sum(losses))
    return {
        "trades": len(rs),
        "wins": len(wins),
        "losses": len(losses),
        "breakeven": len(rs) - len(wins) - len(losses),
        "win_rate": (len(wins) / len(rs) * 100) if rs else None,
        "avg_r": (sum(rs) / len(rs)) if rs else None,
        "total_r": sum(rs),
        "profit_factor": (sum(wins) / gross_loss) if gross_loss > 0 else None,
        "best": max(rs) if rs else None,
        "worst": min(rs) if rs else None,
        "by_symbol": {k: {"n": len(v), "r": round(sum(v), 2)} for k, v in by_symbol.items()},
        "by_exit": by_exit,
    }


def format_report(trades: list[dict], days: int) -> str:
    st = stats(trades)
    head = f"📊 <b>INFORME · últimos {days} días</b>"
    if st["trades"] == 0:
        return f"{head}\n\nSin trades cerrados en este periodo."
    pf = f"{st['profit_factor']:.2f}" if st["profit_factor"] is not None else "n/d (sin pérdidas)"
    lines = [
        head, "",
        f"Trades: <b>{st['trades']}</b> · ganados {st['wins']} · perdidos {st['losses']} · breakeven {st['breakeven']}",
        f"Win rate: <b>{st['win_rate']:.0f}%</b> · R medio: <b>{st['avg_r']:+.2f}</b> · R total: <b>{st['total_r']:+.2f}</b>",
        f"Factor de beneficio: {pf} · mejor {st['best']:+.2f}R · peor {st['worst']:+.2f}R",
        "", "<b>Por moneda</b>",
    ]
    for sym, d in sorted(st["by_symbol"].items(), key=lambda kv: -kv[1]["r"]):
        lines.append(f"{esc(sym)}: {d['n']} trades · {d['r']:+.2f}R")
    lines += ["", "<b>Salidas</b>: " + " · ".join(f"{esc(k)} {v}" for k, v in sorted(st["by_exit"].items()))]
    if st["trades"] < 30:
        lines += ["", f"⚠ Con {st['trades']} trades el resultado no es concluyente (mínimo recomendable: 50–100)."]
    lines.append("R estimado a partir de los paquetes del indicador, no del PnL real del exchange.")
    return "\n".join(lines)
