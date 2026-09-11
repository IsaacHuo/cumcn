"""Matched-state sensitivity runs; no parameter selection from annual costs."""
from solve_q3 import *

def main():
    price,L,P,dates=read_inputs();F=read_forecasts();records=[]
    folder=ROOT/'results/q3/sensitivity';folder.mkdir(parents=True,exist_ok=True)
    for date in ['2025-03-20','2025-06-21','2025-09-23','2025-12-21']:
        baseline=ROOT/'results/q3/main'/f'{date}.npz'
        while not baseline.exists():time.sleep(5)
        with np.load(baseline) as b:
            initial=float(b['soc_kwh'][0]);cost=float(b['total_cost']);em=float(b['emergency_kwh'].sum());end=float(b['soc_kwh'][-1])
        day=dates.index(date)
        for label,count,target in [('14情景',14,6000.),('末端目标4800',7,4800.),('末端目标7200',7,7200.)]:
            path=folder/f'{date}_k{count}_target{int(target)}.npz'
            if not path.exists():
                result=simulate_day(price,L[:day],P[:day],F[:day],zip(L[day],P[day]),lambda h:F[day,h//6],initial,count=count,target=target)
                temporary=path.with_suffix('.tmp.npz');np.savez_compressed(temporary,**result);temporary.replace(path)
            with np.load(path) as r:
                assert not json.loads(str(r['failures_json']))
                current=float(r['total_cost']);last=float(r['soc_kwh'][-1])
                record=dict(date=date,setting=label,count=count,target=target,initial_soc=initial,total_cost=current,
                            cost_difference=current-cost,emergency_total=float(r['emergency_kwh'].sum()),emergency_difference=float(r['emergency_kwh'].sum())-em,
                            final_soc=last,inventory_adjusted_difference=current-cost-float(price.min()/ETA)*(last-end))
                records.append(record);print(json.dumps(record,ensure_ascii=False),flush=True)
            (ROOT/'results/q3/sensitivity.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')

if __name__=='__main__':main()
