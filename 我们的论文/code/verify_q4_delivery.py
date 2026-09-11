"""One final delivery pass: retained data, final outputs, and page previews."""
from pathlib import Path
import sys,json,re,hashlib
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'.deps'))
import pymupdf
import numpy as np
from PIL import Image,ImageDraw

def main():
    out=ROOT/'verification/q4/final';out.mkdir(parents=True,exist_ok=True)
    old=json.loads((ROOT/'verification/paper_revision/protected_hashes.json').read_text(encoding='utf-8'))
    for rel,digest in old.items():assert hashlib.sha256((ROOT/rel).read_bytes()).hexdigest()==digest,rel
    tests=json.loads((ROOT/'verification/q4/tests.json').read_text(encoding='utf-8'));assert tests['passed']
    full=json.loads((ROOT/'verification/q4/full_validation.json').read_text(encoding='utf-8'));assert full['passed'] and not full['events']
    books=json.loads((ROOT/'verification/q4/workbooks/validation.json').read_text(encoding='utf-8'));assert len(books)==2 and all(x['passed'] for x in books)
    reserve=json.loads((ROOT/'results/reserve_verified/report.json').read_text(encoding='utf-8'));assert len(reserve['runs'])==8
    for row in reserve['runs']:
        with np.load(ROOT/f"results/{row['question']}/main/{row['date']}.npz") as z:assert abs(row['initial_soc']-float(z['soc_kwh'][0]))<1e-5
        with np.load(ROOT/f"results/reserve_verified/{row['question']}_{row['date']}.npz") as z:
            assert abs(float(z['soc_kwh'][0])-row['initial_soc'])<1e-5
            assert abs(z['soc_kwh'][1:]-z['soc_kwh'][:-1]-.9*z['charge_kwh']+z['discharge_kwh']/.9).max()<1e-5
    figures=[]
    for p in (ROOT/'paper/figures').glob('*.pdf'):
        with pymupdf.open(p) as doc:assert len(doc)==1 and not doc[0].get_images(),p.name
        assert p.with_suffix('.fig').exists() and p.with_suffix('.png').exists()
        pixels=np.asarray(Image.open(p.with_suffix('.png')).convert('RGB'),dtype=np.int16)
        assert np.max(pixels.max(2)-pixels.min(2))<=3,p.name
        figures.append(p.stem)
    assert len(figures)==22,(len(figures),figures)
    log=(ROOT/'paper/build/main.log').read_text(encoding='utf-8',errors='replace')
    warnings=[s for s in log.splitlines() if any(k in s for k in ['Overfull','Missing character','undefined','Rerun to get'])]
    assert not warnings,warnings
    report=json.loads((ROOT/'results/q4_report.json').read_text(encoding='utf-8'))
    thumbs=[]
    with pymupdf.open(ROOT/'paper/build/main.pdf') as doc:
        text='\n'.join(p.get_text() for p in doc)
        assert '问题四' in text and '问题一' in text and '问题二' in text and '问题三' in text
        assert '针对问题四' in doc[0].get_text() and '问题重述' in doc[1].get_text()
        for v in ['q2','main']:
            value=next(x['total_cost'] for x in report['comparison'] if x['variant']==v)
            assert f'{value/1e4:.4f}' in text
        assert '33801.4955' not in text and '1325.4530' not in text
        pages=len(doc)
        for i,p in enumerate(doc):
            pix=p.get_pixmap(matrix=pymupdf.Matrix(1.2,1.2));file=out/f'page_{i+1:02d}.png';pix.save(str(file))
            im=Image.open(file).convert('RGB');im.thumbnail((340,480));canvas=Image.new('RGB',(360,515),'#dddddd')
            canvas.paste(im,((360-im.width)//2,10));ImageDraw.Draw(canvas).text((10,495),f'Page {i+1}',fill='black');thumbs.append(canvas)
    for start in range(0,len(thumbs),8):
        batch=thumbs[start:start+8];contact=Image.new('RGB',(1440,515*((len(batch)+3)//4)),'white')
        for i,im in enumerate(batch):contact.paste(im,((i%4)*360,(i//4)*515))
        contact.save(out/f'contact_{start//8+1}.png')
    result=dict(passed=True,pages=pages,retained_files=len(old),annual_variants=len(full['variants']),annual_days_per_variant=334,reserve_experiments=8,monochrome_vector_figures=len(figures),workbooks=books,layout_warnings=warnings,pdf_sha256=hashlib.sha256((ROOT/'paper/build/main.pdf').read_bytes()).hexdigest())
    (out/'checks.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(result,ensure_ascii=False))

if __name__=='__main__':main()
