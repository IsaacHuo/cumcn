"""One verified source for fourth-question paper, figures and workbook data."""
from solve_q4 import *
from forecast_diagnostics import tex,metrics

NAMES={'q2':'不调整购电','forecast0':'仅0点预报','h6':'6点调整','h12':'12点调整','h18':'18点调整','h6_12':'6、12点调整',
       'h6_18':'6、18点调整','h12_18':'12、18点调整','main':'6、12、18点调整','q2_point':'不调整：电价点预测','main_point':'全调整：电价点预测'}
SELECTED=['2025-03-20','2025-06-21','2025-09-23','2025-12-21']
KEYS=['plan_cost','refund','penalty','extra_cost','emergency_cost','total_cost','increase_total','decrease_total','expected_emergency_cost']
VECTORS=['plan_kwh','adjusted_kwh','charge_kwh','discharge_kwh','emergency_kwh','unused_kwh','soc_kwh','price_actual','forecast_price','load_kwh','pv_kwh','forecast_load_kwh','forecast_pv_kwh','plan_versions']

def clock(m):return f'{m//60:02d}:{m%60:02d}'

def spans(x):
    out=[];i=0
    while i<N:
        if x[i]<=TOL:i+=1;continue
        j=i+1
        while j<N and x[j]>TOL:j+=1
        out.append(dict(interval=f'{clock(i*10)}-{clock(j*10)}',kwh=float(x[i:j].sum())));i=j
    assert abs(sum(r['kwh'] for r in out)-x.sum())<N*TOL
    return out

def read_day(file,previous):
    with np.load(file) as z:
        r={k:np.array(z[k]) for k in VECTORS};r.update({k:float(z[k]) for k in KEYS})
        failures=json.loads(str(z['failures_json']));recoveries=json.loads(str(z['recoveries_json']));revisions=json.loads(str(z['revisions_json']))
    a,g,c,d,e,w,E,p=[r[k] for k in ['adjusted_kwh','plan_kwh','charge_kwh','discharge_kwh','emergency_kwh','unused_kwh','soc_kwh','price_actual']]
    balance=float(abs(a+r['pv_kwh']+d+e-r['load_kwh']-c-w).max());state=float(abs(np.diff(E)-ETA*c+d/ETA).max())
    assert max(balance,state,abs(E[0]-previous))<TOL,file
    assert E.min()>=LOW-TOL and E.max()<=HIGH+TOL and min(c.min(),d.min(),e.min(),w.min(),g.min(),a.min())>=-TOL
    assert max(c.max(),d.max())<=CAP+TOL and not np.any((c>TOL)&((d>TOL)|(e>TOL)))
    down=np.maximum(g-a,0);up=np.maximum(a-g,0)
    bill=dict(plan_cost=float(np.sum(p*g)),refund=float(np.sum(p*down)),penalty=float(np.sum(.5*p*down)),extra_cost=float(np.sum(1.5*p*up)),emergency_cost=float(np.sum(5*p*e)),increase_total=float(up.sum()),decrease_total=float(down.sum()))
    bill['total_cost']=bill['plan_cost']-bill['refund']+bill['penalty']+bill['extra_cost']+bill['emergency_cost']
    for key,value in bill.items():assert abs(value-r[key])<TOL,(file,key)
    for rev in revisions:assert rev['optimal_objective']<=rev['fixed_objective']+TOL
    info=dict(date=file.stem,**{k:r[k] for k in KEYS},plan_total=float(g.sum()),adjusted_total=float(a.sum()),emergency_total=float(e.sum()),unused_total=float(w.sum()),
              soc_start=float(E[0]),soc_end=float(E[-1]),failure_count=len(failures),recovery_count=len(recoveries),max_balance_error=balance,max_state_error=state,
              blocks=[dict(interval=f'{clock(k*240)}-{clock((k+1)*240)}',charge_kwh=float(c[k*24:(k+1)*24].sum()),discharge_kwh=float(d[k*24:(k+1)*24].sum())) for k in range(6)],emergency_intervals=spans(e))
    events=[dict(variant=file.parent.name,date=file.stem,event=x) for x in failures]
    return r,info,events

