"""Independently reconstruct historical error samples and online probabilities."""
from solve_q2 import ROOT,read_inputs,np,json,hashlib,DATA_FILE,PRICE_FILE

price,L,P,dates=read_inputs()
records=[];max_error=0.;times=[];recoveries=[]
for path in sorted((ROOT/'results/q2/main').glob('2025-*.npz')):
    with np.load(path) as r:
        day=dates.index(path.stem)
        pool=np.arange(max(7,day-29),day-1)
        assert np.array_equal(pool,r['pool_origins'])
        el=np.stack([np.concatenate((L[j]-L[j-7],L[j+1]-L[j-6])) for j in pool])
        ep=np.stack([np.concatenate((P[j]-P[j-1],P[j+1]-P[j-1])) for j in pool])
        ix=np.array([list(pool).index(j) for j in r['scenario_origins']])
        sl=np.maximum(np.std(el,axis=0),1/6);sp=np.maximum(np.std(ep,axis=0),1/6)
        for a,b in [(el[ix],r['scenario_error_load']),(ep[ix],r['scenario_error_pv']),(sl,r['scenario_scale_load']),(sp,r['scenario_scale_pv'])]:
            max_error=max(max_error,float(abs(a-b).max()))
        features=np.concatenate((el/sl,ep/sp),axis=1)
        distance=np.mean((features[:,None,:]-features[ix][None,:,:])**2,axis=2)
        prior=np.bincount(np.argmin(distance,axis=1),minlength=len(ix))/len(pool)
        assert np.allclose(prior,r['scenario_prior'],atol=1e-12,rtol=0)
        net=(el-ep).sum(axis=1)
        assert np.argmin(net) in ix and np.argmax(net) in ix
        fl=np.concatenate((L[day-7],L[day-6]));fp=np.tile(P[day-1],2)
        assert np.allclose(r['scenario_load'],np.maximum(fl+el[ix],0),atol=1e-12,rtol=0)
        assert np.allclose(r['scenario_pv'],np.maximum(fp+ep[ix],0),atol=1e-12,rtol=0)
        z=.5*(((L[day]-fl[:144]-el[ix,:144])/sl[:144])**2+((P[day]-fp[:144]-ep[ix,:144])/sp[:144])**2)
        dist=np.cumsum(z,axis=1)/np.arange(1,145)
        logits=np.log(prior[:,None])-.5*dist
        exp=np.exp(logits-logits.max(axis=0));weights=.95*exp/exp.sum(axis=0)+.05*prior[:,None]
        max_error=max(max_error,float(abs(weights.T-r['weights']).max()))
        times.extend(r['solve_seconds'].tolist())
        recoveries.extend([{'date':path.stem,**v} for v in json.loads(str(r['recoveries_json']))] if 'recoveries_json' in r else [])
        assert not json.loads(str(r['failures_json']))
        records.append({'date':path.stem,'complete_error_pairs':len(pool),'representatives':len(ix)})
assert len(records)==334 and max_error<1e-10
for item in recoveries:assert item['retry_status']=='HighsModelStatus.kOptimal'
checks={
    'passed':True,'days':334,'intervals':48096,'max_reconstruction_error':max_error,
    'current_solve_median_seconds':float(np.median(times)),
    'current_solve_99_percentile_seconds':float(np.quantile(times,.99)),
    'current_solve_max_seconds':float(max(times)),
    'cold_restarts':recoveries,'fallback_events':[],
    'sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [DATA_FILE,PRICE_FILE,ROOT/'code/solve_q2.py']},
    'daily_scenario_counts':records,
}
(ROOT/'verification/q2/scenario_and_runtime_audit.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in checks.items() if k!='daily_scenario_counts'},ensure_ascii=False,indent=2))
