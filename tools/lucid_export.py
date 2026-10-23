"""Export actual successful retry paths and associated logs, with input/output hashes."""
import argparse
import json
import os
from pathlib import Path
import re
import tarfile
import tempfile
from common import sha256


def collect(runs,state,indices):
    if not indices or len(indices)!=len(set(indices)) or any(i not in range(10) for i in indices):
        raise ValueError('需要不重复的 0–9 案例索引')
    selected=[]
    for index in indices:
        job=(state/f'case-{index}.jobid').read_text().strip()
        if not re.fullmatch(r'[0-9]+',job): raise ValueError('无效作业号')
        run=runs/f'lucid-{index:02d}-{job}-{index}'
        m=json.loads((run/'manifest.json').read_text())
        if m.get('status')!='complete' or m.get('mode')!='run' or m.get('model')!='LucidDreamer-CVLab':
            raise RuntimeError('案例尚未成功完成: '+str(run))
        if not {'outputs/gaussians.ply','outputs/video.mp4'}.issubset(m.get('artifacts',{})):
            raise RuntimeError('缺少三维资产/视频记录')
        for rel,record in m['artifacts'].items():
            p=(run/rel).resolve()
            if not p.is_relative_to(run.resolve()) or sha256(p)!=record['sha256']:
                raise RuntimeError('输出摘要错误: '+rel)
        for name,digest in m['input_sha256'].items():
            if Path(name).name!=name or sha256(run/'inputs'/name)!=digest:
                raise RuntimeError('输入摘要错误: '+name)
        selected.append((run,job,index))
    return selected


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--runs',type=Path,default=os.getenv('LUCID_RUNS'))
    p.add_argument('--state',type=Path,default=os.getenv('LUCID_STATE'))
    p.add_argument('--logs',type=Path,default=os.getenv('LUCID_LOGS'))
    p.add_argument('--indices',type=int,nargs='+',required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    if None in (a.runs,a.state,a.logs): p.error('缺少 runs/state/logs')
    if a.output.exists() or a.output.with_name(a.output.name+'.sha256').exists():
        raise RuntimeError('归档已存在，请换新名称')
    selected=collect(a.runs,a.state,a.indices)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='lucid-export-',dir=a.output.parent) as temp:
        candidate=Path(temp)/a.output.name
        with tarfile.open(candidate,'w:gz',dereference=True) as tf:
            for run,job,index in selected:
                tf.add(run,arcname=run.name)
                for name in [f'run-{job}_{index}.out',f'run-{job}_{index}.err',f'gpu-{job}-{index}.csv']:
                    path=a.logs/name
                    if path.exists(): tf.add(path,arcname='logs/'+name)
        digest=sha256(candidate)
        os.rename(candidate,a.output)
        a.output.with_name(a.output.name+'.sha256').write_text(f'{digest}  {a.output.name}\n')
    print(a.output)


if __name__=='__main__':main()
