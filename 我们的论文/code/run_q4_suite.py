"""Run independent annual variants with isolated checkpoints and logs."""
from pathlib import Path
import subprocess,sys,time,json,os
ROOT=Path(__file__).resolve().parents[1]
VARIANTS=['q2','forecast0','h6','h12','h18','h6_12','h6_18','h12_18','main','q2_point','main_point']
if __name__=='__main__':
    assert json.loads((ROOT/'verification/q4/tests.json').read_text(encoding='utf-8'))['passed']
    logs=ROOT/'verification/q4/logs';logs.mkdir(exist_ok=True)
    procs=[]
    for v in VARIANTS:
        stream=(logs/f'{v}.log').open('w',encoding='utf-8')
        env=dict(os.environ,PYTHONIOENCODING='utf-8',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
        p=subprocess.Popen([sys.executable,str(ROOT/'code/solve_q4.py'),'--variant',v],stdout=stream,stderr=subprocess.STDOUT,env=env,creationflags=0x08000000 if os.name=='nt' else 0)
        procs.append((v,p,stream))
    while any(p.poll() is None for _,p,_ in procs):
        print(json.dumps({v:dict(days=len(list((ROOT/'results/q4'/v).glob('2025-*.npz'))),status=p.poll()) for v,p,_ in procs}),flush=True)
        time.sleep(45)
    result={v:p.returncode for v,p,_ in procs}
    for _,_,s in procs:s.close()
    (ROOT/'verification/q4/suite_status.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    assert not any(result.values()),result
    print('ANNUAL SUITE COMPLETE',flush=True)
