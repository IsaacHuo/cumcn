"""Build Q4 report tables from daily NPZ records."""
import argparse,json,csv
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]; VARIANTS=['q2','forecast0','h6','h12','h18','h6_12','h6_18','h12_18','main','q2_point','main_point']; DATES=['2025-03-20','2025-06-21','2025-09-23','2025-12-21']
def clock(m):return f'{m//60:02d}:{m%60:02d}'
def safe(x):
 if isinstance(x,np.ndarray):return [safe(v) for v in x.tolist()]
 if isinstance(x,np.generic):return safe(x.item())
 if isinstance(x,float) and not np.isfinite(x):return None
 if isinstance(x,dict):return {k:safe(v) for k,v in x.items()}
 if isinstance(x,list):return [safe(v) for v in x]
 return x
def spans(x):
 out=[];i=0
 while i<144:
  if x[i]<=1e-5:i+=1;continue
  j=i+1
  while j<144 and x[j]>1e-5:j+=1
  out.append({'interval':f'{clock(10*i)}-{clock(10*j)}','kwh':float(x[i:j].sum())});i=j
 return out
def rec(f):
 with np.load(f) as z:r={k:np.array(z[k]) for k in z.files}
 keys=['plan_cost','refund','penalty','extra_cost','emergency_cost','total_cost','increase_total','decrease_total'];d=dict(date=f.stem,**{k:float(r[k]) for k in keys},plan_total=float(r['plan_kwh'].sum()),adjusted_total=float(r['adjusted_kwh'].sum()),emergency_total=float(r['emergency_kwh'].sum()),unused_total=float(r['unused_kwh'].sum()),soc_start=float(r['soc_kwh'][0]),soc_end=float(r['soc_kwh'][-1]),expected_emergency_cost=float(r['expected_emergency_cost']))
 d['blocks']=[{'interval':f'{clock(240*i)}-{clock(240*(i+1))}','charge_kwh':float(r['charge_kwh'][24*i:24*i+24].sum()),'discharge_kwh':float(r['discharge_kwh'][24*i:24*i+24].sum())} for i in range(6)];d['emergency_intervals']=spans(r['emergency_kwh']);return r,d
def tex(h,rows):
 esc=lambda s:str(s).replace('_',r'\_');return '\\begin{tabular}{'+'l'+'r'*(len(h)-1)+'}\toprule\n'+' & '.join(map(esc,h))+r'\\midrule'+'\n'+'\n'.join(' & '.join(map(esc,x))+r'\\' for x in rows)+'\n\\bottomrule\n\\end{tabular}\n'
def main(partial=False):
 report={'comparison':[],'selected':[],'daily':[]};tables=ROOT/'paper/tables';tables.mkdir(parents=True,exist_ok=True)
 for v in VARIANTS:
  folder=ROOT/'results/q4'/v
  if partial and not folder.exists(): folder=ROOT/'results/q4'/('pilot_'+v)
  fs=sorted(folder.glob('2025-*.npz'))
  if len(fs)!=334 and not partial:raise RuntimeError(f'{v}: expected 334, got {len(fs)}')
  if not fs:continue
  rows=[]
  for f in fs:
   r,d=rec(f);rows.append(d)
   if v=='main':
    report['daily'].append(d)
    if d['date'] in DATES:report['selected'].append({**d,**{k:safe(r[k]) for k in ['plan_kwh','adjusted_kwh','charge_kwh','discharge_kwh','emergency_kwh','unused_kwh','soc_kwh','price_actual','forecast_price'] if k in r}})
  c={k:sum(d[k] for d in rows) for k in ['plan_cost','refund','penalty','extra_cost','emergency_cost','total_cost','increase_total','decrease_total','plan_total','adjusted_total','emergency_total','unused_total','expected_emergency_cost']};c.update(variant=v,emergency_days=sum(d['emergency_total']>1e-5 for d in rows),final_soc=rows[-1]['soc_end']);report['comparison'].append(c)
 (ROOT/'results/q4_report.json').write_text(json.dumps(safe(report),ensure_ascii=False,indent=2),encoding='utf-8')
 (tables/'q4_values.tex').write_text('\n'.join(f'\\newcommand{{\\Qfour{key}}}{{{v:.4f}}}' for key,v in [('Cost',report['comparison'][-1]['total_cost']/1e4),('Emergency',report['comparison'][-1]['emergency_total'])])+'\n',encoding='utf-8')
 (tables/'q4_comparison.tex').write_text(tex(['策略','费用/万元','紧急电量/kWh','天数','期末SOC/kWh'],[[c['variant'],f"{c['total_cost']/1e4:.4f}",f"{c['emergency_total']:.2f}",str(c['emergency_days']),f"{c['final_soc']:.2f}"] for c in report['comparison']]),encoding='utf-8')
 (tables/'q4_selected.tex').write_text(tex(['日期','原计划','调整后','紧急购电','总费用/元','日初SOC','日末SOC'],[[d['date'][5:],f"{d['plan_total']:.2f}",f"{d['adjusted_total']:.2f}",f"{d['emergency_total']:.2f}",f"{d['total_cost']:.2f}",f"{d['soc_start']:.2f}",f"{d['soc_end']:.2f}"] for d in report['selected']]),encoding='utf-8')
 for name,field in [('q4_purchase.tex','plan_kwh'),('q4_adjusted.tex','adjusted_kwh'),('q4_storage.tex','charge_kwh'),('q4_emergency.tex','emergency_intervals')]:
  rows=[]
  for d in report['selected']:
   if field in ('plan_kwh','adjusted_kwh'):rows += [[d['date'][5:],clock(10*t),f'{d[field][t]:.2f}'] for t in range(144)]
   elif field=='charge_kwh':rows += [[d['date'][5:],b['interval'],f"{b['charge_kwh']:.2f}",f"{b['discharge_kwh']:.2f}"] for b in d['blocks']]
   else:rows += [[d['date'][5:],e['interval'],f"{e['kwh']:.2f}"] for e in (d[field] or [{'interval':'无','kwh':0}])]
  (tables/name).write_text(tex(['日期','时段','数值/kWh'] if field!='charge_kwh' else ['日期','时段','充电/kWh','放电/kWh'],rows),encoding='utf-8')
 with (ROOT/'results/q4_daily.csv').open('w',encoding='utf-8-sig',newline='') as f:
  cols=['date','plan_cost','total_cost','emergency_cost','emergency_total','unused_total','soc_start','soc_end'];w=csv.DictWriter(f,fieldnames=cols);w.writeheader();w.writerows([{k:d[k] for k in cols} for d in report['daily']])
 print(json.dumps(report['comparison'],ensure_ascii=False))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--allow-partial',action='store_true');main(p.parse_args().allow_partial)
