"""Short, focused tests for Q3 settlement, interpolation and causal interface."""
import sys, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / ".deps")); sys.path.insert(0, str(ROOT / "code"))
import numpy as np
import solve_q3 as q

class Q3Tests(unittest.TestCase):
    def test_settlement_and_adjustment_arithmetic(self):
        for effective,expected in [(100,100),(80,90),(90,95),(120,130),(0,50)]:
            r=q.settle(np.ones(1),np.array([100.]),np.array([effective]),np.zeros(1))
            self.assertAlmostEqual(r['total_cost'],expected)
        self.assertAlmostEqual(q.settle(np.ones(1),np.array([100.]),np.array([80.]),np.zeros(1),'surcharge')['total_cost'],110)
        p = np.ones(144); original = p.copy(); effective = p.copy(); effective[0] = .8; effective[1] = .9
        r = q.settle(p, original, effective, np.zeros(144))
        self.assertAlmostEqual(r["total_cost"], 144 - .5*.3)

    def test_interpolation_constant_and_linear_first_hour(self):
        self.assertTrue(np.allclose(q.interpolate_energy(np.array([1/3]), np.ones(24)*2), 2/6))
        hourly = np.arange(1, 25, dtype=float); out = q.interpolate_energy(np.array([0.]), hourly)
        self.assertAlmostEqual(out[0], (0 + 1/6) / 12); self.assertAlmostEqual(out[5], (5/6 + 1) / 12)

    def test_midnight_forecast_mapping_and_tail(self):
        load=np.ones((31,144));pv=np.full((31,144),2.)
        hourly=np.arange(1,25)*12.
        fl,fp=q.point_forecast(load,pv,np.ones(108),hourly,18)
        # 18:00 issue: sixth hourly endpoint is midnight, interpolation integral
        # for 23:50--24:00 averages 70 and 72 kW; next-day 00:00--00:10 72 and 74.
        self.assertAlmostEqual(fp[143],71/6)
        self.assertAlmostEqual(fp[144],73/6)
        self.assertTrue(np.array_equal(fp[252:],pv[-1,108:]))

    def test_current_roots_and_cancelled_energy(self):
        sc=dict(load=np.full((2,288),100.),pv=np.zeros((2,288)),prior=np.array([.5,.5]))
        price=np.ones(144)
        for name,soc,load,pv in [('load_surge',6000,1000,0),('pv_drop',6000,100,0),('low',q.LOW,100,0),('full',q.HIGH,0,100)]:
            scenario={**sc,'pv':np.full((2,288),100.)} if name=='pv_drop' else sc
            ctl=q.RevisionLP(price,scenario,soc,0)
            ctl.fix_plan(np.zeros(144));c,d,e,w=ctl.step(0,soc,load,pv,sc['prior'])
            self.assertLess(abs(pv+d+e-load-c-w),1e-5)
            self.assertGreaterEqual(soc+.9*c-d/.9,q.LOW-1e-5)
            self.assertLessEqual(soc+.9*c-d/.9,q.HIGH+1e-5)
            self.assertFalse(c>1e-5 and (d>1e-5 or e>1e-5))
        ctl=q.RevisionLP(price,sc,q.LOW,0)
        # Original purchase 100, delivered purchase 80: cancelled 20 cannot serve load.
        ctl.fix_plan(np.full(144,80.));c,d,e,w=ctl.step(0,q.LOW,100.,0.,sc['prior'])
        self.assertAlmostEqual(e,20.);self.assertAlmostEqual(c,0.)

    def test_zero_error_and_pure_surcharge_dominance(self):
        load=np.full((31,144),100.);pv=np.zeros((31,144));forecasts=np.zeros((31,4,24))
        r=q.simulate_day(np.ones(144),load,pv,forecasts,zip(load[-1],pv[-1]),lambda h:np.zeros(24),6000.)
        self.assertAlmostEqual(r['total_cost'],14400,places=4)
        self.assertLess(r['emergency_kwh'].sum(),1e-5)
        sc=q.make_scenarios(load,pv,forecasts,[],np.zeros(24),0)
        original=np.full(144,200.)
        ctl=q.RevisionLP(np.ones(144),sc,6000.,0,original=original,mode='surcharge')
        revised,record=ctl.revise(original)
        self.assertLess(np.maximum(original-revised,0).sum(),1e-5)

    def test_public_simulate_day_forecast_calls_and_future_causality(self):
        rng = np.random.default_rng(4); price = np.ones(144); hist_l = rng.uniform(4, 8, (31, 144)); hist_p = rng.uniform(0, 2, (31, 144)); hist_f = rng.uniform(0, 2, (31, 4, 24)); meas = list(zip(hist_l[-1], hist_p[-1])); calls=[]
        def f(h): calls.append(h); return hist_f[-1, h//6]
        r1 = q.simulate_day(price, hist_l, hist_p, hist_f, meas, f, q.INITIAL, updates=(6,), adjustments=(6,), count=1)
        calls.clear()
        altered = list(zip(hist_l[-1].copy(), hist_p[-1].copy())); altered[36:] = list(zip(hist_l[-1, 36:] + 20, hist_p[-1, 36:]))
        def f2(h): calls.append(h); return hist_f[-1, h//6] + (100 if h >= 6 else 0)
        r2 = q.simulate_day(price, hist_l, hist_p, hist_f, altered, f2, q.INITIAL, updates=(6,), adjustments=(6,), count=1)
        self.assertEqual(calls, [0, 6]); self.assertTrue(np.allclose(r1["plan_kwh"], r2["plan_kwh"])); self.assertTrue(np.allclose(r1["charge_kwh"][:36], r2["charge_kwh"][:36])); self.assertTrue(np.allclose(r1["discharge_kwh"][:36], r2["discharge_kwh"][:36])); self.assertTrue(np.allclose(r1["emergency_kwh"][:36], r2["emergency_kwh"][:36])); self.assertTrue(np.allclose(r1["unused_kwh"][:36], r2["unused_kwh"][:36])); self.assertTrue(np.allclose(r1["soc_kwh"][:37], r2["soc_kwh"][:37]))

if __name__ == "__main__": unittest.main()
