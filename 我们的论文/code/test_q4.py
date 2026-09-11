"""Necessary pilot, causal information and physical/billing checks."""
from solve_q4 import *
from solve_q2 import HorizonLP,scenarios

def check(r):
    c,d,e,w=[r[k] for k in ['charge_kwh','discharge_kwh','emergency_kwh','unused_kwh']]
    a=r['adjusted_kwh'];soc=r['soc_kwh'];p=r['price_actual']
    assert np.max(abs(a+r['pv_kwh']+d+e-r['load_kwh']-c-w))<TOL
    assert np.max(abs(np.diff(soc)-ETA*c+d/ETA))<TOL
    assert soc.min()>=LOW-TOL and soc.max()<=HIGH+TOL and max(c.max(),d.max())<=CAP+TOL
    assert not np.any((c>TOL)&((d>TOL)|(e>TOL)))
    bill=settle(p,r['plan_kwh'],a,e)
    assert abs(bill['total_cost']-r['total_cost'])<TOL
    assert not json.loads(str(r['failures_json'])),r['failures_json']
    for record in json.loads(str(r['revisions_json'])):assert record['optimal_objective']<=record['fixed_objective']+TOL

def main():
    price,L,P,dates=read_inputs();F=read_forecasts();pr=read_prices();records=[]
    # A constant zero-error price matrix must reproduce the old fixed-price LP.
    sc=scenarios(L[:31],P[:31]);sc.update(price=np.tile(price,(len(sc['prior']),2)),forecast_price=np.tile(price,2))
    old=HorizonLP(price,sc['load'],sc['pv'],sc['prior'],6000);new=PriceLP(sc,6000)
    x=old.solve();y=new.solve();assert abs(old.h.getObjectiveValue()-new.h.getObjectiveValue())<TOL
    # Include a consecutive pair plus four required dates, from existing same-day states.
    for variant in ['q2','main']:
        for date in ['2025-02-01','2025-02-02','2025-03-20','2025-06-21','2025-09-23','2025-12-21']:
            day=dates.index(date);q='q2' if variant=='q2' else 'q3'
            if date.startswith('2025-02'):
                with np.load(ROOT/f'results/q4/pilot_{variant}/{date}.npz') as z:r={k:z[k] for k in z.files}
            else:
                with np.load(ROOT/f'results/{q}/main/{date}.npz') as z:soc=float(z['soc_kwh'][0])
                r=simulate(L[:day],P[:day],F[:day],pr[:day],zip(L[day],P[day],pr[day]),lambda hour:F[day,hour//6],soc,variant)
                np.savez_compressed(ROOT/f'verification/q4/pilot_{variant}_{date}.npz',**r)
            check(r);records.append(dict(variant=variant,date=date,seconds=float(r['elapsed_seconds']),cost=float(r['total_cost'])))
            print(records[-1],flush=True)
    # Perturb prices and unpublished PV forecasts after noon, compare the prefix.
    day=31;changed=pr[day].copy();changed[72:]*=1.7;fc=F[day].copy();fc[2:]*=.3
    original=np.load(ROOT/'results/q4/pilot_main/2025-02-01.npz')
    altered=simulate(L[:day],P[:day],F[:day],pr[:day],zip(L[day],P[day],changed),lambda hour:fc[hour//6],6000,'main')
    for key in ['plan_kwh']:assert np.max(abs(original[key]-altered[key]))<TOL,key
    for key in ['adjusted_kwh','charge_kwh','discharge_kwh','emergency_kwh']:assert np.max(abs(original[key][:72]-altered[key][:72]))<TOL,key
    # Current delivery price used in every settlement component.
    b=settle(np.array([1.,2.]),np.array([100.,100.]),np.array([90.,130.]),np.array([0.,5.]))
    assert abs(b['total_cost']-(95+290+50))<TOL
    result=dict(passed=True,constant_price_equivalence=True,causal_future_price_and_forecast=True,settlement=True,pilots=records)
    (ROOT/'verification/q4/tests.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print('ALL Q4 PILOT CHECKS PASSED',flush=True)

if __name__=='__main__':main()
