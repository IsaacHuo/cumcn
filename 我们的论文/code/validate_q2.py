"""Reconstruct every executed energy flow from exports and original observations."""
from solve_q2 import ROOT,read_inputs,np,json,hashlib,N,LOW,HIGH,CAP,ETA,INITIAL,TOL
import argparse

def check(variant,require_complete=True):
    price,L,P,dates=read_inputs();folder=ROOT/'results/q2'/variant
    files=sorted(folder.glob('2025-*.npz'))
    if require_complete:assert len(files)==334,(variant,len(files))
    previous=INITIAL;max_balance=max_soc=max_bound=max_fee=0.;expected_dates=dates[31:31+len(files)]
    total_cost=emergency_total=unused_total=0.;failed=[]
    for file,date in zip(files,expected_dates):
        assert file.stem==date
        with np.load(file) as r:
            day=dates.index(date);g=r['plan_kwh'];c=r['charge_kwh'];d=r['discharge_kwh'];e=r['emergency_kwh'];w=r['unused_kwh'];soc=r['soc_kwh']
            assert g.shape==(144,) and soc.shape==(145,)
            assert all(np.isfinite(a).all() for a in [g,c,d,e,w,soc])
            assert np.array_equal(r['load_kwh'],L[day]) and np.array_equal(r['pv_kwh'],P[day])
            # Exact historical forecast identities, evaluated directly from source arrays.
            assert np.array_equal(r['forecast_load_kwh'],L[day-7])
            assert np.array_equal(r['forecast_pv_kwh'],P[day-1])
            assert np.all(r['pool_origins']+1<day)
            assert np.all(r['scenario_origins']+1<day)
            assert np.min(r['weights'])>=0 and np.max(abs(r['weights'].sum(1)-1))<1e-10
            assert abs(soc[0]-previous)<TOL
            physical=g+P[day]+d+e-L[day]-c-w
            reconstructed=previous+np.r_[0,np.cumsum(ETA*c-d/ETA)]
            max_balance=max(max_balance,float(abs(physical).max()));max_soc=max(max_soc,float(abs(soc-reconstructed).max()))
            max_bound=max(max_bound,float(max(0,-min(g.min(),c.min(),d.min(),e.min(),w.min()),c.max()-CAP,d.max()-CAP,LOW-soc.min(),soc.max()-HIGH)))
            assert not np.any((c>TOL)&((d>TOL)|(e>TOL)))
            net=L[day]-P[day]-g
            assert np.max(c[net>=0],initial=0)<TOL and np.max(d[net<0],initial=0)<TOL and np.max(e[net<0],initial=0)<TOL
            pc=float(price@g);ec=float((5*price)@e)
            max_fee=max(max_fee,abs(pc-float(r['plan_cost'])),abs(ec-float(r['emergency_cost'])),abs(pc+ec-float(r['total_cost'])))
            failed.extend([{'date':date,**item} for item in json.loads(str(r['failures_json']))])
            previous=float(soc[-1]);total_cost+=pc+ec;emergency_total+=e.sum();unused_total+=w.sum()
    report={'variant':variant,'days':len(files),'max_energy_balance_error_kwh':max_balance,'max_reconstructed_soc_error_kwh':max_soc,'max_bound_violation_kwh':max_bound,
            'max_accounting_error_yuan':max_fee,'final_soc':previous,'total_cost':total_cost,'emergency_total':float(emergency_total),'unused_total':float(unused_total),'fallback_events':failed,'passed':True}
    assert max(max_balance,max_soc,max_bound,max_fee)<TOL
    assert not failed,failed
    if require_complete:(ROOT/'verification/q2'/f'{variant}_checks.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2));return report

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--variant',default='main');p.add_argument('--partial',action='store_true');a=p.parse_args();check(a.variant,not a.partial)
