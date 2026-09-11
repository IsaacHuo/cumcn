"""Causal joint load/PV/price scenarios; actual delivery-price settlement."""
from solve_q3 import *
from solve_q2 import forecast

PRICE_FILE=ROOT/'data/raw/附件4.xlsx'
Q4_VARIANTS=['q2','forecast0','h6','h12','h18','h6_12','h6_18','h12_18','main','q2_point','main_point']

def read_prices():
    w=load_workbook(PRICE_FILE,read_only=True,data_only=True)
    rows=list(w.active.values);w.close()
    a=np.asarray([r[1:] for r in rows[1:]],float)
    assert a.shape==(365,N) and np.isfinite(a).all() and (a>0).all()
    for i,r in enumerate(rows[1:]):assert r[0].date()==datetime.date(2025,1,1)+datetime.timedelta(days=i)
    return a

def joint_scenarios(hl,hp,hf,hprice,prefix,hourly,hour,count=7,point=False):
    day=len(hl);start=hour*6
    fl,fp=forecast(hl,hp) if hourly is None else point_forecast(hl,hp,prefix,hourly,hour)
    fc=np.tile(np.mean(hprice[-7:],axis=0),2)
    origins=np.arange(max(7,day-29),day-1);el=[];ep=[];ec=[]
    for j in origins:
        jl,jp=forecast(hl[:j],hp[:j]) if hourly is None else point_forecast(hl[:j],hp[:j],hp[j,:start],hf[j,hour//6],hour)
        el.append(hl[j:j+2].ravel()-jl);ep.append(hp[j:j+2].ravel()-jp)
        ec.append(hprice[j:j+2].ravel()-np.tile(hprice[j-7:j].mean(0),2))
    el,ep,ec=map(np.asarray,[el,ep,ec])
    sl=np.maximum(el.std(0),1/6);sp=np.maximum(ep.std(0),1/6);sc=np.maximum(ec.std(0),1e-4)
    features=np.c_[el[:,start:]/sl[start:],ep[:,start:]/sp[start:],ec[:,start:]/sc[start:]]
    dist=np.mean((features[:,None]-features[None,:])**2,axis=2)
    net=(el[:,start:]-ep[:,start:]).sum(1);k=min(count,len(origins))
    med=list(dict.fromkeys([int(net.argmin()),int(net.argmax()),int(ec[:,start:].mean(1).argmax())]))[:k];fixed=len(med)
    while len(med)<k:
        ds=dist[:,med].min(1);ds[med]=-1;med.append(int(ds.argmax()))
    for _ in range(10):
        assign=dist[:,med].argmin(1);new=list(med)
        for s in range(fixed,k):
            ix=np.flatnonzero(assign==s)
            if len(ix):new[s]=int(ix[dist[np.ix_(ix,ix)].sum(1).argmin()])
        if new==med:break
        med=new
    assign=dist[:,med].argmin(1);prior=np.bincount(assign,minlength=k)/len(origins)
    ix=np.asarray(med)[prior>0];prior=prior[prior>0]
    return dict(load=np.maximum(fl+el[ix],0),pv=np.maximum(fp+ep[ix],0),price=np.tile(fc,(len(ix),1)) if point else np.maximum(fc+ec[ix],1e-4),
                prior=prior,forecast_load=fl,forecast_pv=fp,forecast_price=fc,error_load=el[ix],error_pv=ep[ix],error_price=ec[ix],
                scale_load=sl,scale_pv=sp,scale_price=sc,origins=origins[ix],pool_origins=origins)

def joint_weights(sc,ol,op,oc,start):
    parts=[];end=len(ol)
    for obs,key in [(ol,'load'),(op,'pv')]:
        if end>start:
            z=(np.asarray(obs[start:])-sc['forecast_'+key][start:end]-sc['error_'+key][:,start:end])/sc['scale_'+key][start:end]
            parts.append((z*z).mean(1))
    if len(oc):
        z=(np.asarray(oc)-sc['forecast_price'][:len(oc)]-sc['error_price'][:,:len(oc)])/sc['scale_price'][:len(oc)]
        parts.append((z*z).mean(1))
    if not parts:return sc['prior'].copy()
    distance=np.mean(parts,axis=0);logw=np.log(sc['prior'])-.5*distance
    w=np.exp(logw-logw.max());w/=w.sum();return .95*w+.05*sc['prior']

class PriceLP(RevisionLP):
    def __init__(self,sc,soc,start=0,original=None,target=6000.,known_prices=(),prob=None):
        self.price_scenarios=np.array(sc['price'],copy=True)
        self.price_scenarios[:,:len(known_prices)]=known_prices
        self.current_prob=sc['prior'] if prob is None else prob
        super().__init__(sc['forecast_price'][:N],sc,soc,start,original=original,target=target)
        self.refresh_costs(self.current_prob)

    def objective(self,prob):
        c=np.zeros(self.size);c[:H]=prob@self.price_scenarios
        for s,w in enumerate(prob):c[self.base(s)+2*H:self.base(s)+3*H]=5*w*self.price_scenarios[s]
        return c

    def refresh_costs(self,prob):
        self.current_prob=np.array(prob);cost=np.zeros(self.h.getNumCol());cost[:self.size]=self.objective(prob)
        if self.original is not None:
            cost[:N]=0;n=self.revision_count;mean=prob@self.price_scenarios
            cost[self.up:self.up+n]=1.5*mean[self.start:N]
            cost[self.down:self.down+n]=-.5*mean[self.start:N]
        ids=np.arange(len(cost),dtype=np.int32);self.h.changeColsCost(len(ids),ids,cost)

    def priced_step(self,t,soc,load,pv,price,prob):
        self.price_scenarios[:,t]=price;self.refresh_costs(prob)
        return self.step(t,soc,load,pv,prob)

def simulate(hl,hp,hf,hprice,measurements,forecast_at,soc,variant='main',count=7,target=6000.):
    begin=time.perf_counter();isq2=variant.startswith('q2');point=variant.endswith('_point')
    base=variant.removesuffix('_point');updates=() if isq2 else VARIANTS[base][0]
    sc=joint_scenarios(hl,hp,hf,hprice,[],None if isq2 else forecast_at(0),0,count,point)
    ctl=PriceLP(sc,soc,target=target);x=ctl.solve();original=np.maximum(x[:N],0);active=original.copy();ctl.fix_plan(active)
    expected=sum(float(5*sc['price'][s,:N]@x[ctl.base(s)+2*H:ctl.base(s)+2*H+N])*p for s,p in enumerate(sc['prior']))
    plans=np.tile(original,(4,1));pvs=np.full((4,N),np.nan);pvs[0]=sc['forecast_pv'][:N]
    ol=[];op=[];oc=[];states=[soc];actions=[];effective=[];failures=[];recoveries=[];revisions=[];seconds=[]
    scenes={0:sc};weights={0:[]};stage=0;stage_start=0
    for t,(load,pv,price) in enumerate(measurements):
        assert t<N
        if t in [36,72,108]:
            hour=t//6;slot=hour//6;plans[slot]=active
            if hour in updates:
                recoveries.extend([dict(stage=stage,**v) for v in ctl.recoveries])
                sc=joint_scenarios(hl,hp,hf,hprice,op,forecast_at(hour),hour,count,point)
                stage=slot;stage_start=t;scenes[slot]=sc;weights[slot]=[];pvs[slot,t:]=sc['forecast_pv'][t:N]
                known=oc+[float(price)];prob=joint_weights(sc,ol,op,known,stage_start)
                ctl=PriceLP(sc,soc,t,original,target,known,prob)
                try:active,record=ctl.revise(active);revisions.append(record)
                except RuntimeError as exc:
                    failures.append(dict(kind='revision',interval=t,status=str(exc)))
                    ctl=PriceLP(sc,soc,t,original,target,known,prob);ctl.fix_plan(active)
                plans[slot]=active
        ol.append(float(load));op.append(float(pv));oc.append(float(price))
        prob=joint_weights(sc,ol,op,oc,stage_start);weights[stage].append(prob);tick=time.perf_counter()
        try:c,d,e,w=ctl.priced_step(t,soc,float(load),float(pv),float(price),prob)
        except RuntimeError as exc:
            failures.append(dict(kind='execution',interval=t,status=str(exc)));c,d,e,w=fallback(soc,load-pv-active[t])
        seconds.append(time.perf_counter()-tick);c,d,e,w=[max(0,float(v)) for v in [c,d,e,w]]
        nextsoc=soc+ETA*c-d/ETA
        assert abs(active[t]+pv+d+e-load-c-w)<TOL
        assert LOW-TOL<=nextsoc<=HIGH+TOL and max(c,d)<=CAP+TOL
        assert not(c>TOL and (d>TOL or e>TOL))
        soc=float(np.clip(nextsoc,LOW,HIGH));states.append(soc);actions.append([c,d,e,w]);effective.append(active[t])
    assert len(actions)==N
    recoveries.extend([dict(stage=stage,**v) for v in ctl.recoveries]);a=np.asarray(actions);effective=np.asarray(effective)
    result=dict(plan_kwh=original,adjusted_kwh=effective,plan_versions=plans,forecast_pv_versions=pvs,
                forecast_load_kwh=scenes[0]['forecast_load'][:N],forecast_pv_kwh=scenes[0]['forecast_pv'][:N],
                forecast_price=scenes[0]['forecast_price'][:N],price_actual=np.asarray(oc),load_kwh=np.asarray(ol),pv_kwh=np.asarray(op),
                soc_kwh=np.asarray(states),solve_seconds=np.asarray(seconds),expected_emergency_cost=expected,
                failures_json=json.dumps(failures),recoveries_json=json.dumps(recoveries),revisions_json=json.dumps(revisions),elapsed_seconds=time.perf_counter()-begin)
    for i,k in enumerate(['charge_kwh','discharge_kwh','emergency_kwh','unused_kwh']):result[k]=a[:,i]
    result.update(settle(np.asarray(oc),original,effective,a[:,2]))
    for slot,s in scenes.items():
        for key,value in s.items():result[f'sc{slot}_{key}']=value
        result[f'sc{slot}_weights']=np.asarray(weights[slot])
    return result

def run(variant='main',end=365,tag=None):
    _,L,P,dates=read_inputs();F=read_forecasts();prices=read_prices()
    folder=ROOT/'results/q4'/(tag or variant);folder.mkdir(parents=True,exist_ok=True)
    cfg=dict(version=1,variant=variant,price_forecast='previous 7 complete days mean',scenario_count=7,target=6000,history_pairs=28,prior_mix=.05,
             settlement='actual delivery price; original minus 0.5 cancellation plus 1.5 additions plus 5 emergency',
             source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),price_sha256=hashlib.sha256(PRICE_FILE.read_bytes()).hexdigest())
    cp=folder/'config.json'
    if cp.exists():assert json.loads(cp.read_text(encoding='utf-8'))==cfg,'Changed configuration: use a new tag'
    else:cp.write_text(json.dumps(cfg,ensure_ascii=False,indent=2),encoding='utf-8')
    soc=INITIAL
    for day in range(31,end):
        file=folder/f'{dates[day]}.npz'
        if file.exists():
            with np.load(file) as r:
                assert abs(float(r['soc_kwh'][0])-soc)<TOL;soc=float(r['soc_kwh'][-1])
            continue
        r=simulate(L[:day],P[:day],F[:day],prices[:day],zip(L[day],P[day],prices[day]),lambda hour:F[day,hour//6],soc,variant)
        r.update(day_index=day,date=dates[day]);temp=file.with_suffix('.tmp.npz');np.savez_compressed(temp,**r);temp.replace(file);soc=float(r['soc_kwh'][-1])
        print(json.dumps(dict(variant=variant,date=dates[day],cost=round(r['total_cost'],2),seconds=round(r['elapsed_seconds'],2),failures=len(json.loads(r['failures_json'])))),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--variant',choices=Q4_VARIANTS,default='main');p.add_argument('--end',type=int,default=365);p.add_argument('--tag')
    args=p.parse_args();run(args.variant,args.end,args.tag)
