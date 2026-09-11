"""Eight same-start experiments with power AND energy reserve constraints."""
import solve_q2 as q2
import solve_q3 as q3
from solve_q4 import *
from forecast_diagnostics import tex

def reserve_pool(hl,hp,hf=None,prefix=None,hourly=None,hour=0):
    day=len(hl);origins=np.arange(max(7,day-29),day-1);errors=[]
    for j in origins:
        fl,fp=forecast(hl[:j],hp[:j]) if hf is None else point_forecast(hl[:j],hp[:j],hp[j,:hour*6],hf[j,hour//6],hour)
        errors.append((hl[j:j+2].ravel()-fl)-(hp[j:j+2].ravel()-fp))
    raw=np.maximum(np.quantile(errors,.8,axis=0),0)
    return np.minimum(raw,CAP),raw

class ReserveMixin:
    reserve=np.zeros(H)
    def apply_reserve(self,start):
        ids=[];lower=[];upper=[]
        for s in range(self.S):
            b=self.base(s)
            for t in range(start,H):
                ids.append(b+H+t);lower.append(0.);upper.append(CAP-self.reserve[t])
                # Inventory retained at the END of each future interval.
                if t+1<H:
                    ids.append(b+4*H+t+1);lower.append(LOW+self.reserve[t]/ETA);upper.append(HIGH)
                else:assert self.target>=LOW+self.reserve[t]/ETA
        self.h.changeColsBounds(len(ids),np.asarray(ids,np.int32),np.asarray(lower),np.asarray(upper))

    def release_current(self,t):
        ids=[];lo=[];hi=[]
        for s in range(self.S):
            b=self.base(s)
            ids.extend([b+H+t,b+4*H+t+1]);lo.extend([0,LOW]);hi.extend([CAP,HIGH])
        self.h.changeColsBounds(len(ids),np.asarray(ids,np.int32),np.asarray(lo,float),np.asarray(hi,float))

    def step(self,t,soc,load,pv,prob):
        self.release_current(t)
        return super().step(t,soc,load,pv,prob)

def main():
    price,L,P,dates=read_inputs();F=read_forecasts();folder=ROOT/'results/reserve_verified';folder.mkdir(exist_ok=True)
    rows=[];records=[];lam=float(price.min()/ETA)
    old_h=q2.HorizonLP;old_r=q3.RevisionLP;old_s=q3.make_scenarios
    for question in ['q2','q3']:
        for date in ['2025-03-20','2025-06-21','2025-09-23','2025-12-21']:
            day=dates.index(date)
            with np.load(ROOT/f'results/{question}/main/{date}.npz') as z:
                initial=float(z['soc_kwh'][0]);basecost=float(z['total_cost']);baseem=float(z['emergency_kwh'].sum());baseend=float(z['soc_kwh'][-1])
            pools={}
            if question=='q2':
                reserve,raw=reserve_pool(L[:day],P[:day]);pools[0]=(reserve,raw)
                class ReservedHorizon(ReserveMixin,old_h):
                    def __init__(self,*a,**kw):
                        super().__init__(*a,**kw);self.reserve=reserve;self.apply_reserve(0)
                q2.HorizonLP=ReservedHorizon
            else:
                def make(*a,**kw):
                    s=old_s(*a,**kw);hour=a[5] if len(a)>5 else kw['hour']
                    reserve,raw=reserve_pool(L[:day],P[:day],F[:day],hour=hour);s['reserve_kwh']=reserve;s['reserve_raw_kwh']=raw;pools[hour]=(reserve,raw);return s
                class ReservedRevision(ReserveMixin,old_r):
                    def __init__(self,price,sc,soc,start,**kw):
                        super().__init__(price,sc,soc,start,**kw);self.reserve=sc['reserve_kwh'];self.apply_reserve(start)
                q3.make_scenarios=make;q3.RevisionLP=ReservedRevision
            try:
                if question=='q2':r=q2.simulate_day(price,L[:day],P[:day],zip(L[day],P[day]),initial)
                else:r=q3.simulate_day(price,L[:day],P[:day],F[:day],zip(L[day],P[day]),lambda h:F[day,h//6],initial)
            finally:q2.HorizonLP=old_h;q3.RevisionLP=old_r;q3.make_scenarios=old_s
            assert not json.loads(r['failures_json']),r['failures_json']
            for h,(rv,raw) in pools.items():r[f'reserve_{h}']=rv;r[f'reserve_raw_{h}']=raw
            np.savez_compressed(folder/f'{question}_{date}.npz',**r)
            cost=float(r['total_cost']);em=float(r['emergency_kwh'].sum());end=float(r['soc_kwh'][-1])
            record=dict(question=question,date=date,initial_soc=initial,base_cost=basecost,total_cost=cost,cost_difference=cost-basecost,
                        base_emergency=baseem,emergency_total=em,emergency_difference=em-baseem,base_end=baseend,final_soc=end,
                        adjusted_cost_difference=cost-basecost-lam*(end-baseend),excess_reserve_targets=sum(int((raw>CAP).sum()) for _,raw in pools.values()),failures=0)
            records.append(record);print(record,flush=True)
            rows.append([question.upper(),date[5:]]+[f'{record[k]:.2f}' for k in ['cost_difference','emergency_difference','final_soc','adjusted_cost_difference']])
    (folder/'report.json').write_text(json.dumps(dict(runs=records,quantile=.8,unit='kWh',power_cap=CAP,inventory_price=lam),ensure_ascii=False,indent=2),encoding='utf-8')
    (ROOT/'paper/tables/reserve_comparison.tex').write_text(tex(['问题','日期','费用变化/元','紧急量变化','日末电量','库存校正费用变化'],rows,align='llrrrr'),encoding='utf-8')

if __name__=='__main__':main()
