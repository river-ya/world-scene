"""Copy both supplied architecture SVGs unchanged into the static website."""
import hashlib,json,pathlib,shutil,xml.etree.ElementTree as ET
ROOT=pathlib.Path(__file__).resolve().parents[1]
out=ROOT/'src/media/architecture'
entries=[]
for model,slug in [('FlashWorld','flashworld'),('LucidDreamer','luciddreamer')]:
 source=ROOT.parent/f'{model}_Architecture_v0.10.0.svg'
 root=ET.parse(source).getroot()
 assert root.tag=='{http://www.w3.org/2000/svg}svg','Expected an SVG document'
 entries.append((model,slug,source,root))
out.mkdir(parents=True,exist_ok=True)
records={}
for model,slug,source,root in entries:
 shutil.copyfile(source,out/f'{slug}-v0.10.0.svg')
 records[model]={'source':source.name,'sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'width':root.get('width'),'height':root.get('height'),'viewBox':root.get('viewBox'),'import':'Original SVG copied byte-for-byte; no conversion or redraw'}
 print('Imported',model,root.get('viewBox'))
(out/'source.json').write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n')
old=out/'flashworld-v0.10.0.pdf'
if old.exists():old.unlink()
