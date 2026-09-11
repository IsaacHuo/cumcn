"""Q3 causal forecasts, final-quantity settlement and receding-horizon control.

All energy variables are microgrid-side kWh. Future recourse is a look-ahead
relaxation; only the shared current action is implemented.
"""
from solve_q2 import (ROOT,read_inputs,np,json,hashlib,time,csv,argparse,datetime,
                      HorizonLP,N,H,ETA,CAP,LOW,HIGH,INITIAL,TOL,fallback,highspy)
from pathlib import Path
from openpyxl import load_workbook

FORECAST_FILE=ROOT/'data/raw/附件3.xlsx'
VARIANTS={
    'main':((6,12,18),(6,12,18),'refund','6、12、18点调整'),
    'forecast0':((),(),'refund','仅0点预报'),
    'h6':((6,),(6,),'refund','6点调整'),
    'h12':((12,),(12,),'refund','12点调整'),
    'h18':((18,),(18,),'refund','18点调整'),
    'h6_12':((6,12),(6,12),'refund','6、12点调整'),
    'h6_18':((6,18),(6,18),'refund','6、18点调整'),
    'h12_18':((12,18),(12,18),'refund','12、18点调整'),
    'info_only':((6,12,18),(),'refund','全预报仅调储能'),
    'literal_all':((6,12,18),(6,12,18),'surcharge','原计划照付口径'),
}

def read_forecasts():
    wb=load_workbook(FORECAST_FILE,read_only=True,data_only=True)
    rows=list(wb.active.values);wb.close()
    assert len(rows)==1461 and len(rows[0])==26
    result=np.zeros((365,4,24));last=None
    for k,row in enumerate(rows[1:]):
        if row[0]:last=datetime.date.fromisoformat('-'.join(f'{int(x):02d}' if i else x for i,x in enumerate(row[0].split('-'))))
        day,slot=divmod(k,4)
        assert last==datetime.date(2025,1,1)+datetime.timedelta(days=day)
        assert row[1]==f'{slot*6}:00'
        assert all(isinstance(x,(int,float)) for x in row[2:])
        result[day,slot]=row[2:]
    assert np.isfinite(result).all() and (result>=0).all()
    return result

def interpolate_energy(anchor_kwh,hourly_kw):
    """Exact ten-minute integral of a piecewise-linear hourly power curve."""
    boundaries=np.interp(np.arange(N+1)/6,np.arange(25),np.r_[anchor_kwh*6,hourly_kw])
    return (boundaries[:-1]+boundaries[1:])/12

def point_forecast(history_load,history_pv,prefix_pv,hourly_kw,hour):
    start=hour*6
    fl=np.r_[history_load[-7],history_load[-6]]
    fp=np.tile(history_pv[-1],2)
    anchor=prefix_pv[-1] if start else history_pv[-1,-1]
    assert len(prefix_pv)==start
    fp[start:start+N]=interpolate_energy(anchor,hourly_kw)
    return fl,fp

