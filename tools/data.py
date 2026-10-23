"""Freeze a small, scene-disjoint indoor WorldScore subset before inference."""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path, PurePosixPath
import zipfile
from assets import blob_path, valid
from common import lock, sha256, write_json


def select_scenes(rows, dev=6, test=12):
    unique={}
    for row in rows:
        if row.get('scene_type')!='indoor' or row.get('visual_movement')!='static' or row.get('visual_style')!='photorealistic':continue
        contents=row.get('content_list',[])
        # This first-stage subset stays inside the same room instead of changing scenes.
        if not contents or any(x!=contents[0] for x in contents):continue
        key=row['image']
        if key not in unique:unique[key]=row
    categories=defaultdict(list)
    for row in unique.values():categories[row['category']].append(row)
    for rows_in_category in categories.values():
        rows_in_category.sort(key=lambda r:hashlib.sha256(('world-scene-v1:'+r['image']).encode()).hexdigest())
    selected=[]
    while len(selected)<dev+test:
        added=False
        for category in sorted(categories):
            if categories[category]:selected.append(categories[category].pop(0));added=True
            if len(selected)==dev+test:break
        if not added:raise RuntimeError('符合规则的独立室内场景不足')
    return [(row,'dev' if i<dev else 'test') for i,row in enumerate(selected)]


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,required=True);a=p.parse_args()
    repo=next(x for x in lock()['assets'] if x['group']=='worldscore')
    entry=repo['files'][0];archive=blob_path(a.root,repo,entry)
    if not valid(archive,entry):raise RuntimeError('WorldScore 原始包尚未完整校验通过')
    dest=a.root/'data/worldscore-indoor-v1'
    if dest.exists():
        saved=json.loads((dest/'manifest.json').read_text())
        for row in saved['samples']:
            if sha256(dest/row['local_image'])!=row['image_sha256']:raise RuntimeError('已冻结数据变化')
        print('已存在冻结子集，未覆盖:',dest);return
    dest.mkdir(parents=True)
    try:
        with zipfile.ZipFile(archive) as z:
            raw=z.read('WorldScore-Dataset/static/static.json')
            rows=json.loads(raw)
            out=[]
            for i,(row,split) in enumerate(select_scenes(rows)):
                path=PurePosixPath(row['image'])
                if path.is_absolute() or '..' in path.parts:raise RuntimeError('不安全的原始图片路径')
                local=Path('images')/f'{i:03d}{path.suffix}'
                (dest/local).parent.mkdir(exist_ok=True)
                (dest/local).write_bytes(z.read('WorldScore-Dataset/'+str(path)))
                out.append({'id':f'ws-indoor-{i:03d}','split':split,'source_scene':row['image'],
                    'category':row['category'],'local_image':str(local),'image_sha256':sha256(dest/local),
                    'text':row['prompt_list'][0],'original':row,'manual_review':'pending',
                    'camera_adapter':'pending; source uses symbolic commands, not calibrated camera matrices'})
        write_json(dest/'manifest.json',{'schema_version':1,'subset_version':'1.0.0','source':repo['repo'],
            'revision':repo['revision'],'archive_sha256':entry['digest'],
            'selection':'photorealistic/static/indoor; unchanged content_list; deduplicate image; category round-robin; sha256(world-scene-v1:image); 6 dev + 12 test',
            'protocol':'custom indoor subset; not full WorldScore benchmark reproduction','samples':out})
        print('冻结场景:',len(out),'目录:',dest)
    except BaseException:
        import shutil
        shutil.rmtree(dest)
        raise


if __name__=='__main__':main()
