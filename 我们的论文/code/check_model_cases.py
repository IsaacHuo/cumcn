"""Analytically known cases test signs, losses, curtailment and daily closure."""
from pathlib import Path
import json
from solve_q1 import np,optimize,N

checks=[]
for name,load,pv,expected_cost,expected_curtail in [
    ('flat_price_no_pv',100.,0.,14400.,0.),
    ('pv_exactly_meets_load',100.,100.,0.,0.),
    ('pv_surplus_can_be_curtailed',100.,200.,0.,14400.),
]:
    x,meta=optimize(np.ones(N),np.full(N,load),np.full(N,pv),.9)
    assert abs(x[:N].sum()-expected_cost)<1e-5
    assert abs(x[3*N:4*N].sum()-expected_curtail)<1e-5
    assert np.max(np.abs(x[N:3*N]))<1e-5
    assert np.max(np.abs(x[4*N:]-6000))<1e-5
    checks.append({'case':name,'passed':True})
root=Path(__file__).resolve().parents[1]
(root/'verification/model_cases.json').write_text(json.dumps(checks,indent=2),encoding='utf-8')
print(json.dumps(checks,indent=2))
