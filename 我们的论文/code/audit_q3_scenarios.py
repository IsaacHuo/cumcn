"""Independent reconstruction of Q3 forecast vintages and historical errors."""
from solve_q3 import ROOT,read_inputs,read_forecasts,np,json,VARIANTS

def pv_prediction(P,F,j,h):
    first=h*6;prediction=np.tile(P[j-1],2)
    anchor=P[j,first-1]*6 if first else P[j-1,-1]*6
    nodes=np.r_[anchor,F[j,h//6]]
    m=np.arange(144);hour=m//6;fraction=(m%6+.5)/6
    prediction[first:first+144]=(nodes[hour]*(1-fraction)+nodes[hour+1]*fraction)/6
    return prediction

def main():
    price,L,P,dates=read_inputs();F=read_forecasts();errors=[];run_times=[];changes=[];restarts=[]
    files=sorted((ROOT/'results/q3/main').glob('2025-*.npz'));assert len(files)==334
    for path in files:
        day=dates.index(path.stem)
        with np.load(path) as r:
            for slot,h in enumerate([0,6,12,18]):
                first=h*6;key=f'sc{slot}_';origins=np.arange(max(7,day-29),day-1)
                assert np.array_equal(r[key+'pool_origins'],origins)
                assert np.array_equal(r[key+'hourly_kw'],F[day,slot])
                point_p=pv_prediction(P,F,day,h);point_l=np.r_[L[day-7],L[day-6]]
                errors.extend([np.max(abs(point_p-r[key+'forecast_pv'])),np.max(abs(point_l-r[key+'forecast_load']))])
                el=np.array([L[j:j+2].reshape(-1)-np.r_[L[j-7],L[j-6]] for j in origins])
                ep=np.array([P[j:j+2].reshape(-1)-pv_prediction(P,F,j,h) for j in origins])
                selected=np.array([list(origins).index(j) for j in r[key+'origins']])
                sl=np.maximum(np.std(el,axis=0),1/6);sp=np.maximum(np.std(ep,axis=0),1/6)
                for expected,actual in [(el[selected],r[key+'error_load']),(ep[selected],r[key+'error_pv']),(sl,r[key+'scale_load']),(sp,r[key+'scale_pv']),
                                        (np.maximum(point_l+el[selected],0),r[key+'load']),(np.maximum(point_p+ep[selected],0),r[key+'pv'])]:
                    errors.append(np.max(abs(expected-actual)))
                feature=np.c_[el[:,first:]/sl[first:],ep[:,first:]/sp[first:]]
                distance=np.mean((feature[:,None,:]-feature[selected][None,:,:])**2,axis=2)
                prior=np.bincount(np.argmin(distance,axis=1),minlength=len(selected))/len(origins)
                assert np.allclose(prior,r[key+'prior'],rtol=0,atol=1e-12)
                extremes=(el[:,first:]-ep[:,first:]).sum(1)
                assert np.argmin(extremes) in selected and np.argmax(extremes) in selected
                # Main uses a new forecast at every six-hour boundary.
                error_l=(L[day,first:first+36]-point_l[first:first+36]-el[selected,first:first+36])/sl[first:first+36]
                error_p=(P[day,first:first+36]-point_p[first:first+36]-ep[selected,first:first+36])/sp[first:first+36]
                distance=np.cumsum(.5*(error_l**2+error_p**2),axis=1)/np.arange(1,37)
                logits=np.log(prior[:,None])-.5*distance;weights=np.exp(logits-logits.max(0));weights/=weights.sum(0)
                weights=.95*weights+.05*prior[:,None]
                errors.append(np.max(abs(weights.T-r[key+'weights'])))
            run_times.extend(r['solve_seconds'].tolist());changes.extend(json.loads(str(r['revisions_json'])))
            restarts.extend([{'date':path.stem,**v} for v in json.loads(str(r['recoveries_json']))])
    maximum=float(max(errors));assert maximum<1e-8
    result=dict(passed=True,days=334,forecast_vintages=1336,max_reconstruction_error=maximum,
                adjustment_decisions=len(changes),changed=sum(c['changed'] for c in changes),
                min_expected_gain=float(min(c['expected_gain'] for c in changes)),
                median_current_solve_seconds=float(np.median(run_times)),max_current_solve_seconds=float(max(run_times)),
                successful_cold_restarts=restarts)
    (ROOT/'verification/q3/scenario_audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
