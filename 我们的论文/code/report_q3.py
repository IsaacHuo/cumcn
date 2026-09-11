"""All Q3 tables, MATLAB inputs and workbook inputs share checked daily records."""
from solve_q3 import *
from validate_q3 import validate
from report_q2 import intervals,clock,table,money

DATES=['2025-03-20','2025-06-21','2025-09-23','2025-12-21']
ORDER=['forecast0','h6','h12','h18','h6_12','h6_18','h12_18','main','info_only','literal_all']
TOTAL_KEYS=['plan_cost','refund','penalty','extra_cost','emergency_cost','total_cost','increase_total','decrease_total']

def day_record(path):
    with np.load(path) as z:r={k:np.array(z[k]) for k in z.files}
    d=dict(date=path.stem,**{k:float(r[k]) for k in TOTAL_KEYS},plan_total=float(r['plan_kwh'].sum()),
           adjusted_total=float(r['adjusted_kwh'].sum()),emergency_total=float(r['emergency_kwh'].sum()),
           unused_total=float(r['unused_kwh'].sum()),soc_start=float(r['soc_kwh'][0]),soc_end=float(r['soc_kwh'][-1]),
           expected_emergency_cost=float(r['expected_emergency_cost']),elapsed_seconds=float(r['elapsed_seconds']))
    d['blocks']=[dict(interval=f'{clock(240*k)}-{clock(240*(k+1))}',charge_kwh=float(r['charge_kwh'][24*k:24*(k+1)].sum()),
                       discharge_kwh=float(r['discharge_kwh'][24*k:24*(k+1)].sum())) for k in range(6)]
    d['emergency_intervals']=intervals(r['emergency_kwh'])
    assert abs(sum(x['kwh'] for x in d['emergency_intervals'])-d['emergency_total'])<TOL
    return r,d

def json_safe(x):
    if isinstance(x,np.ndarray):return json_safe(x.tolist())
    if isinstance(x,dict):return {k:json_safe(v) for k,v in x.items()}
    if isinstance(x,list):return [json_safe(v) for v in x]
    if isinstance(x,float) and not np.isfinite(x):return None
    return x

def interpretation(report):
    lookup={c['variant']:c for c in report['comparison']};base=lookup['forecast0'];info=lookup['info_only'];ma=lookup['main']
    difference=base['total_cost']-info['total_cost']
    text=f'仅更新预报并调整储能，相对0点基准的实际费用'+('减少' if difference>=0 else '增加')+f'{abs(difference):.2f}元。'
    text+=f'进一步允许修改购电量，相对仅更新储能的方案，费用减少{info["total_cost"]-ma["total_cost"]:.2f}元。'
    text+='本次对照中，购电修订提供的灵活性是费用改善的主要来源。这是不同连续运行策略之间的费用差，包含其后续储电状态变化的影响。'
    return text

