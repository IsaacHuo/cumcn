"""Check retained computation and revised paper/monochrome vector delivery."""
from pathlib import Path
import sys,json,hashlib,re
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'.deps'))
import pymupdf
from PIL import Image
import numpy as np
out=ROOT/'verification/paper_revision'
protected=json.loads((out/'protected_hashes.json').read_text(encoding='utf-8'))
for name,digest in protected.items():
    assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest,name
layout=json.loads((ROOT/'verification/q2/pdf/checks.json').read_text(encoding='utf-8'))
assert layout['pages']>15 and not layout['layout_or_reference_warnings']
matlab=json.loads((out/'matlab_checks.json').read_text(encoding='utf-8'))
assert matlab['passed'] and matlab['monochrome_figures']==15
figures={}
for path in (ROOT/'paper/figures').glob('*.pdf'):
    with pymupdf.open(path) as doc:
        assert len(doc)==1 and not doc[0].get_images(),path.name
    a=np.array(Image.open(path.with_suffix('.png')).convert('RGB'),dtype=np.int16)
    assert np.max(np.max(a,axis=2)-np.min(a,axis=2))<=3,path.name
    assert path.with_suffix('.fig').stat().st_size>1000
    figures[path.stem]={'vector':True,'monochrome':True}
assert len(figures)==15
with pymupdf.open(ROOT/'paper/build/main.pdf') as doc:
    text='\n'.join(p.get_text() for p in doc)
    for heading in ['问题重述','问题分析','模型假设','符号说明','数据处理与特征分析',
                    '模型建立与求解','模型检验与敏感性分析','模型评价与改进方向','结论','参考文献']:
        assert heading in text,heading
    assert '问题四' not in text
    assert '35126.9486' in text and '1453.6842' in text and '1382.9943' in text
    assert not any(p.get_images() for p in doc),'Raster figure found in paper'
    assert len(doc)==layout['pages']
src={p: p.read_text(encoding='utf-8') for p in (ROOT/'paper').rglob('*.tex') if 'build' not in p.parts}
labels=[]
for p,t in src.items():
    # Only included sections and generated tables are present in this project.
    labels+=re.findall(r'\\label\{([^}]+)\}',t)
assert len(labels)==len(set(labels)),'Duplicate labels'
files=[ROOT/'paper/build/main.pdf']+list((ROOT/'paper/sections').glob('*.tex'))+list((ROOT/'code').glob('plot*.m'))
result={'passed':True,'pages':layout['pages'],'protected_files_unchanged':len(protected),
        'figures':figures,'matlab_checks':matlab,
        'sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}}
(out/'delivery_checks.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k not in ['sha256','figures']},ensure_ascii=False))
