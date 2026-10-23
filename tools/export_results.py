"""Export completed runs without model caches, including portable inputs."""
import argparse
import io
import json
from pathlib import Path
import tarfile
from common import safe_name, sha256


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--runs',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--logs',type=Path,required=True);p.add_argument('--names',nargs='+',required=True)
    a=p.parse_args()
    if a.output.exists():raise RuntimeError('归档已存在；请使用新的文件名')
    runs=[]
    for name in a.names:
        run=a.runs/safe_name(name);m=json.loads((run/'manifest.json').read_text())
        if m['status']!='complete' or m['mode']!='run':raise RuntimeError('仅导出完成的推理；失败日志请单独保留: '+name)
        for rel,record in m['artifacts'].items():
            if sha256(run/rel)!=record['sha256']:raise RuntimeError('输出在实验后发生变化: '+rel)
        runs.append((run,m))
    a.output.parent.mkdir(parents=True,exist_ok=True)
    try:
        with tarfile.open(a.output,'w:gz',dereference=True) as tf:
            for run,m in runs:
                tf.add(run,arcname=run.name)
                for file in (run/'inputs').glob('*.json'):
                    d=json.loads(file.read_text());image=d['image_prompt']
                    if not image.startswith('data:') and Path(image).is_absolute():
                        d['image_prompt']='../inputs/'+Path(image).name
                    payload=json.dumps(d,ensure_ascii=False,indent=2).encode()
                    info=tarfile.TarInfo(run.name+'/portable_inputs/'+file.name);info.size=len(payload)
                    tf.addfile(info,io.BytesIO(payload))
            # Keep logs as a separate versioned directory, including failed comparisons.
            if a.logs.is_dir():tf.add(a.logs,arcname='logs')
        digest=sha256(a.output)
        a.output.with_name(a.output.name+'.sha256').write_text(f'{digest}  {a.output.name}\n')
        print(a.output)
    except BaseException:
        a.output.unlink(missing_ok=True)
        raise


if __name__=='__main__':main()
