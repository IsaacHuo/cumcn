"""Independent physical, causal and settlement checks for Q3 NPZ results."""
import argparse, json, math, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".deps"))
import numpy as np
from openpyxl import load_workbook

N, ETA, CAP, LOW, HIGH = 144, .9, 5000 / 6, 1200., 10800.
TOL = 1e-5

def finite(a): return np.asarray(a).dtype.kind in "fiu" and np.isfinite(a).all()
def scalar(z, key):
    v = float(np.asarray(z[key]).reshape(())); assert math.isfinite(v), key; return v
def js(z, key):
    raw = str(np.asarray(z[key]).reshape(())); return json.loads(raw)

def source_data():
    from solve_q2 import read_inputs
    return read_inputs()

def expected_cost(price, plan, adjusted, emergency, mode):
    up = np.maximum(adjusted - plan, 0); down = np.maximum(plan - adjusted, 0)
    return float(price @ plan + (-.5 if mode == "refund" else .5) * (price @ down) + 1.5 * (price @ up) + 5 * (price @ emergency))

def validate(variant="main", partial=False):
    folder = ROOT / "results" / "q3" / variant
    files = sorted(folder.glob("2025-*.npz")); assert files, f"no files in {folder}"
    if not partial: assert len(files) == 334, f"expected 334 days, got {len(files)}"
    price, loads, pvs, dates = source_data()
    cfg = json.loads((folder / "config.json").read_text(encoding="utf-8"))
    mode = cfg["settlement_mode"]
    seen = []
    prev_soc = None; max_balance = 0.; max_soc_residual = 0.; max_settlement_residual = 0.; recovery_events=[]
    for fn in files:
        with np.load(fn, allow_pickle=False) as z:
            day = int(np.asarray(z["day_index"]).reshape(())); date = str(np.asarray(z["date"]).reshape(())); assert dates[day] == date
            assert fn.stem == date
            plan, adj = z["plan_kwh"], z["adjusted_kwh"]
            assert min(plan.min(),adj.min())>=-TOL
            for key in ("plan_kwh", "adjusted_kwh", "charge_kwh", "discharge_kwh", "emergency_kwh", "unused_kwh", "load_kwh", "pv_kwh"): assert z[key].shape == (N,) and finite(z[key]), key
            soc = z["soc_kwh"]; assert soc.shape == (N + 1,) and finite(soc)
            if prev_soc is not None: assert abs(float(soc[0]) - prev_soc) < TOL, (date, soc[0], prev_soc)
            if prev_soc is None: assert abs(float(soc[0]) - 6000.) < TOL
            prev_soc = float(soc[-1]); seen.append(day)
            assert np.max(np.abs(z["load_kwh"] - loads[day])) < TOL and np.max(np.abs(z["pv_kwh"] - pvs[day])) < TOL
            assert np.all((z["charge_kwh"] >= -TOL) & (z["discharge_kwh"] >= -TOL) & (z["emergency_kwh"] >= -TOL) & (z["unused_kwh"] >= -TOL))
            assert np.all((z["charge_kwh"] <= CAP + TOL) & (z["discharge_kwh"] <= CAP + TOL))
            assert np.all((soc >= LOW - TOL) & (soc <= HIGH + TOL))
            assert np.all(np.minimum(z["charge_kwh"], z["discharge_kwh"]) <= TOL)
            net = z["load_kwh"] - z["pv_kwh"] - adj
            assert np.all(np.where(net > TOL, z["charge_kwh"] <= TOL, True)) and np.all(np.where(net < -TOL, z["discharge_kwh"] <= TOL, True))
            assert np.all(np.where(net < -TOL, z["emergency_kwh"] <= TOL, True)) and np.all(np.where(net <= TOL, z["emergency_kwh"] <= TOL, True))
            balance = adj + z["pv_kwh"] + z["discharge_kwh"] + z["emergency_kwh"] - z["load_kwh"] - z["charge_kwh"] - z["unused_kwh"]
            soc_res = soc[1:] - soc[:-1] - ETA * z["charge_kwh"] + z["discharge_kwh"] / ETA
            max_balance = max(max_balance, float(np.max(np.abs(balance)))); max_soc_residual = max(max_soc_residual, float(np.max(np.abs(soc_res))))
            assert max_balance < TOL, (date, max_balance); assert max_soc_residual < TOL
            pc = float(price @ plan); down = np.maximum(plan-adj, 0); up = np.maximum(adj-plan, 0); ec = float(5 * price @ z["emergency_kwh"])
            assert abs(scalar(z, "plan_cost") - pc) < TOL
            assert abs(scalar(z, "refund") - (float(price @ down) if mode == "refund" else 0.)) < TOL
            assert abs(scalar(z, "penalty") - .5*float(price @ down)) < TOL
            assert abs(scalar(z, "extra_cost") - 1.5*float(price @ up)) < TOL
            assert abs(scalar(z, "increase_total") - up.sum()) < TOL and abs(scalar(z, "decrease_total") - down.sum()) < TOL
            assert abs(scalar(z, "emergency_cost") - ec) < TOL
            expected = expected_cost(price, plan, adj, z["emergency_kwh"], mode); max_settlement_residual = max(max_settlement_residual, abs(scalar(z, "total_cost") - expected)); assert max_settlement_residual < TOL
            assert not js(z, "failures_json")
            recoveries = js(z, "recoveries_json")
            assert all(r['retry_status']=='HighsModelStatus.kOptimal' for r in recoveries)
            recovery_events.extend([{'date':date,**r} for r in recoveries])
            versions = z["plan_versions"]
            assert versions.shape == (4, N)
            bounds = [0, 36, 72, 108, 144]
            assert np.max(abs(versions[0]-plan))<TOL
            for slot in range(4): assert np.max(np.abs(versions[slot, bounds[slot]:bounds[slot+1]] - adj[bounds[slot]:bounds[slot+1]])) < TOL
            for slot in range(1, 4):
                assert np.max(np.abs(versions[slot, :bounds[slot]] - versions[slot-1, :bounds[slot]])) < TOL
                if slot*6 not in cfg['adjustment_hours']:assert np.max(abs(versions[slot]-versions[slot-1]))<TOL
            for revision in js(z,'revisions_json'):
                assert revision['optimal_objective']<=revision['fixed_objective']+TOL
                assert revision['selected_objective']<=revision['fixed_objective']+TOL
                assert revision['changed']==(revision['expected_gain']>.01)
            update_hours = set(cfg["forecast_update_hours"])
            for slot, hour in enumerate((0, 6, 12, 18)):
                has_scene = any(k.startswith(f"sc{slot}_") for k in z.files)
                assert has_scene == (hour == 0 or hour in update_hours)
    assert seen == list(range(31, 365))[:len(seen)]
    out = {"variant": variant, "days": len(files), "full_year": len(files) == 334, "physical_checks": len(files), "settlement_checks": len(files), "cross_day_soc_checks": max(0, len(files)-1), "causal_version_checks": len(files), "fallback_events": [], "successful_cold_restarts": recovery_events, "max_balance_residual": max_balance, "max_soc_residual": max_soc_residual, "max_settlement_residual": max_settlement_residual}
    dest = ROOT / "verification" / "q3"; dest.mkdir(parents=True, exist_ok=True); (dest / f"{variant}_checks.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8"); print(json.dumps(out, ensure_ascii=False)); return out

if __name__ == "__main__":
    p = argparse.ArgumentParser(); p.add_argument("--variant", default="main"); p.add_argument("--partial", action="store_true"); a = p.parse_args(); validate(a.variant, a.partial)
