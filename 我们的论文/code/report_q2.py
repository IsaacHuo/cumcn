"""Generate publication tables and interchange data from checked checkpoints."""
from solve_q2 import *
from validate_q2 import check

SELECTED=['2025-03-20','2025-06-21','2025-09-23','2025-12-21']
LABELS={'no_storage':'无储能多情景购电','deterministic':'单预测计划+滚动控制','main':'多情景计划+滚动控制'}

def clock(minutes):return f'{minutes//60:02d}:{minutes%60:02d}'

def money(value):return f'{0.0 if abs(value)<0.005 else value:.2f}'

def intervals(values):
    active=np.asarray(values)>TOL;events=[];start=None
    for t in range(N+1):
        on=bool(active[t]) if t<N else False
        if on and start is None:start=t
        if not on and start is not None:
            events.append({'interval':f'{clock(start*10)}-{clock(t*10)}','kwh':float(np.sum(values[start:t]))});start=None
    return events

def get_day(path):
    with np.load(path) as r:
        d={k:np.array(r[k]) for k in r.files}
    blocks=[]
    for k in range(6):blocks.append({'interval':f'{clock(k*240)}-{clock((k+1)*240)}','charge_kwh':float(d['charge_kwh'][k*24:(k+1)*24].sum()),'discharge_kwh':float(d['discharge_kwh'][k*24:(k+1)*24].sum())})
    events=intervals(d['emergency_kwh'])
    assert abs(sum(x['kwh'] for x in events)-d['emergency_kwh'].sum())<TOL
    summary={'date':path.stem,'plan_cost':float(d['plan_cost']),'emergency_cost':float(d['emergency_cost']),'total_cost':float(d['total_cost']),
             'plan_total':float(d['plan_kwh'].sum()),'emergency_total':float(d['emergency_kwh'].sum()),'unused_total':float(d['unused_kwh'].sum()),
             'soc_start':float(d['soc_kwh'][0]),'soc_end':float(d['soc_kwh'][-1]),'expected_emergency_cost':float(d['expected_emergency_cost']),
             'blocks':blocks,'emergency_intervals':events,'elapsed_seconds':float(d['elapsed_seconds'])}
    return d,summary

def table(headers,rows,align):
    return '\n'.join(['\\begin{tabular}{'+align+'}',r'\toprule',' & '.join(headers)+r' \\',r'\midrule']+[' & '.join(map(str,r))+r' \\' for r in rows]+[r'\bottomrule',r'\end{tabular}'])

