"""Matched-start, four-date sensitivity checks; no retuning on evaluation results."""
from solve_q2 import *

def main():
    price,L,P,dates=read_inputs();records=[]
    folder=ROOT/'results/q2/sensitivity';folder.mkdir(exist_ok=True)
    for date in ['2025-03-20','2025-06-21','2025-09-23','2025-12-21']:
        basefile=ROOT/'results/q2/main'/f'{date}.npz'
        while not basefile.exists():time.sleep(2)
        with np.load(basefile) as b:
            initial=float(b['soc_kwh'][0]);basecost=float(b['total_cost']);baseem=float(b['emergency_kwh'].sum());baseend=float(b['soc_kwh'][-1])
        day=dates.index(date)
        for label,count,target in [('14情景',14,6000.),('末端目标4800',7,4800.),('末端目标7200',7,7200.)]:
            path=folder/f'{date}_k{count}_target{int(target)}.npz'
            if not path.exists():
                r=simulate_day(price,L[:day],P[:day],zip(L[day],P[day]),initial,'main',count,target)
                np.savez_compressed(path,**r)
            with np.load(path) as r:
                assert not json.loads(str(r['failures_json']))
                end=float(r['soc_kwh'][-1]);cost=float(r['total_cost'])
                records.append({'date':date,'setting':label,'count':count,'target':target,'initial_soc':initial,'total_cost':cost,'cost_difference':cost-basecost,
                                'emergency_total':float(r['emergency_kwh'].sum()),'emergency_difference':float(r['emergency_kwh'].sum())-baseem,
                                'final_soc':end,'inventory_adjusted_difference':cost-basecost-float(price.min()/ETA)*(end-baseend),
                                'max_balance_error':float(abs(r['plan_kwh']+P[day]+r['discharge_kwh']+r['emergency_kwh']-L[day]-r['charge_kwh']-r['unused_kwh']).max())})
                assert records[-1]['max_balance_error']<TOL
                print(json.dumps(records[-1],ensure_ascii=False),flush=True)
            (ROOT/'results/q2/sensitivity.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')

if __name__=='__main__':main()