def main():
    fixed,L,P,dates=read_inputs();prices=read_prices();lam=float(fixed.min()/ETA);tables=ROOT/'paper/tables'
    report=dict(comparison=[],selected=[],selected_q2=[],daily=[],daily_q2=[],repriced=[],inventory_price=lam);events=[];exports={};checks=[]
    for variant in Q4_VARIANTS:
        files=sorted((ROOT/'results/q4'/variant).glob('2025-*.npz'));assert [f.stem for f in files]==dates[31:],variant
        previous=6000.;daily=[];export=[]
        for file in files:
            r,info,errors=read_day(file,previous);previous=info['soc_end'];daily.append(info);events.extend(errors)
            day=dates.index(file.stem);assert np.array_equal(r['price_actual'],prices[day])
            if variant=='q2':assert np.max(abs(r['plan_kwh']-r['adjusted_kwh']))<TOL
            if variant in ['main','q2']:
                if file.stem in SELECTED:
                    report['selected' if variant=='main' else 'selected_q2'].append(dict(**info,**{k:r[k].tolist() for k in VECTORS}))
                export.append(dict(**info,plan_kwh=r['plan_kwh'].tolist(),adjusted_kwh=r['adjusted_kwh'].tolist(),price_actual=r['price_actual'].tolist(),
                                   charge_kwh=r['charge_kwh'].tolist(),discharge_kwh=r['discharge_kwh'].tolist(),emergency_kwh=r['emergency_kwh'].tolist()))
        summary={k:float(sum(x[k] for x in daily)) for k in KEYS+['plan_total','adjusted_total','emergency_total','unused_total']}
        summary.update(variant=variant,name=NAMES[variant],final_soc=previous,emergency_days=sum(x['emergency_total']>TOL for x in daily),
                       failures=sum(x['failure_count'] for x in daily),recoveries=sum(x['recovery_count'] for x in daily))
        summary['inventory_adjusted_cost']=summary['total_cost']-lam*(previous-6000)
        report['comparison'].append(summary)
        if variant in ['main','q2']:
            report['daily' if variant=='main' else 'daily_q2']=daily;exports[variant]=export
        checks.append(dict(variant=variant,days=len(daily),max_balance=max(x['max_balance_error'] for x in daily),max_state=max(x['max_state_error'] for x in daily),failures=summary['failures'],recoveries=summary['recoveries']))
    assert not events,events
    comparison={c['variant']:c for c in report['comparison']}
    # Isolate revaluation of the original strategy from its reoptimization.
    for question,newvariant in [('q2','q2'),('q3','main')]:
        original=0.;repriced=0.;last=0.
        for day,date in enumerate(dates[31:],31):
            with np.load(ROOT/f'results/{question}/main/{date}.npz') as z:
                g=z['plan_kwh'];a=z['adjusted_kwh'] if question=='q3' else g;e=z['emergency_kwh']
                original+=float(z['total_cost']);repriced+=settle(prices[day],g,a,e)['total_cost'];last=float(z['soc_kwh'][-1])
        optimized=comparison[newvariant]['total_cost']
        report['repriced'].append(dict(question=question,original_cost=original,repriced_cost=repriced,reoptimized_cost=optimized,
                                     price_effect=repriced-original,policy_effect=optimized-repriced,old_final_soc=last,new_final_soc=comparison[newvariant]['final_soc'],
                                     adjusted_policy_effect=optimized-repriced-lam*(comparison[newvariant]['final_soc']-last)))
    report['lower_bound']=json.loads((ROOT/'results/q4/perfect_information.json').read_text(encoding='utf-8'))
    report['best_combination']=min((comparison[v] for v in Q4_VARIANTS[1:9]),key=lambda x:x['total_cost'])['variant']
    report['point_differences']={v:comparison[v]['total_cost']-comparison[v+'_point']['total_cost'] for v in ['q2','main']}
    for v,days in exports.items():
        (ROOT/f'results/q4/{v}_export.json').write_text(json.dumps(dict(days=days),ensure_ascii=False),encoding='utf-8')
    (ROOT/'results/q4_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    (ROOT/'verification/q4/full_validation.json').write_text(json.dumps(dict(passed=True,variants=checks,events=events),ensure_ascii=False,indent=2),encoding='utf-8')
    for variant in ['q2','main']:
        daily=report['daily_q2' if variant=='q2' else 'daily'];cols=['date']+KEYS+['emergency_total','unused_total','soc_start','soc_end']
        with (ROOT/f'results/q4/{variant}_daily.csv').open('w',newline='',encoding='utf-8-sig') as f:
            wr=csv.DictWriter(f,fieldnames=cols);wr.writeheader();wr.writerows({k:x[k] for k in cols} for x in daily)
    rows=[[x['name'],f"{x['total_cost']/1e4:.4f}",f"{x['emergency_total']:.2f}",x['emergency_days'],f"{x['unused_total']:.2f}",f"{x['final_soc']:.2f}"] for x in report['comparison']]
    (tables/'q4_comparison.tex').write_text(tex(['策略','费用/万元','紧急电量','天数','未利用电量','期末电量'],rows),encoding='utf-8')
    rows=[[x['name']]+[f"{x[k]/1e4:.4f}" for k in ['plan_cost','refund','penalty','extra_cost','emergency_cost']]+[f"{x[k]:.2f}" for k in ['increase_total','decrease_total']] for x in [comparison['q2'],comparison['main']]]
    (tables/'q4_cost_parts.tex').write_text(tex(['策略','原计划金额','取消退款','违约费','增购费','紧急费','增购量','减购量'],rows),encoding='utf-8')
    rows=[[x['question'].upper()]+[f"{x[k]/1e4:.4f}" for k in ['original_cost','repriced_cost','reoptimized_cost','policy_effect']] for x in report['repriced']]
    (tables/'q4_reprice.tex').write_text(tex(['原策略','原电价费用','波动电价重计费','重新优化费用','调度费用变化'],rows),encoding='utf-8')
    for family,key in [('q2','selected_q2'),('q3','selected')]:
        sel=report[key]
        rows=[[x['date'][5:]]+[f"{x[k]:.4f}" for k in ['plan_total','adjusted_total','emergency_total','total_cost','soc_start','soc_end']] for x in sel]
        (tables/f'q4_{family}_selected.tex').write_text(tex(['日期','原计划量','最终有效量','紧急量','费用/元','日初电量','日末电量'],rows),encoding='utf-8')
        rows=[]
        for hour in [10,12,14,16,18,20]:
            for field in (['plan_kwh'] if family=='q2' else ['plan_kwh','adjusted_kwh']):
                rows.append([f'{hour}:00--{hour}:10', '原计划' if field=='plan_kwh' else '最终有效']+[f'{x[field][hour*6]:.4f}' for x in sel])
        (tables/f'q4_{family}_purchase.tex').write_text(tex(['区间','电量类型']+[x['date'][5:] for x in sel],rows,'llrrrr'),encoding='utf-8')
        rows=[]
        for x in sel:
            for block in x['blocks']:rows.append([x['date'][5:],block['interval'],f"{block['charge_kwh']:.4f}",f"{block['discharge_kwh']:.4f}"])
        (tables/f'q4_{family}_storage.tex').write_text(tex(['日期','区间','充电量','放电量'],rows,'llrr'),encoding='utf-8')
        rows=[]
        for x in sel:
            for event in x['emergency_intervals'] or [dict(interval='无',kwh=0)]:rows.append([x['date'][5:],event['interval'],f"{event['kwh']:.4f}"])
        (tables/f'q4_{family}_emergency.tex').write_text(tex(['日期','连续紧急购电区间','紧急电量'],rows,'llr'),encoding='utf-8')
    macros={'QfourTwoCost':comparison['q2']['total_cost']/1e4,'QfourThreeCost':comparison['main']['total_cost']/1e4,'QfourTwoEmergency':comparison['q2']['emergency_total'],
            'QfourThreeEmergency':comparison['main']['emergency_total'],'QfourLower':report['lower_bound']['total_cost']/1e4,
            'QfourTwoPointDiff':report['point_differences']['q2'],'QfourThreePointDiff':report['point_differences']['main'],
            'QfourTwoEnd':comparison['q2']['final_soc'],'QfourThreeEnd':comparison['main']['final_soc']}
    lines=['\\newcommand{\\'+k+'}{'+f'{v:.4f}'+'}' for k,v in macros.items()]
    lines+=[r'\newcommand{\QfourBestName}{'+NAMES[report['best_combination']]+'}',r'\newcommand{\QfourBestCost}{'+f"{comparison[report['best_combination']]['total_cost']/1e4:.4f}"+'}',r'\newcommand{\QfourRecoveries}{'+str(sum(c['recoveries'] for c in report['comparison']))+'}']
    (tables/'q4_values.tex').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    paragraphs=[]
    for v,label in [('q2','不允许调整购电'),('main','采用全部日内预报调整')]:
        delta=report['point_differences'][v];word='降低' if delta<0 else '增加'
        adj=delta-lam*(comparison[v]['final_soc']-comparison[v+'_point']['final_soc'])
        paragraphs.append(f'{label}时，电价情景方案的实际费用比点预测对照{word}{abs(delta)/1e4:.4f}万元，库存校正后的费用差为{adj/1e4:.4f}万元。')
    paragraphs.append('这些对照不保证误差建模必然改善实际费用。所用情景有限且预测简单，价格误差进入目标函数后改变了购电和储能时序，实际效果仍由全年账单判断。')
    for v,label in [('q2','不调整购电方案'),('main','全部日内预报方案')]:
        x=comparison[v];paragraphs.append(f'{label}的日前情景预计紧急费合计为{x["expected_emergency_cost"]/1e4:.4f}万元，实际紧急费为{x["emergency_cost"]/1e4:.4f}万元；预计值仅汇总每天前144段，未重复计入次日前瞻。')
    (tables/'q4_interpretation.tex').write_text('\n\n'.join(paragraphs)+'\n',encoding='utf-8')
    print(json.dumps(dict(comparison=report['comparison'],repriced=report['repriced'],best=report['best_combination']),ensure_ascii=False),flush=True)

if __name__=='__main__':main()