def main():
    price,_,_,_=read_inputs();report=dict(daily=[],selected=[],comparison=[]);export={'days':[]};tables=ROOT/'paper/tables'
    daily_by={}
    for variant in ORDER:
        validate(variant)
        summaries=[]
        for path in sorted((ROOT/'results/q3'/variant).glob('2025-*.npz')):
            r,d=day_record(path);summaries.append(d)
            if variant=='main':
                report['daily'].append(d);export['days'].append({**d,'plan_kwh':r['plan_kwh'],'adjusted_kwh':r['adjusted_kwh']})
                if d['date'] in DATES:
                    selected={**d,**{k:r[k] for k in ['plan_kwh','adjusted_kwh','plan_versions','forecast_pv_versions','load_kwh','pv_kwh','charge_kwh','discharge_kwh','emergency_kwh','unused_kwh','soc_kwh']}}
                    report['selected'].append(selected)
        daily_by[variant]=summaries
        c={k:sum(d[k] for d in summaries) for k in TOTAL_KEYS+['plan_total','adjusted_total','emergency_total','unused_total','expected_emergency_cost']}
        c.update(name=VARIANTS[variant][3],variant=variant,emergency_days=sum(d['emergency_total']>TOL for d in summaries),final_soc=summaries[-1]['soc_end'])
        c['inventory_adjusted_cost']=c['total_cost']-float(price.min()/ETA)*(c['final_soc']-INITIAL)
        report['comparison'].append(c)
    lookup={r['variant']:r for r in report['comparison']};base=lookup['forecast0'];main=lookup['main'];info=lookup['info_only']
    report['sensitivity']=json.loads((ROOT/'results/q3/sensitivity.json').read_text(encoding='utf-8'));assert len(report['sensitivity'])==12
    report['perfect_information']=json.loads((ROOT/'results/q2/perfect_information.json').read_text(encoding='utf-8'))
    report['marginal_forecast_value']=[]
    for hour in [6,12,18]:
        records=[]
        for source in ORDER[:8]:
            hours=VARIANTS[source][0]
            if hour in hours:continue
            target=next(v for v in ORDER[:8] if set(VARIANTS[v][0])==set(hours)|{hour})
            records.append(dict(from_variant=source,to_variant=target,cost_reduction=lookup[source]['total_cost']-lookup[target]['total_cost']))
        report['marginal_forecast_value'].append(dict(hour=hour,comparisons=records))
    for name,data in [('q3_report.json',report),('q3_export.json',export)]:
        (ROOT/'results'/name).write_text(json.dumps(json_safe(data),ensure_ascii=False,indent=2),encoding='utf-8')
    keys=['date']+TOTAL_KEYS+['plan_total','adjusted_total','emergency_total','unused_total','soc_start','soc_end']
    with (ROOT/'results/q3_daily.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=keys,extrasaction='ignore');w.writeheader();w.writerows(report['daily'])
    with (ROOT/'results/q3_detail.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.writer(f);w.writerow(['date','interval','price','plan_kwh','adjusted_kwh','load_kwh','pv_kwh','charge_kwh','discharge_kwh','emergency_kwh','unused_kwh','soc_start','soc_end','refund','penalty','extra_cost','total_cost'])
        for path in sorted((ROOT/'results/q3/main').glob('2025-*.npz')):
            r,d=day_record(path)
            for t in range(N):
                up=max(r['adjusted_kwh'][t]-r['plan_kwh'][t],0);down=max(-r['adjusted_kwh'][t]+r['plan_kwh'][t],0)
                refund=price[t]*down;penalty=.5*refund;extra=1.5*price[t]*up
                total=price[t]*r['plan_kwh'][t]-refund+penalty+extra+5*price[t]*r['emergency_kwh'][t]
                w.writerow([path.stem,f'{clock(10*t)}-{clock(10*(t+1))}',price[t]]+[r[k][t] for k in ['plan_kwh','adjusted_kwh','load_kwh','pv_kwh','charge_kwh','discharge_kwh','emergency_kwh','unused_kwh']]+[r['soc_kwh'][t],r['soc_kwh'][t+1],refund,penalty,extra,total])
    with (ROOT/'results/q3_versions.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.writer(f);w.writerow(['date','issued_hour','interval','original_kwh','effective_version_kwh','forecast_pv_kwh'])
        for path in sorted((ROOT/'results/q3/main').glob('2025-*.npz')):
            r,d=day_record(path)
            for slot in range(4):
                for t in range(slot*36,N):w.writerow([path.stem,slot*6,f'{clock(10*t)}-{clock(10*(t+1))}',r['plan_kwh'][t],r['plan_versions'][slot,t],r['forecast_pv_versions'][slot,t]])
    rows=[[c['name'],money(c['total_cost']/1e4),money(c['emergency_total']),str(c['emergency_days']),money(c['unused_total']),money(c['final_soc'])] for c in report['comparison']]
    (tables/'q3_comparison.tex').write_text(table(['策略','费用/万元','紧急电量/kWh','天数','未利用电量/kWh','期末储电/kWh'],rows,'lrrrrr'),encoding='utf-8')
    rows=[[d['date'][5:]]+[money(d[k]) for k in ['plan_total','adjusted_total','emergency_total','total_cost','soc_start','soc_end']] for d in report['selected']]
    (tables/'q3_selected.tex').write_text(table(['日期','原计划电量','调整后电量','紧急电量','总费用/元','日初储电','日末储电'],rows,'lrrrrrr'),encoding='utf-8')
    rows=[]
    for h in [10,12,14,16,18,20]:rows.append([f'{h}:00--{h}:10']+[f'{d[k][h*6]:.2f}' for d in report['selected'] for k in ['plan_kwh','adjusted_kwh']])
    headers=['时段']+[r'\multicolumn{2}{c}{'+d[5:]+'}' for d in DATES]
    purchase=table(headers,[['']+['原计划','调整后']*4]+rows,'lrrrrrrrr')
    (tables/'q3_purchase.tex').write_text(purchase,encoding='utf-8')
    rows=[[report['selected'][0]['blocks'][k]['interval'].replace('-','--')]+[money(d['blocks'][k][field]) for d in report['selected'] for field in ['charge_kwh','discharge_kwh']] for k in range(6)]
    (tables/'q3_storage.tex').write_text(table(headers,[['']+['充电','放电']*4]+rows,'lrrrrrrrr'),encoding='utf-8')
    rows=[]
    for d in report['selected']:
        for i,e in enumerate(d['emergency_intervals'] or [dict(interval='无',kwh=0)]):rows.append([d['date'][5:] if i==0 else '',e['interval'].replace('-','--'),money(e['kwh'])])
    (tables/'q3_emergency.tex').write_text(table(['日期','紧急购电区间','电量/kWh'],rows,'llr'),encoding='utf-8')
    rows=[[r['date'][5:],r['setting'],money(r['cost_difference']),money(r['emergency_difference']),money(r['final_soc']),money(r['inventory_adjusted_difference'])] for r in report['sensitivity']]
    (tables/'q3_sensitivity.tex').write_text(table(['日期','设置','费用变化/元','紧急量变化/kWh','日末储电/kWh','库存校正变化/元'],rows,'llrrrr'),encoding='utf-8')
    macros={'QthreeCost':main['total_cost']/1e4,'QthreeSaving':100*(base['total_cost']-main['total_cost'])/base['total_cost'],
            'QthreeDifference':base['total_cost']-main['total_cost'],'QthreeEmergency':main['emergency_total'],'QthreeDays':main['emergency_days'],
            'QthreePlanCost':main['plan_cost']/1e4,'QthreeRefund':main['refund']/1e4,'QthreePenalty':main['penalty']/1e4,
            'QthreeExtra':main['extra_cost']/1e4,'QthreeEmergencyCost':main['emergency_cost']/1e4,'QthreeEnd':main['final_soc'],
            'QthreeInventoryDifference':base['inventory_adjusted_cost']-main['inventory_adjusted_cost'],
            'QthreeInfoSaving':base['total_cost']-info['total_cost'],'QthreeRevisionSaving':info['total_cost']-main['total_cost'],
            'QthreeLiteralCost':lookup['literal_all']['total_cost']/1e4,'QthreeLower':report['perfect_information']['total_cost']/1e4}
    (tables/'q3_values.tex').write_text('\n'.join('\\newcommand{\\'+k+'}{'+(str(int(v)) if k=='QthreeDays' else f'{v:.4f}')+'}' for k,v in macros.items()),encoding='utf-8')
    best=min(report['comparison'][:8],key=lambda c:c['total_cost'])
    sentences=[f'在八种预报组合中，本次回测费用最低的是“{best["name"]}”，总费用为{best["total_cost"]/1e4:.4f}万元。该排序是样本内的运行比较，不作为重新选择主方案参数的依据。']
    for item in report['marginal_forecast_value']:
        delta=[x['cost_reduction'] for x in item['comparisons']]
        sentences.append(f'在其余预报组合固定时，加入{item["hour"]}点预报的全年费用减少量介于{min(delta):.2f}至{max(delta):.2f}元。')
    if all(c['cost_reduction']>0 for item in report['marginal_forecast_value'] for c in item['comparisons']):
        sentences.append('因此，在本次数据与模型设定下，采用6、12、18点预报并允许购电调整具有费用优势；接收预报不意味着每次都必须修改计划。')
    else:sentences.append('负的费用减少量表示费用增加，故应根据组合对照判断预报时刻的作用，不能保证逐次增加预报必然改善。')
    other=lookup['literal_all'];difference=base['total_cost']-other['total_cost']
    sentences.append(f'在原计划照付的另一结算口径下，全部预报方案相对无调整基准的费用'+('减少' if difference>=0 else '增加')+f'{abs(difference):.2f}元，全年减购量为{other["decrease_total"]:.4f} kWh。')
    (tables/'q3_findings.tex').write_text(''.join(sentences),encoding='utf-8')
    (tables/'q3_information_text.tex').write_text(interpretation(report),encoding='utf-8')
    representative=max(report['selected'],key=lambda d:d['emergency_total']);token=representative['date'].replace('-','')
    (tables/'q3_figure.tex').write_text('\n'.join([r'\begin{figure}[htbp]\centering',r'\includegraphics[width=\textwidth,height=.83\textheight,keepaspectratio]{figures/q3_day_'+token+'.pdf}',r'\caption{'+representative['date'][5:]+r'的预报更新、购电调整与储能响应。}',r'\end{figure}']),encoding='utf-8')
    print(json.dumps(report['comparison'],ensure_ascii=False,indent=2))

if __name__=='__main__':main()
