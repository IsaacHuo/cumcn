"""Final cross-artifact checks after numerical, workbook and layout review."""
from pathlib import Path
import sys,json,hashlib
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'.deps'))
import pymupdf

checks={}
for name in ['main','deterministic','no_storage']:
    result=json.loads((ROOT/f'verification/q2/{name}_checks.json').read_text(encoding='utf-8'))
    assert result['passed'] and result['days']==334 and not result['fallback_events']
    checks[name]=result
layout=json.loads((ROOT/'verification/q2/pdf/checks.json').read_text(encoding='utf-8'))
assert not layout['layout_or_reference_warnings'],layout
xlsx=json.loads((ROOT/'verification/q2_xlsx_independent_checks.json').read_text(encoding='utf-8'))
assert xlsx['plan_days']==334 and xlsx['storage_rows']==2004 and not xlsx['template_residuals']
figures={}
for name in ['q2_year','q2_compare','q2_day_20250320','q2_day_20250621','q2_day_20250923','q2_day_20251221']:
    for extension in ['pdf','fig','png']:assert (ROOT/f'paper/figures/{name}.{extension}').stat().st_size>1000
    with pymupdf.open(ROOT/f'paper/figures/{name}.pdf') as doc:
        rasters=sum(len(p.get_images()) for p in doc)
        assert rasters==0,(name,rasters)
        figures[name]={'pages':len(doc),'raster_images':rasters}
files=[ROOT/'paper/build/main.pdf',ROOT/'paper/main.tex',ROOT/'paper/sections/q2.tex',ROOT/'results/result2.xlsx',ROOT/'results/q2_report.json',ROOT/'results/q2_detail.csv',ROOT/'code/plot_q2.m',ROOT/'code/solve_q2.py']
report={'passed':True,'numerical_checks':checks,'workbook':xlsx,'paper':layout,'matlab_vector_figures':figures,
    'sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}}
(ROOT/'verification/q2/delivery_checks.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'passed':True,'days_per_strategy':334,'paper_pages':layout['pages'],'matlab_figure_sets':len(figures),'xlsx_emergency_rows':xlsx['emergency_rows']},ensure_ascii=False))
