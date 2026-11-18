import json
import math
import os
import time
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

import report
from config import _hours
from engine import Engine
from main import create_app
from packet import parse_packet
from state import State
from test_bot import FakeTG, load, make_cfg, run

DAY = 86_400_000


def engine_with(env: dict, pub=None):
    try:
        cfg = make_cfg("signals", **env)
    finally:
        for k in env:
            os.environ.pop(k, None)
    tg = FakeTG()
    return Engine(cfg, State(cfg.data_dir, cfg.tz), tg, None, pub), tg


def daily(fn, n=40):
    start = int(time.time() * 1000) // DAY * DAY - n * DAY
    return [{"t": start + i * DAY, "o": fn(i), "h": fn(i) + 1, "l": fn(i) - 1, "c": fn(i), "v": 1.0} for i in range(n)]


class PubUp:
    async def klines(self, s, i, l): return daily(lambda k: k * 0.5 + 5 * math.sin(k / 3))


class PubDown:
    async def klines(self, s, i, l): return daily(lambda k: -k * 0.5 + 5 * math.sin(k / 3))


class PubBroken:
    async def klines(self, s, i, l): raise RuntimeError("sin red")


def test_hours_parsing():
    assert _hours("") is None and _hours("13-17") == (13, 17) and _hours("22-6") == (22, 6)
    for bad in ("13", "a-b", "5-5", "25-3"):
        with pytest.raises(ValueError):
            _hours(bad)


def test_trade_hours_filter():
    eng, _ = engine_with({"TRADE_HOURS_UTC": "13-17"})
    ok = run(eng.handle(parse_packet(load("long_entry"))))                      # 15:35Z
    assert ok["decision"] == "TAKE"
    d = load("long_entry"); d["time"] = "2026-11-17T09:05:00Z"
    r = run(eng.handle(parse_packet(d)))
    assert r["decision"] == "SKIP" and any("horario" in x for x in r["reasons"])


def test_weekend_filter():
    eng, _ = engine_with({"SKIP_WEEKENDS": "true"})
    d = load("long_entry"); d["time"] = "2026-11-14T15:35:00Z"                  # sábado
    r = run(eng.handle(parse_packet(d)))
    assert r["decision"] == "SKIP" and any("Fin de semana" in x for x in r["reasons"])


def test_daily_alignment():
    eng, _ = engine_with({}, PubDown())
    r = run(eng.handle(parse_packet(load("long_entry"))))
    assert r["decision"] == "SKIP" and any("diaria bajista" in x for x in r["reasons"])
    eng, _ = engine_with({}, PubUp())
    assert run(eng.handle(parse_packet(load("long_entry"))))["decision"] == "TAKE"
    eng, _ = engine_with({}, PubUp())
    short = run(eng.handle(parse_packet(load("short_entry"))))
    assert short["decision"] == "SKIP" and any("diaria alcista" in x for x in short["reasons"])


def test_daily_check_fails_open_and_can_be_disabled():
    eng, _ = engine_with({}, PubBroken())
    assert run(eng.handle(parse_packet(load("long_entry"))))["decision"] == "TAKE"
    eng, _ = engine_with({"REQUIRE_DAILY_ALIGN": "false"}, PubDown())
    assert run(eng.handle(parse_packet(load("long_entry"))))["decision"] == "TAKE"


def test_report_stats_and_format():
    now = datetime.now(timezone.utc)
    mk = lambda sym, r, st, days_ago: {"symbol": sym, "result_r": r, "closed_status": st, "closed_at": (now - timedelta(days=days_ago)).isoformat()}
    hist = [mk("BTC-USDT", 3.0, "TARGET_HIT", 1), mk("BTC-USDT", -1.0, "STOPPED", 2), mk("ETH-USDT", 0.0, "BREAKEVEN", 3),
            mk("ETH-USDT", 1.5, "TRAIL_STOP", 4), mk("SOL-USDT", -1.0, "STOPPED", 20)]
    week = report.select(hist, 7, now)
    assert len(week) == 4
    st = report.stats(week)
    assert st["trades"] == 4 and st["wins"] == 2 and st["losses"] == 1 and st["breakeven"] == 1
    assert st["win_rate"] == 50.0 and round(st["total_r"], 2) == 3.5 and round(st["profit_factor"], 2) == 4.5
    html = report.format_report(week, 7)
    assert "Win rate" in html and "BTC-USDT" in html and "no es concluyente" in html
    assert "Sin trades" in report.format_report([], 7)


def test_report_endpoint_and_closed_at_saved():
    eng, tg = engine_with({})
    run(eng.handle(parse_packet(load("long_entry"))))
    run(eng.handle(parse_packet(load("target_hit"))))
    assert "closed_at" in eng.state.d["history"][-1]
    with TestClient(create_app(eng)) as c:
        assert c.get("/report").status_code == 401
        r = c.get("/report?secret=s3cret&days=7")
        assert r.status_code == 200 and r.json()["trades"] == 1 and r.json()["total_r"] == 3.0
        assert "INFORME" in tg.sent[-1]
