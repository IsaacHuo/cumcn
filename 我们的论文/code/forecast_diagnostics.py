"""Forecast errors on matching ten-minute delivery intervals, in kWh."""
from solve_q4 import *

def metrics(e):
    e=np.asarray(e,float).ravel();e=e[np.isfinite(e)]
    return dict(bias=float(e.mean()),mae=float(abs(e).mean()),rmse=float(np.sqrt((e*e).mean())),n=len(e))

def tex(headers,rows,align=None):
    return '\n'.join([r'\begin{tabular}{'+(align or 'l'+'r'*(len(headers)-1))+'}',r'\toprule',' & '.join(headers)+r' \\',r'\midrule']+[' & '.join(map(str,r))+r' \\' for r in rows]+[r'\bottomrule',r'\end{tabular}',''])

def main():
    _,L,P,dates=read_inputs();F=read_forecasts();price=read_prices();q2={k:[] for k in ['load','pv','net']}
    release={str(h):[] for h in [0,6,12,18]};lead={str(h):{str(k):[] for k in range(4)} for h in [0,6,12,18]}
    overlap={str(h):dict(old=[],new=[]) for h in [6,12,18]};pe=[]
    for day in range(31,365):
        fl,fp=forecast(L[:day],P[:day]);el=L[day]-fl[:N];ep=P[day]-fp[:N]
        for k,v in [('load',el),('pv',ep),('net',el-ep)]:q2[k].extend(v)
        pe.extend(price[day]-price[day-7:day].mean(0))
        fs={}
        for hour in [0,6,12,18]:
            start=day*N+hour*6;anchor=P.ravel()[start-1]
            pred=interpolate_energy(anchor,F[day,hour//6]);actual=P.ravel()[start:start+N]
            err=actual-pred[:len(actual)];fs[hour]=pred
            release[str(hour)].extend(err)
            for k in range(4):lead[str(hour)][str(k)].extend(err[k*36:(k+1)*36])
        for hour in [6,12,18]:
            start=hour*6;actual=P[day,start:];old=fs[0][start:];new=fs[hour][:N-start]
            overlap[str(hour)]['old'].extend(actual-old);overlap[str(hour)]['new'].extend(actual-new)
    result=dict(unit='kWh per 10-minute interval; error=actual-forecast',q2={k:metrics(v) for k,v in q2.items()},
                q3_release={h:metrics(v) for h,v in release.items()},q3_lead={h:{k:metrics(v) for k,v in x.items()} for h,x in lead.items()},
                q3_overlap={h:{k:metrics(v) for k,v in x.items()} for h,x in overlap.items()},price=metrics(pe),price_unit='yuan/kWh')
    (ROOT/'results/forecast_diagnostics.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    rows=[]
    for group,values in [('q2',result['q2']),('q3_release',result['q3_release'])]:
        for key,m in values.items():rows.append(dict(group=group,key=key,**m))
    for h,x in result['q3_lead'].items():
        for k,m in x.items():rows.append(dict(group='q3_lead',key=f'{h}:00/{int(k)*6+1}-{int(k)*6+6}h',**m))
    with (ROOT/'results/forecast_diagnostics.csv').open('w',newline='',encoding='utf-8-sig') as f:
        wr=csv.DictWriter(f,fieldnames=list(rows[0]));wr.writeheader();wr.writerows(rows)
    names={'load':'负载','pv':'光伏','net':'净负荷'}
    tab=[[names[k]]+[f'{m[j]:.4f}' for j in ['bias','mae','rmse']] for k,m in result['q2'].items()]
    (ROOT/'paper/tables/q2_forecast_errors.tex').write_text(tex(['预测对象','平均偏差','MAE','RMSE'],tab),encoding='utf-8')
    tab=[[h+':00']+[f'{result["q3_release"][h][j]:.4f}' for j in ['mae','rmse']]+[str(result['q3_release'][h]['n'])] for h in release]
    (ROOT/'paper/tables/q3_forecast_errors.tex').write_text(tex(['发布时间','MAE','RMSE','区间数'],tab),encoding='utf-8')
    tab=[[h+':00']+[f'{result["q3_overlap"][h][s][j]:.4f}' for s in ['old','new'] for j in ['mae','rmse']] for h in overlap]
    (ROOT/'paper/tables/q3_forecast_overlap.tex').write_text(tex(['更新时刻','0点MAE','0点RMSE','更新MAE','更新RMSE'],tab),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False))

if __name__=='__main__':main()
