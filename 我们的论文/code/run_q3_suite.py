"""Run independent annual strategies in bounded parallel worker processes."""
from concurrent.futures import ProcessPoolExecutor,as_completed
from pathlib import Path
import contextlib,json,traceback
from solve_q3 import ROOT,VARIANTS,run

def one(variant):
    log=ROOT/'verification/q3'/f'run_{variant}.log'
    with log.open('a',encoding='utf-8',buffering=1) as f,contextlib.redirect_stdout(f),contextlib.redirect_stderr(f):
        try:run(variant);return {'variant':variant,'completed':True}
        except Exception:
            traceback.print_exc();return {'variant':variant,'completed':False}

if __name__=='__main__':
    (ROOT/'verification/q3').mkdir(parents=True,exist_ok=True)
    with ProcessPoolExecutor(max_workers=8) as executor:
        tasks=[executor.submit(one,v) for v in VARIANTS]
        for task in as_completed(tasks):print(json.dumps(task.result()),flush=True)
