"""Rebuild question 1 from immutable input; all energy variables are grid-side kWh."""
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
if (ROOT / '.deps').exists():
    sys.path.insert(0, str(ROOT / '.deps'))
import csv
import json
import hashlib
import platform
import datetime as dt
import numpy as np
import scipy
from scipy.optimize import linprog, milp, Bounds, LinearConstraint
from openpyxl import load_workbook

N, STEP, LIMIT = 144, 1 / 6, 5000 / 6
SOC_MIN, SOC_MAX, INITIAL = 1200., 10800., 6000.
FEAS_TOL, COST_TOL = 1e-5, 1e-6

def clock(minutes):
    return f'{minutes // 60:02d}:{minutes % 60:02d}'

def inputs():
    path = ROOT / 'data/raw/附件1.xlsx'
    wb = load_workbook(path, read_only=True, data_only=True)
    raw = list(wb.active.values)[1:]
    wb.close()
    assert len(raw) == N
    for i, (time, *_) in enumerate(raw, 1):
        if isinstance(time, dt.time):
            minute = time.hour * 60 + time.minute
        elif time == '0:00+1':
            minute = 1440
        else:
            h, m = map(int, time.split(':'))
            minute = h * 60 + m
        assert minute == 10 * i, (i, time)
    a = np.asarray([r[1:] for r in raw], dtype=float)
    assert np.isfinite(a).all() and (a >= 0).all()
    return a[:, 0], a[:, 1] * STEP, a[:, 2] * STEP

def optimize(price, load, pv, eta):
    # x = [grid, charge, discharge, curtailment, E_0...E_144]
    size = 5 * N + 1
    a = np.zeros((2 * N, size))
    for t in range(N):
        a[t, [t, N+t, 2*N+t, 3*N+t]] = [1, -1, 1, -1]
        a[N+t, [N+t, 2*N+t, 4*N+t, 4*N+t+1]] = [-eta, 1/eta, -1, 1]
    rhs = np.r_[load-pv, np.zeros(N)]
    lower = np.r_[np.zeros(4*N), np.full(N+1, SOC_MIN)]
    upper = np.r_[np.full(N, np.inf), np.full(2*N, LIMIT), pv, np.full(N+1, SOC_MAX)]
    lower[4*N] = upper[4*N] = INITIAL
    lower[-1] = upper[-1] = INITIAL
    objective = np.r_[price, np.zeros(size-N)]
    turnover = np.zeros(size)
    turnover[N:3*N] = 1
    opts = {'dual_feasibility_tolerance': 1e-8, 'primal_feasibility_tolerance': 1e-8}
    first = linprog(objective, A_eq=a, b_eq=rhs, bounds=list(zip(lower, upper)), method='highs', options=opts)
    if not first.success:
        raise RuntimeError(first.message)
    second = linprog(turnover, A_eq=a, b_eq=rhs, A_ub=objective[None,:], b_ub=[first.fun+COST_TOL], bounds=list(zip(lower, upper)), method='highs', options=opts)
    if not second.success:
        raise RuntimeError(second.message)
    x, mode, optimum = second.x, 'LP', float(first.fun)
    if np.any((x[N:2*N] > FEAS_TOL) & (x[2*N:3*N] > FEAS_TOL)):
        # Binary u: charge <= LIMIT*u; discharge <= LIMIT*(1-u).
        aa = np.pad(a, ((0,0),(0,N)))
        mutual = np.zeros((2*N, size+N))
        for t in range(N):
            mutual[t,N+t], mutual[t,size+t] = 1, -LIMIT
            mutual[N+t,2*N+t], mutual[N+t,size+t] = 1, LIMIT
        constraints = [LinearConstraint(aa,rhs,rhs), LinearConstraint(mutual,-np.inf,np.r_[np.zeros(N),np.full(N,LIMIT)])]
        bounds = Bounds(np.r_[lower,np.zeros(N)],np.r_[upper,np.ones(N)])
        integrality = np.r_[np.zeros(size),np.ones(N)]
        primary = milp(np.r_[objective,np.zeros(N)], integrality=integrality, bounds=bounds, constraints=constraints, options={'mip_rel_gap':1e-10})
        if not primary.success:
            raise RuntimeError(primary.message)
        constraints.append(LinearConstraint(np.r_[objective,np.zeros(N)][None,:],-np.inf,primary.fun+COST_TOL))
        secondary = milp(np.r_[turnover,np.zeros(N)], integrality=integrality, bounds=bounds, constraints=constraints, options={'mip_rel_gap':1e-10})
        if not secondary.success:
            raise RuntimeError(secondary.message)
        x, mode, optimum = secondary.x[:size], 'MILP', float(primary.fun)
    assert np.max(np.abs(a @ x-rhs)) < FEAS_TOL
    assert np.min(x-lower) > -FEAS_TOL and np.min(upper-x) > -FEAS_TOL
    assert not np.any((x[N:2*N]>FEAS_TOL)&(x[2*N:3*N]>FEAS_TOL))
    return x, {'method':mode,'primary_optimum_yuan':optimum,'cost_tolerance_yuan':COST_TOL}

