"""Final cross-artifact gate after independent numerical and visual review."""
from solve_q3 import ROOT,VARIANTS,np,json,hashlib
import pymupdf

checks=[]
for v in VARIANTS:
    d=json.loads((ROOT/'verification/q3'/f'{v}_checks.json').read_text(encoding='utf-8'))
    assert d['days']==334 and not d['fallback_events']
    checks.append(d)
layout=json.loads((ROOT/'verification/q2/pdf/checks.json').read_text(encoding='utf-8'))
assert layout['pages'] > 0 and layout['text_characters'] > 1000
assert not layout['layout_or_reference_warnings']
xlsx=json.loads((ROOT/'verification/q3导出检查/q3_xlsx_independent_checks.json').read_text(encoding='utf-8'))
assert xlsx['plan_days']==334 and xlsx['storage_rows']==2004 and not xlsx['template_residuals']
figures={}
for name in ['q3_year','q3_compare','q3_day_20250320','q3_day_20250621','q3_day_20250923','q3_day_20251221']:
    for ext in ['pdf','png','fig']:assert (ROOT/f'paper/figures/{name}.{ext}').stat().st_size>1000
    with pymupdf.open(ROOT/f'paper/figures/{name}.pdf') as doc:
        assert sum(len(p.get_images()) for p in doc)==0
        figures[name]=dict(pages=len(doc),vector=True)
with (ROOT/'results/q3_detail.csv').open(encoding='utf-8-sig') as f:assert sum(1 for _ in f)==48097
files=[ROOT/'paper/build/main.pdf',ROOT/'paper/main.tex',ROOT/'paper/sections/q3.tex',ROOT/'results/result3.xlsx',ROOT/'results/q3_report.json',ROOT/'results/q3_detail.csv',ROOT/'code/solve_q3.py',ROOT/'code/plot_q3.m']
result=dict(passed=True,strategies=10,days_per_strategy=334,numerical=checks,paper=layout,workbook=xlsx,figures=figures,
            sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files})
(ROOT/'verification/q3/delivery_checks.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(dict(passed=True,strategies=10,paper_pages=layout['pages'],figure_sets=6),ensure_ascii=False))
