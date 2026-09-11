"""Whole-evaluation-period perfect-information lower bound, not an online policy."""
from solve_q2 import *
from solve_q4 import read_prices

def main():
    price,L,P,dates=read_inputs();load=L[31:].ravel();pv=P[31:].ravel();n=len(load)
    price=read_prices()[31:].ravel();t=np.arange(n);nvar=5*n+1
    # grid, charge, discharge, unused, 145*334 continuous SOC states (n+1).
    rows=np.r_[t,t,t,t,n+t,n+t,n+t,n+t]
    cols=np.r_[t,n+t,2*n+t,3*n+t,4*n+t,4*n+t+1,n+t,2*n+t]
    vals=np.r_[np.ones(n),-np.ones(n),np.ones(n),-np.ones(n),-np.ones(n),np.ones(n),np.full(n,-ETA),np.full(n,1/ETA)]
    a=coo_matrix((vals,(rows,cols)),shape=(2*n,nvar)).tocsc()
    cost=np.r_[price,np.zeros(4*n+1)]
    lower=np.r_[np.zeros(4*n),np.full(n+1,LOW)]
    upper=np.r_[np.full(n,np.inf),np.full(2*n,CAP),pv,np.full(n+1,HIGH)]
    lower[4*n]=upper[4*n]=INITIAL
    rhs=np.r_[load-pv,np.zeros(n)]
    lp=highspy.HighsLp();lp.num_col_=nvar;lp.num_row_=2*n
    lp.col_cost_=cost;lp.col_lower_=lower;lp.col_upper_=upper;lp.row_lower_=rhs;lp.row_upper_=rhs
    lp.a_matrix_.format_=highspy.MatrixFormat.kColwise;lp.a_matrix_.start_=a.indptr.astype(np.int32);lp.a_matrix_.index_=a.indices.astype(np.int32);lp.a_matrix_.value_=a.data
    h=highspy.Highs();h.setOptionValue('output_flag',False);h.setOptionValue('threads',1);h.setOptionValue('solver','simplex')
    h.passModel(lp);start=time.perf_counter();h.run()
    assert h.getModelStatus()==highspy.HighsModelStatus.kOptimal
    x=np.array(h.getSolution().col_value);residual=float(abs(a@x-rhs).max())
    assert residual<TOL
    result={'name':'完全信息下界','total_cost':float(cost@x),'emergency_total':0.,'emergency_days':0,'unused_total':float(x[3*n:4*n].sum()),'final_soc':float(x[-1]),
            'max_balance_or_soc_error':residual,'elapsed_seconds':time.perf_counter()-start,'terminal_condition':'Free within [1200,10800]; initial 6000; therefore valid lower bound for all tested terminal inventories.'}
    np.savez_compressed(ROOT/'results/q4/perfect_information.npz',plan_kwh=x[:n].reshape(-1,N),charge_kwh=x[n:2*n].reshape(-1,N),discharge_kwh=x[2*n:3*n].reshape(-1,N),unused_kwh=x[3*n:4*n].reshape(-1,N),soc_kwh=x[4*n:])
    (ROOT/'results/q4/perfect_information.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(result,ensure_ascii=False))

if __name__=='__main__':main()