def make_scenarios(history_load,history_pv,history_forecasts,prefix_pv,hourly_kw,hour,count=7):
    day=len(history_load);start=hour*6
    assert len(history_pv)==day and len(history_forecasts)==day
    fl,fp=point_forecast(history_load,history_pv,prefix_pv,hourly_kw,hour)
    origins=np.arange(max(7,day-29),day-1)
    el=[];ep=[]
    for j in origins:
        a,b=point_forecast(history_load[:j],history_pv[:j],history_pv[j,:start],history_forecasts[j,hour//6],hour)
        el.append(history_load[j:j+2].reshape(-1)-a)
        ep.append(history_pv[j:j+2].reshape(-1)-b)
    el=np.array(el);ep=np.array(ep)
    sl=np.maximum(el.std(0),1/6);sp=np.maximum(ep.std(0),1/6)
    features=np.c_[el[:,start:]/sl[start:],ep[:,start:]/sp[start:]]
    distance=np.mean((features[:,None,:]-features[None,:,:])**2,axis=2)
    k=min(count,len(origins));net=(el[:,start:]-ep[:,start:]).sum(1)
    medoids=list(dict.fromkeys([int(np.argmin(net)),int(np.argmax(net))]))[:k]
    while len(medoids)<k:
        nearest=distance[:,medoids].min(1);nearest[medoids]=-1
        medoids.append(int(np.argmax(nearest)))
    for _ in range(10):
        assignment=np.argmin(distance[:,medoids],axis=1);new=list(medoids)
        for s in range(2,k):
            members=np.flatnonzero(assignment==s)
            if len(members):new[s]=int(members[np.argmin(distance[np.ix_(members,members)].sum(1))])
        if new==medoids:break
        medoids=new
    assignment=np.argmin(distance[:,medoids],axis=1)
    prior=np.bincount(assignment,minlength=k)/len(origins)
    keep=prior>0;ix=np.array(medoids)[keep];prior=prior[keep]
    return dict(load=np.maximum(fl+el[ix],0),pv=np.maximum(fp+ep[ix],0),prior=prior,
                forecast_load=fl,forecast_pv=fp,error_load=el[ix],error_pv=ep[ix],
                scale_load=sl,scale_pv=sp,origins=origins[ix],pool_origins=origins,
                hourly_kw=np.array(hourly_kw),anchor_kwh=float(prefix_pv[-1] if start else history_pv[-1,-1]))

def update_weights(sc,loads,pvs,start):
    stop=start+len(loads)
    l=(np.asarray(loads)-sc['forecast_load'][start:stop]-sc['error_load'][:,start:stop])/sc['scale_load'][start:stop]
    p=(np.asarray(pvs)-sc['forecast_pv'][start:stop]-sc['error_pv'][:,start:stop])/sc['scale_pv'][start:stop]
    distance=.5*np.mean(l*l+p*p,axis=1)
    logits=np.log(sc['prior'])-.5*distance;w=np.exp(logits-logits.max());w/=w.sum()
    return .95*w+.05*sc['prior']

def settle(price,original,effective,emergency,mode='refund'):
    up=np.maximum(effective-original,0);down=np.maximum(original-effective,0)
    pc=float(price@original);refund=float(price@down) if mode=='refund' else 0.
    penalty=float(.5*price@down);extra=float(1.5*price@up);ec=float(5*price@emergency)
    return dict(plan_cost=pc,refund=refund,penalty=penalty,extra_cost=extra,emergency_cost=ec,
                total_cost=pc-refund+penalty+extra+ec,increase_total=float(up.sum()),decrease_total=float(down.sum()))

class RevisionLP(HorizonLP):
    def __init__(self,price,sc,soc,start,original=None,mode='refund',target=6000.):
        super().__init__(price,sc['load'],sc['pv'],sc['prior'],soc,target)
        self.start=start;self.original=original;self.mode=mode
        self.retire_prefix(start,soc)
        self.t=start-1
        if original is not None:
            n=N-start;offset=self.h.getNumCol();self.up=offset;self.down=offset+n;self.delta=offset+2*n
            costs=np.r_[1.5*price[start:],(-.5 if mode=='refund' else .5)*price[start:],np.zeros(n)]
            self.h.addCols(3*n,costs,np.zeros(3*n),np.full(3*n,np.inf),0,np.zeros(3*n+1,np.int32),np.array([],np.int32),np.array([]))
            ids=np.arange(N,dtype=np.int32);self.h.changeColsCost(N,ids,np.zeros(N))
            for j,t in enumerate(range(start,N)):
                self.h.addRow(float(original[t]),float(original[t]),3,np.array([t,self.up+j,self.down+j],np.int32),np.array([1.,-1.,1.]))
            self.revision_count=n

    def retire_prefix(self,start,soc):
        if not start:return
        columns=[];rows=[]
        for s in range(self.S):
            b=self.base(s)
            columns.extend(b+kind*H+t for kind in range(4) for t in range(start))
            rows.extend(int(table[s,t]) for table in [self.balance,self.state,self.spill] for t in range(start))
            i=np.array([b+4*H+start],np.int32)
            self.h.changeColsBounds(1,i,np.array([soc]),np.array([soc]))
        self.h.changeColsBounds(len(columns),np.array(columns,np.int32),np.zeros(len(columns)),np.zeros(len(columns)))
        self.h.changeRowsBounds(len(rows),np.array(rows,np.int32),np.full(len(rows),-np.inf),np.full(len(rows),np.inf))

    def revise(self,current):
        """Compare the same LP with and without changing the remaining commitment."""
        self.fix_plan(current)
        fixed=self.solve();fixed_cost=float(self.h.getObjectiveValue())
        ids=np.arange(self.start,N,dtype=np.int32)
        self.h.changeColsBounds(len(ids),ids,np.zeros(len(ids)),np.full(len(ids),np.inf))
        optimum=self.solve();optimal_cost=float(self.h.getObjectiveValue())
        assert optimal_cost<=fixed_cost+TOL,(optimal_cost,fixed_cost)
        gain=fixed_cost-optimal_cost
        if gain<=.01:
            answer=np.array(current);selected_cost=fixed_cost
        else:
            # Lexicographic tie-break: minimize change within a micro-yuan of optimum.
            original_cost=np.array(self.h.getLp().col_cost_);ncols=len(original_cost)
            costrow=self.h.getNumRow();nonzero=np.flatnonzero(original_cost).astype(np.int32)
            self.h.addRow(-np.inf,optimal_cost+1e-6,len(nonzero),nonzero,original_cost[nonzero])
            for j,t in enumerate(ids):
                self.h.addRow(-np.inf,float(current[t]),2,np.array([t,self.delta+j],np.int32),np.array([1.,-1.]))
                self.h.addRow(-np.inf,float(-current[t]),2,np.array([t,self.delta+j],np.int32),np.array([-1.,-1.]))
            tiecost=np.zeros(ncols);tiecost[self.delta:self.delta+self.revision_count]=1
            allids=np.arange(ncols,dtype=np.int32);self.h.changeColsCost(ncols,allids,tiecost)
            optimum=self.solve();selected_cost=float(original_cost@optimum)
            answer=np.array(current);answer[self.start:]=np.maximum(optimum[self.start:N],0)
            self.h.changeColsCost(ncols,allids,original_cost)
            self.h.changeRowBounds(costrow,-np.inf,np.inf)
            assert selected_cost<=optimal_cost+2e-6
        self.fix_plan(answer)
        return answer,dict(interval=self.start,fixed_objective=fixed_cost,optimal_objective=optimal_cost,
                           selected_objective=selected_cost,expected_gain=gain,changed=bool(gain>.01))

def simulate_day(price,history_load,history_pv,history_forecasts,measurements,forecast_at,soc,
                 updates=(6,12,18),adjustments=(6,12,18),mode='refund',count=7,target=6000.):
    start_time=time.perf_counter();ol=[];op=[];scenes={};weights={};failures=[];recoveries=[];revisions=[]
    base_sc=make_scenarios(history_load,history_pv,history_forecasts,[],forecast_at(0),0,count)
    ctl=RevisionLP(price,base_sc,soc,0,target=target)
    initial=ctl.solve();original=np.maximum(initial[:N],0);active=original.copy();ctl.fix_plan(active)
    expected_em=sum(float(5*price@initial[ctl.base(s)+2*H:ctl.base(s)+2*H+N])*p for s,p in enumerate(base_sc['prior']))
    plan_versions=np.tile(original,(4,1));pv_versions=np.full((4,N),np.nan);pv_versions[0]=base_sc['forecast_pv'][:N]
    scenes[0]=base_sc;weights[0]=[];sc=base_sc;stage=0;stage_start=0
    soc_values=[soc];actions=[];effective=[];seconds=[]
    for t,(load,pv) in enumerate(measurements):
        assert t<N
        if t in [36,72,108]:
            hour=t//6;slot=hour//6
            plan_versions[slot]=active
            if hour in updates:
                recoveries.extend([{'stage':stage,**v} for v in ctl.recoveries])
                sc=make_scenarios(history_load,history_pv,history_forecasts,op,forecast_at(hour),hour,count)
                scenes[slot]=sc;weights[slot]=[];stage=slot;stage_start=t
                pv_versions[slot,t:]=sc['forecast_pv'][t:N]
                ctl=RevisionLP(price,sc,soc,t,original=original,mode=mode,target=target)
                if hour in adjustments:
                    try:
                        active,record=ctl.revise(active);revisions.append(record)
                    except RuntimeError as exc:
                        failures.append({'kind':'revision','interval':t,'status':str(exc)})
                        ctl=RevisionLP(price,sc,soc,t,original=original,mode=mode,target=target)
                        ctl.fix_plan(active)
                else:ctl.fix_plan(active)
                plan_versions[slot]=active
        ol.append(float(load));op.append(float(pv))
        prob=update_weights(sc,ol[stage_start:],op[stage_start:],stage_start);weights[stage].append(prob)
        tick=time.perf_counter()
        try:c,d,e,w=ctl.step(t,soc,float(load),float(pv),prob)
        except RuntimeError as exc:
            failures.append({'kind':'execution','interval':t,'status':str(exc)})
            c,d,e,w=fallback(soc,load-pv-active[t])
        seconds.append(time.perf_counter()-tick)
        c,d,e,w=[max(0,float(x)) for x in [c,d,e,w]]
        nextsoc=soc+ETA*c-d/ETA
        assert abs(active[t]+pv+d+e-load-c-w)<TOL
        assert LOW-TOL<=nextsoc<=HIGH+TOL and max(c,d)<=CAP+TOL
        assert not(c>TOL and (d>TOL or e>TOL))
        soc=float(np.clip(nextsoc,LOW,HIGH));soc_values.append(soc);actions.append([c,d,e,w]);effective.append(active[t])
    assert len(actions)==N
    recoveries.extend([{'stage':stage,**v} for v in ctl.recoveries])
    a=np.array(actions);effective=np.array(effective)
    result=dict(plan_kwh=original,adjusted_kwh=effective,plan_versions=plan_versions,forecast_pv_versions=pv_versions,
                forecast_load_kwh=base_sc['forecast_load'][:N],soc_kwh=np.array(soc_values),load_kwh=np.array(ol),pv_kwh=np.array(op),
                solve_seconds=np.array(seconds),expected_emergency_cost=expected_em,failures_json=json.dumps(failures),
                recoveries_json=json.dumps(recoveries),revisions_json=json.dumps(revisions),elapsed_seconds=time.perf_counter()-start_time)
    for i,name in enumerate(['charge_kwh','discharge_kwh','emergency_kwh','unused_kwh']):result[name]=a[:,i]
    result.update(settle(price,original,effective,a[:,2],mode))
    for slot,s in scenes.items():
        for key,value in s.items():result[f'sc{slot}_{key}']=value
        result[f'sc{slot}_weights']=np.array(weights[slot])
    return result

def configuration(variant,count,target):
    upd,adj,mode,_=VARIANTS[variant]
    sources=[Path(__file__),ROOT/'code/solve_q2.py',FORECAST_FILE,ROOT/'data/raw/附件1.xlsx',ROOT/'data/raw/附件2.xlsx']
    return dict(version=1,variant=variant,forecast_update_hours=list(upd),adjustment_hours=list(adj),settlement_mode=mode,
                scenario_count=count,target=target,history_pairs=28,prior_mix=.05,min_adjustment_gain_yuan=.01,
                highspy=highspy.Highs().version(),sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources})

def run(variant='main',count=7,target=6000.,end=365,tag=None):
    price,L,P,dates=read_inputs();F=read_forecasts();upd,adj,mode,_=VARIANTS[variant]
    folder=ROOT/'results/q3'/(tag or variant);folder.mkdir(parents=True,exist_ok=True)
    cfg=configuration(variant,count,target);path=folder/'config.json'
    if path.exists():assert json.loads(path.read_text(encoding='utf-8'))==cfg,'Changed configuration; use a new tag.'
    else:path.write_text(json.dumps(cfg,ensure_ascii=False,indent=2),encoding='utf-8')
    soc=INITIAL
    for day in range(31,end):
        file=folder/f'{dates[day]}.npz'
        if file.exists():
            with np.load(file) as r:
                assert abs(float(r['soc_kwh'][0])-soc)<TOL
                soc=float(r['soc_kwh'][-1])
            continue
        r=simulate_day(price,L[:day],P[:day],F[:day],zip(L[day],P[day]),lambda hour:F[day,hour//6],soc,upd,adj,mode,count,target)
        r['day_index']=day;r['date']=dates[day]
        temp=file.with_suffix('.tmp.npz');np.savez_compressed(temp,**r);temp.replace(file)
        soc=float(r['soc_kwh'][-1])
        print(json.dumps(dict(variant=tag or variant,date=dates[day],cost=round(r['total_cost'],2),
                             emergency=round(float(r['emergency_kwh'].sum()),2),seconds=round(r['elapsed_seconds'],2),
                             failures=len(json.loads(r['failures_json'])))),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--variant',choices=list(VARIANTS),default='main');p.add_argument('--count',type=int,default=7)
    p.add_argument('--target',type=float,default=6000.);p.add_argument('--end',type=int,default=365);p.add_argument('--tag')
    a=p.parse_args();run(a.variant,a.count,a.target,a.end,a.tag)