def package(price, load, pv, eta):
    x, solver = optimize(price,load,pv,eta)
    g,c,d,w = [x[k*N:(k+1)*N] for k in range(4)]
    e = x[4*N:]
    rows = []
    for t in range(N):
        rows.append(dict(interval=f'{clock(t*10)}-{clock((t+1)*10)}', source_end=clock((t+1)*10),price_yuan_per_kwh=float(price[t]),load_kwh=float(load[t]),pv_kwh=float(pv[t]),grid_kwh=float(g[t]),charge_kwh=float(c[t]),discharge_kwh=float(d[t]),curtail_kwh=float(w[t]),soc_start_kwh=float(e[t]),soc_end_kwh=float(e[t+1]),cost_yuan=float(price[t]*g[t])))
    blocks = [dict(interval=f'{clock(k*240)}-{clock((k+1)*240)}',charge_kwh=float(c[k*24:(k+1)*24].sum()),discharge_kwh=float(d[k*24:(k+1)*24].sum())) for k in range(6)]
    baseline = float(np.dot(price,np.maximum(load-pv,0)))
    cost = float(np.dot(price,g))
    summary = dict(cost_yuan=cost,grid_kwh=float(g.sum()),charge_kwh=float(c.sum()),discharge_kwh=float(d.sum()),curtail_kwh=float(w.sum()),initial_kwh=float(e[0]),final_kwh=float(e[-1]),min_soc_kwh=float(e.min()),max_soc_kwh=float(e.max()),baseline_cost_yuan=baseline,baseline_grid_kwh=float(np.maximum(load-pv,0).sum()),baseline_curtail_kwh=float(np.maximum(pv-load,0).sum()),saving_yuan=baseline-cost,saving_percent=100*(baseline-cost)/baseline,loss_kwh=float(((1-eta)*c+(1/eta-1)*d).sum()),load_kwh=float(load.sum()),pv_kwh=float(pv.sum()))
    return dict(eta=eta,solver=solver,rows=rows,blocks=blocks,summary=summary)

def table_tex(data, alternate):
    folder = ROOT/'paper/tables'
    s=data['summary']
    def fmt(v): return f'{v:.4f}'
    def texfile(name, text): (folder/name).write_text(text,encoding='utf-8')
    rows = data['rows']
    lines = [r'\begin{tabular}{lr lr lr}',r'\toprule',r'时间段 & 购电量 & 时间段 & 购电量 & 时间段 & 购电量 \\',r'\midrule']
    for hours in [(10,12,14),(16,18,20)]:
        lines.append(' & '.join(f'{h:02d}:00--{h:02d}:10 & {fmt(rows[h*6]["grid_kwh"])}' for h in hours)+r' \\')
    lines.extend([r'\midrule',f'全天购电量 & {fmt(s["grid_kwh"])} & 全天购电费 & {fmt(s["cost_yuan"])} & & '+r'\\',r'\bottomrule',r'\end{tabular}'])
    texfile('q1_purchase.tex','\n'.join(lines))
    lines=[r'\begin{tabular}{lrr lrr}',r'\toprule',r'时间段 & 充电量 & 放电量 & 时间段 & 充电量 & 放电量 \\',r'\midrule']
    for i in [0,2,4]:
        lines.append(' & '.join(f'{b["interval"].replace("-","--")} & {fmt(b["charge_kwh"])} & {fmt(b["discharge_kwh"])}' for b in data['blocks'][i:i+2])+r' \\')
    lines.extend([r'\midrule',r'0:00储电量 & \multicolumn{2}{r}{6000.0000} & 24:00储电量 & \multicolumn{2}{r}{6000.0000} \\',r'\bottomrule',r'\end{tabular}'])
    texfile('q1_storage.tex','\n'.join(lines))
    macros={'QoneCost':s['cost_yuan'],'QoneGrid':s['grid_kwh'],'BaseCost':s['baseline_cost_yuan'],'Saving':s['saving_yuan'],'SavingPercent':s['saving_percent'],'ChargeTotal':s['charge_kwh'],'DischargeTotal':s['discharge_kwh'],'LossTotal':s['loss_kwh'],'AltCost':alternate['summary']['cost_yuan'],'AltDifference':alternate['summary']['cost_yuan']-s['cost_yuan'],'BaseCurtail':s['baseline_curtail_kwh']}
    texfile('q1_values.tex','\n'.join('\\newcommand{\\'+k+'}{'+fmt(v)+'}' for k,v in macros.items()))

def main():
    price,load,pv=inputs()
    data=package(price,load,pv,.9);alt=package(price,load,pv,float(np.sqrt(.9)))
    for name,obj in [('q1.json',data),('q1_efficiency_sensitivity.json',alt)]:
        (ROOT/'results'/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
    with (ROOT/'results/q1_detail.csv').open('w',newline='',encoding='utf-8-sig') as f:
        writer=csv.DictWriter(f,fieldnames=list(data['rows'][0]));writer.writeheader();writer.writerows(data['rows'])
    table_tex(data,alt)
    provenance={'python':platform.python_version(),'numpy':np.__version__,'scipy':scipy.__version__,'source_sha256':hashlib.sha256((ROOT/'data/raw/附件1.xlsx').read_bytes()).hexdigest(),'solver_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    (ROOT/'verification/environment.json').write_text(json.dumps(provenance,indent=2),encoding='utf-8')
    print(json.dumps({'main':data['summary'],'alternative':alt['summary'],'solver':data['solver']},ensure_ascii=False,indent=2))

if __name__=='__main__':main()
