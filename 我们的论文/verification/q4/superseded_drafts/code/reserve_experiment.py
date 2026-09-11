"""Reserve constrained Q2/Q3 experiment using temporary solver subclasses."""
from pathlib import Path
import json,numpy as np,importlib,sys
ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'results'/'reserve'; OUT.mkdir(parents=True,exist_ok=True)
sys.path.insert(0,str(ROOT/'code'));sys.path.insert(0,str(ROOT/'.deps'))
q2=importlib.import_module('solve_q2'); q3=importlib.import_module('solve_q3')
CAP,LOW,ETA,N,H=q2.CAP,q2.LOW,q2.ETA,q2.N,q2.H
class ReserveHorizonLP(q2.HorizonLP):
 def __init__(self,price,loads,pvs,prob,soc,target=6000.,capacity=CAP):
  super().__init__(price,loads,pvs,prob,soc,target,capacity); e=np.maximum(np.asarray(loads)-np.asarray(pvs),0); self.reserve=np.clip(np.quantile(e,.8,axis=0),0,capacity)
 def step(self,t,soc,load,pv,prob):
  c=[];lo=[];hi=[]
  for s in range(self.S):
   b=self.base(s)
   for u in range(t+1,H): c += [b+H+u,b+4*H+u];lo += [0,LOW+self.reserve[u]/ETA];hi += [max(0,self.capacity-self.reserve[u]),q2.HIGH]
  if c:self.h.changeColsBounds(len(c),np.asarray(c,np.int32),np.asarray(lo),np.asarray(hi))
  return super().step(t,soc,load,pv,prob)
class ReserveRevisionLP(q3.RevisionLP):
 def __init__(self,price,sc,soc,start,original=None,mode='refund',target=6000.):
  super().__init__(price,sc,soc,start,original,mode,target);e=np.maximum(np.asarray(sc['error_load'])-np.asarray(sc['error_pv']),0);self.reserve=np.clip(np.quantile(e,.8,axis=0),0,CAP)
 def revise(self,current):
  c=[];lo=[];hi=[]
  for s in range(self.S):
   b=self.base(s)
   for u in range(self.start,H):c += [b+H+u,b+4*H+u];lo += [0,LOW+self.reserve[u]/ETA];hi += [max(0,CAP-self.reserve[u]),q2.HIGH]
  if c:self.h.changeColsBounds(len(c),np.asarray(c,np.int32),np.asarray(lo),np.asarray(hi))
  return super().revise(current)
def main():
 price,L,P,dates=q2.read_inputs();wanted=['2025-03-20','2025-06-21','2025-09-23','2025-12-21'];out=[];old=q2.HorizonLP;q2.HorizonLP=ReserveHorizonLP
 try:
  for date in wanted:
   d=dates.index(date);r=q2.simulate_day(price,L[:d],P[:d],zip(L[d],P[d]),6000.,'main');np.savez(OUT/f'q2_{date.replace("-","")}.npz',result=r);out.append({'question':'q2','date':date,'total_cost':float(r['total_cost']),'emergency_total':float(np.sum(r['emergency_kwh'])),'final_soc':float(r['soc_kwh'][-1])})
 finally:q2.HorizonLP=old
 old=q3.RevisionLP;q3.RevisionLP=ReserveRevisionLP
 try:
  F=q3.read_forecasts()
  for date in wanted:
   d=dates.index(date);r=q3.simulate_day(price,L[:d],P[:d],F[:d],zip(L[d],P[d]),lambda h:F[d,h//6],6000.,updates=(6,12,18),adjustments=(6,12,18));np.savez(OUT/f'q3_{date.replace("-","")}.npz',result=r);out.append({'question':'q3','date':date,'total_cost':float(r['total_cost']),'emergency_total':float(np.sum(r['emergency_kwh'])),'final_soc':float(r['soc_kwh'][-1])})
 finally:q3.RevisionLP=old
 (OUT/'report.json').write_text(json.dumps({'runs':out},ensure_ascii=False,indent=2),encoding='utf-8')
if __name__=='__main__':main()
