"""Render the compiled paper for manual visual review and scan layout warnings."""
from pathlib import Path
import sys,json,re
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'.deps'))
import fitz
from PIL import Image,ImageDraw

out=ROOT/'verification/q2/pdf';out.mkdir(parents=True,exist_ok=True)
doc=fitz.open(ROOT/'paper/build/main.pdf');thumbs=[]
for i,page in enumerate(doc):
    pix=page.get_pixmap(matrix=fitz.Matrix(1.4,1.4))
    pix.save(str(out/f'page_{i+1:02d}.png'))
    im=Image.open(out/f'page_{i+1:02d}.png').convert('RGB');im.thumbnail((340,485))
    canvas=Image.new('RGB',(360,520),'#dddddd');canvas.paste(im,((360-im.width)//2,20))
    ImageDraw.Draw(canvas).text((10,500),f'Page {i+1}',fill='black');thumbs.append(canvas)
for start in range(0,len(thumbs),8):
    batch=thumbs[start:start+8];contact=Image.new('RGB',(360*4,520*((len(batch)+3)//4)),'white')
    for i,im in enumerate(batch):contact.paste(im,((i%4)*360,(i//4)*520))
    contact.save(out/f'contact_{start//8+1}.png')
log=(ROOT/'paper/build/main.log').read_text(encoding='utf-8',errors='replace')
warnings=[line for line in log.splitlines() if any(k in line for k in ['Overfull','Missing character','undefined'])]
summary={'pages':len(doc),'layout_or_reference_warnings':warnings,'text_characters':sum(len(p.get_text()) for p in doc)}
(out/'checks.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(summary,ensure_ascii=False,indent=2))
