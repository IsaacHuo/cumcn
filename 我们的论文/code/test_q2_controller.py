"""Focused, short tests for the causal Q2 receding-horizon controller.

This is deliberately a runnable verification script rather than a mirror of
the implementation.  It exercises the public LP/controller calls and the two
pilot artifacts; it never runs the year simulation.
"""
from pathlib import Path
import json
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".deps"))
from solve_q2 import (CAP, H, HIGH, LOW, N, TOL, HorizonLP, read_inputs, simulate_day, scenarios)


def _controller(forecast_pv=0.0):
    price = np.linspace(1.0, 2.0, N)
    loads = np.full((2, H), 100.0)
    pvs = np.full((2, H),forecast_pv)
    prior = np.array([.5, .5])
    ctl = HorizonLP(price, loads, pvs, prior, 6000.0, target=6000.0)
    # A zero day-ahead purchase makes the current balance and storage actions
    # visible in the root cases below.
    ctl.fix_plan(np.zeros(N))
    return ctl, price, loads, pvs, prior


def test_information_isolation():
    """The first four actions do not depend on observations after t=3."""
    a, _, _, _, prob = _controller()
    b, _, _, _, _ = _controller()
    first = [(100.0, 0.0)] * 4
    tail_a = [(100.0, 0.0)] * (N - 4)
    tail_b = [(900.0, 0.0)] * (N - 4)
    out_a, out_b = [], []
    soc_a = soc_b = 6000.0
    for t, ((la, pa), (lb, pb)) in enumerate(zip(first + tail_a, first + tail_b)):
        # The calls themselves receive only the current measurement and a
        # posterior based on the completed prefix.
        xa = a.step(t, soc_a, la, pa, prob)
        xb = b.step(t, soc_b, lb, pb, prob)
        if t < 4:
            out_a.append(xa); out_b.append(xb)
        soc_a += .9 * xa[0] - xa[1] / .9
        soc_b += .9 * xb[0] - xb[1] / .9
    assert np.allclose(out_a, out_b, atol=2e-6)
    return {"passed": True, "prefix_intervals": 4}


def test_root_cases():
    """Zero error, PV fall, load rise, and LOW/HIGH supply/demand roots."""
    cases = [
        ("zero_error", 6000.0, 100.0, 0.0),
        ("pv_drop", 6000.0, 100.0, 0.0),
        ("load_surge", 6000.0, 1000.0, 0.0),
        ("low_supply", LOW, 100.0, 0.0),
        ("low_demand", LOW, 0.0, 100.0),
        ("high_supply", HIGH, 100.0, 0.0),
        ("high_demand", HIGH, 0.0, 100.0),
    ]
    records = []
    for name, soc, load, pv in cases:
        ctl, _, _, _, prob = _controller(forecast_pv=100.0 if name=='pv_drop' else 0.0)
        c, d, e, w = ctl.step(0, soc, load, pv, prob)
        assert min(c, d, e, w) >= -TOL
        assert c <= CAP + TOL and d <= CAP + TOL
        assert abs(pv + d + e - load - c - w) < TOL
        assert not (c > TOL and (d > TOL or e > TOL))
        next_soc = soc + .9 * c - d / .9
        assert LOW - TOL <= next_soc <= HIGH + TOL
        records.append({"case": name, "passed": True,
                        "action": [float(c), float(d), float(e), float(w)]})
    return records


def test_crossday_pilots():
    files = sorted((ROOT / "results" / "q2" / "pilot").glob("*.npz"))
    assert len(files) >= 2
    price, _, _, _ = read_inputs()
    checks = []
    previous_end = None
    for path in files[:2]:
        with np.load(path, allow_pickle=False) as r:
            day = int(r["day_index"])
            soc = r["soc_kwh"]; plan = r["plan_kwh"]
            load = r["load_kwh"]; pv = r["pv_kwh"]
            c, d, e, w = (r[k] for k in ("charge_kwh", "discharge_kwh", "emergency_kwh", "unused_kwh"))
            assert len(soc) == N + 1 and all(len(x) == N for x in (plan, load, pv, c, d, e, w))
            assert all(np.isfinite(x).all() for x in (soc, plan, load, pv, c, d, e, w))
            assert np.allclose(plan + pv + d + e, load + c + w, atol=TOL)
            assert np.all((c >= -TOL) & (d >= -TOL) & (e >= -TOL) & (w >= -TOL))
            assert abs(float(r["plan_cost"]) - float(np.dot(price, plan))) < 1e-4
            assert abs(float(r["total_cost"]) - float(r["plan_cost"] + r["emergency_cost"])) < 1e-4
            origins = r["scenario_origins"]; pool = r["pool_origins"]
            assert np.all(origins + 1 < day) and np.all(pool + 1 < day)
            if previous_end is not None:
                assert abs(float(soc[0]) - previous_end) < TOL
            previous_end = float(soc[-1])
            checks.append({"file": path.name, "passed": True, "day_index": day})
    return checks


def main():
    history_load=np.full((31,N),100.0);history_pv=np.zeros((31,N))
    zero=simulate_day(np.ones(N),history_load,history_pv,zip(np.full(N,100.),np.zeros(N)),6000.)
    assert zero['emergency_kwh'].sum()<TOL and abs(zero['total_cost']-14400)<TOL
    price,L,P,_=read_inputs()
    altered_l=L.copy();altered_p=P.copy();altered_l[31:]*=3;altered_p[31:]=0
    a=scenarios(L[:31],P[:31]);b=scenarios(altered_l[:31],altered_p[:31])
    assert all(np.array_equal(a[k],b[k]) for k in a)
    plans=[]
    for s in [a,b]:
        planner=HorizonLP(price,s['load'],s['pv'],s['prior'],6000.)
        plans.append(planner.solve()[:N])
    assert np.array_equal(plans[0],plans[1])
    result = {"information_isolation": test_information_isolation(),
              "root_cases": test_root_cases(), "crossday_pilots": test_crossday_pilots(),
              "zero_error_closed_loop": {"passed":True,"emergency_kwh":float(zero['emergency_kwh'].sum())},
              "future_mutation_day_ahead_plan_unchanged":True}
    out = ROOT / "verification" / "q2" / "controller_tests.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
