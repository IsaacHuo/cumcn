"""Recheck independent-date experiments directly against original observations."""
from solve_q3 import ROOT,read_inputs,np,json,ETA,LOW,HIGH,CAP,TOL
from validate_q3 import expected_cost

price,L,P,dates=read_inputs();records=[]
for path in sorted((ROOT/'results/q3/sensitivity').glob('2025-*.npz')):
    date=path.name[:10];day=dates.index(date)
    with np.load(path) as r,np.load(ROOT/'results/q3/main'/f'{date}.npz') as b:
        assert abs(float(r['soc_kwh'][0])-float(b['soc_kwh'][0]))<TOL
        assert np.array_equal(r['load_kwh'],L[day]) and np.array_equal(r['pv_kwh'],P[day])
        a=r['adjusted_kwh'];c=r['charge_kwh'];d=r['discharge_kwh'];e=r['emergency_kwh'];w=r['unused_kwh'];s=r['soc_kwh']
        balance=float(np.max(abs(a+P[day]+d+e-L[day]-c-w)))
        state=float(np.max(abs(s[1:]-s[:-1]-ETA*c+d/ETA)))
        cost=expected_cost(price,r['plan_kwh'],a,e,'refund')
        assert max(balance,state,abs(cost-float(r['total_cost'])))<TOL
        assert min(a.min(),c.min(),d.min(),e.min(),w.min())>=-TOL
        assert LOW-TOL<=s.min() and s.max()<=HIGH+TOL and max(c.max(),d.max())<=CAP+TOL
        assert not np.any((c>TOL)&((d>TOL)|(e>TOL)))
        assert not json.loads(str(r['failures_json']))
        records.append(dict(file=path.name,passed=True,balance_residual=balance,soc_residual=state,cost=cost))
assert len(records)==12
(ROOT/'verification/q3/sensitivity_checks.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
print('Validated 12 matched-state sensitivity runs.')