def main():
    price,_,_,_=read_inputs();report={'daily':[],'selected':[],'comparison':[]};export={'days':[]};selected=[]
    folder=ROOT/'paper/tables';checks=[]
    for variant in ['no_storage','deterministic','main']:
        checks.append(check(variant))
        summaries=[]
        for file in sorted((ROOT/'results/q2'/variant).glob('2025-*.npz')):
            d,s=get_day(file);summaries.append(s)
            if variant=='main':
                report['daily'].append(s)
                export['days'].append({**s,'plan_kwh':d['plan_kwh'].tolist()})
                if s['date'] in SELECTED:
                    report['selected'].append({**s,**{k:d[k].tolist() for k in ['plan_kwh','load_kwh','pv_kwh','forecast_load_kwh','forecast_pv_kwh','charge_kwh','discharge_kwh','emergency_kwh','unused_kwh','soc_kwh']}})
                    selected.append((d,s))
        comp={'name':LABELS[variant],'variant':variant,'total_cost':sum(s['total_cost'] for s in summaries),'plan_cost':sum(s['plan_cost'] for s in summaries),'emergency_cost':sum(s['emergency_cost'] for s in summaries),
              'emergency_total':sum(s['emergency_total'] for s in summaries),'emergency_days':sum(s['emergency_total']>TOL for s in summaries),'unused_total':sum(s['unused_total'] for s in summaries),
              'final_soc':summaries[-1]['soc_end'],'plan_total':sum(s['plan_total'] for s in summaries),'expected_emergency_cost':sum(s['expected_emergency_cost'] for s in summaries)}
        comp['inventory_adjusted_cost']=comp['total_cost']-float(price.min()/ETA)*(comp['final_soc']-INITIAL)
        report['comparison'].append(comp)
    bound=json.loads((ROOT/'results/q2/perfect_information.json').read_text(encoding='utf-8'))
    report['comparison'].append(bound)
    sensitivities=json.loads((ROOT/'results/q2/sensitivity.json').read_text(encoding='utf-8'));assert len(sensitivities)==12
    report['sensitivity']=sensitivities
    (ROOT/'results/q2_export.json').write_text(json.dumps(export,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    (ROOT/'results/q2_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    compactkeys=['date','plan_total','emergency_total','plan_cost','emergency_cost','total_cost','unused_total','soc_start','soc_end','expected_emergency_cost']
    with (ROOT/'results/q2_daily.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=compactkeys,extrasaction='ignore');writer.writeheader();writer.writerows(report['daily'])
    # Complete executed detail, one row per actual ten-minute interval.
    with (ROOT/'results/q2_detail.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.writer(f);writer.writerow(['date','interval','price_yuan_per_kwh','plan_kwh','load_kwh','pv_kwh','charge_kwh','discharge_kwh','emergency_kwh','unused_kwh','soc_start_kwh','soc_end_kwh','plan_cost_yuan','emergency_cost_yuan'])
        for file in sorted((ROOT/'results/q2/main').glob('2025-*.npz')):
            d,s=get_day(file)
            for t in range(N):writer.writerow([file.stem,f'{clock(10*t)}-{clock(10*(t+1))}',price[t]]+[d[k][t] for k in ['plan_kwh','load_kwh','pv_kwh','charge_kwh','discharge_kwh','emergency_kwh','unused_kwh']]+[d['soc_kwh'][t],d['soc_kwh'][t+1],price[t]*d['plan_kwh'][t],5*price[t]*d['emergency_kwh'][t]])
    rows=[]
    for c in report['comparison']:rows.append([c['name'],f"{c['total_cost']/10000:.4f}",f"{c['emergency_total']:.2f}",str(c['emergency_days']),f"{c['unused_total']:.2f}",f"{c['final_soc']:.2f}"])
    (folder/'q2_comparison.tex').write_text(table(['策略','总费用/万元','紧急电量/kWh','发生天数','未利用电量/kWh','期末储电/kWh'],rows,'lrrrrr'),encoding='utf-8')
    rows=[]
    for d,s in selected:rows.append([s['date'][5:]]+[f"{s[k]:.2f}" for k in ['plan_cost','emergency_cost','total_cost','plan_total','emergency_total','soc_start','soc_end']])
    (folder/'q2_selected_summary.tex').write_text(table(['日期','计划费','紧急费','总费用','计划电量','紧急电量','日初储电','日末储电'],rows,'lrrrrrrr'),encoding='utf-8')
    # Six purchase slots: columns are quantities bought under the locked plan.
    rows=[]
    for h in [10,12,14,16,18,20]:rows.append([f'{h}:00--{h}:10']+[f"{d['plan_kwh'][h*6]:.4f}" for d,s in selected])
    (folder/'q2_purchase.tex').write_text(table(['时段']+[s['date'][5:] for d,s in selected],rows,'lrrrr'),encoding='utf-8')
    rows=[]
    for k in range(6):
        rows.append([selected[0][1]['blocks'][k]['interval'].replace('-','--')]+[f"{s['blocks'][k][v]:.2f}" for d,s in selected for v in ['charge_kwh','discharge_kwh']])
    h=[r'\multirow{2}{*}{时段}']+[r'\multicolumn{2}{c}{'+date[5:]+'}' for date in SELECTED]
    text='\n'.join([r'\begin{tabular}{lrrrrrrrr}',r'\toprule',' & '.join(h)+r' \\',' & '+' & '.join(['充电','放电']*4)+r' \\',r'\midrule']+[' & '.join(r)+r' \\' for r in rows]+[r'\bottomrule',r'\end{tabular}'])
    (folder/'q2_storage.tex').write_text(text,encoding='utf-8')
    rows=[]
    for d,s in selected:
        events=s['emergency_intervals'] or [{'interval':'无','kwh':0}]
        for i,e in enumerate(events):rows.append([s['date'][5:] if i==0 else '',e['interval'].replace('-','--'),f"{e['kwh']:.4f}"])
    (folder/'q2_emergency.tex').write_text(table(['日期','紧急购电时段','电量/kWh'],rows,'llr'),encoding='utf-8')
    rows=[[r['date'][5:],r['setting'],money(r['cost_difference']),money(r['emergency_difference']),money(r['final_soc']),money(r['inventory_adjusted_difference'])] for r in sensitivities]
    (folder/'q2_sensitivity.tex').write_text(table(['日期','设置','费用变化/元','紧急量变化/kWh','日末储电/kWh','库存校正变化/元'],rows,'llrrrr'),encoding='utf-8')
    ns,de,ma=report['comparison'][:3]
    macros={'QtwoCost':ma['total_cost']/10000,'QtwoEmergency':ma['emergency_total'],'QtwoEmergencyCost':ma['emergency_cost']/10000,'QtwoPlanCost':ma['plan_cost']/10000,
            'QtwoDays':ma['emergency_days'],'QtwoUnused':ma['unused_total'],'QtwoEnd':ma['final_soc'],'QtwoNoStorageSaving':100*(ns['total_cost']-ma['total_cost'])/ns['total_cost'],
            'QtwoDetDifference':ma['total_cost']-de['total_cost'],'QtwoLower':bound['total_cost']/10000,'QtwoGap':100*(ma['total_cost']-bound['total_cost'])/bound['total_cost'],
            'QtwoExpectedEmergency':ma['expected_emergency_cost']/10000,'QtwoInventoryPrice':float(price.min()/ETA),
            'QtwoAdjustedDifference':ma['inventory_adjusted_cost']-de['inventory_adjusted_cost']}
    (folder/'q2_values.tex').write_text('\n'.join('\\newcommand{\\'+k+'}{'+(str(int(v)) if k=='QtwoDays' else f'{v:.4f}')+'}' for k,v in macros.items()),encoding='utf-8')
    # Conditional prose follows observed comparison, without forcing superiority.
    if ma['total_cost']<de['total_cost']:
        comparison=f'与单预测日前计划相比，多情景方案减少实际购电费用{de["total_cost"]-ma["total_cost"]:.2f}元。'
    else:comparison=f'与单预测日前计划相比，多情景方案的实际购电费用增加{ma["total_cost"]-de["total_cost"]:.2f}元，说明本组历史情景构造尚未带来费用优势。'
    comparison+=f'两方案紧急购电量分别为{ma["emergency_total"]:.2f}和{de["emergency_total"]:.2f} kWh。'
    comparison+=f'主方案增加计划购电支出{ma["plan_cost"]-de["plan_cost"]:.2f}元，同时减少紧急购电支出{de["emergency_cost"]-ma["emergency_cost"]:.2f}元。费用改善来自这两项变化的净效应；其未利用供给也比单预测方案增加{ma["unused_total"]-de["unused_total"]:.2f} kWh，表明更保守的购电安排仍有消纳代价。'
    (folder/'q2_comparison_text.tex').write_text(comparison,encoding='utf-8')
    representative=max(report['selected'],key=lambda s:s['emergency_total'])
    token=representative['date'].replace('-','')
    figure='\n'.join([r'\begin{figure}[htbp]\centering',
        r'\includegraphics[width=\textwidth,height=.48\textheight,keepaspectratio]{figures/q2_day_'+token+'.pdf}',
        r'\caption{'+representative['date'][5:]+r'的净负荷预测偏差、实际储电量与紧急购电响应。}\label{fig:q2response}',
        r'\end{figure}'])
    (folder/'q2_selected_figures.tex').write_text(figure,encoding='utf-8')
    print(json.dumps(report['comparison'],ensure_ascii=False,indent=2))

if __name__=='__main__':main()
