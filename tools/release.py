"""Build a reproducible source release, including the pinned submodule."""
import argparse
import gzip
import io
import json
from pathlib import Path
import subprocess
import tarfile
import tempfile
from common import ROOT, lock, project_identity, sha256, source_check


def tracked_files(root=ROOT):
    # NUL delimiters preserve Git paths containing Chinese, spaces or newlines.
    return subprocess.check_output(['git','ls-files','-z'],cwd=root,text=True).rstrip('\0').split('\0')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if (ROOT/'configs/lucid.lock.json').exists():
        from lucid_assets import source_check as lucid_source_check
        lucid_source_check()
    source_check();identity=project_identity();version=identity['version']
    tag=subprocess.check_output(['git','rev-parse',f'v{version}^{{commit}}'],cwd=ROOT,text=True).strip()
    if tag!=identity['commit']:raise RuntimeError('VERSION 对应标签没有指向当前提交')
    files=tracked_files()
    files=[n for n in files if (ROOT/n).is_file()]
    files += ['upstream/FlashWorld/'+n for n in lock()['upstream']['files']]
    files=sorted(set(files))
    payload={'version':version,'commit':identity['commit'],'upstream_commit':identity['upstream_commit'],
             'files':{n:sha256(ROOT/n) for n in files}}
    manifest=(json.dumps(payload,indent=2,ensure_ascii=False)+'\n').encode()
    a.output.mkdir(parents=True,exist_ok=True)
    dest=a.output/f'world_scene-v{version}.tar.gz'
    with tempfile.TemporaryDirectory(prefix='world-scene-release-') as temp:
        candidate=Path(temp)/dest.name
        with candidate.open('wb') as raw,gzip.GzipFile(filename='',fileobj=raw,mode='wb',mtime=0) as gz,tarfile.open(fileobj=gz,mode='w') as tf:
            for name in files+['RELEASE.json']:
                data=manifest if name=='RELEASE.json' else (ROOT/name).read_bytes()
                info=tarfile.TarInfo(f'world_scene-v{version}/'+name)
                info.size=len(data);info.mode=0o644;info.mtime=0
                tf.addfile(info,io.BytesIO(data))
        digest=sha256(candidate)
        if dest.exists() and sha256(dest)!=digest:raise RuntimeError('同版本发布包已存在但内容不同，必须升级版本')
        if not dest.exists():
            import shutil
            shutil.copyfile(candidate,dest)
        dest.with_name(dest.name+'.sha256').write_text(f'{digest}  {dest.name}\n')
    print(dest,identity['commit'],digest)


if __name__=='__main__':main()
